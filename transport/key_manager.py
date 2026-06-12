"""
KeyManager — password strength scoring and secure share tokens.

v2 changes (fixes audit finding V1 — CRITICAL):
- REMOVED generate_share_link(), which QR-encoded the RAW PASSWORD and wrote it
  to a temp file with delete=False, leaving the cleartext secret on disk forever.
- Added generate_one_time_token(): returns a high-entropy random token that is
  NOT the password. The token can be exchanged out-of-band; the password is
  never serialized, logged, or written to disk by this module.
"""
import secrets
import string


class KeyManager:
    # ── Secure sharing ──
    @staticmethod
    def generate_one_time_token(num_bytes: int = 24) -> str:
        """
        Generate a URL-safe, single-use token to coordinate a secret exchange.

        This token is independent of the user's password. Share it through a
        separate channel from the stego image. The password itself is NEVER
        encoded, persisted, or transmitted by StegoXpress.
        """
        return secrets.token_urlsafe(num_bytes)

    @staticmethod
    def make_token_qr(token: str, output_path: str) -> str:
        """
        Optionally render a QR for a NON-SECRET token (never the password).
        Requires the optional `qrcode` dependency. Raises if a password-like
        value is passed by mistake is the caller's responsibility — only pass
        tokens from generate_one_time_token().
        """
        try:
            import qrcode
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "QR support requires the optional 'qrcode' package: pip install qrcode[pil]"
            ) from exc
        qrcode.make(token).save(output_path)
        return output_path

    # ── Password strength ──
    @staticmethod
    def validate_password_strength(password: str) -> dict:
        length = len(password)
        class_count = KeyManager._character_class_count(password)
        suggestions = []

        if length < 8:
            score = 0
            suggestions.append("Use at least 8 characters.")
        elif 8 <= length <= 11 and class_count == 1:
            score = 1
        elif length >= 16 and class_count == 4:
            score = 4
        elif length >= 12 and class_count >= 3:
            score = 3
        elif length >= 8 and class_count >= 2:
            score = 2
        else:
            score = 1

        if length < 12:
            suggestions.append("Use 12 or more characters for stronger protection.")
        if length < 16:
            suggestions.append("Use 16 or more characters for the strongest score.")
        if not any(char.isupper() for char in password):
            suggestions.append("Add an uppercase letter.")
        if not any(char.islower() for char in password):
            suggestions.append("Add a lowercase letter.")
        if not any(char.isdigit() for char in password):
            suggestions.append("Add a number.")
        if not any(char in string.punctuation for char in password):
            suggestions.append("Add a symbol.")

        labels = {0: "Weak", 1: "Fair", 2: "Good", 3: "Strong", 4: "Strong"}
        return {"score": score, "label": labels[score], "suggestions": suggestions}

    @staticmethod
    def _character_class_count(password: str) -> int:
        classes = [
            any(char.isupper() for char in password),
            any(char.islower() for char in password),
            any(char.isdigit() for char in password),
            any(char in string.punctuation for char in password),
        ]
        return sum(classes)
