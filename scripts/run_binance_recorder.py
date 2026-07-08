#!/usr/bin/env python
from __future__ import annotations

import asyncio
import logging
import signal

from trading_market_data import BinanceMarketDataRecorder, RecorderConfig


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def main() -> None:
    configure_logging()
    config = RecorderConfig.from_env()
    recorder = BinanceMarketDataRecorder(config)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    task = asyncio.create_task(recorder.start())
    await stop_event.wait()
    await recorder.stop()
    task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
