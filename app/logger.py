import json
import logging
import os
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger()

LOG_FILE = "logs/app.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


file_handler = TimedRotatingFileHandler(
    LOG_FILE,
    when="midnight",
    interval=1,
    backupCount=7,
)

file_handler.setFormatter(JsonFormatter())

logger.handlers = [file_handler]
logger.setLevel(logging.INFO)
