import argparse
import os
import sys
import time
from datetime import datetime

from PIL import Image

from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.lsb_engine import LSBEngine
from utils.logger import StegoLogger


EXIT_SUCCESS = 0
EXIT_WRONG_PASSWORD = 1
EXIT_CAPACITY = 2
EXIT_FILE_NOT_FOUND = 3


def build_parser():
    parser = argparse.ArgumentParser(description="StegoXpress CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode = subparsers.add_parser("encode", help="Hide text or a file inside an image")
    encode.add_argument("--image", required=True, help="Cover image path")
    payload = encode.add_mutually_exclusive_group(required=True)
    payload.add_argument("--message", help="Text message to hide")
    payload.add_argument("--file", help="File to hide")
    encode.add_argument("--password", required=True, help="Decode password")
    encode.add_argument("--output", required=True, help="Output PNG path")

    decode = subparsers.add_parser("decode", help="Extract hidden content from an image")
    decode.add_argument("--image", required=True, help="Stego image path")
    decode.add_argument("--password", required=True, help="Decode password")

    return parser


def run_cli(argv):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "encode":
        return cli_encode(args)
    if args.command == "decode":
        return cli_decode(args)

    parser.print_help()
    return EXIT_FILE_NOT_FOUND


def cli_encode(args):
    logger = StegoLogger.get()
    start = time.perf_counter()
    image = None
    payload_size = 0

    try:
        if not os.path.exists(args.image):
            print(f"Status: failed\nReason: image not found: {args.image}")
            return EXIT_FILE_NOT_FOUND
        if args.file and not os.path.exists(args.file):
            print(f"Status: failed\nReason: file not found: {args.file}")
            return EXIT_FILE_NOT_FOUND

        with Image.open(args.image) as cover:
            image = cover.copy()

        payload = (
            FilePacker.pack_file(args.file)
            if args.file
            else FilePacker.pack_text(args.message)
        )
        payload_size = len(payload)
        encrypted = CryptoEngine.encrypt(payload, args.password)
        stego_image = LSBEngine.encode(image, encrypted)
        stego_image.save(args.output, "PNG")
        duration_ms = elapsed_ms(start)
        log_operation(logger, "encode", image, payload_size, True, "", duration_ms)

        print("Status: success")
        print(f"Output: {args.output}")
        print(f"Payload bytes: {payload_size}")
        print(f"Image dimensions: {image.width}x{image.height}")
        print(f"Duration ms: {duration_ms:.0f}")
        return EXIT_SUCCESS

    except ValueError as exc:
        duration_ms = elapsed_ms(start)
        reason = str(exc)
        log_operation(logger, "encode", image, payload_size, False, reason, duration_ms)
        if "Payload too large" in reason:
            print("Status: failed")
            print(f"Reason: {reason}")
            return EXIT_CAPACITY
        print("Status: failed")
        print(f"Reason: {reason}")
        return EXIT_WRONG_PASSWORD
    except FileNotFoundError as exc:
        duration_ms = elapsed_ms(start)
        log_operation(logger, "encode", image, payload_size, False, str(exc), duration_ms)
        print("Status: failed")
        print(f"Reason: {exc}")
        return EXIT_FILE_NOT_FOUND
    except OSError as exc:
        duration_ms = elapsed_ms(start)
        log_operation(logger, "encode", image, payload_size, False, str(exc), duration_ms)
        print("Status: failed")
        print(f"Reason: {exc}")
        return EXIT_FILE_NOT_FOUND


def cli_decode(args):
    logger = StegoLogger.get()
    start = time.perf_counter()
    image = None
    payload_size = 0

    try:
        if not os.path.exists(args.image):
            print(f"Status: failed\nReason: image not found: {args.image}")
            return EXIT_FILE_NOT_FOUND

        with Image.open(args.image) as stego:
            image = stego.copy()

        raw_encrypted = LSBEngine.decode(image)
        decrypted = CryptoEngine.decrypt(raw_encrypted, args.password)
        payload_size = len(decrypted)
        result = FilePacker.unpack(decrypted)
        duration_ms = elapsed_ms(start)
        log_operation(logger, "decode", image, payload_size, True, "", duration_ms)

        print("Status: success")
        print(f"Image: {args.image}")
        print(f"Payload bytes: {payload_size}")
        print(f"Duration ms: {duration_ms:.0f}")

        if result["type"] == "text":
            print("Type: text")
            print(f"Text: {result['text']}")
        else:
            output_path = unique_output_path(result["filename"])
            with open(output_path, "wb") as output_file:
                output_file.write(result["data"])
            print("Type: file")
            print(f"Filename: {result['filename']}")
            print(f"Saved: {output_path}")
            print(f"Bytes: {len(result['data'])}")

        return EXIT_SUCCESS

    except ValueError as exc:
        duration_ms = elapsed_ms(start)
        reason = str(exc)
        log_operation(logger, "decode", image, payload_size, False, reason, duration_ms)
        print("Status: failed")
        print("Reason: wrong password or image is not a StegoXpress image")
        return EXIT_WRONG_PASSWORD
    except FileNotFoundError as exc:
        duration_ms = elapsed_ms(start)
        log_operation(logger, "decode", image, payload_size, False, str(exc), duration_ms)
        print("Status: failed")
        print(f"Reason: {exc}")
        return EXIT_FILE_NOT_FOUND
    except OSError as exc:
        duration_ms = elapsed_ms(start)
        log_operation(logger, "decode", image, payload_size, False, str(exc), duration_ms)
        print("Status: failed")
        print(f"Reason: {exc}")
        return EXIT_FILE_NOT_FOUND


def unique_output_path(filename):
    safe_name = os.path.basename(filename or "stegoxpress_output.bin")
    candidate = os.path.abspath(safe_name)
    stem, extension = os.path.splitext(candidate)
    index = 1

    while os.path.exists(candidate):
        candidate = f"{stem}_{index}{extension}"
        index += 1

    return candidate


def elapsed_ms(start):
    return (time.perf_counter() - start) * 1000


def log_operation(logger, operation, image, payload_size, success, reason, duration_ms):
    dimensions = f"{image.width}x{image.height}" if image is not None else "unknown"
    logger.info(
        "operation=%s timestamp=%s image_dimensions=%s payload_size=%s "
        "success=%s reason=%s duration_ms=%.0f",
        operation,
        datetime.now().isoformat(timespec="seconds"),
        dimensions,
        payload_size,
        success,
        reason or "-",
        duration_ms,
    )


def run_gui():
    import customtkinter
    from gui.app import StegoXpressApp

    customtkinter.set_appearance_mode("dark")
    root = customtkinter.CTk()
    app = StegoXpressApp(root)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(run_cli(sys.argv[1:]))

    run_gui()
