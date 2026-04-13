"""Tests for the Discord Reader Tool (self-bot REST API)."""

import json
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_user_token(monkeypatch):
    """Ensure DISCORD_USER_TOKEN is set for all tests."""
    monkeypatch.setenv("DISCORD_USER_TOKEN", "test_token_12345")


@pytest.fixture
def _no_token(monkeypatch):
    """Remove the token for tests that check missing-token behaviour."""
    monkeypatch.delenv("DISCORD_USER_TOKEN", raising=False)


# ---------------------------------------------------------------------------
# Import helpers – must happen after monkeypatch is applied
# ---------------------------------------------------------------------------

def _import_tool():
    from tools.discord_reader_tool import discord_reader_tool, _check_discord_reader
    return discord_reader_tool, _check_discord_reader


# ---------------------------------------------------------------------------
# Token check
# ---------------------------------------------------------------------------

class TestCheckAvailability:
    def test_available_when_token_set(self):
        _, check = _import_tool()
        assert check() is True

    @pytest.mark.usefixtures("_no_token")
    def test_unavailable_when_token_missing(self):
        _, check = _import_tool()
        assert check() is False


# ---------------------------------------------------------------------------
# Missing token
# ---------------------------------------------------------------------------

class TestMissingToken:
    @pytest.mark.usefixtures("_no_token")
    def test_returns_error_without_token(self):
        tool, _ = _import_tool()
        result = json.loads(tool({"action": "guilds"}))
        assert "error" in result
        assert "DISCORD_USER_TOKEN" in result["error"]


# ---------------------------------------------------------------------------
# Bad action
# ---------------------------------------------------------------------------

class TestBadAction:
    def test_unknown_action(self):
        tool, _ = _import_tool()
        with patch("tools.discord_reader_tool._get_token", return_value="tok"):
            result = json.loads(tool({"action": "nope"}))
        assert "error" in result
        assert "nope" in result["error"]

    def test_missing_action(self):
        tool, _ = _import_tool()
        with patch("tools.discord_reader_tool._get_token", return_value="tok"):
            result = json.loads(tool({"action": None}))
        assert "error" in result


# ---------------------------------------------------------------------------
# Guilds
# ---------------------------------------------------------------------------

class TestGuilds:
    def test_guilds_success(self):
        tool, _ = _import_tool()
        fake_guilds = [
            {"id": "111", "name": "Server A", "owner": True, "icon": "abc"},
            {"id": "222", "name": "Server B", "owner": False, "icon": None},
        ]

        async def fake_get(token, path, params=None):
            return fake_guilds

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "guilds"}))

        assert result["count"] == 2
        assert result["guilds"][0]["name"] == "Server A"
        assert result["guilds"][1]["icon"] is False

    def test_guilds_api_error(self):
        tool, _ = _import_tool()

        async def fake_get(token, path, params=None):
            return {"_error": "Invalid or expired user token."}

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "guilds"}))

        assert "error" in result


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

class TestChannels:
    def test_channels_requires_guild_id(self):
        tool, _ = _import_tool()

        async def fake_get(token, path, params=None):
            return []

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "channels"}))

        assert "error" in result
        assert "guild_id" in result["error"]

    def test_channels_filters_text_channels(self):
        tool, _ = _import_tool()
        fake_channels = [
            {"id": "10", "name": "General", "type": 4, "position": 0},  # Category
            {"id": "11", "name": "general", "type": 0, "parent_id": "10", "position": 1},
            {"id": "12", "name": "voice-chat", "type": 2, "parent_id": "10", "position": 2},  # Voice
            {"id": "13", "name": "announcements", "type": 5, "parent_id": "10", "position": 3},
        ]

        async def fake_get(token, path, params=None):
            return fake_channels

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "channels", "guild_id": "111"}))

        assert result["count"] == 2  # text + announcement, not voice or category
        names = {ch["name"] for ch in result["channels"]}
        assert "general" in names
        assert "announcements" in names
        assert "voice-chat" not in names


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class TestHistory:
    def test_history_requires_channel_id(self):
        tool, _ = _import_tool()

        async def fake_get(token, path, params=None):
            return []

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "history"}))

        assert "error" in result
        assert "channel_id" in result["error"]

    def test_history_returns_chronological_order(self):
        tool, _ = _import_tool()
        # API returns newest first
        fake_messages = [
            {
                "id": "3", "author": {"username": "bob", "global_name": "Bob"},
                "content": "third", "timestamp": "2025-01-01T00:03:00",
                "attachments": [], "embeds": [],
            },
            {
                "id": "2", "author": {"username": "alice", "global_name": None},
                "content": "second", "timestamp": "2025-01-01T00:02:00",
                "attachments": [{"id": "a1"}], "embeds": [],
            },
            {
                "id": "1", "author": {"username": "charlie", "global_name": "Charlie"},
                "content": "first", "timestamp": "2025-01-01T00:01:00",
                "attachments": [], "embeds": [],
            },
        ]

        async def fake_get(token, path, params=None):
            return fake_messages

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "history", "channel_id": "11"}))

        assert result["count"] == 3
        # Should be reversed to chronological
        assert result["messages"][0]["content"] == "first"
        assert result["messages"][2]["content"] == "third"
        # alice has no global_name, should fall back to username
        assert result["messages"][1]["author"] == "alice"
        # attachment count
        assert result["messages"][1]["attachments"] == 1

    def test_history_limit_clamped(self):
        tool, _ = _import_tool()
        calls = []

        async def fake_get(token, path, params=None):
            calls.append(params)
            return []

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            tool({"action": "history", "channel_id": "11", "limit": 999})

        assert calls[0]["limit"] == "100"  # clamped to max 100

    def test_history_with_before_pagination(self):
        tool, _ = _import_tool()
        calls = []

        async def fake_get(token, path, params=None):
            calls.append(params)
            return []

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            tool({"action": "history", "channel_id": "11", "before": "99999"})

        assert calls[0]["before"] == "99999"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_requires_guild_and_query(self):
        tool, _ = _import_tool()

        async def fake_get(token, path, params=None):
            return []

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "search", "guild_id": "111"}))
        assert "error" in result

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "search", "query": "hello"}))
        assert "error" in result

    def test_search_returns_hits(self):
        tool, _ = _import_tool()
        fake_search = {
            "total_results": 1,
            "messages": [
                [
                    {
                        "id": "55", "hit": True,
                        "author": {"username": "alice", "global_name": "Alice"},
                        "content": "deploy is done", "channel_id": "11",
                        "timestamp": "2025-01-01T12:00:00",
                    },
                    {
                        "id": "54", "hit": False,
                        "author": {"username": "bob", "global_name": "Bob"},
                        "content": "context message",
                        "channel_id": "11",
                        "timestamp": "2025-01-01T11:59:00",
                    },
                ]
            ],
        }

        async def fake_get(token, path, params=None):
            return fake_search

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "search", "guild_id": "111", "query": "deploy"}))

        assert result["total"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["content"] == "deploy is done"


# ---------------------------------------------------------------------------
# DM Channels
# ---------------------------------------------------------------------------

class TestDMChannels:
    def test_dm_channels(self):
        tool, _ = _import_tool()
        fake_dms = [
            {
                "id": "900", "type": 1,
                "recipients": [{"username": "friend1", "global_name": "Friend One"}],
                "last_message_id": "800",
            },
            {
                "id": "901", "type": 3, "name": "Squad",
                "recipients": [
                    {"username": "a", "global_name": "A"},
                    {"username": "b", "global_name": "B"},
                ],
                "last_message_id": "801",
            },
            {
                "id": "902", "type": 2,  # Voice DM — should be skipped
                "recipients": [],
            },
        ]

        async def fake_get(token, path, params=None):
            return fake_dms

        with patch("tools.discord_reader_tool._get", side_effect=fake_get):
            result = json.loads(tool({"action": "dm_channels"}))

        assert result["count"] == 2
        assert result["dm_channels"][0]["recipient"] == "Friend One"
        assert result["dm_channels"][1]["name"] == "Squad"
        assert result["dm_channels"][1]["recipient_count"] == 2
