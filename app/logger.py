import json
import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger()


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
    "logs/app.log",
    when="midnight",
    interval=1 // 86400,
    backupCount=7,
)

file_handler.setFormatter(JsonFormatter())

logger.handlers = [file_handler]
logger.setLevel(logging.INFO)
