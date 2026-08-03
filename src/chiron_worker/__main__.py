"""Worker daemon entrypoint: ``python -m chiron_worker`` (AD-2).

One long-running process hosts every Domain's APScheduler job — the only
place trigger-loop state lives.
"""

import asyncio
import logging

from chiron_cache import create_pool, ensure_schema

from .config import WorkerConfigError, load_worker_config
from .scheduler import build_scheduler

logger = logging.getLogger(__name__)


async def run() -> None:
    logging.basicConfig(level=logging.INFO)

    try:
        config = load_worker_config()
    except WorkerConfigError as exc:
        logger.error("chiron_worker startup failed: %s", exc)
        raise SystemExit(1) from exc

    pool = await create_pool()
    async with pool.acquire() as conn:
        await ensure_schema(conn)

    scheduler = build_scheduler(config, pool)
    scheduler.start()
    logger.info("chiron_worker started with jobs: %s", [j.id for j in scheduler.get_jobs()])

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await pool.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
