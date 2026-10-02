import unittest
from dataclasses import replace

from snake_media.config import Config, ConfigError
from snake_media.requests import IncomingMessage
from snake_media.service import RequestService, TestBackend


def config():
    return Config.from_env({
        "DISCORD_TOKEN": "test-secret-never-real",
        "ALLOWED_DISCORD_USER_IDS": "111, 222,111",
        "ALLOWED_DISCORD_CHANNEL_IDS": "333",
    })


def message(**changes):
    original = IncomingMessage(
        text="<@999> add The Matrix from 1999", user_id="111",
        username="someone", channel_id="333", guild_id="444", is_bot=False,
    )
    return replace(original, **changes)


class ConfigTests(unittest.TestCase):
    def test_multiple_ids_and_secrets_not_in_repr(self):
        settings = config()
        self.assertEqual(settings.allowed_user_ids, frozenset({"111", "222"}))
        self.assertNotIn("test-secret", repr(settings))

    def test_missing_or_invalid_required_configuration_fails_closed(self):
        valid = {"DISCORD_TOKEN": "test", "ALLOWED_DISCORD_USER_IDS": "111",
                 "ALLOWED_DISCORD_CHANNEL_IDS": "333"}
        for key in valid:
            for value in ("", "   "):
                with self.subTest(key=key, value=value), self.assertRaises(ConfigError):
                    Config.from_env(valid | {key: value})
        for value in ("abc", "111,", "0", "-12", "１２", str(2**64)):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                Config.from_env(valid | {"ALLOWED_DISCORD_USER_IDS": value})


class RecordingBackend:
    def __init__(self, fail=False):
        self.requests = []
        self.fail = fail

    async def submit(self, request):
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("sensitive upstream credential")
        return "Accepted by test backend"


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_normalized_request_preserves_identity_and_removes_both_mentions(self):
        backend = RecordingBackend()
        service = RequestService(config(), backend)
        reply = await service.handle(message(text=" <@!999> add Matrix <@999> "), "999")
        self.assertEqual(reply, "Accepted by test backend")
        self.assertEqual(backend.requests[0].to_payload(), {
            "source": "discord", "text": "add Matrix", "userId": "111",
            "username": "someone", "channelId": "333", "guildId": "444",
        })

    async def test_unauthorized_identity_never_reaches_backend(self):
        backend = RecordingBackend()
        service = RequestService(config(), backend)
        reply = await service.handle(message(user_id="555", username="111"), "999")
        self.assertIn("isn't authorized", reply)
        self.assertEqual(backend.requests, [])

    async def test_ignored_messages_never_reach_backend(self):
        backend = RecordingBackend()
        service = RequestService(config(), backend)
        for changes in ({"is_bot": True}, {"guild_id": None}, {"channel_id": "777"},
                        {"text": "add Matrix"}, {"text": "<@9990> add Matrix"},
                        {"text": "<@&999> add Matrix"}):
            with self.subTest(changes=changes):
                self.assertIsNone(await service.handle(message(**changes), "999"))
        self.assertEqual(backend.requests, [])

    async def test_empty_and_oversized_requests_do_not_reach_backend(self):
        backend = RecordingBackend()
        service = RequestService(config(), backend)
        for content in ("<@999>   ", "<@999> " + "x" * 2001):
            self.assertIsNotNone(await service.handle(message(text=content), "999"))
        self.assertEqual(backend.requests, [])

    async def test_phase1_reply_clearly_says_no_submission(self):
        reply = await RequestService(config(), TestBackend()).handle(message(), "999")
        self.assertIn("No media request was submitted", reply)

    async def test_backend_failure_is_safe_and_next_request_succeeds(self):
        backend = RecordingBackend(fail=True)
        service = RequestService(config(), backend)
        with self.assertLogs("snake_media", level="ERROR") as logs:
            reply = await service.handle(message(), "999")
        self.assertIn("try again", reply)
        self.assertNotIn("sensitive", " ".join(logs.output) + reply)
        backend.fail = False
        self.assertEqual(await service.handle(message(), "999"), "Accepted by test backend")
