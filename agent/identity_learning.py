"""Identity learning for Hermes.

Learns agent-self patterns from completed sessions without mutating SOUL.md.

Design goals:
- SOUL.md stays the protected core identity.
- Repeated patterns become durable via IDENTITY.md and LESSONS.md.
- Learning only happens at session boundaries so prompt caching stays intact.
- Generated sections are written inside managed markers so user edits survive.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.auxiliary_client import call_llm
from hermes_constants import get_hermes_home
from utils import atomic_json_write

logger = logging.getLogger(__name__)

_STATE_FILE = ".identity_learning.json"
_REFLECTION_LOG = "identity_reflections.jsonl"
_IDENTITY_FILE = "IDENTITY.md"
_LESSONS_FILE = "LESSONS.md"

_BEGIN_MARKER = "<!-- HERMES:IDENTITY-LEARNING:BEGIN -->"
_END_MARKER = "<!-- HERMES:IDENTITY-LEARNING:END -->"

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", re.IGNORECASE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")

_MAX_EVENT_HISTORY = 4
_MAX_PROMPT_HYPOTHESES = 8

_REFLECTION_SYSTEM_PROMPT = """You maintain the agent's learned self-model.

Your job is to extract durable AGENT-SIDE learning from a session transcript.

Focus on:
- the agent's working style
- recurring strengths
- recurring mistakes or blind spots
- behavioral lessons that should shape future decisions

Do not include:
- user preferences or facts about the user
- workspace/project conventions
- temporary task progress
- one-off achievements
- rewrites of the agent's core values or soul

Be conservative. Only keep patterns that would still matter later.
Treat current learned items as hypotheses, not truths. If the new transcript
clearly supports a current hypothesis, mark it as reinforce. If the transcript
clearly shows the hypothesis overgeneralizes or fails, mark it as contradict.
Do not emit reinforce/contradict unless the transcript contains concrete evidence.

Return strict JSON only with this schema:
{
  "identity_traits": [
    {
      "key": "stable-lowercase-slug",
      "statement": "First-person durable self-model statement.",
      "evidence": "One short concrete sentence from the transcript."
    }
  ],
  "lessons": [
    {
      "key": "stable-lowercase-slug",
      "lesson": "Behavioral lesson in imperative or first-person style.",
      "applies_when": "When this lesson should be used.",
      "avoid_when": "When not to over-apply it.",
      "evidence": "One short concrete sentence from the transcript."
    }
  ],
  "trait_updates": [
    {
      "key": "stable-lowercase-slug",
      "status": "reinforce or contradict",
      "evidence": "One short concrete sentence from the transcript."
    }
  ],
  "lesson_updates": [
    {
      "key": "stable-lowercase-slug",
      "status": "reinforce or contradict",
      "evidence": "One short concrete sentence from the transcript."
    }
  ]
}

Rules:
- At most 3 identity_traits and 4 lessons.
- At most 4 trait_updates and 4 lesson_updates.
- Keep keys stable, lowercase, and short.
- If a key already exists in the current hypotheses, prefer *_updates instead
  of re-proposing the same item as new learning.
- If nothing durable was learned, return empty arrays.
"""


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _slugify(value: str) -> str:
    text = (value or "").strip().lower()
    text = _SLUG_RE.sub("-", text).strip("-")
    return text[:64] or "unknown"


def _confidence_label(support_count: int, conflict_count: int) -> str:
    if conflict_count >= support_count and conflict_count > 0:
        return "contested"
    if support_count >= 4 and conflict_count == 0:
        return "high"
    if support_count >= 2 and (support_count - conflict_count) >= 2:
        return "medium"
    return "low"


def _extract_response_text(response: Any) -> str:
    try:
        choice = response.choices[0]
        message = choice.message
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content") or ""
                    if text:
                        parts.append(str(text))
                elif hasattr(item, "text"):
                    parts.append(str(getattr(item, "text", "")))
                else:
                    parts.append(str(item))
            return "\n".join(p for p in parts if p).strip()
        return str(content or "").strip()
    except Exception:
        return ""


def _extract_json_payload(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}

    match = _JSON_BLOCK_RE.search(raw)
    if match:
        raw = match.group(1).strip()

    if raw.startswith("{") and raw.endswith("}"):
        try:
            return json.loads(raw)
        except Exception:
            pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            pass

    return {}


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            elif isinstance(item, str) and item.strip():
                parts.append(item.strip())
        return "\n".join(parts).strip()
    return ""


def _build_transcript(messages: List[Dict[str, Any]], max_chars: int) -> str:
    lines: List[str] = []
    total = 0
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _stringify_content(msg.get("content"))
        if not text:
            continue
        line = f"{role.upper()}: {text}"
        lines.append(line)
        total += len(line) + 1

    if not lines:
        return ""

    transcript = "\n".join(lines)
    if len(transcript) <= max_chars:
        return transcript

    return transcript[-max_chars:]


def _count_user_turns(messages: List[Dict[str, Any]]) -> int:
    return sum(1 for msg in messages or [] if isinstance(msg, dict) and msg.get("role") == "user")


def _dedupe_keep_recent(items: List[str], limit: int = 3) -> List[str]:
    out: List[str] = []
    for item in items:
        text = (item or "").strip()
        if not text or text in out:
            continue
        out.append(text)
    return out[-limit:]


def _dedupe_events_keep_recent(events: List[Dict[str, Any]], limit: int = _MAX_EVENT_HISTORY) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        evidence = (event.get("evidence") or "").strip()
        transcript_hash = str(event.get("transcript_hash") or "").strip()
        trigger = str(event.get("trigger") or "").strip()
        signature = (transcript_hash, trigger, evidence)
        if signature in seen or not evidence:
            continue
        seen.add(signature)
        out.append(
            {
                "timestamp": event.get("timestamp"),
                "transcript_hash": transcript_hash,
                "trigger": trigger,
                "evidence": evidence,
            }
        )
    return out[-limit:]


def _latest_event_text(events: List[Dict[str, Any]]) -> str:
    for event in reversed(events or []):
        if isinstance(event, dict):
            text = (event.get("evidence") or "").strip()
            if text:
                return text
    return ""


def _replace_managed_block(existing: str, body: str) -> str:
    payload = f"{_BEGIN_MARKER}\n{body.rstrip()}\n{_END_MARKER}\n"
    if _BEGIN_MARKER in existing and _END_MARKER in existing:
        pattern = re.compile(
            re.escape(_BEGIN_MARKER) + r"[\s\S]*?" + re.escape(_END_MARKER) + r"\n?",
            re.MULTILINE,
        )
        return pattern.sub(payload, existing).rstrip() + "\n"
    if existing.strip():
        return existing.rstrip() + "\n\n" + payload
    return payload


class IdentityLearningStore:
    """Session-bound identity learner with durable profile-scoped state."""

    def __init__(
        self,
        *,
        enabled: bool,
        min_turns: int,
        max_transcript_chars: int,
        promote_after: int,
        max_traits: int,
        max_lessons: int,
    ) -> None:
        self.enabled = bool(enabled)
        self.min_turns = max(1, int(min_turns))
        self.max_transcript_chars = max(2000, int(max_transcript_chars))
        self.promote_after = max(1, int(promote_after))
        self.max_traits = max(1, int(max_traits))
        self.max_lessons = max(1, int(max_lessons))
        self.hermes_home = get_hermes_home()
        self.state_path = self.hermes_home / _STATE_FILE
        self.identity_path = self.hermes_home / _IDENTITY_FILE
        self.lessons_path = self.hermes_home / _LESSONS_FILE
        self.reflection_log_path = self.hermes_home / _REFLECTION_LOG
        self._state = self._load_state()

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]]) -> "IdentityLearningStore":
        cfg = config if isinstance(config, dict) else {}
        return cls(
            enabled=cfg.get("enabled", False),
            min_turns=cfg.get("min_turns", 4),
            max_transcript_chars=cfg.get("max_transcript_chars", 12000),
            promote_after=cfg.get("promote_after", 2),
            max_traits=cfg.get("max_traits", 12),
            max_lessons=cfg.get("max_lessons", 20),
        )

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {
                "traits": {},
                "lessons": {},
                "processed_hashes": [],
                "updated_at": None,
            }
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("identity state must be a dict")
            data.setdefault("traits", {})
            data.setdefault("lessons", {})
            data.setdefault("processed_hashes", [])
            self._normalize_state(data)
            return data
        except Exception as exc:
            logger.warning("Identity learning state reset after read failure: %s", exc)
            return {
                "traits": {},
                "lessons": {},
                "processed_hashes": [],
                "updated_at": None,
            }

    def _normalize_state(self, data: Dict[str, Any]) -> None:
        for bucket, field_name in (("traits", "statement"), ("lessons", "lesson")):
            items = data.get(bucket, {})
            if not isinstance(items, dict):
                data[bucket] = {}
                continue
            for key, raw_item in list(items.items()):
                if not isinstance(raw_item, dict):
                    items.pop(key, None)
                    continue

                support_count = int(raw_item.get("support_count", raw_item.get("count", 0)) or 0)
                conflict_count = int(raw_item.get("conflict_count", 0) or 0)
                raw_item["support_count"] = max(0, support_count)
                raw_item["conflict_count"] = max(0, conflict_count)

                legacy_evidence = raw_item.pop("evidence", [])
                support_events = raw_item.get("support_events", [])
                conflict_events = raw_item.get("conflict_events", [])

                if legacy_evidence and not support_events:
                    support_events = [
                        {
                            "timestamp": raw_item.get("last_seen") or raw_item.get("first_seen"),
                            "transcript_hash": "",
                            "trigger": "legacy",
                            "evidence": text,
                        }
                        for text in legacy_evidence
                        if isinstance(text, str) and text.strip()
                    ]

                raw_item["support_events"] = _dedupe_events_keep_recent(support_events)
                raw_item["conflict_events"] = _dedupe_events_keep_recent(conflict_events)
                raw_item["confidence"] = _confidence_label(
                    raw_item["support_count"],
                    raw_item["conflict_count"],
                )
                raw_item.setdefault("key", key)
                raw_item.setdefault(field_name, "")
                raw_item.setdefault("applies_when", "")
                raw_item.setdefault("avoid_when", "")
                raw_item.setdefault("first_seen", raw_item.get("last_seen"))
                raw_item.setdefault("last_seen", raw_item.get("first_seen"))

    def _persist_state(self) -> None:
        self.hermes_home.mkdir(parents=True, exist_ok=True)
        self._state["updated_at"] = _now_iso()
        atomic_json_write(self.state_path, self._state)

    def _append_reflection_log(self, payload: Dict[str, Any]) -> None:
        self.hermes_home.mkdir(parents=True, exist_ok=True)
        with self.reflection_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _should_process(self, messages: List[Dict[str, Any]]) -> bool:
        if not self.enabled:
            return False
        return _count_user_turns(messages) >= self.min_turns

    def _mark_processed(self, transcript_hash: str) -> None:
        hashes = list(self._state.get("processed_hashes", []))
        if transcript_hash in hashes:
            return
        hashes.append(transcript_hash)
        self._state["processed_hashes"] = hashes[-32:]

    def _already_processed(self, transcript_hash: str) -> bool:
        return transcript_hash in set(self._state.get("processed_hashes", []))

    def _build_reflection_context(self) -> str:
        parts: List[str] = []
        for label, bucket, field_name in (
            ("Current identity hypotheses", "traits", "statement"),
            ("Current lesson hypotheses", "lessons", "lesson"),
        ):
            items = list(self._state.get(bucket, {}).values())
            items.sort(
                key=lambda item: (
                    -(int(item.get("support_count", 0)) - int(item.get("conflict_count", 0))),
                    -int(item.get("support_count", 0)),
                    item.get("key", ""),
                )
            )
            items = items[:_MAX_PROMPT_HYPOTHESES]
            if not items:
                continue
            parts.append(label + ":")
            for item in items:
                parts.append(
                    "- "
                    f"{item.get('key')}: {item.get(field_name)} "
                    f"(support={int(item.get('support_count', 0))}, "
                    f"conflicts={int(item.get('conflict_count', 0))})"
                )
            parts.append("")
        return "\n".join(parts).strip()

    def _event_payload(self, *, evidence: str, transcript_hash: str, trigger: str, timestamp: str) -> Dict[str, Any]:
        return {
            "timestamp": timestamp,
            "transcript_hash": transcript_hash,
            "trigger": trigger,
            "evidence": (evidence or "").strip(),
        }

    def _merge_entry(
        self,
        bucket: str,
        key: str,
        payload: Dict[str, Any],
        *,
        field_name: str,
        transcript_hash: str,
        trigger: str,
    ) -> None:
        items = self._state.setdefault(bucket, {})
        existing = items.get(key)
        now = _now_iso()
        statement = (payload.get(field_name) or "").strip()
        evidence = (payload.get("evidence") or "").strip()
        applies_when = (payload.get("applies_when") or "").strip()
        avoid_when = (payload.get("avoid_when") or "").strip()
        event = self._event_payload(
            evidence=evidence,
            transcript_hash=transcript_hash,
            trigger=trigger,
            timestamp=now,
        )

        if existing:
            existing["support_count"] = int(
                existing.get("support_count", existing.get("count", 1))
            ) + 1
            existing["last_seen"] = now
            if statement and len(statement) > len(existing.get(field_name, "")):
                existing[field_name] = statement
            if applies_when:
                existing["applies_when"] = applies_when
            if avoid_when:
                existing["avoid_when"] = avoid_when
            support_events = list(existing.get("support_events", []))
            support_events.append(event)
            existing["support_events"] = _dedupe_events_keep_recent(support_events)
            existing["confidence"] = _confidence_label(
                int(existing.get("support_count", 0)),
                int(existing.get("conflict_count", 0)),
            )
            items[key] = existing
            return

        items[key] = {
            "key": key,
            field_name: statement,
            "support_events": _dedupe_events_keep_recent([event]),
            "conflict_events": [],
            "applies_when": applies_when,
            "avoid_when": avoid_when,
            "support_count": 1,
            "conflict_count": 0,
            "confidence": _confidence_label(1, 0),
            "first_seen": now,
            "last_seen": now,
        }

    def _merge_update(
        self,
        bucket: str,
        key: str,
        payload: Dict[str, Any],
        *,
        transcript_hash: str,
        trigger: str,
    ) -> bool:
        items = self._state.setdefault(bucket, {})
        existing = items.get(key)
        if not existing:
            return False

        now = _now_iso()
        status = str(payload.get("status") or "").strip().lower()
        evidence = (payload.get("evidence") or "").strip()
        if status not in {"reinforce", "contradict"} or not evidence:
            return False

        event = self._event_payload(
            evidence=evidence,
            transcript_hash=transcript_hash,
            trigger=trigger,
            timestamp=now,
        )
        existing["last_seen"] = now

        if status == "reinforce":
            support_events = list(existing.get("support_events", []))
            support_events.append(event)
            existing["support_events"] = _dedupe_events_keep_recent(support_events)
            existing["support_count"] = int(
                existing.get("support_count", existing.get("count", 0))
            ) + 1
        else:
            conflict_events = list(existing.get("conflict_events", []))
            conflict_events.append(event)
            existing["conflict_events"] = _dedupe_events_keep_recent(conflict_events)
            existing["conflict_count"] = int(existing.get("conflict_count", 0)) + 1

        existing["confidence"] = _confidence_label(
            int(existing.get("support_count", 0)),
            int(existing.get("conflict_count", 0)),
        )
        items[key] = existing
        return True

    def _merge_reflection(self, payload: Dict[str, Any], *, transcript_hash: str, trigger: str) -> bool:
        changed = False
        seen_updates: set[tuple[str, str]] = set()

        for raw_item in payload.get("trait_updates", []) or []:
            if not isinstance(raw_item, dict):
                continue
            key = _slugify(raw_item.get("key") or "")
            if not key or ("traits", key) in seen_updates:
                continue
            seen_updates.add(("traits", key))
            changed = self._merge_update(
                "traits",
                key,
                raw_item,
                transcript_hash=transcript_hash,
                trigger=trigger,
            ) or changed

        for raw_item in payload.get("lesson_updates", []) or []:
            if not isinstance(raw_item, dict):
                continue
            key = _slugify(raw_item.get("key") or "")
            if not key or ("lessons", key) in seen_updates:
                continue
            seen_updates.add(("lessons", key))
            changed = self._merge_update(
                "lessons",
                key,
                raw_item,
                transcript_hash=transcript_hash,
                trigger=trigger,
            ) or changed

        for raw_item in payload.get("identity_traits", []) or []:
            if not isinstance(raw_item, dict):
                continue
            key = _slugify(raw_item.get("key") or raw_item.get("statement") or "")
            statement = (raw_item.get("statement") or "").strip()
            if not key or not statement:
                continue
            if ("traits", key) in seen_updates:
                continue
            self._merge_entry(
                "traits",
                key,
                raw_item,
                field_name="statement",
                transcript_hash=transcript_hash,
                trigger=trigger,
            )
            changed = True

        for raw_item in payload.get("lessons", []) or []:
            if not isinstance(raw_item, dict):
                continue
            key = _slugify(raw_item.get("key") or raw_item.get("lesson") or "")
            lesson = (raw_item.get("lesson") or "").strip()
            if not key or not lesson:
                continue
            if ("lessons", key) in seen_updates:
                continue
            self._merge_entry(
                "lessons",
                key,
                raw_item,
                field_name="lesson",
                transcript_hash=transcript_hash,
                trigger=trigger,
            )
            changed = True

        return changed

    def _render_identity(self) -> str:
        traits = list(self._state.get("traits", {}).values())
        traits = [
            t
            for t in traits
            if int(t.get("support_count", t.get("count", 0))) >= self.promote_after
            and (
                int(t.get("support_count", t.get("count", 0)))
                - int(t.get("conflict_count", 0))
            )
            > 0
        ]
        traits.sort(
            key=lambda item: (
                -(
                    int(item.get("support_count", item.get("count", 0)))
                    - int(item.get("conflict_count", 0))
                ),
                -int(item.get("support_count", item.get("count", 0))),
                item.get("key", ""),
            )
        )
        traits = traits[: self.max_traits]

        if not traits:
            return ""

        lines = [
            "# IDENTITY.md",
            "",
            "This file contains learned agent-self patterns.",
            "SOUL.md remains the protected core identity.",
            "",
            "## Stable Learned Traits",
        ]
        for item in traits:
            support_count = int(item.get("support_count", item.get("count", 0)))
            conflict_count = int(item.get("conflict_count", 0))
            lines.append(
                f"- {item.get('statement')} "
                f"(confidence: {item.get('confidence')}, "
                f"support: {support_count}, conflicts: {conflict_count})"
            )
            support_text = _latest_event_text(item.get("support_events", []))
            conflict_text = _latest_event_text(item.get("conflict_events", []))
            if support_text:
                lines.append(f"  Last support: {support_text}")
            if conflict_text:
                lines.append(f"  Last contradiction: {conflict_text}")

        return "\n".join(lines).strip() + "\n"

    def _render_lessons(self) -> str:
        lessons = list(self._state.get("lessons", {}).values())
        lessons.sort(
            key=lambda item: (
                -(
                    int(item.get("support_count", item.get("count", 0)))
                    - int(item.get("conflict_count", 0))
                ),
                -int(item.get("support_count", item.get("count", 0))),
                item.get("key", ""),
            )
        )
        lessons = lessons[: self.max_lessons]

        if not lessons:
            return ""

        lines = [
            "# LESSONS.md",
            "",
            "Behavioral lessons learned from completed sessions.",
            "Use these as adaptive guidance, not as replacements for SOUL.md.",
            "",
            "## Lessons",
        ]
        for item in lessons:
            support_count = int(item.get("support_count", item.get("count", 0)))
            conflict_count = int(item.get("conflict_count", 0))
            lines.append(f"### {item.get('key')}")
            lines.append(f"Lesson: {item.get('lesson')}")
            if item.get("applies_when"):
                lines.append(f"Apply when: {item.get('applies_when')}")
            if item.get("avoid_when"):
                lines.append(f"Avoid when: {item.get('avoid_when')}")
            lines.append(
                f"Confidence: {item.get('confidence')} "
                f"(support: {support_count}, conflicts: {conflict_count})"
            )
            support_text = _latest_event_text(item.get("support_events", []))
            conflict_text = _latest_event_text(item.get("conflict_events", []))
            if support_text:
                lines.append(f"Last support: {support_text}")
            if conflict_text:
                lines.append(f"Last contradiction: {conflict_text}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _write_rendered_file(self, path: Path, body: str) -> None:
        existing = ""
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
            except Exception:
                existing = ""

        if not body.strip():
            if not existing.strip():
                return
            if _BEGIN_MARKER in existing and _END_MARKER in existing:
                updated = _replace_managed_block(existing, "")
                updated = updated.replace(f"{_BEGIN_MARKER}\n{_END_MARKER}\n", "").strip()
                if updated:
                    path.write_text(updated + "\n", encoding="utf-8")
                else:
                    path.unlink(missing_ok=True)
            return

        updated = _replace_managed_block(existing, body)
        path.write_text(updated, encoding="utf-8")

    def _write_rendered_files(self) -> None:
        self._write_rendered_file(self.identity_path, self._render_identity())
        self._write_rendered_file(self.lessons_path, self._render_lessons())

    def reflect_session(self, messages: List[Dict[str, Any]], *, trigger: str) -> bool:
        """Extract durable self-learning from a completed session."""
        if not self._should_process(messages):
            return False

        transcript = _build_transcript(messages, self.max_transcript_chars)
        if not transcript:
            return False

        transcript_hash = hashlib.sha1(transcript.encode("utf-8")).hexdigest()
        if self._already_processed(transcript_hash):
            return False

        prior_context = self._build_reflection_context()
        prompt = (
            "Reflect on this transcript and extract only durable agent-side learning.\n\n"
            + (
                f"{prior_context}\n\n"
                if prior_context
                else ""
            )
            + "Transcript:\n"
            f"{transcript}"
        )

        try:
            response = call_llm(
                task="identity_reflection",
                messages=[
                    {"role": "system", "content": _REFLECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1600,
                timeout=45.0,
            )
        except Exception as exc:
            logger.debug("Identity reflection call failed: %s", exc)
            return False

        response_text = _extract_response_text(response)
        payload = _extract_json_payload(response_text)
        if not payload:
            logger.debug("Identity reflection returned no parseable JSON")
            return False

        changed = self._merge_reflection(
            payload,
            transcript_hash=transcript_hash,
            trigger=trigger,
        )
        self._mark_processed(transcript_hash)
        self._persist_state()
        self._append_reflection_log(
            {
                "timestamp": _now_iso(),
                "trigger": trigger,
                "transcript_hash": transcript_hash,
                "payload": payload,
            }
        )
        if changed:
            self._write_rendered_files()
        return changed
