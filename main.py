"""
StegoXpress — entry point.

Launches the GUI when called with no arguments; runs the CLI otherwise.

CLI commands
------------
  encode   Hide text or a file inside an image or audio file
  decode   Extract and decrypt hidden content
  version  Print version and exit

Env vars
--------
  STEGO_PASSWORD   Encode/decode password (avoids shell history exposure).
                   --password on the command line overrides this.

Exit codes
----------
  0  success
  1  wrong password / corrupt / tampered data
  2  payload too large for carrier
  3  file not found / I/O error
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

from PIL import Image

from core.audio_engine import AudioEngine
from core.crypto_engine import CryptoEngine
from core.file_packer import FilePacker
from core.lsb_engine import LSBEngine
from core.png_chunk_engine import PngChunkEngine
from core.vault_engine import VaultEngine
from core.shield_engine import ShieldEngine
from utils.logger import StegoLogger

__version__ = "2.1.0"

EXIT_SUCCESS = 0
EXIT_WRONG_PASSWORD = 1
EXIT_CAPACITY = 2
EXIT_FILE_NOT_FOUND = 3


# ── Argument parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stegoxpress",
        description="StegoXpress — encrypt-first steganography toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Password priority: --password flag > STEGO_PASSWORD env var\n"
            "Avoid --password in scripts — it appears in process listings.\n"
            "Use:  export STEGO_PASSWORD='your passphrase'  instead.\n\n"
            "Examples:\n"
            "  # Hide a message (env-var password)\n"
            "  export STEGO_PASSWORD='strong passphrase'\n"
            "  %(prog)s encode --image cover.png --text \"meet at noon\" --output secret.png\n\n"
            "  # Hide a file with tamper-proof seal\n"
            "  %(prog)s encode --image cover.png --file plans.pdf --seal --output secret.png\n\n"
            "  # Use adaptive LSB (hides in high-entropy regions)\n"
            "  %(prog)s encode --image photo.png --text \"secret\" --adaptive --output out.png\n\n"
            "  # Decode with seal verification\n"
            "  %(prog)s decode --image secret.png --verify-seal\n\n"
            "  # Machine-readable output\n"
            "  %(prog)s decode --image secret.png --json\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"StegoXpress {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    # ── encode ──
    enc = sub.add_parser("encode", help="Hide text or a file inside a carrier")
    carrier_enc = enc.add_argument_group("carrier")
    carrier_enc.add_argument(
        "--image", metavar="PATH",
        help="Cover image (PNG/JPG). Used for Image-LSB, Adaptive-LSB, and PNG-chunk carriers."
    )
    carrier_enc.add_argument(
        "--audio", metavar="PATH",
        help="Cover WAV audio file (16-bit PCM). Used for audio carrier."
    )
    carrier_enc.add_argument(
        "--carrier",
        choices=["image-lsb", "image-adaptive", "png-chunk", "audio"],
        default="image-lsb",
        help=(
            "Embedding method. Default: image-lsb.\n"
            "  image-lsb      Standard LSB in every pixel (max capacity)\n"
            "  image-adaptive Embed only in high-entropy pixel regions (lower detectability)\n"
            "  png-chunk      Store in a private PNG metadata chunk (pixels untouched)\n"
            "  audio          LSB of WAV audio samples (requires --audio)"
        ),
    )

    payload_enc = enc.add_argument_group("payload")
    payload_group = payload_enc.add_mutually_exclusive_group(required=True)
    payload_group.add_argument("--text", "--message", dest="message", metavar="TEXT",
                               help="Text message to hide")
    payload_group.add_argument("--file", metavar="PATH",
                               help="File to hide inside the carrier")

    sec_enc = enc.add_argument_group("security")
    sec_enc.add_argument("--password", metavar="PASS",
                         help="Encryption password. Prefer STEGO_PASSWORD env var.")
    sec_enc.add_argument("--seal", action="store_true",
                         help="Add an HMAC-SHA256 tamper-proof seal to the payload.")
    sec_enc.add_argument("--self-destruct", action="store_true",
                         help="Mark payload for local erasure after first decode.")

    out_enc = enc.add_argument_group("output")
    out_enc.add_argument("--output", "-o", required=True, metavar="PATH",
                         help="Output path for the stego carrier (PNG for images, WAV for audio).")
    out_enc.add_argument("--json", action="store_true", dest="json_out",
                         help="Emit machine-readable JSON instead of human-readable text.")

    # ── decode ──
    dec = sub.add_parser("decode", help="Extract hidden content from a carrier")
    carrier_dec = dec.add_argument_group("carrier")
    carrier_dec.add_argument("--image", metavar="PATH",
                             help="Stego image path (PNG/JPG). Required for image carriers.")
    carrier_dec.add_argument("--audio", metavar="PATH",
                             help="Stego WAV audio file. Required for audio carrier.")
    carrier_dec.add_argument(
        "--carrier",
        choices=["image-lsb", "image-adaptive", "png-chunk", "audio"],
        default="image-lsb",
        help="Must match the carrier used during encode. Default: image-lsb.",
    )

    sec_dec = dec.add_argument_group("security")
    sec_dec.add_argument("--password", metavar="PASS",
                         help="Decryption password. Prefer STEGO_PASSWORD env var.")
    sec_dec.add_argument("--verify-seal", action="store_true",
                         help="Verify the HMAC tamper-proof seal and abort if broken.")

    out_dec = dec.add_argument_group("output")
    out_dec.add_argument("--save-dir", metavar="DIR", default=".",
                         help="Directory to save extracted files. Default: current directory.")
    out_dec.add_argument("--json", action="store_true", dest="json_out",
                         help="Emit machine-readable JSON instead of human-readable text.")

    # ── version ──
    sub.add_parser("version", help="Print version and exit")

    return parser


# ── Password resolution ───────────────────────────────────────────────────────

def resolve_password(args_password: str | None) -> str | None:
    """Return password from CLI flag or STEGO_PASSWORD env var, in that order."""
    if args_password:
        return args_password
    return os.environ.get("STEGO_PASSWORD") or None


# ── Encode ───────────────────────────────────────────────────────────────────

def cli_encode(args) -> int:
    logger = StegoLogger.get()
    start = time.perf_counter()

    password = resolve_password(args.password)
    if not password:
        _emit(args, error="No password supplied. Use --password or set STEGO_PASSWORD.")
        return EXIT_WRONG_PASSWORD

    carrier = args.carrier

    # Validate carrier ↔ source file pairing
    if carrier == "audio":
        if not args.audio:
            _emit(args, error="--audio is required when using the audio carrier.")
            return EXIT_FILE_NOT_FOUND
        source_path = args.audio
    else:
        if not args.image:
            _emit(args, error="--image is required for image/png-chunk carriers.")
            return EXIT_FILE_NOT_FOUND
        source_path = args.image

    if not os.path.exists(source_path):
        _emit(args, error=f"Carrier file not found: {source_path}")
        return EXIT_FILE_NOT_FOUND

    if args.file and not os.path.exists(args.file):
        _emit(args, error=f"Payload file not found: {args.file}")
        return EXIT_FILE_NOT_FOUND

    try:
        # Build payload
        if args.seal and args.self_destruct:
            _emit(args, error="--seal and --self-destruct are mutually exclusive.")
            return EXIT_WRONG_PASSWORD

        if args.seal:
            payload = (
                FilePacker.pack_file_sealed(args.file, password)
                if args.file
                else FilePacker.pack_text_sealed(args.message, password)
            )
        elif args.self_destruct:
            payload = (
                FilePacker.pack_file_self_destruct(args.file)
                if args.file
                else FilePacker.pack_text_self_destruct(args.message)
            )
        else:
            payload = (
                FilePacker.pack_file(args.file)
                if args.file
                else FilePacker.pack_text(args.message)
            )

        payload_size = len(payload)
        encrypted = CryptoEngine.encrypt(payload, password)

        # Embed
        if carrier == "audio":
            AudioEngine.encode(source_path, encrypted, args.output)
            duration_ms = elapsed_ms(start)
            _emit(args, status="success", output=args.output,
                  payload_bytes=payload_size, carrier=carrier,
                  duration_ms=duration_ms)
            logger.info("operation=encode carrier=%s payload_size=%d success=True duration_ms=%.0f",
                        carrier, payload_size, duration_ms)
            return EXIT_SUCCESS

        if carrier == "png-chunk":
            PngChunkEngine.encode(source_path, encrypted, args.output)
            duration_ms = elapsed_ms(start)
            _emit(args, status="success", output=args.output,
                  payload_bytes=payload_size, carrier=carrier,
                  duration_ms=duration_ms)
            logger.info("operation=encode carrier=%s payload_size=%d success=True duration_ms=%.0f",
                        carrier, payload_size, duration_ms)
            return EXIT_SUCCESS

        with Image.open(source_path) as cover:
            image = cover.copy()

        if carrier == "image-adaptive":
            stego = LSBEngine.encode_adaptive(image, encrypted)
        else:
            stego = LSBEngine.encode(image, encrypted)

        stego.save(args.output, "PNG")
        duration_ms = elapsed_ms(start)
        _emit(args, status="success", output=args.output,
              payload_bytes=payload_size,
              image_dimensions=f"{image.width}x{image.height}",
              carrier=carrier,
              seal=args.seal,
              self_destruct=args.self_destruct,
              duration_ms=duration_ms)
        logger.info("operation=encode carrier=%s image=%dx%d payload_size=%d "
                    "seal=%s success=True duration_ms=%.0f",
                    carrier, image.width, image.height, payload_size,
                    args.seal, duration_ms)
        return EXIT_SUCCESS

    except ValueError as exc:
        duration_ms = elapsed_ms(start)
        reason = str(exc)
        _emit(args, error=reason, duration_ms=duration_ms)
        logger.warning("operation=encode success=False reason=%s duration_ms=%.0f", reason, duration_ms)
        if "too large" in reason.lower():
            return EXIT_CAPACITY
        return EXIT_WRONG_PASSWORD

    except (OSError, FileNotFoundError) as exc:
        duration_ms = elapsed_ms(start)
        _emit(args, error=str(exc), duration_ms=duration_ms)
        logger.warning("operation=encode success=False reason=%s", exc)
        return EXIT_FILE_NOT_FOUND


# ── Decode ───────────────────────────────────────────────────────────────────

def cli_decode(args) -> int:
    logger = StegoLogger.get()
    start = time.perf_counter()

    password = resolve_password(args.password)
    carrier = args.carrier

    # Validate source
    if carrier == "audio":
        if not args.audio:
            _emit(args, error="--audio is required when using the audio carrier.")
            return EXIT_FILE_NOT_FOUND
        source_path = args.audio
    else:
        if not args.image:
            _emit(args, error="--image is required for image/png-chunk carriers.")
            return EXIT_FILE_NOT_FOUND
        source_path = args.image

    if not os.path.exists(source_path):
        _emit(args, error=f"Carrier file not found: {source_path}")
        return EXIT_FILE_NOT_FOUND

    try:
        # Extract encrypted bytes
        if carrier == "audio":
            raw_encrypted = AudioEngine.decode(source_path)
        elif carrier == "png-chunk":
            raw_encrypted = PngChunkEngine.decode(source_path)
        else:
            with Image.open(source_path) as stego:
                image = stego.copy()
            if carrier == "image-adaptive":
                raw_encrypted = LSBEngine.decode_adaptive(image)
            else:
                raw_encrypted = LSBEngine.decode(image)

        if not password:
            _emit(args, error="No password supplied. Use --password or set STEGO_PASSWORD.")
            return EXIT_WRONG_PASSWORD

        decrypted = CryptoEngine.decrypt(raw_encrypted, password)
        duration_ms = elapsed_ms(start)

        # Handle seal verification
        if FilePacker.is_sealed(decrypted):
            if args.verify_seal:
                result = FilePacker.verify_and_unpack_sealed(decrypted, password)
                seal_status = "verified"
            else:
                result = FilePacker.unpack(decrypted)
                seal_status = "present (not verified — use --verify-seal)"
        else:
            if args.verify_seal:
                _emit(args, error="--verify-seal was requested but this payload has no seal.",
                      duration_ms=duration_ms)
                return EXIT_WRONG_PASSWORD
            result = FilePacker.unpack(decrypted)
            seal_status = "none"

        # Handle self-destruct
        if result.get("type") in ("self_destruct_text", "self_destruct_file"):
            if carrier not in ("audio", "png-chunk"):
                erased = LSBEngine.erase(image)
                erased.save(source_path, "PNG")
            logger.info("operation=self_destruct source=%s", source_path)

        payload_size = len(decrypted)

        if result["type"] in ("text", "sealed_text", "vault_outer", "vault_inner",
                               "self_destruct_text"):
            _emit(args, status="success", payload_bytes=payload_size,
                  content_type="text", text=result["text"],
                  seal=seal_status, carrier=carrier, duration_ms=duration_ms)
        else:
            output_path = unique_output_path(result["filename"], args.save_dir)
            with open(output_path, "wb") as f:
                f.write(result["data"])
            _emit(args, status="success", payload_bytes=payload_size,
                  content_type="file", filename=result["filename"],
                  saved=output_path, file_bytes=len(result["data"]),
                  seal=seal_status, carrier=carrier, duration_ms=duration_ms)

        logger.info("operation=decode carrier=%s payload_size=%d success=True duration_ms=%.0f",
                    carrier, payload_size, duration_ms)
        return EXIT_SUCCESS

    except ValueError as exc:
        duration_ms = elapsed_ms(start)
        reason = str(exc)
        _emit(args, error="Wrong password, corrupt data, or seal broken.",
              detail=reason, duration_ms=duration_ms)
        logger.warning("operation=decode success=False reason=%s duration_ms=%.0f", reason, duration_ms)
        return EXIT_WRONG_PASSWORD

    except (OSError, FileNotFoundError) as exc:
        duration_ms = elapsed_ms(start)
        _emit(args, error=str(exc), duration_ms=duration_ms)
        logger.warning("operation=decode success=False reason=%s", exc)
        return EXIT_FILE_NOT_FOUND


# ── Output helpers ────────────────────────────────────────────────────────────

def _emit(args, *, status: str = "failed", error: str = "", **fields) -> None:
    """Print either human-readable or JSON output, consistently."""
    if getattr(args, "json_out", False):
        data = {"status": status}
        if error:
            data["error"] = error
        data.update(fields)
        print(json.dumps(data, default=str))
        return

    if error:
        print(f"Status: failed")
        print(f"Error:  {error}")
        if "detail" in fields:
            print(f"Detail: {fields['detail']}")
        if "duration_ms" in fields:
            print(f"Duration ms: {fields['duration_ms']:.0f}")
        return

    print(f"Status: {status}")
    label_map = {
        "output": "Output",
        "payload_bytes": "Payload bytes",
        "image_dimensions": "Image dimensions",
        "carrier": "Carrier",
        "seal": "Seal",
        "self_destruct": "Self-destruct",
        "content_type": "Type",
        "text": "Text",
        "filename": "Filename",
        "saved": "Saved to",
        "file_bytes": "File bytes",
        "duration_ms": "Duration ms",
    }
    for key, label in label_map.items():
        if key in fields and fields[key] is not None:
            val = fields[key]
            if key == "duration_ms":
                print(f"{label}: {val:.0f}")
            else:
                print(f"{label}: {val}")


def unique_output_path(filename: str | None, directory: str = ".") -> str:
    safe_name = os.path.basename(filename or "stegoxpress_output.bin")
    candidate = os.path.abspath(os.path.join(directory, safe_name))
    stem, ext = os.path.splitext(candidate)
    index = 1
    while os.path.exists(candidate):
        candidate = f"{stem}_{index}{ext}"
        index += 1
    return candidate


def elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


# ── Dispatch ─────────────────────────────────────────────────────────────────

def run_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"StegoXpress {__version__}")
        return EXIT_SUCCESS
    if args.command == "encode":
        return cli_encode(args)
    if args.command == "decode":
        return cli_decode(args)

    parser.print_help()
    return EXIT_FILE_NOT_FOUND


def run_gui() -> None:
    import customtkinter

    from gui.app import StegoXpressApp

    customtkinter.set_appearance_mode("dark")
    root = customtkinter.CTk()
    StegoXpressApp(root)
    root.mainloop()


def main(argv: list[str] | None = None) -> int:
    """Entry point: CLI when arguments are given, GUI otherwise."""
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        return run_cli(argv)
    run_gui()
    return 0




# ═══════════════════════════════════════════════════════════════════════════
# VAULT  — dual-password hidden volumes
# ═══════════════════════════════════════════════════════════════════════════

def _add_vault_parser(sub):
    vault = sub.add_parser("vault", help="Dual-password hidden-volume steganography")
    vs = vault.add_subparsers(dest="vault_cmd", required=True)

    # vault encode
    ve = vs.add_parser("encode", help="Encode two independent payloads with different passwords")
    ve.add_argument("--image", required=True, metavar="PATH", help="Cover image (PNG)")
    ve.add_argument("--output", "-o", required=True, metavar="PATH")

    ve.add_argument("--decoy", metavar="TEXT", help="Decoy (outer zone) text message")
    ve.add_argument("--decoy-file", metavar="PATH", help="Decoy (outer zone) file")
    ve.add_argument("--outer-password", metavar="PASS",
                    help="Password for decoy zone. Env: STEGO_OUTER_PASSWORD")

    ve.add_argument("--real", metavar="TEXT", help="Real (inner zone) text message")
    ve.add_argument("--real-file", metavar="PATH", help="Real (inner zone) file")
    ve.add_argument("--real-password", metavar="PASS",
                    help="Password for real zone. Env: STEGO_REAL_PASSWORD")

    ve.add_argument("--json", action="store_true", dest="json_out")

    # vault decode
    vd = vs.add_parser("decode",
                        help="Decode: tries outer zone first, then inner. "
                             "Returns whichever the given password unlocks.")
    vd.add_argument("--image", required=True, metavar="PATH")
    vd.add_argument("--password", metavar="PASS",
                    help="Password to try. Env: STEGO_PASSWORD")
    vd.add_argument("--save-dir", metavar="DIR", default=".",
                    help="Directory for extracted files (default: .)")
    vd.add_argument("--json", action="store_true", dest="json_out")

    return vault


def cli_vault_encode(args) -> int:
    from core.file_packer import FilePacker
    from core.vault_engine import VaultEngine

    start = time.perf_counter()

    pw_outer = (args.outer_password
                or os.environ.get("STEGO_OUTER_PASSWORD")
                or os.environ.get("STEGO_PASSWORD"))
    pw_real = (args.real_password
               or os.environ.get("STEGO_REAL_PASSWORD"))

    if not pw_outer:
        _emit(args, error="No outer password. Use --outer-password or STEGO_OUTER_PASSWORD.")
        return EXIT_WRONG_PASSWORD
    if not pw_real:
        _emit(args, error="No real password. Use --real-password or STEGO_REAL_PASSWORD.")
        return EXIT_WRONG_PASSWORD
    if not os.path.exists(args.image):
        _emit(args, error=f"Cover image not found: {args.image}")
        return EXIT_FILE_NOT_FOUND

    try:
        if args.decoy_file:
            decoy_payload = FilePacker.pack_file(args.decoy_file)
        elif args.decoy:
            decoy_payload = FilePacker.pack_text(args.decoy)
        else:
            _emit(args, error="Provide either --decoy TEXT or --decoy-file PATH")
            return EXIT_WRONG_PASSWORD

        if args.real_file:
            real_payload = FilePacker.pack_file(args.real_file)
        elif args.real:
            real_payload = FilePacker.pack_text(args.real)
        else:
            _emit(args, error="Provide either --real TEXT or --real-file PATH")
            return EXIT_WRONG_PASSWORD

        with Image.open(args.image) as im:
            cover = im.copy()

        stego = VaultEngine.encode(cover, decoy_payload, real_payload, pw_outer, pw_real)
        stego.save(args.output, "PNG")
        dur = elapsed_ms(start)
        _emit(args, status="success", output=args.output,
              outer_bytes=len(decoy_payload), inner_bytes=len(real_payload),
              image_dimensions=f"{cover.width}x{cover.height}",
              duration_ms=dur)
        return EXIT_SUCCESS

    except (ValueError, OSError) as exc:
        _emit(args, error=str(exc), duration_ms=elapsed_ms(start))
        return EXIT_CAPACITY if "too large" in str(exc).lower() else EXIT_WRONG_PASSWORD


def cli_vault_decode(args) -> int:
    from core.crypto_engine import CryptoEngine
    from core.file_packer import FilePacker
    from core.vault_engine import VaultEngine

    start = time.perf_counter()
    password = resolve_password(args.password)
    if not password:
        _emit(args, error="No password. Use --password or STEGO_PASSWORD.")
        return EXIT_WRONG_PASSWORD
    if not os.path.exists(args.image):
        _emit(args, error=f"Image not found: {args.image}")
        return EXIT_FILE_NOT_FOUND

    with Image.open(args.image) as im:
        image = im.copy()

    # Try outer zone first (what an adversary would probe)
    for zone_name, decoder in [("outer", VaultEngine.decode_outer),
                                ("inner", VaultEngine.decode_inner)]:
        try:
            raw = decoder(image, password)
            result = FilePacker.unpack(raw)
            dur = elapsed_ms(start)
            if result["type"] in ("text", "sealed_text"):
                _emit(args, status="success", zone=zone_name,
                      content_type="text", text=result["text"], duration_ms=dur)
            else:
                out = unique_output_path(result["filename"], args.save_dir)
                with open(out, "wb") as f:
                    f.write(result["data"])
                _emit(args, status="success", zone=zone_name,
                      content_type="file", filename=result["filename"],
                      saved=out, duration_ms=dur)
            return EXIT_SUCCESS
        except ValueError:
            continue

    dur = elapsed_ms(start)
    _emit(args, error="Password did not unlock either vault zone.", duration_ms=dur)
    return EXIT_WRONG_PASSWORD


# ═══════════════════════════════════════════════════════════════════════════
# SHIELD  — N-of-K secret sharing across multiple carrier images
# ═══════════════════════════════════════════════════════════════════════════

def _add_shield_parser(sub):
    shield = sub.add_parser("shield", help="N-of-K secret sharing across multiple images")
    ss = shield.add_subparsers(dest="shield_cmd", required=True)

    # shield encode
    se = ss.add_parser("encode",
                       help="Split a secret across N cover images; any K reconstruct it")
    se.add_argument("--covers", required=True, nargs="+", metavar="PATH",
                    help="Cover images (must be exactly --shares N images)")
    se.add_argument("--shares", "-n", required=True, type=int, metavar="N",
                    help="Total number of shares")
    se.add_argument("--threshold", "-k", required=True, type=int, metavar="K",
                    help="Minimum shares needed to reconstruct")
    payload_g = se.add_mutually_exclusive_group(required=True)
    payload_g.add_argument("--text", "--message", dest="message", metavar="TEXT")
    payload_g.add_argument("--file", metavar="PATH")
    se.add_argument("--password", metavar="PASS",
                    help="Encryption password. Env: STEGO_PASSWORD")
    se.add_argument("--output-dir", metavar="DIR", default=".",
                    help="Directory for share output images (default: current dir)")
    se.add_argument("--output-prefix", metavar="PREFIX", default="shield_share",
                    help="Filename prefix for shares (default: shield_share)")
    se.add_argument("--json", action="store_true", dest="json_out")

    # shield decode
    sd = ss.add_parser("decode",
                       help="Reconstruct secret from K (or more) share images")
    sd.add_argument("--images", required=True, nargs="+", metavar="PATH",
                    help="Share images (provide at least K images)")
    sd.add_argument("--password", metavar="PASS",
                    help="Decryption password. Env: STEGO_PASSWORD")
    sd.add_argument("--save-dir", metavar="DIR", default=".",
                    help="Directory for extracted files (default: .)")
    sd.add_argument("--json", action="store_true", dest="json_out")

    return shield


def cli_shield_encode(args) -> int:
    from core.file_packer import FilePacker
    from core.shield_engine import ShieldEngine

    start = time.perf_counter()

    password = resolve_password(args.password)
    if not password:
        _emit(args, error="No password. Use --password or STEGO_PASSWORD.")
        return EXIT_WRONG_PASSWORD

    n, k = args.shares, args.threshold
    if k > n:
        _emit(args, error=f"Threshold ({k}) cannot exceed total shares ({n}).")
        return EXIT_WRONG_PASSWORD
    if len(args.covers) != n:
        _emit(args, error=f"Need exactly {n} cover images, got {len(args.covers)}.")
        return EXIT_FILE_NOT_FOUND

    for path in args.covers:
        if not os.path.exists(path):
            _emit(args, error=f"Cover image not found: {path}")
            return EXIT_FILE_NOT_FOUND

    if args.file and not os.path.exists(args.file):
        _emit(args, error=f"Payload file not found: {args.file}")
        return EXIT_FILE_NOT_FOUND

    try:
        payload = (FilePacker.pack_file(args.file) if args.file
                   else FilePacker.pack_text(args.message))

        covers = []
        for path in args.covers:
            with Image.open(path) as im:
                covers.append(im.copy())

        share_images = ShieldEngine.encode_shares(payload, covers, password, n, k)

        os.makedirs(args.output_dir, exist_ok=True)
        saved = []
        for i, img in enumerate(share_images, 1):
            out = os.path.join(args.output_dir, f"{args.output_prefix}_{i:02d}.png")
            img.save(out, "PNG")
            saved.append(out)

        dur = elapsed_ms(start)
        _emit(args, status="success", shares_created=n, threshold=k,
              outputs=saved, payload_bytes=len(payload), duration_ms=dur)
        return EXIT_SUCCESS

    except (ValueError, OSError) as exc:
        _emit(args, error=str(exc), duration_ms=elapsed_ms(start))
        return EXIT_CAPACITY if "too large" in str(exc).lower() else EXIT_WRONG_PASSWORD


def cli_shield_decode(args) -> int:
    from core.file_packer import FilePacker
    from core.shield_engine import ShieldEngine

    start = time.perf_counter()

    password = resolve_password(args.password)
    if not password:
        _emit(args, error="No password. Use --password or STEGO_PASSWORD.")
        return EXIT_WRONG_PASSWORD

    for path in args.images:
        if not os.path.exists(path):
            _emit(args, error=f"Share image not found: {path}")
            return EXIT_FILE_NOT_FOUND

    try:
        indexed = []
        for idx, path in enumerate(args.images):
            with Image.open(path) as im:
                indexed.append((idx, im.copy()))

        raw = ShieldEngine.decode_shares(indexed, password)
        result = FilePacker.unpack(raw)
        dur = elapsed_ms(start)

        if result["type"] in ("text", "sealed_text"):
            _emit(args, status="success", shares_used=len(args.images),
                  content_type="text", text=result["text"], duration_ms=dur)
        else:
            out = unique_output_path(result["filename"], args.save_dir)
            with open(out, "wb") as f:
                f.write(result["data"])
            _emit(args, status="success", shares_used=len(args.images),
                  content_type="file", filename=result["filename"],
                  saved=out, file_bytes=len(result["data"]), duration_ms=dur)
        return EXIT_SUCCESS

    except (ValueError, OSError) as exc:
        _emit(args, error=str(exc), duration_ms=elapsed_ms(start))
        return EXIT_WRONG_PASSWORD


# ═══════════════════════════════════════════════════════════════════════════
# INFO  — carrier capacity and format summary
# ═══════════════════════════════════════════════════════════════════════════

def _add_info_parser(sub):
    info = sub.add_parser("info",
                          help="Show capacity and format details for a carrier file")
    info.add_argument("--image", metavar="PATH", help="Image file to inspect")
    info.add_argument("--audio", metavar="PATH", help="WAV audio file to inspect")
    info.add_argument("--json", action="store_true", dest="json_out")
    return info


def cli_info(args) -> int:
    import wave
    from core.crypto_engine import CryptoEngine
    from core.lsb_engine import LSBEngine
    from core.vault_engine import VaultEngine

    source = args.image or args.audio
    if not source:
        _emit(args, error="Provide --image or --audio.")
        return EXIT_FILE_NOT_FOUND
    if not os.path.exists(source):
        _emit(args, error=f"File not found: {source}")
        return EXIT_FILE_NOT_FOUND

    if args.audio:
        try:
            with wave.open(args.audio, "rb") as w:
                channels = w.getnchannels()
                sampwidth = w.getsampwidth()
                rate = w.getframerate()
                nframes = w.getnframes()
            duration_s = nframes / rate
            lsb_cap = (nframes * channels) // 8 - 4
            _emit_info(args, dict(
                file=args.audio,
                format="WAV",
                channels=channels,
                sample_width_bytes=sampwidth,
                sample_rate_hz=rate,
                frames=nframes,
                duration_seconds=round(duration_s, 2),
                carrier_audio_lsb_capacity_bytes=max(0, lsb_cap),
                carrier_audio_lsb_capacity_human=_fmt_bytes(max(0, lsb_cap)),
                kdf_default="Argon2id" if CryptoEngine.argon2_available() else "PBKDF2-600k",
            ))
            return EXIT_SUCCESS
        except (wave.Error, OSError) as exc:
            _emit(args, error=str(exc))
            return EXIT_FILE_NOT_FOUND

    try:
        with Image.open(args.image) as im:
            fmt = im.format or "unknown"
            w, h = im.size
            mode = im.mode
            rgb = im.convert("RGB")   # do all work inside the 'with' block

        cap_lsb = LSBEngine.capacity_bytes(rgb)
        cap_adaptive_est = int(cap_lsb * 0.55)  # ~55% capacity when entropy-filtered
        cap_vault_outer = VaultEngine.capacity_outer_bytes(rgb)
        cap_vault_inner = VaultEngine.capacity_inner_bytes(rgb)

        _emit_info(args, dict(
            file=args.image,
            format=fmt,
            mode=mode,
            width=w,
            height=h,
            pixels=w * h,
            carrier_lsb_capacity_bytes=cap_lsb,
            carrier_lsb_capacity_human=_fmt_bytes(cap_lsb),
            carrier_adaptive_capacity_approx_bytes=cap_adaptive_est,
            carrier_adaptive_capacity_approx_human=_fmt_bytes(cap_adaptive_est),
            carrier_vault_outer_bytes=cap_vault_outer,
            carrier_vault_outer_human=_fmt_bytes(cap_vault_outer),
            carrier_vault_inner_bytes=cap_vault_inner,
            carrier_vault_inner_human=_fmt_bytes(cap_vault_inner),
            kdf_default="Argon2id" if CryptoEngine.argon2_available() else "PBKDF2-600k",
            argon2_available=CryptoEngine.argon2_available(),
        ))
        return EXIT_SUCCESS
    except (OSError, Exception) as exc:
        _emit(args, error=str(exc))
        return EXIT_FILE_NOT_FOUND


def _emit_info(args, data: dict) -> None:
    if getattr(args, "json_out", False):
        print(json.dumps(data, default=str))
        return
    for key, val in data.items():
        label = key.replace("_", " ").capitalize()
        print(f"{label}: {val}")


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.2f} MB"


# ═══════════════════════════════════════════════════════════════════════════
# HEATMAP  — visualize entropy distribution
# ═══════════════════════════════════════════════════════════════════════════

def _add_heatmap_parser(sub):
    hm = sub.add_parser("heatmap",
                         help="Generate entropy heatmap showing where data can safely hide")
    hm.add_argument("--image", required=True, metavar="PATH")
    hm.add_argument("--output", "-o", required=True, metavar="PATH",
                    help="Output PNG path for the heatmap")
    hm.add_argument("--json", action="store_true", dest="json_out")
    return hm


def cli_heatmap(args) -> int:
    from core.lsb_engine import LSBEngine

    start = time.perf_counter()
    if not os.path.exists(args.image):
        _emit(args, error=f"Image not found: {args.image}")
        return EXIT_FILE_NOT_FOUND

    try:
        with Image.open(args.image) as im:
            image = im.convert("RGB")

        heatmap = LSBEngine.generate_heatmap(image)
        heatmap.save(args.output, "PNG")
        dur = elapsed_ms(start)
        _emit(args, status="success", output=args.output,
              width=image.width, height=image.height, duration_ms=dur)
        return EXIT_SUCCESS

    except (OSError, ValueError) as exc:
        _emit(args, error=str(exc), duration_ms=elapsed_ms(start))
        return EXIT_FILE_NOT_FOUND


# ═══════════════════════════════════════════════════════════════════════════
# STEGANALYSIS  — compare original vs suspected stego image
# ═══════════════════════════════════════════════════════════════════════════

def _add_steganalysis_parser(sub):
    sa = sub.add_parser("steganalysis",
                        help="Score how detectable a stego image is vs the original")
    sa.add_argument("--original", required=True, metavar="PATH",
                    help="The clean original image before embedding")
    sa.add_argument("--stego", required=True, metavar="PATH",
                    help="The stego image to analyze")
    sa.add_argument("--json", action="store_true", dest="json_out")
    return sa


_STEG_SCORE_LABELS = [
    (0.10, "Excellent — statistically indistinguishable from original"),
    (0.25, "Good     — minor statistical differences, unlikely to raise suspicion"),
    (0.40, "Fair     — detectable by automated tools; consider adaptive carrier or PNG-chunk"),
    (0.60, "Poor     — clearly modified; use a higher-entropy image or reduce payload"),
    (1.01, "High risk — stego image is easily detectable; do not use"),
]


def cli_steganalysis(args) -> int:
    from core.lsb_engine import LSBEngine

    start = time.perf_counter()

    for path in (args.original, args.stego):
        if not os.path.exists(path):
            _emit(args, error=f"File not found: {path}")
            return EXIT_FILE_NOT_FOUND

    try:
        with Image.open(args.original) as im:
            original = im.convert("RGB")
        with Image.open(args.stego) as im:
            stego = im.convert("RGB")

        score = LSBEngine.steganalysis_score(original, stego)
        label = next(lbl for threshold, lbl in _STEG_SCORE_LABELS if score <= threshold)
        dur = elapsed_ms(start)

        if getattr(args, "json_out", False):
            print(json.dumps(dict(
                status="success",
                score=round(score, 4),
                rating=label.strip(),
                duration_ms=round(dur, 1),
            )))
        else:
            print(f"Status:   success")
            print(f"Score:    {score:.4f}  (0.0 = identical, 1.0 = maximally detectable)")
            print(f"Rating:   {label.strip()}")
            print(f"Duration: {dur:.0f} ms")
            print()
            print("Tip: Run  stegoxpress heatmap --image <original>  to see high-entropy "
                  "regions where data hides best, then re-encode with --carrier image-adaptive.")

        return EXIT_SUCCESS

    except (ValueError, OSError) as exc:
        _emit(args, error=str(exc), duration_ms=elapsed_ms(start))
        return EXIT_WRONG_PASSWORD



# ═══════════════════════════════════════════════════════════════════════════
# Full dispatcher — wraps build_parser() and routes all subcommands
# ═══════════════════════════════════════════════════════════════════════════

def _find_subparsers(parser: argparse.ArgumentParser):
    """Reliably retrieve the _SubParsersAction from any ArgumentParser."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            return action
    raise RuntimeError("No subparsers action found in parser")


def run_cli(argv: list[str]) -> int:  # noqa: F811 — intentional redefinition
    """
    Extended CLI dispatcher.
    Builds the base parser then appends vault/shield/info/heatmap/steganalysis.
    """
    parser = build_parser()           # encode, decode, version
    sub = _find_subparsers(parser)    # reliably retrieve _SubParsersAction
    _add_vault_parser(sub)
    _add_shield_parser(sub)
    _add_info_parser(sub)
    _add_heatmap_parser(sub)
    _add_steganalysis_parser(sub)

    args = parser.parse_args(argv)
    cmd = args.command

    if cmd == "version":
        print(f"StegoXpress {__version__}")
        return EXIT_SUCCESS
    if cmd == "encode":
        return cli_encode(args)
    if cmd == "decode":
        return cli_decode(args)
    if cmd == "vault":
        return cli_vault_encode(args) if args.vault_cmd == "encode" else cli_vault_decode(args)
    if cmd == "shield":
        return cli_shield_encode(args) if args.shield_cmd == "encode" else cli_shield_decode(args)
    if cmd == "info":
        return cli_info(args)
    if cmd == "heatmap":
        return cli_heatmap(args)
    if cmd == "steganalysis":
        return cli_steganalysis(args)

    parser.print_help()
    return EXIT_FILE_NOT_FOUND

if __name__ == "__main__":
    sys.exit(main())
