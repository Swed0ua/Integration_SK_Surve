from core.logger import LOG_LEVEL_INFO
from services.DBService import add_log

class LoggerService:
    @staticmethod
    def log(
        main_msg: str,
        level: str = LOG_LEVEL_INFO,
        msg_log_db: str = "",
        msg_console: str = "",
        receipt_id: str = None
    ):
        db_message = main_msg
        if msg_log_db:
            db_message += f" | {msg_log_db}"

        console_message = main_msg
        if msg_console:
            console_message += f" | {msg_console}"

        add_log(level, db_message, receipt_id)

        print(f"[{level}] {console_message}")