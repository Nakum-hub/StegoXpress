import os

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def enable_image_drop(widget, on_file, on_error, on_highlight=None):
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD

        TkinterDnD._require(widget.winfo_toplevel())
        widget.drop_target_register(DND_FILES)
    except Exception:
        return False

    def set_highlight(active):
        if on_highlight:
            on_highlight(active)

    def first_path(event):
        paths = widget.tk.splitlist(event.data)
        return paths[0] if paths else ""

    def on_enter(_event):
        set_highlight(True)
        return "copy"

    def on_leave(_event):
        set_highlight(False)
        return "copy"

    def on_drop(event):
        set_highlight(False)
        path = first_path(event)
        extension = os.path.splitext(path)[1].lower()
        if extension not in IMAGE_EXTENSIONS:
            on_error("Please drop a PNG or JPG image.")
            return "break"
        on_file(path)
        return "copy"

    widget.dnd_bind("<<DropEnter>>", on_enter)
    widget.dnd_bind("<<DropLeave>>", on_leave)
    widget.dnd_bind("<<Drop>>", on_drop)
    return True
