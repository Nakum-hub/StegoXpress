import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailSender:
    PROVIDERS = {
        "gmail": {"host": "smtp.gmail.com", "port": 587, "tls": True},
        "outlook": {"host": "smtp.outlook.com", "port": 587, "tls": True},
        "yahoo": {"host": "smtp.mail.yahoo.com", "port": 587, "tls": True},
        "custom": {"host": None, "port": None, "tls": True},
    }

    def __init__(self, provider: str, host: str = None, port: int = None):
        if provider not in self.PROVIDERS:
            raise ValueError("Unsupported email provider")

        if provider == "custom":
            if not host or port is None:
                raise ValueError("Custom SMTP provider requires host and port")
            self.host = host
            self.port = int(port)
            self.tls = True
        else:
            config = self.PROVIDERS[provider]
            self.host = config["host"]
            self.port = config["port"]
            self.tls = config["tls"]

        self.provider = provider

    def test_connection(self, username: str, password: str) -> bool:
        try:
            with self._open_server() as server:
                server.login(username, password)
            return True
        except smtplib.SMTPAuthenticationError:
            return False
        except (OSError, TimeoutError, smtplib.SMTPConnectError) as exc:
            raise ConnectionError(
                f"Could not connect to SMTP host {self.host}:{self.port}"
            ) from exc
        except smtplib.SMTPException:
            return False

    def send_stego_image(
        self,
        username: str,
        password: str,
        recipient: str,
        image_path: str,
        hint_message: str = "",
        subject: str = "",
    ) -> bool:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Stego image not found: {image_path}")

        try:
            message = self._build_message(username, recipient, image_path, hint_message, subject)

            with self._open_server() as server:
                server.login(username, password)
                server.send_message(message)

            return True
        except smtplib.SMTPAuthenticationError as exc:
            raise PermissionError(
                "SMTP authentication failed. Check the sender email and app password."
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise ValueError("Recipient address was refused by the SMTP server.") from exc
        except (OSError, TimeoutError, smtplib.SMTPConnectError) as exc:
            raise ConnectionError(
                f"Could not connect to SMTP host {self.host}:{self.port}"
            ) from exc
        except smtplib.SMTPException as exc:
            raise RuntimeError(f"Failed to send email: {exc}") from exc

    def _open_server(self):
        server = smtplib.SMTP(self.host, self.port, timeout=15)
        server.ehlo()
        if self.tls:
            # v2 hardening (audit V9): explicit, modern SSL context with
            # certificate verification and hostname checking enforced.
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            server.starttls(context=context)
            server.ehlo()
        return server

    def _build_message(
        self,
        username: str,
        recipient: str,
        image_path: str,
        hint_message: str,
        subject: str = "",
    ) -> EmailMessage:
        message = EmailMessage()
        message["From"] = username
        message["To"] = recipient
        # Default subject is deliberately generic — do not reveal the tool name.
        # The caller can supply a custom subject; empty string triggers the default.
        message["Subject"] = subject.strip() if subject.strip() else "Shared image"

        body = "Please find the attached image."
        if hint_message:
            body += f"\n\n{hint_message}"

        message.set_content(body)

        with open(image_path, "rb") as image_file:
            message.add_attachment(
                image_file.read(),
                maintype="image",
                subtype="png",
                filename=os.path.basename(image_path),
            )

        return message
