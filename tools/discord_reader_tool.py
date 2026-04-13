"""Discord Reader Tool -- read-only access to Discord via user token.

Uses the Discord REST API directly with a **user token** (self-bot) to give
read-only access to every server, channel, and DM the account can see.

No discord.py dependency — only aiohttp (already a project dependency).

Environment:
    DISCORD_USER_TOKEN  – Personal account token (NOT a bot token).
    DISCORD_PROXY       – Optional HTTP/SOCKS proxy URL.

Actions:
    guilds       – List all servers the account is in.
    channels     – List text channels in a server.
    history      – Fetch recent messages from a channel (with pagination).
    search       – Search messages in a guild by content.
    dm_channels  – List recent DM conversations.
    server_overview – Auto-detect key channels and fetch a summary batch.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_API_BASE = "https://discord.com/api/v10"
_API_VERSION = 10

# Discord channel types we care about
_CHANNEL_TEXT = 0
_CHANNEL_CATEGORY = 4
_CHANNEL_ANNOUNCEMENT = 5
_CHANNEL_FORUM = 15

_TEXT_CHANNEL_TYPES = {_CHANNEL_TEXT, _CHANNEL_ANNOUNCEMENT, _CHANNEL_FORUM}

# Rate-limit safety: minimum seconds between requests
_MIN_REQUEST_INTERVAL = 0.25
_last_request_time: float = 0.0

# Channel classification patterns (compiled once)
_ANNOUNCE_RE = re.compile(
    r"announce|news|update|changelog|release|important", re.I
)
_DEV_RE = re.compile(
    r"dev|develop|engineer|tech|build|code|github|deploy|infra|protocol|sdk|api", re.I
)
_GENERAL_RE = re.compile(
    r"general|(?<!\w)chat(?!\w)|lounge|discuss|community|lobby|hangout", re.I
)
_GOVERNANCE_RE = re.compile(
    r"govern|dao|vote|proposal|snapshot", re.I
)
_MARKET_RE = re.compile(
    r"price|market|trading|alpha|calls|degen", re.I
)
_SKIP_RE = re.compile(
    r"bot|command|spam|meme|media|selfie|music|nsfw|off.?topic|intro|rule|"
    r"welcome|verify|role|faq|ticket|support|log|mod|admin|entry|archive", re.I
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DISCORD_READER_SCHEMA = {
    "name": "discord_reader",
    "description": (
        "Read-only access to Discord servers, channels, and messages via your personal account.\n\n"
        "Actions:\n"
        "  guilds          – List all servers you are in.\n"
        "  channels        – List text channels in a server (requires guild_id).\n"
        "  history         – Fetch messages from a channel (requires channel_id, optional limit 1-100, optional before for pagination).\n"
        "  search          – Search messages in a guild (requires guild_id + query).\n"
        "  dm_channels     – List recent DM conversations.\n"
        "  server_overview – Auto-detect key channels and fetch summary from a server (requires guild_id).\n\n"
        "SAFETY: This tool is STRICTLY READ-ONLY. It cannot send messages, react, or modify anything."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["guilds", "channels", "history", "search", "dm_channels", "server_overview"],
                "description": "Action to perform.",
            },
            "guild_id": {
                "type": "string",
                "description": "Server (guild) ID. Required for channels, search, server_overview.",
            },
            "channel_id": {
                "type": "string",
                "description": "Channel ID. Required for history.",
            },
            "limit": {
                "type": "integer",
                "description": "Messages to fetch (1-100, default 50).",
            },
            "query": {
                "type": "string",
                "description": "Search query. Required for search.",
            },
            "before": {
                "type": "string",
                "description": "Message ID for pagination — fetch messages older than this.",
            },
        },
        "required": ["action"],
    },
}


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def _get_token() -> Optional[str]:
    """Read user token from environment."""
    return os.getenv("DISCORD_USER_TOKEN")


def _build_headers(token: str) -> Dict[str, str]:
    """Build request headers. User tokens omit the 'Bot ' prefix."""
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        # Mimic browser to avoid automated-user-agent blocks
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }


async def _api_get(
    token: str,
    path: str,
    params: Optional[Dict[str, str]] = None,
) -> Tuple[Any, Optional[str]]:
    """GET request to Discord API with rate-limit handling.

    Returns:
        (data, error) — one of them is always None.
    """
    global _last_request_time

    import aiohttp

    # Proxy support (reuse hermes gateway helpers)
    try:
        from gateway.platforms.base import resolve_proxy_url, proxy_kwargs_for_aiohttp
        proxy = resolve_proxy_url(platform_env_var="DISCORD_PROXY")
        sess_kw, req_kw = proxy_kwargs_for_aiohttp(proxy)
    except ImportError:
        sess_kw, req_kw = {}, {}

    url = f"{_API_BASE}{path}"

    # Simple rate-limit spacing
    now = time.monotonic()
    wait = _MIN_REQUEST_INTERVAL - (now - _last_request_time)
    if wait > 0:
        await asyncio.sleep(wait)

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            **sess_kw,
        ) as session:
            async with session.get(
                url,
                headers=_build_headers(token),
                params=params,
                **req_kw,
            ) as resp:
                _last_request_time = time.monotonic()

                if resp.status == 200:
                    return await resp.json(), None

                # Error handling
                if resp.status == 401:
                    return None, "Invalid or expired user token. Check DISCORD_USER_TOKEN."
                if resp.status == 403:
                    return None, f"Access denied for {path}. Missing permissions."
                if resp.status == 404:
                    return None, f"Not found: {path}. Check the ID."
                if resp.status == 429:
                    try:
                        body = await resp.json()
                        retry = body.get("retry_after", "?")
                    except Exception:
                        retry = "?"
                    return None, f"Rate limited — retry after {retry}s."

                body = await resp.text()
                return None, f"Discord API {resp.status}: {body[:300]}"

    except aiohttp.ClientError as exc:
        return None, f"Network error: {exc}"
    except asyncio.TimeoutError:
        return None, "Request timed out (30s)."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error(msg: str) -> str:
    return json.dumps({"error": msg})


def _ok(payload: dict) -> str:
    return json.dumps(payload)


def _extract_author(author: dict) -> str:
    """Best-effort display name from author object."""
    return (
        author.get("global_name")
        or author.get("username")
        or "unknown"
    )


def _strip_emoji_prefix(name: str) -> str:
    """Remove leading emoji/unicode decorators from channel names.

    e.g. '︱📢︱announcements' → 'announcements'
    """
    # Strip common separator chars and emoji
    cleaned = re.sub(r"^[^\w]*", "", name, flags=re.UNICODE)
    return cleaned or name


def _classify_channel(name: str, category: Optional[str] = None) -> Tuple[str, int]:
    """Classify a channel by name pattern. Returns (label, priority).

    Priority: 1 = highest (announcements), 5 = lowest, 99 = skip.
    """
    stripped = _strip_emoji_prefix(name)
    check_str = f"{stripped} {category or ''}"

    # Check channel name only (not category) for skip/specific matches
    if _SKIP_RE.search(stripped):
        return "skip", 99
    if _ANNOUNCE_RE.search(stripped):
        return "announcements", 1
    if _DEV_RE.search(stripped):
        return "development", 2
    if _GOVERNANCE_RE.search(stripped):
        return "governance", 4
    if _MARKET_RE.search(stripped):
        return "market", 5
    if _GENERAL_RE.search(stripped):
        return "general", 3
    # Fallback: check category name for broader context
    if category:
        if _ANNOUNCE_RE.search(category):
            return "announcements", 1
        if _DEV_RE.search(category):
            return "development", 2
    return "other", 6


def _parse_message(m: dict) -> dict:
    """Extract relevant fields from a raw Discord message."""
    msg: Dict[str, Any] = {
        "id": m["id"],
        "author": _extract_author(m.get("author", {})),
        "content": m.get("content", ""),
        "timestamp": m.get("timestamp", ""),
    }
    if m.get("attachments"):
        msg["attachments"] = len(m["attachments"])
    if m.get("embeds"):
        msg["embeds"] = len(m["embeds"])
    ref = m.get("message_reference")
    if ref and ref.get("message_id"):
        msg["reply_to"] = ref["message_id"]
    return msg


def _is_within_hours(timestamp_str: str, hours: int) -> bool:
    """Check if an ISO timestamp is within the last N hours."""
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("+00:00", "+00:00").rstrip("Z"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return ts >= cutoff
    except (ValueError, TypeError):
        return True  # If we can't parse, include it


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

async def _action_guilds(token: str, args: dict) -> str:
    """List all guilds the user is a member of."""
    data, err = await _api_get(token, "/users/@me/guilds", {"limit": "200"})
    if err:
        return _error(err)

    guilds = [
        {
            "id": g["id"],
            "name": g["name"],
            "owner": g.get("owner", False),
        }
        for g in data
    ]
    return _ok({"guilds": guilds, "count": len(guilds)})


async def _action_channels(token: str, args: dict) -> str:
    """List text channels in a guild, grouped by category."""
    guild_id = args.get("guild_id")
    if not guild_id:
        return _error("guild_id is required for 'channels'.")

    data, err = await _api_get(token, f"/guilds/{guild_id}/channels")
    if err:
        return _error(err)

    # Build category map
    categories: Dict[str, str] = {}
    for ch in data:
        if ch.get("type") == _CHANNEL_CATEGORY:
            categories[ch["id"]] = ch["name"]

    # Collect text-based channels
    channels = []
    for ch in data:
        if ch.get("type") not in _TEXT_CHANNEL_TYPES:
            continue
        cat_name = categories.get(ch.get("parent_id"), None)
        label, priority = _classify_channel(ch["name"], cat_name)
        channels.append({
            "id": ch["id"],
            "name": ch["name"],
            "category": cat_name,
            "topic": (ch.get("topic") or "")[:120],
            "classification": label,
            "priority": priority,
            "position": ch.get("position", 999),
        })

    channels.sort(key=lambda c: (c["priority"], c["position"]))
    return _ok({"channels": channels, "count": len(channels), "guild_id": guild_id})


async def _action_history(token: str, args: dict) -> str:
    """Fetch message history from a channel."""
    channel_id = args.get("channel_id")
    if not channel_id:
        return _error("channel_id is required for 'history'.")

    limit = max(1, min(args.get("limit", 50), 100))
    params: Dict[str, str] = {"limit": str(limit)}
    before = args.get("before")
    if before:
        params["before"] = before

    data, err = await _api_get(token, f"/channels/{channel_id}/messages", params)
    if err:
        return _error(err)

    if not isinstance(data, list):
        return _error(f"Unexpected response format from Discord API.")

    messages = [_parse_message(m) for m in data]
    # API returns newest-first; reverse to chronological
    messages.reverse()

    result: Dict[str, Any] = {
        "messages": messages,
        "count": len(messages),
        "channel_id": channel_id,
    }
    # Provide pagination hint
    if messages:
        result["oldest_id"] = messages[0]["id"]
        result["newest_id"] = messages[-1]["id"]
    return _ok(result)


async def _action_search(token: str, args: dict) -> str:
    """Search messages in a guild by content."""
    guild_id = args.get("guild_id")
    query = args.get("query")
    if not guild_id or not query:
        return _error("guild_id and query are required for 'search'.")

    params: Dict[str, str] = {"content": query}
    limit = args.get("limit")
    if limit:
        params["limit"] = str(max(1, min(limit, 25)))

    data, err = await _api_get(token, f"/guilds/{guild_id}/messages/search", params)
    if err:
        return _error(err)

    results = []
    for group in data.get("messages", []):
        for m in group:
            if m.get("hit"):
                results.append({
                    "id": m["id"],
                    "author": _extract_author(m.get("author", {})),
                    "content": m.get("content", "")[:500],
                    "channel_id": m.get("channel_id"),
                    "timestamp": m.get("timestamp", ""),
                })

    return _ok({
        "results": results,
        "total": data.get("total_results", len(results)),
        "guild_id": guild_id,
    })


async def _action_dm_channels(token: str, args: dict) -> str:
    """List recent DM channels."""
    data, err = await _api_get(token, "/users/@me/channels")
    if err:
        return _error(err)

    dms = []
    for ch in data:
        if ch.get("type") == 1:  # DM
            recips = ch.get("recipients", [])
            name = _extract_author(recips[0]) if recips else "?"
            dms.append({
                "id": ch["id"],
                "recipient": name,
                "last_message_id": ch.get("last_message_id"),
            })
        elif ch.get("type") == 3:  # Group DM
            dms.append({
                "id": ch["id"],
                "name": ch.get("name") or "Group DM",
                "recipient_count": len(ch.get("recipients", [])),
                "last_message_id": ch.get("last_message_id"),
            })
    return _ok({"dm_channels": dms, "count": len(dms)})


async def _action_server_overview(token: str, args: dict) -> str:
    """Auto-detect key channels and fetch a summary batch.

    This is the power action: give it a guild_id and it will:
    1. List all channels and classify them
    2. Pick the top channels by priority
    3. Fetch recent messages from each
    4. Return everything in one structured response

    Limits: max 5 channels, 50 msgs each (to avoid rate limits).
    General/chat channels are filtered to last 48h only.
    """
    guild_id = args.get("guild_id")
    if not guild_id:
        return _error("guild_id is required for 'server_overview'.")

    # Step 1: Get channels
    ch_data, err = await _api_get(token, f"/guilds/{guild_id}/channels")
    if err:
        return _error(err)

    # Build categories
    categories: Dict[str, str] = {}
    for ch in ch_data:
        if ch.get("type") == _CHANNEL_CATEGORY:
            categories[ch["id"]] = ch["name"]

    # Classify and rank
    ranked: List[Dict[str, Any]] = []
    for ch in ch_data:
        if ch.get("type") not in _TEXT_CHANNEL_TYPES:
            continue
        cat_name = categories.get(ch.get("parent_id"))
        label, priority = _classify_channel(ch["name"], cat_name)
        if priority >= 99:  # skip
            continue
        ranked.append({
            "id": ch["id"],
            "name": ch["name"],
            "category": cat_name,
            "classification": label,
            "priority": priority,
        })

    ranked.sort(key=lambda c: (c["priority"], c["name"]))

    # Pick top channels: max 2 announcements, 2 dev, 1 general
    selected: List[Dict[str, Any]] = []
    counts = {"announcements": 0, "development": 0, "general": 0, "governance": 0, "market": 0}
    limits = {"announcements": 2, "development": 2, "general": 1, "governance": 1, "market": 1}

    for ch in ranked:
        cls = ch["classification"]
        if cls in counts and counts[cls] < limits.get(cls, 1):
            selected.append(ch)
            counts[cls] += 1
        if len(selected) >= 5:
            break

    if not selected:
        return _ok({
            "guild_id": guild_id,
            "error": "No readable channels found in this server.",
            "all_channels_count": len(ranked),
        })

    # Step 2: Fetch messages from each selected channel
    overview_channels = []
    for ch in selected:
        msg_data, msg_err = await _api_get(
            token,
            f"/channels/{ch['id']}/messages",
            {"limit": "50"},
        )
        if msg_err:
            overview_channels.append({
                **ch,
                "messages": [],
                "fetch_error": msg_err,
            })
            continue

        if not isinstance(msg_data, list):
            overview_channels.append({**ch, "messages": [], "fetch_error": "Unexpected API response."})
            continue

        messages = [_parse_message(m) for m in msg_data]
        messages.reverse()  # Chronological

        # For general/chat channels, filter to last 48h
        if ch["classification"] == "general" and messages:
            messages = [
                m for m in messages
                if _is_within_hours(m["timestamp"], 48)
            ]

        overview_channels.append({
            **ch,
            "messages": messages,
            "message_count": len(messages),
        })

    return _ok({
        "guild_id": guild_id,
        "channels_scanned": len(selected),
        "channels_total": len(ranked),
        "overview": overview_channels,
    })


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_ACTIONS = {
    "guilds": _action_guilds,
    "channels": _action_channels,
    "history": _action_history,
    "search": _action_search,
    "dm_channels": _action_dm_channels,
    "server_overview": _action_server_overview,
}


def discord_reader_tool(args: dict, **kw) -> str:
    """Entry point for discord_reader tool calls."""
    token = _get_token()
    if not token:
        return _error(
            "DISCORD_USER_TOKEN not set. "
            "Get your token from Discord DevTools → Console → paste the snippet "
            "from the discord-summarize skill. Then: export DISCORD_USER_TOKEN='...'"
        )

    action = args.get("action")
    if not action or action not in _ACTIONS:
        return _error(f"Unknown action '{action}'. Available: {', '.join(_ACTIONS)}")

    from model_tools import _run_async
    try:
        return _run_async(_ACTIONS[action](token, args))
    except Exception as exc:
        logger.error("discord_reader %s failed: %s", action, exc, exc_info=True)
        return _error(f"discord_reader failed: {exc}")


def _check_discord_reader() -> bool:
    """Tool is available when user token is configured."""
    return bool(_get_token())


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

from tools.registry import registry

registry.register(
    name="discord_reader",
    toolset="messaging",
    schema=DISCORD_READER_SCHEMA,
    handler=discord_reader_tool,
    check_fn=_check_discord_reader,
    emoji="🔍",
)
