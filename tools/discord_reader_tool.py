"""Discord Reader Tool -- read channels & message history via user token.

Uses the Discord REST API directly with a **user token** (self-bot style) so
it can access every server and channel the account belongs to, including
private and DM channels.  No discord.py dependency — just aiohttp.

Environment variable:
    DISCORD_USER_TOKEN  – The user account token (NOT a bot token).

Actions:
    guilds       – List all servers the account is in.
    channels     – List text channels in a server.
    history      – Fetch recent messages from a channel.
    search       – Search messages in a guild by content.
    dm_channels  – List recent DM conversations.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_API_BASE = "https://discord.com/api/v10"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DISCORD_READER_SCHEMA = {
    "name": "discord_reader",
    "description": (
        "Read Discord channels and message history using your personal account.\n\n"
        "Actions:\n"
        "  guilds    – List all servers you are in.\n"
        "  channels  – List text channels in a server (requires guild_id).\n"
        "  history   – Fetch recent messages from a channel (requires channel_id, optional limit 1-100).\n"
        "  search    – Search messages in a guild (requires guild_id + query).\n"
        "  dm_channels – List your recent DM conversations.\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["guilds", "channels", "history", "search", "dm_channels"],
                "description": "Action to perform.",
            },
            "guild_id": {
                "type": "string",
                "description": "Server (guild) ID. Required for 'channels' and 'search'.",
            },
            "channel_id": {
                "type": "string",
                "description": "Channel ID. Required for 'history'.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of messages to fetch (1-100, default 50).",
            },
            "query": {
                "type": "string",
                "description": "Search query string. Required for 'search'.",
            },
            "before": {
                "type": "string",
                "description": "Fetch messages before this message ID (for pagination).",
            },
        },
        "required": ["action"],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_token() -> Optional[str]:
    return os.getenv("DISCORD_USER_TOKEN")


def _headers(token: str) -> dict:
    """Build request headers for a user-token request."""
    return {
        "Authorization": token,  # User tokens don't use "Bot " prefix
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }


def _error(msg: str) -> str:
    return json.dumps({"error": msg})


async def _get(token: str, path: str, params: dict = None) -> Any:
    """Perform a GET request against the Discord API."""
    import aiohttp
    from gateway.platforms.base import resolve_proxy_url, proxy_kwargs_for_aiohttp

    proxy = resolve_proxy_url(platform_env_var="DISCORD_PROXY")
    sess_kw, req_kw = proxy_kwargs_for_aiohttp(proxy)
    url = f"{_API_BASE}{path}"

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30), **sess_kw
    ) as session:
        async with session.get(
            url, headers=_headers(token), params=params, **req_kw
        ) as resp:
            if resp.status == 401:
                return {"_error": "Invalid or expired user token. Check DISCORD_USER_TOKEN."}
            if resp.status == 403:
                return {"_error": f"Access denied (403) for {path}. You may not have permission."}
            if resp.status == 429:
                retry_after = (await resp.json()).get("retry_after", "?")
                return {"_error": f"Rate limited. Retry after {retry_after}s."}
            if resp.status != 200:
                body = await resp.text()
                return {"_error": f"Discord API error ({resp.status}): {body[:300]}"}
            return await resp.json()


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

async def _action_guilds(token: str, args: dict) -> str:
    """List all guilds the user is a member of."""
    data = await _get(token, "/users/@me/guilds", {"limit": "200"})
    if isinstance(data, dict) and "_error" in data:
        return _error(data["_error"])

    guilds = []
    for g in data:
        guilds.append({
            "id": g["id"],
            "name": g["name"],
            "owner": g.get("owner", False),
            "icon": bool(g.get("icon")),
        })
    return json.dumps({"guilds": guilds, "count": len(guilds)})


async def _action_channels(token: str, args: dict) -> str:
    """List text channels in a guild."""
    guild_id = args.get("guild_id")
    if not guild_id:
        return _error("guild_id is required for 'channels' action.")

    data = await _get(token, f"/guilds/{guild_id}/channels")
    if isinstance(data, dict) and "_error" in data:
        return _error(data["_error"])

    # Filter to text-based channels (type 0=text, 5=announcement, 15=forum)
    text_types = {0, 5, 15}
    # Also include category (type 4) for context
    channels = []
    categories = {}
    for ch in data:
        if ch["type"] == 4:  # Category
            categories[ch["id"]] = ch["name"]

    for ch in data:
        if ch["type"] in text_types:
            channels.append({
                "id": ch["id"],
                "name": ch["name"],
                "type": ch["type"],
                "category": categories.get(ch.get("parent_id"), None),
                "topic": ch.get("topic", ""),
                "nsfw": ch.get("nsfw", False),
            })

    # Sort by position
    channels.sort(key=lambda c: (c.get("category") or "", c["name"]))
    return json.dumps({"channels": channels, "count": len(channels), "guild_id": guild_id})


async def _action_history(token: str, args: dict) -> str:
    """Fetch message history from a channel."""
    channel_id = args.get("channel_id")
    if not channel_id:
        return _error("channel_id is required for 'history' action.")

    limit = min(max(args.get("limit", 50), 1), 100)
    params = {"limit": str(limit)}
    before = args.get("before")
    if before:
        params["before"] = before

    data = await _get(token, f"/channels/{channel_id}/messages", params)
    if isinstance(data, dict) and "_error" in data:
        return _error(data["_error"])

    messages = []
    for m in data:
        msg = {
            "id": m["id"],
            "author": m["author"].get("global_name") or m["author"].get("username", "unknown"),
            "content": m.get("content", ""),
            "timestamp": m.get("timestamp", ""),
        }
        # Note attachments
        if m.get("attachments"):
            msg["attachments"] = len(m["attachments"])
        # Note embeds
        if m.get("embeds"):
            msg["embeds"] = len(m["embeds"])
        # Note replies
        ref = m.get("message_reference")
        if ref:
            msg["reply_to"] = ref.get("message_id")
        messages.append(msg)

    # Messages come newest-first from API; reverse for chronological order
    messages.reverse()
    return json.dumps({
        "messages": messages,
        "count": len(messages),
        "channel_id": channel_id,
    })


async def _action_search(token: str, args: dict) -> str:
    """Search messages in a guild."""
    guild_id = args.get("guild_id")
    query = args.get("query")
    if not guild_id or not query:
        return _error("guild_id and query are required for 'search' action.")

    params = {"content": query}
    limit = args.get("limit")
    if limit:
        params["limit"] = str(min(max(limit, 1), 25))

    data = await _get(token, f"/guilds/{guild_id}/messages/search", params)
    if isinstance(data, dict) and "_error" in data:
        return _error(data["_error"])

    results = []
    for group in data.get("messages", []):
        for m in group:
            if m.get("hit"):
                results.append({
                    "id": m["id"],
                    "author": m["author"].get("global_name") or m["author"].get("username", "unknown"),
                    "content": m.get("content", "")[:500],
                    "channel_id": m.get("channel_id"),
                    "timestamp": m.get("timestamp", ""),
                })
    return json.dumps({
        "results": results,
        "total": data.get("total_results", len(results)),
        "guild_id": guild_id,
    })


async def _action_dm_channels(token: str, args: dict) -> str:
    """List recent DM channels."""
    data = await _get(token, "/users/@me/channels")
    if isinstance(data, dict) and "_error" in data:
        return _error(data["_error"])

    dms = []
    for ch in data:
        if ch["type"] == 1:  # DM
            recipients = ch.get("recipients", [])
            name = recipients[0].get("global_name") or recipients[0].get("username", "?") if recipients else "?"
            dms.append({
                "id": ch["id"],
                "recipient": name,
                "last_message_id": ch.get("last_message_id"),
            })
        elif ch["type"] == 3:  # Group DM
            dms.append({
                "id": ch["id"],
                "name": ch.get("name") or "Group DM",
                "recipient_count": len(ch.get("recipients", [])),
                "last_message_id": ch.get("last_message_id"),
            })
    return json.dumps({"dm_channels": dms, "count": len(dms)})


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

_ACTIONS = {
    "guilds": _action_guilds,
    "channels": _action_channels,
    "history": _action_history,
    "search": _action_search,
    "dm_channels": _action_dm_channels,
}


def discord_reader_tool(args: dict, **kw) -> str:
    """Handle discord_reader tool calls."""
    token = _get_token()
    if not token:
        return _error(
            "DISCORD_USER_TOKEN not set. "
            "Get your token from Discord DevTools (Ctrl+Shift+I → Network tab → "
            "copy Authorization header) and set it: "
            "export DISCORD_USER_TOKEN='your_token_here'"
        )

    action = args.get("action")
    if not action or action not in _ACTIONS:
        return _error(f"Unknown action: {action}. Available: {', '.join(_ACTIONS)}")

    from model_tools import _run_async
    return _run_async(_ACTIONS[action](token, args))


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
