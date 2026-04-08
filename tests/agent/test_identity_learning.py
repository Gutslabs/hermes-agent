"""Tests for agent.identity_learning."""

from pathlib import Path
from types import SimpleNamespace

from agent.identity_learning import IdentityLearningStore


def _mock_response(text: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


def test_reflect_session_writes_identity_and_lessons(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    def fake_call_llm(**kwargs):
        return _mock_response(
            """{
              "identity_traits": [
                {
                  "key": "resourceful-before-asking",
                  "statement": "I investigate available context before asking for clarification.",
                  "evidence": "I checked local files before asking follow-up questions."
                }
              ],
              "lessons": [
                {
                  "key": "verify-live-state",
                  "lesson": "Verify live system facts with tools before answering.",
                  "applies_when": "When the question depends on the current machine state.",
                  "avoid_when": "When the answer is about durable user preferences.",
                  "evidence": "A tool lookup corrected an assumption about the current environment."
                }
              ]
            }"""
        )

    monkeypatch.setattr("agent.identity_learning.call_llm", fake_call_llm)

    store = IdentityLearningStore.from_config(
        {
            "enabled": True,
            "min_turns": 1,
            "promote_after": 1,
        }
    )
    changed = store.reflect_session(
        [
            {"role": "user", "content": "help me debug this"},
            {"role": "assistant", "content": "i will inspect the files first"},
        ],
        trigger="session_end",
    )

    assert changed is True
    assert (tmp_path / "IDENTITY.md").exists()
    assert (tmp_path / "LESSONS.md").exists()
    identity_text = (tmp_path / "IDENTITY.md").read_text(encoding="utf-8")
    lessons_text = (tmp_path / "LESSONS.md").read_text(encoding="utf-8")
    assert "I investigate available context before asking for clarification." in identity_text
    assert "support: 1, conflicts: 0" in identity_text
    assert "Last support: I checked local files before asking follow-up questions." in identity_text
    assert "Verify live system facts with tools before answering." in lessons_text
    assert "support: 1, conflicts: 0" in lessons_text
    assert "Last support: A tool lookup corrected an assumption about the current environment." in lessons_text


def test_repeated_trait_promotes_confidence(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    captured_prompts = []

    def fake_call_llm(**kwargs):
        captured_prompts.append(kwargs["messages"][-1]["content"])
        return _mock_response(
            """{
              "identity_traits": [
                {
                  "key": "resourceful-before-asking",
                  "statement": "I investigate available context before asking for clarification.",
                  "evidence": "I checked local files before asking follow-up questions."
                }
              ],
              "lessons": []
            }"""
        )

    monkeypatch.setattr("agent.identity_learning.call_llm", fake_call_llm)

    store = IdentityLearningStore.from_config(
        {
            "enabled": True,
            "min_turns": 1,
            "promote_after": 2,
        }
    )

    first_messages = [
        {"role": "user", "content": "debug repo a"},
        {"role": "assistant", "content": "i will inspect the repo first"},
    ]
    second_messages = [
        {"role": "user", "content": "debug repo b"},
        {"role": "assistant", "content": "i will inspect the repo before asking"},
    ]

    assert store.reflect_session(first_messages, trigger="session_end") is True
    assert not (tmp_path / "IDENTITY.md").exists()

    assert store.reflect_session(second_messages, trigger="session_end") is True
    identity_text = (tmp_path / "IDENTITY.md").read_text(encoding="utf-8")
    assert "confidence: medium" in identity_text
    assert "support: 2, conflicts: 0" in identity_text
    assert "Current identity hypotheses" in captured_prompts[-1]
    assert "resourceful-before-asking" in captured_prompts[-1]


def test_existing_manual_identity_content_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    identity_path = Path(tmp_path) / "IDENTITY.md"
    identity_path.write_text("# Manual notes\n\nKeep this intro.\n", encoding="utf-8")

    def fake_call_llm(**kwargs):
        return _mock_response(
            """{
              "identity_traits": [
                {
                  "key": "direct-without-filler",
                  "statement": "I do better when I stay direct without filler.",
                  "evidence": "Direct answers improved clarity."
                }
              ],
              "lessons": []
            }"""
        )

    monkeypatch.setattr("agent.identity_learning.call_llm", fake_call_llm)

    store = IdentityLearningStore.from_config(
        {
            "enabled": True,
            "min_turns": 1,
            "promote_after": 1,
        }
    )
    store.reflect_session(
        [
            {"role": "user", "content": "answer directly"},
            {"role": "assistant", "content": "understood"},
        ],
        trigger="session_end",
    )

    text = identity_path.read_text(encoding="utf-8")
    assert "# Manual notes" in text
    assert "I do better when I stay direct without filler." in text


def test_conflicts_can_demote_a_trait_from_rendered_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    responses = iter(
        [
            """{
              "identity_traits": [
                {
                  "key": "resourceful-before-asking",
                  "statement": "I investigate available context before asking for clarification.",
                  "evidence": "I checked the repo layout before asking a follow-up question."
                }
              ],
              "lessons": [],
              "trait_updates": [],
              "lesson_updates": []
            }""",
            """{
              "identity_traits": [
                {
                  "key": "resourceful-before-asking",
                  "statement": "I investigate available context before asking for clarification.",
                  "evidence": "I inspected the available files before replying."
                }
              ],
              "lessons": [],
              "trait_updates": [],
              "lesson_updates": []
            }""",
            """{
              "identity_traits": [],
              "lessons": [],
              "trait_updates": [
                {
                  "key": "resourceful-before-asking",
                  "status": "contradict",
                  "evidence": "I asked a clarifying question before checking the local files."
                }
              ],
              "lesson_updates": []
            }""",
            """{
              "identity_traits": [],
              "lessons": [],
              "trait_updates": [
                {
                  "key": "resourceful-before-asking",
                  "status": "contradict",
                  "evidence": "I asked for more details without first inspecting the obvious context."
                }
              ],
              "lesson_updates": []
            }""",
        ]
    )

    def fake_call_llm(**kwargs):
        return _mock_response(next(responses))

    monkeypatch.setattr("agent.identity_learning.call_llm", fake_call_llm)

    store = IdentityLearningStore.from_config(
        {
            "enabled": True,
            "min_turns": 1,
            "promote_after": 2,
        }
    )

    sessions = [
        [
            {"role": "user", "content": "debug repo a"},
            {"role": "assistant", "content": "i will inspect the repo first"},
        ],
        [
            {"role": "user", "content": "debug repo b"},
            {"role": "assistant", "content": "i inspected the files before replying"},
        ],
        [
            {"role": "user", "content": "help with repo c"},
            {"role": "assistant", "content": "what exactly is broken?"},
        ],
        [
            {"role": "user", "content": "help with repo d"},
            {"role": "assistant", "content": "can you give me more detail first?"},
        ],
    ]

    for messages in sessions:
        assert store.reflect_session(messages, trigger="session_end") is True

    identity_path = tmp_path / "IDENTITY.md"
    if identity_path.exists():
        identity_text = identity_path.read_text(encoding="utf-8")
        assert "I investigate available context before asking for clarification." not in identity_text
    else:
        assert not identity_path.exists()

    trait_state = store._state["traits"]["resourceful-before-asking"]
    assert trait_state["support_count"] == 2
    assert trait_state["conflict_count"] == 2
    assert trait_state["confidence"] == "contested"
