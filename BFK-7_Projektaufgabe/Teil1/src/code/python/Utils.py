import logging
import logging.handlers
import smtplib
from email.mime.text import MIMEText
import sqlite3
from datetime import datetime


def get_logger(thread_name: str, file_name: str) -> logging.Logger:
    # Create a custom logger
    logger = logging.getLogger(thread_name)

    # Set level of logger
    logger.setLevel(logging.INFO)

    # Create handlers
    central_handler = logging.handlers.RotatingFileHandler(file_name, maxBytes=10240000, encoding="UTF-8", backupCount=10)
    stream_handler = logging.StreamHandler()

    # Create a formatter
    formatter = logging.Formatter('[(%(asctime)s) (%(name)s) (thread=%(thread)-6s) (%(filename)s:%(lineno)d) |-%(levelname)s] %(message)s', "%d.%m.%Y - %H:%M:%S")

    # Set formatter for each handler
    central_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(central_handler)
    logger.addHandler(stream_handler)

    return logger


class Notifier:

    def __init__(self, sender_address, sender_passwd, receiver_address, log_file_path, **kwargs):
        self.log = get_logger(self.__class__.__name__, log_file_path)
        self.sender_email_address = sender_address
        self.sender_email_passwd = sender_passwd
        self.receiver_email_address = receiver_address
        self.server_port = kwargs.get("port", 587)
        self.server_url = kwargs.get("server", "smtp.gmail.com")

    def send_email(self, **kwargs):
        # default subject and message if not provided
        subject = kwargs.get("subject", "Cistern Notification (Automation)")
        message_body = kwargs.get("message", "Look after your Water!")
        self.log.info(f"Sending email to {self.receiver_email_address} >>> {message_body.splitlines()}")

        # create a plain text email message
        msg = MIMEText(message_body)  # MIMEText is used for plain text messages
        msg["From"] = self.sender_email_address
        msg["To"] = self.receiver_email_address
        msg["Subject"] = subject

        try:
            # connect to the Gmail SMTP server using `with ... as` for proper resource handling
            with smtplib.SMTP(self.server_url, self.server_port) as server:
                server.starttls()  # Start a secure connection with TLS encryption
                server.login(self.sender_email_address, self.sender_email_passwd)  # Login to the email account
                server.sendmail(self.sender_email_address, self.receiver_email_address, msg.as_string())  # Send the email
        except Exception as e:
            self.log.error(f"Could not send email to {self.receiver_email_address} due to '{e}'")
            return

        # log that the email was sent successfully
        self.log.info("Email sent successfully.")


class DatabaseManager:
    def __init__(self, db_name: str, log_file_path: str, table_name: str):
        self.db_name = db_name
        self.table_name = table_name
        self.log = get_logger(self.__class__.__name__, log_file_path)
        self._initialize_database()

    def _initialize_database(self):
        """Create the database and table if they do not exist."""
        self.log.info(f"Initializing the database with table '{self.table_name}'.")
        self.execute(f'''
           CREATE TABLE IF NOT EXISTS {self.table_name} (
               id INTEGER PRIMARY KEY,
               level TEXT,
               timestamp TEXT
           )
       ''', commit=True)

    def execute(self, sql: str, params: tuple = (), commit: bool = False):
        """Execute a SQL query with optional parameters."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        if commit:
            conn.commit()
            self.log.info(f"Executed SQL with commit: {[x.strip() for x in sql.splitlines()]}")
        else:
            self.log.info(f"Executed SQL: {[x.strip() for x in sql.strip().splitlines()]}")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def add_entry(self, level: str):
        """Add a new measurement entry."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            f"INSERT INTO {self.table_name} (level, timestamp) VALUES (?, ?)",
            (level, timestamp),
            commit=True
        )
        self.log.info(f"Added entry: {level} at {timestamp}")

    def read_all_entries(self):
        """Read all measurement entries."""
        rows = self.execute(f"SELECT * FROM {self.table_name}")
        self.log.info(f"Read {len(rows)} entries from the database.")
        return rows

    def read_last_entries(self, count: int):
        """Read the last N measurement entries."""
        rows = self.execute(f"SELECT * FROM {self.table_name} ORDER BY id DESC LIMIT ?", (count,))
        self.log.info(f"Read the last {count} entries.")
        return rows

    def delete_all_entries(self):
        """Delete all measurement entries."""
        self.execute(f"DELETE FROM {self.table_name}", commit=True)
        self.log.info("All entries deleted from the database.")

    def delete_entries_by_level(self, level: str):
        """Delete entries for a specific level."""
        self.execute(f"DELETE FROM {self.table_name} WHERE level = ?", (level,), commit=True)
        self.log.warning(f"Deleted all entries with level: {level}")

    def count_entries_by_level(self):
        """Count the number of entries per level."""
        rows = self.execute(f"SELECT level, COUNT(*) FROM {self.table_name} GROUP BY level")
        self.log.info("Counted entries by level.")
        return rows
