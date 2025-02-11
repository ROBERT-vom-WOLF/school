import logging
import logging.handlers
import smtplib
from email.mime.text import MIMEText


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

    def __init__(self, sender_address, sender_passwd, receiver_address, log_file_path):
        self.log = get_logger(Notifier.__name__, log_file_path)
        self.sender_email_address = sender_address
        self.sender_email_passwd = sender_passwd
        self.receiver_email_address = receiver_address

    def send_email(self, **kwargs):
        # default subject and message if not provided
        subject = kwargs.get("subject", "Cistern Notification (Automation)")
        message_body = kwargs.get("message", "Look after your Cistern!")
        self.log.info(f"Sending email to {self.receiver_email_address} >>> {message_body.splitlines()}")

        # create a plain text email message
        msg = MIMEText(message_body)  # MIMEText is used for plain text messages
        msg["From"] = self.sender_email_address
        msg["To"] = self.receiver_email_address
        msg["Subject"] = subject

        try:
            # connect to the Gmail SMTP server using `with ... as` for proper resource handling
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()  # Start a secure connection with TLS encryption
                server.login(self.sender_email_address, self.sender_email_passwd)  # Login to the email account
                server.sendmail(self.sender_email_address, self.receiver_email_address, msg.as_string())  # Send the email
        except Exception as e:
            self.log.error(f"Could not send email to {self.receiver_email_address} due to '{e}'")
            return

        # log that the email was sent successfully
        self.log.info("Email sent successfully.")
