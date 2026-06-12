import customtkinter as ctk
from PIL import Image

COLORS = {
    "background": "#080c10",
    "surface": "#0e1318",
    "card": "#141b22",
    "accent": "#00ffe5",
    "accent_dim": "#00ccb8",
    "text_primary": "#e8e8e8",
    "text_muted": "#888888",
    "error": "#ff5252",
    "warning": "#ffab40",
    "border": "#1e2d3d",
}


def inter(size=13, weight="normal"):
    return ctk.CTkFont(family="Inter", size=size, weight=weight)


def mono(size=12, weight="normal"):
    return ctk.CTkFont(family="JetBrains Mono", size=size, weight=weight)


def format_bytes(size):
    value = float(size)
    units = ["B", "KB", "MB", "GB"]

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{value:.2f} GB"


class ImagePreview(ctk.CTkLabel):
    def __init__(self, parent, size=280):
        super().__init__(
            parent,
            width=size,
            height=size,
            text="Drop image here",
            fg_color=COLORS["surface"],
            text_color=COLORS["text_muted"],
            corner_radius=8,
            font=inter(13),
        )
        self.size = size
        self._image_ref = None
        self.grid_propagate(False)

    def set_image(self, image: Image.Image | None):
        if image is None:
            self._image_ref = None
            self.configure(image=None, text="Drop image here")
            return

        preview = image.copy()
        preview.thumbnail((self.size - 10, self.size - 10))
        self._image_ref = ctk.CTkImage(
            light_image=preview,
            dark_image=preview,
            size=preview.size,
        )
        self.configure(image=self._image_ref, text="")


class CapacityBar(ctk.CTkFrame):
    def __init__(self, parent, width=400):
        super().__init__(parent, fg_color="transparent")
        self.total_bytes = 0
        self.used_bytes = 0
        self.bar = ctk.CTkProgressBar(
            self,
            width=width,
            height=10,
            fg_color=COLORS["border"],
            progress_color=COLORS["accent"],
            corner_radius=6,
        )
        self.bar.grid(row=0, column=0, sticky="ew")
        self.bar.set(0)

        self.text = ctk.CTkLabel(
            self,
            text="0.0 KB used / 0.0 KB available (0.0%)",
            text_color=COLORS["text_muted"],
            font=mono(11),
        )
        self.text.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.grid_columnconfigure(0, weight=1)

    def update(self, used_bytes=None, total_bytes=None):
        if used_bytes is None or total_bytes is None:
            return super().update()

        self.used_bytes = max(0, int(used_bytes))
        self.total_bytes = max(0, int(total_bytes))
        percent = 0 if self.total_bytes == 0 else self.used_bytes / self.total_bytes
        self.bar.set(min(percent, 1))
        self.text.configure(
            text=(
                f"{self.used_bytes / 1024:.1f} KB used / "
                f"{self.total_bytes / 1024:.1f} KB available "
                f"({percent * 100:.1f}%)"
            )
        )


class ReusableWidgets:
    @staticmethod
    def card(parent, **kwargs):
        options = {"corner_radius": 12, "fg_color": COLORS["card"]}
        options.update(kwargs)
        return ctk.CTkFrame(parent, **options)

    @staticmethod
    def label(parent, text, size=13, weight="normal", muted=False):
        return ctk.CTkLabel(
            parent,
            text=text,
            text_color=COLORS["text_muted"] if muted else COLORS["text_primary"],
            font=inter(size, weight),
        )

    @staticmethod
    def entry(parent, placeholder, width=400, show=None):
        return ctk.CTkEntry(
            parent,
            width=width,
            height=38,
            placeholder_text=placeholder,
            show=show,
            fg_color=COLORS["surface"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text_color=COLORS["text_muted"],
            font=mono(12),
            corner_radius=8,
            border_width=1,
        )

    @staticmethod
    def primary_button(parent, text, command, width=200):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=40,
            fg_color=COLORS["accent"],
            text_color=COLORS["background"],
            hover_color=COLORS["accent_dim"],
            corner_radius=8,
            font=inter(13, "bold"),
        )

    @staticmethod
    def ghost_button(parent, text, command, width=160):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=38,
            fg_color="transparent",
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            hover_color=COLORS["surface"],
            corner_radius=8,
            font=inter(12, "bold"),
        )

    @staticmethod
    def progress_bar(parent, width=400):
        bar = ctk.CTkProgressBar(
            parent,
            width=width,
            height=10,
            progress_color=COLORS["accent"],
            fg_color=COLORS["border"],
            corner_radius=6,
        )
        bar.set(0)
        return bar

    @staticmethod
    def image_preview(parent, size=280):
        return ImagePreview(parent, size=size)

    @staticmethod
    def load_preview(label_widget, image_path: str, size: int = 280):
        """Load an image from disk and display it in a CTkLabel preview widget."""
        try:
            img = Image.open(image_path).convert("RGB")
            img.thumbnail((size, size), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            label_widget.configure(image=ctk_img, text="")
            label_widget._ctk_image = ctk_img  # prevent GC
        except Exception as exc:
            label_widget.configure(text=f"Error: {exc}", image=None)

    @staticmethod
    def capacity_bar(parent, width=400):
        return CapacityBar(parent, width=width)
