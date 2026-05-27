import logging
import json
import sys
from datetime import datetime

from config import settings


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3],
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        extra_fields = getattr(record, "fields", None)
        if extra_fields:
            log_entry.update(extra_fields)
        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rid = getattr(record, "request_id", "")
        rid_str = f" [{rid}]" if rid else ""
        msg = f"{ts} {record.levelname:5s} {record.name}{rid_str} | {record.getMessage()}"
        if record.exc_info and record.exc_info[1]:
            msg += "\n" + self.formatException(record.exc_info)
        return msg


def setup_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    fmt_class = JSONFormatter if settings.log_format == "json" else TextFormatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt_class())
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler.setLevel(level)

    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
