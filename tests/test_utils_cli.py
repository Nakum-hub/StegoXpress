import json

from PIL import Image

from main import (
    EXIT_CAPACITY,
    EXIT_FILE_NOT_FOUND,
    EXIT_SUCCESS,
    EXIT_WRONG_PASSWORD,
    run_cli,
)
from utils.config import Config
from utils.logger import StegoLogger


def test_config_persists_and_resets(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(Config, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(Config, "_settings", None)

    Config.set("default_provider", "outlook")
    assert Config.get("default_provider") == "outlook"

    with open(Config.CONFIG_PATH, "r", encoding="utf-8") as config_file:
        saved = json.load(config_file)
    assert saved["default_provider"] == "outlook"

    Config.reset()
    assert Config.get("default_provider") == "gmail"


def test_logger_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr("utils.logger.Path.home", lambda: tmp_path)
    StegoLogger._logger = None

    logger = StegoLogger.get()
    logger.info("operation=test event=logger-check")

    log_path = tmp_path / ".stegoxpress" / "logs" / "stegoxpress.log"
    assert log_path.exists()
    assert "operation=test" in log_path.read_text(encoding="utf-8")


def test_cli_text_roundtrip(tmp_path):
    cover = tmp_path / "cover.png"
    output = tmp_path / "out.png"
    Image.new("RGB", (120, 120), "white").save(cover)

    encode_code = run_cli(
        [
            "encode",
            "--image",
            str(cover),
            "--message",
            "secret text",
            "--password",
            "mypassword",
            "--output",
            str(output),
        ]
    )
    assert encode_code == EXIT_SUCCESS
    assert output.exists()

    decode_code = run_cli(
        [
            "decode",
            "--image",
            str(output),
            "--password",
            "mypassword",
        ]
    )
    assert decode_code == EXIT_SUCCESS


def test_cli_wrong_password(tmp_path):
    cover = tmp_path / "cover.png"
    output = tmp_path / "out.png"
    Image.new("RGB", (120, 120), "white").save(cover)

    assert run_cli(
        [
            "encode",
            "--image",
            str(cover),
            "--message",
            "secret text",
            "--password",
            "mypassword",
            "--output",
            str(output),
        ]
    ) == EXIT_SUCCESS

    assert run_cli(
        [
            "decode",
            "--image",
            str(output),
            "--password",
            "wrongpassword",
        ]
    ) == EXIT_WRONG_PASSWORD


def test_cli_capacity_and_missing_file(tmp_path):
    tiny = tmp_path / "tiny.png"
    Image.new("RGB", (10, 10), "white").save(tiny)

    assert run_cli(
        [
            "encode",
            "--image",
            str(tiny),
            "--message",
            "x" * 10000,
            "--password",
            "mypassword",
            "--output",
            str(tmp_path / "out.png"),
        ]
    ) == EXIT_CAPACITY

    assert run_cli(
        [
            "encode",
            "--image",
            str(tmp_path / "missing.png"),
            "--message",
            "secret",
            "--password",
            "mypassword",
            "--output",
            str(tmp_path / "out.png"),
        ]
    ) == EXIT_FILE_NOT_FOUND
