import string
import tempfile


class KeyManager:
    @staticmethod
    def generate_share_link(password: str, expiry_hours: int = 24) -> str:
        import qrcode

        _ = expiry_hours
        password_hint = password
        qr_image = qrcode.make(password_hint)
        handle = tempfile.NamedTemporaryFile(
            prefix="stegoxpress_hint_",
            suffix=".png",
            delete=False,
        )
        handle.close()
        qr_image.save(handle.name)
        return handle.name

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

        labels = {
            0: "Weak",
            1: "Fair",
            2: "Good",
            3: "Strong",
            4: "Strong",
        }
        return {
            "score": score,
            "label": labels[score],
            "suggestions": suggestions,
        }

    @staticmethod
    def _character_class_count(password: str) -> int:
        classes = [
            any(char.isupper() for char in password),
            any(char.islower() for char in password),
            any(char.isdigit() for char in password),
            any(char in string.punctuation for char in password),
        ]
        return sum(classes)
