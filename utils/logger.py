import logging
import sys
from pathlib import Path


LOG_FORMAT = "[%(levelname)s] %(message)s"
DEBUG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"


def setup_logger(nome: str = "TradeSimulado", debug: bool = False, arquivo: str | None = None):
    logger = logging.getLogger(nome)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    handler.setFormatter(logging.Formatter(DEBUG_FORMAT if debug else LOG_FORMAT))
    logger.addHandler(handler)

    if arquivo:
        Path("logs").mkdir(exist_ok=True)
        fh = logging.FileHandler(f"logs/{arquivo}", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(DEBUG_FORMAT))
        logger.addHandler(fh)

    return logger
