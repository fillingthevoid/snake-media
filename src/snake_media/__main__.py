import asyncio
import logging
import signal
from contextlib import AsyncExitStack

from .bot import SnakeMediaClient
from .config import Config, ConfigError
from .service import RequestService, TestBackend
from .n8n_client import N8NClient
from .notifications import NotificationTransport
from .delivery_journal import DeliveryJournal

log = logging.getLogger("snake_media")


async def serve(client, token: str, stop: asyncio.Event):
    async with client:
        connection = asyncio.create_task(client.start(token, reconnect=True))
        stopping = asyncio.create_task(stop.wait())
        try:
            done, _ = await asyncio.wait({connection, stopping},
                                         return_when=asyncio.FIRST_COMPLETED)
            if connection in done:
                await connection
        finally:
            for task in (connection, stopping):
                task.cancel()
            await asyncio.gather(connection, stopping, return_exceptions=True)


async def run(config: Config):
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    registered = []
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
            registered.append(sig)
        except NotImplementedError:
            # Windows local development uses asyncio.run's Ctrl+C handling.
            pass
    try:
        async with AsyncExitStack() as stack:
            backend = TestBackend()
            notifications = None
            journal = None
            if config.bot_mode == 'n8n':
                backend = await stack.enter_async_context(N8NClient(
                    config.n8n_webhook_url, config.n8n_webhook_secret,
                    config.n8n_timeout_seconds))
                if config.n8n_notifications_url:
                    journal = stack.enter_context(DeliveryJournal(config.notification_state_path))
                    notifications = await stack.enter_async_context(NotificationTransport(
                        config.n8n_notifications_url, config.n8n_webhook_secret))
            await serve(SnakeMediaClient(RequestService(config, backend), notifications, journal),
                        config.discord_token, stop)
    finally:
        for sig in registered:
            loop.remove_signal_handler(sig)
        log.info("Snake Media stopped")


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # Library error strings can contain network URLs or payloads. The adapter
    # emits safe lifecycle/error diagnostics instead of forwarding those logs.
    for name in ("discord", "aiohttp", "asyncio"):
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
    try:
        config = Config.from_env()
        log.info("Starting Snake Media mode=%s", config.bot_mode)
        asyncio.run(run(config))
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 1
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log.error("Bot stopped unexpectedly error_type=%s", type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
