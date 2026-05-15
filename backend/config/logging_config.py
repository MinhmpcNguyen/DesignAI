from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logging(level: str | None = None) -> None:
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    _ensure_run_id()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _setup_console_log()
    _setup_all_log_file()
    _setup_extra_loggers()


def _ensure_run_id() -> str:
    run_id = os.getenv("LOG_RUN_ID")
    if run_id:
        return run_id
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"{run_id}_{os.getpid()}"
    os.environ["LOG_RUN_ID"] = run_id
    return run_id


def _setup_all_log_file() -> None:
    base_dir = Path(os.getenv("LOG_DIR", "logs"))
    base_dir.mkdir(parents=True, exist_ok=True)
    run_id = _ensure_run_id()
    default_name = f"all_{run_id}.log"
    log_path = str((base_dir / os.getenv("LOG_ALL_FILENAME", default_name)).resolve())
    root = logging.getLogger()
    if _has_file_handler(root, log_path):
        return
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root.addHandler(handler)


def _setup_console_log() -> None:
    root = logging.getLogger()
    if any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root.addHandler(handler)


def _setup_extra_loggers() -> None:
    base_dir = Path(os.getenv("LOG_DIR", "logs"))
    base_dir.mkdir(parents=True, exist_ok=True)
    run_id = _ensure_run_id()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    rag_logger = logging.getLogger("rag")
    rag_logger.setLevel(logging.INFO)
    rag_logger.propagate = False

    search_logger = logging.getLogger("search")
    search_logger.setLevel(logging.INFO)
    search_logger.propagate = False

    self_loop_logger = logging.getLogger("self_loop")
    self_loop_logger.setLevel(logging.INFO)
    self_loop_logger.propagate = False

    exchange_logger = logging.getLogger("agent_exchange")
    exchange_logger.setLevel(logging.INFO)
    exchange_logger.propagate = False

    pairwise_logger = logging.getLogger("pairwise")
    pairwise_logger.setLevel(logging.INFO)
    pairwise_logger.propagate = False

    image_flow_logger = logging.getLogger("image_flow")
    image_flow_logger.setLevel(logging.INFO)
    image_flow_logger.propagate = False

    rag_log_path = str((base_dir / f"rag_{run_id}.log").resolve())
    if not _has_file_handler(rag_logger, rag_log_path):
        rag_handler = logging.FileHandler(rag_log_path, encoding="utf-8")
        rag_handler.setFormatter(formatter)
        rag_logger.addHandler(rag_handler)

    search_log_path = str((base_dir / f"search_{run_id}.log").resolve())
    if not _has_file_handler(search_logger, search_log_path):
        search_handler = logging.FileHandler(search_log_path, encoding="utf-8")
        search_handler.setFormatter(formatter)
        search_logger.addHandler(search_handler)

    self_loop_path = str((base_dir / f"self_loop_{run_id}.log").resolve())
    if not _has_file_handler(self_loop_logger, self_loop_path):
        self_loop_handler = logging.FileHandler(self_loop_path, encoding="utf-8")
        self_loop_handler.setFormatter(formatter)
        self_loop_logger.addHandler(self_loop_handler)

    exchange_path = str((base_dir / f"agent_exchange_{run_id}.log").resolve())
    if not _has_file_handler(exchange_logger, exchange_path):
        exchange_handler = logging.FileHandler(exchange_path, encoding="utf-8")
        exchange_handler.setFormatter(formatter)
        exchange_logger.addHandler(exchange_handler)

    pairwise_path = str((base_dir / f"pairwise_{run_id}.log").resolve())
    if not _has_file_handler(pairwise_logger, pairwise_path):
        pairwise_handler = logging.FileHandler(pairwise_path, encoding="utf-8")
        pairwise_handler.setFormatter(formatter)
        pairwise_logger.addHandler(pairwise_handler)

    image_flow_path = str((base_dir / f"image_flow_{run_id}.jsonl").resolve())
    if not _has_file_handler(image_flow_logger, image_flow_path):
        image_flow_handler = logging.FileHandler(image_flow_path, encoding="utf-8")
        image_flow_handler.setFormatter(logging.Formatter("%(message)s"))
        image_flow_logger.addHandler(image_flow_handler)


def _has_file_handler(logger: logging.Logger, path: str) -> bool:
    for handler in logger.handlers:
        if (
            isinstance(handler, logging.FileHandler)
            and str(Path(getattr(handler, "baseFilename", "")).resolve()) == path
        ):
            return True
    return False
