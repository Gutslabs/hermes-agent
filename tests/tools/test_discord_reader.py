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
    monkeypatch.setenv("DISCORD_USER_TOKEN", "test_token_12345")


@pytest.fixture
def _no_token(monkeypatch):
    monkeypatch.delenv("DISCORD_USER_TOKEN", raising=False)


def _import_tool():
    from tools.discord_reader_tool import discord_reader_tool, _check_discord_reader
    return discord_reader_tool, _check_discord_reader


# Helper: mock _api_get to return (data, None) or (None, error)
def _mock_api(return_value):
    """Create an async mock for _api_get that returns (data, None)."""
    async def fake_get(token, path, params=None):
        return return_value, None
    return fake_get


def _mock_api_err(error_msg):
    async def fake_get(token, path, params=None):
        return None, error_msg
    return fake_get


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


class TestMissingToken:
    @pytest.mark.usefixtures("_no_token")
    def test_returns_error_without_token(self):
        tool, _ = _import_tool()
        result = json.loads(tool({"action": "guilds"}))
        assert "error" in result
        assert "DISCORD_USER_TOKEN" in result["error"]


class TestBadAction:
    def test_unknown_action(self):
        tool, _ = _import_tool()
        result = json.loads(tool({"action": "nope"}))
        assert "error" in result

    def test_missing_action(self):
        tool, _ = _import_tool()
        result = json.loads(tool({"action": None}))
        assert "error" in result


# ---------------------------------------------------------------------------
# Guilds
# ---------------------------------------------------------------------------

class TestGuilds:
    def test_guilds_success(self):
        tool, _ = _import_tool()
        fake = [
            {"id": "111", "name": "Server A", "owner": True, "icon": "abc"},
            {"id": "222", "name": "Server B", "owner": False, "icon": None},
        ]
        with patch("tools.discord_reader_tool._api_get", side_effect=_mock_api(fake)):
            result = json.loads(tool({"action": "guilds"}))
        assert result["count"] == 2
        assert result["guilds"][0]["name"] == "Server A"

    def test_guilds_api_error(self):
        tool, _ = _import_tool()
        with patch("tools.discord_reader_tool._api_get", side_effect=_mock_api_err("Invalid token")):
            result = json.loads(tool({"action": "guilds"}))
        assert "error" in result


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

class TestChannels:
    def test_channels_requires_guild_id(self):
        tool, _ = _import_tool()
        result = json.loads(tool({"action": "channels"}))
        assert "error" in result
        assert "guild_id" in result["error"]

    def test_channels_classifies_and_filters(self):
        tool, _ = _import_tool()
        fake = [
            {"id": "10", "name": "General", "type": 4, "position": 0},
            {"id": "11", "name": "announcements", "type": 0, "parent_id": "10", "position": 1},
            {"id": "12", "name": "voice-chat", "type": 2, "parent_id": "10", "position": 2},
            {"id": "13", "name": "general", "type": 0, "parent_id": "10", "position": 3},
            {"id": "14", "name": "dev-chat", "type": 0, "parent_id": "10", "position": 4},
            {"id": "15", "name": "bot-commands", "type": 0, "parent_id": "10", "position": 5},
        ]
        with patch("tools.discord_reader_tool._api_get", side_effect=_mock_api(fake)):
            result = json.loads(tool({"action": "channels", "guild_id": "111"}))

        # voice channel filtered out, 4 text channels remain
        assert result["count"] == 4
        names = [ch["name"] for ch in result["channels"]]
        assert "voice-chat" not in names
        # Check classification
        by_name = {ch["name"]: ch for ch in result["channels"]}
        assert by_name["announcements"]["classification"] == "announcements"
        assert by_name["dev-chat"]["classification"] == "development"
        assert by_name["general"]["classification"] == "general"
        assert by_name["bot-commands"]["classification"] == "skip"
        assert by_name["bot-commands"]["priority"] == 99
        # Sorted by priority: announcements (1) first, skip (99) last
        assert result["channels"][0]["name"] == "announcements"
        assert result["channels"][-1]["name"] == "bot-commands"


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class TestHistory:
    def test_history_requires_channel_id(self):
        tool, _ = _import_tool()
        result = json.loads(tool({"action": "history"}))
        assert "error" in result

    def test_history_chronological_order(self):
        tool, _ = _import_tool()
        fake = [
            {"id": "3", "author": {"username": "bob", "global_name": "Bob"},
             "content": "third", "timestamp": "2025-01-01T00:03:00",
             "attachments": [], "embeds": []},
            {"id": "2", "author": {"username": "alice", "global_name": None},
             "content": "second", "timestamp": "2025-01-01T00:02:00",
             "attachments": [{"id": "a1"}], "embeds": []},
            {"id": "1", "author": {"username": "charlie", "global_name": "Charlie"},
             "content": "first", "timestamp": "2025-01-01T00:01:00",
             "attachments": [], "embeds": []},
        ]
        with patch("tools.discord_reader_tool._api_get", side_effect=_mock_api(fake)):
            result = json.loads(tool({"action": "history", "channel_id": "11"}))

        assert result["count"] == 3
        assert result["messages"][0]["content"] == "first"
        assert result["messages"][2]["content"] == "third"
        assert result["messages"][1]["author"] == "alice"  # fallback to username
        assert result["messages"][1]["attachments"] == 1
        assert result["oldest_id"] == "1"
        assert result["newest_id"] == "3"

    def test_history_limit_clamped(self):
        tool, _ = _import_tool()
        calls = []

        async def spy(token, path, params=None):
            calls.append(params)
            return [], None

        with patch("tools.discord_reader_tool._api_get", side_effect=spy):
            tool({"action": "history", "channel_id": "11", "limit": 999})
        assert calls[0]["limit"] == "100"

    def test_history_pagination_before(self):
        tool, _ = _import_tool()
        calls = []

        async def spy(token, path, params=None):
            calls.append(params)
            return [], None

        with patch("tools.discord_reader_tool._api_get", side_effect=spy):
            tool({"action": "history", "channel_id": "11", "before": "99999"})
        assert calls[0]["before"] == "99999"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_requires_both_params(self):
        tool, _ = _import_tool()
        r1 = json.loads(tool({"action": "search", "guild_id": "111"}))
        assert "error" in r1
        r2 = json.loads(tool({"action": "search", "query": "hello"}))
        assert "error" in r2

    def test_search_returns_hits_only(self):
        tool, _ = _import_tool()
        fake = {
            "total_results": 1,
            "messages": [[
                {"id": "55", "hit": True,
                 "author": {"username": "alice", "global_name": "Alice"},
                 "content": "deploy done", "channel_id": "11",
                 "timestamp": "2025-01-01T12:00:00"},
                {"id": "54", "hit": False,
                 "author": {"username": "bob", "global_name": "Bob"},
                 "content": "context", "channel_id": "11",
                 "timestamp": "2025-01-01T11:59:00"},
            ]],
        }
        with patch("tools.discord_reader_tool._api_get", side_effect=_mock_api(fake)):
            result = json.loads(tool({"action": "search", "guild_id": "111", "query": "deploy"}))
        assert result["total"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["content"] == "deploy done"


# ---------------------------------------------------------------------------
# DM Channels
# ---------------------------------------------------------------------------

class TestDMChannels:
    def test_dm_channels(self):
        tool, _ = _import_tool()
        fake = [
            {"id": "900", "type": 1,
             "recipients": [{"username": "friend1", "global_name": "Friend One"}],
             "last_message_id": "800"},
            {"id": "901", "type": 3, "name": "Squad",
             "recipients": [{"username": "a"}, {"username": "b"}],
             "last_message_id": "801"},
            {"id": "902", "type": 2, "recipients": []},  # Voice — skipped
        ]
        with patch("tools.discord_reader_tool._api_get", side_effect=_mock_api(fake)):
            result = json.loads(tool({"action": "dm_channels"}))
        assert result["count"] == 2
        assert result["dm_channels"][0]["recipient"] == "Friend One"
        assert result["dm_channels"][1]["name"] == "Squad"


# ---------------------------------------------------------------------------
# Server Overview
# ---------------------------------------------------------------------------

class TestServerOverview:
    def test_overview_requires_guild_id(self):
        tool, _ = _import_tool()
        result = json.loads(tool({"action": "server_overview"}))
        assert "error" in result

    def test_overview_fetches_key_channels(self):
        tool, _ = _import_tool()
        fake_channels = [
            {"id": "10", "name": "Info", "type": 4, "position": 0},
            {"id": "11", "name": "announcements", "type": 5, "parent_id": "10", "position": 1},
            {"id": "12", "name": "dev-chat", "type": 0, "parent_id": "10", "position": 2},
            {"id": "13", "name": "general", "type": 0, "parent_id": "10", "position": 3},
            {"id": "14", "name": "bot-commands", "type": 0, "parent_id": "10", "position": 4},
            {"id": "15", "name": "memes", "type": 0, "parent_id": "10", "position": 5},
        ]
        fake_msg = [
            {"id": "1", "author": {"username": "u"}, "content": "hello",
             "timestamp": "2025-01-01T00:00:00", "attachments": [], "embeds": []},
        ]

        call_count = {"n": 0}

        async def multi_get(token, path, params=None):
            call_count["n"] += 1
            if "/channels" in path and "/messages" in path:
                return fake_msg, None
            return fake_channels, None

        with patch("tools.discord_reader_tool._api_get", side_effect=multi_get):
            result = json.loads(tool({"action": "server_overview", "guild_id": "111"}))

        assert result["channels_scanned"] == 3  # announcements, dev, general (skip bot-commands, memes)
        names = [ch["name"] for ch in result["overview"]]
        assert "announcements" in names
        assert "dev-chat" in names
        assert "general" in names
        assert "bot-commands" not in names
        assert "memes" not in names


# ---------------------------------------------------------------------------
# Channel classification
# ---------------------------------------------------------------------------

class TestClassification:
    def test_classify_patterns(self):
        from tools.discord_reader_tool import _classify_channel
        assert _classify_channel("announcements")[0] == "announcements"
        assert _classify_channel("📢-announcements")[0] == "announcements"
        assert _classify_channel("dev-chat")[0] == "development"
        assert _classify_channel("general")[0] == "general"
        assert _classify_channel("bot-commands")[0] == "skip"
        assert _classify_channel("memes")[0] == "skip"
        assert _classify_channel("governance")[0] == "governance"
        assert _classify_channel("price-talk")[0] == "market"
        assert _classify_channel("random-stuff")[0] == "other"

    def test_strip_emoji_prefix(self):
        from tools.discord_reader_tool import _strip_emoji_prefix
        assert _strip_emoji_prefix("︱📢︱announcements") == "announcements"
        assert _strip_emoji_prefix("general") == "general"
        assert _strip_emoji_prefix("🛠-dev") == "dev"
