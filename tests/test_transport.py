import os
import smtplib
import types

import pytest
from PIL import Image

from transport.email_sender import EmailSender
from transport.key_manager import KeyManager


def test_password_strength_scores():
    assert KeyManager.validate_password_strength("short")["score"] == 0
    assert KeyManager.validate_password_strength("abcdefgh")["score"] == 1
    assert KeyManager.validate_password_strength("abcd1234")["score"] == 2
    assert KeyManager.validate_password_strength("Abcd1234!xyz")["score"] == 3
    assert KeyManager.validate_password_strength("Abcd1234!xyz5678")["score"] == 4


def test_generate_share_link_uses_hint_not_raw_key(monkeypatch):
    class FakeQR:
        def __init__(self, content):
            self.content = content

        def save(self, path):
            with open(path, "wb") as output:
                output.write(self.content.encode("utf-8"))

    fake_qrcode = types.SimpleNamespace(make=lambda content: FakeQR(content))
    monkeypatch.setitem(__import__("sys").modules, "qrcode", fake_qrcode)

    path = KeyManager.generate_share_link("shared phrase reminder")

    try:
        assert os.path.exists(path)
        with open(path, "rb") as qr_file:
            assert qr_file.read() == b"shared phrase reminder"
    finally:
        os.remove(path)


def test_email_message_contains_only_stego_transport_text(tmp_path):
    image_path = tmp_path / "stego.png"
    Image.new("RGB", (10, 10), "white").save(image_path, format="PNG")
    sender = EmailSender("custom", host="smtp.example.test", port=2525)

    message = sender._build_message(
        "sender@example.com",
        "recipient@example.com",
        str(image_path),
        "the hiking trip",
    )

    body = message.get_body(preferencelist=("plain",)).get_content()
    assert message["Subject"] == "StegoXpress — Secure Message"
    assert "hidden StegoXpress content" in body
    assert "agreed with the sender" in body
    assert "Hint: the hiking trip" in body
    assert "encryption key" not in body.lower()


def test_email_sender_connection_and_send(monkeypatch, tmp_path):
    calls = {"login": 0, "send": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def ehlo(self):
            return None

        def starttls(self):
            return None

        def login(self, username, password):
            calls["login"] += 1
            if password == "bad":
                raise smtplib.SMTPAuthenticationError(535, b"bad password")

        def send_message(self, message):
            calls["send"] += 1

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    image_path = tmp_path / "stego.png"
    Image.new("RGB", (10, 10), "white").save(image_path, format="PNG")
    sender = EmailSender("custom", host="smtp.example.test", port=2525)

    assert sender.test_connection("sender@example.com", "good") is True
    assert sender.test_connection("sender@example.com", "bad") is False
    assert sender.send_stego_image(
        "sender@example.com",
        "good",
        "recipient@example.com",
        str(image_path),
        "hint only",
    ) is True
    assert calls == {"login": 3, "send": 1}


def test_email_sender_unreachable_host(monkeypatch):
    class BrokenSMTP:
        def __init__(self, host, port, timeout):
            raise OSError("network unreachable")

    monkeypatch.setattr(smtplib, "SMTP", BrokenSMTP)
    sender = EmailSender("custom", host="smtp.example.test", port=2525)

    with pytest.raises(ConnectionError):
        sender.test_connection("sender@example.com", "password")
