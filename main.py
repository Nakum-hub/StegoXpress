import customtkinter

from gui.app import StegoXpressApp


if __name__ == "__main__":
    customtkinter.set_appearance_mode("dark")
    root = customtkinter.CTk()
    app = StegoXpressApp(root)
    root.mainloop()
