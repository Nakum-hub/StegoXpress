import tkinter as tk
from tkinter import filedialog, messagebox
from cryptography.fernet import Fernet
from PIL import Image, ImageTk
import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import threading
import subprocess
import webbrowser
import http.server
import socketserver
import sys
import os


class SteganographyApp:
    LENGTH_HEADER_BYTES = 4
    EMBED_CHANNELS = 3

    def __init__(self, root):
        self.root = root
        self.root.title("Image Steganography Tool")
        self.root.geometry("700x650")
        self.root.configure(bg="#1e1e1e")
        self.cover_image_path = tk.StringVar()
        self.hidden_file_path = tk.StringVar()

        # Title
        tk.Label(
            self.root,
            text="  Image Steganography Tool !!!",
            font=("Helvetica", 18, "bold"),
            bg="#1e1e1e",
            fg="#00FF00",
        ).grid(row=0, column=0, columnspan=3, pady=10)

        # Email Inputs
        self.email_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.email_frame.grid(row=1, column=0, columnspan=3, pady=20, sticky="ew")

        tk.Label(
            self.email_frame,
            text="Sender Email:",
            font=("Arial", 12),
            bg="#1e1e1e",
            fg="#00FF00",
        ).grid(row=0, column=0, sticky="w", padx=20)
        self.sender_email_entry = tk.Entry(
            self.email_frame, width=50, font=("Arial", 10), bg="#333", fg="#00FF00"
        )
        self.sender_email_entry.grid(row=0, column=1, padx=20, pady=5)

        tk.Label(
            self.email_frame,
            text="Sender Password:",
            font=("Arial", 12),
            bg="#1e1e1e",
            fg="#00FF00",
        ).grid(row=1, column=0, sticky="w", padx=20)
        self.sender_password_entry = tk.Entry(
            self.email_frame,
            width=50,
            font=("Arial", 10),
            show="*",
            bg="#333",
            fg="#00FF00",
        )
        self.sender_password_entry.grid(row=1, column=1, padx=20, pady=5)

        tk.Label(
            self.email_frame,
            text="Recipient Email:",
            font=("Arial", 12),
            bg="#1e1e1e",
            fg="#00FF00",
        ).grid(row=2, column=0, sticky="w", padx=20)
        self.recipient_email_entry = tk.Entry(
            self.email_frame, width=50, font=("Arial", 10), bg="#333", fg="#00FF00"
        )
        self.recipient_email_entry.grid(row=2, column=1, padx=20, pady=5)

        # Image File and Message
        self.file_message_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.file_message_frame.grid(
            row=2, column=0, columnspan=3, pady=10, sticky="ew"
        )

        tk.Label(
            self.file_message_frame,
            text="Image File:",
            font=("Arial", 12),
            bg="#1e1e1e",
            fg="#00FF00",
        ).grid(row=0, column=0, sticky="w", padx=10)
        self.image_path = tk.StringVar()
        tk.Entry(
            self.file_message_frame,
            textvariable=self.image_path,
            width=40,
            font=("Arial", 10),
            bg="#333",
            fg="#00FF00",
        ).grid(row=0, column=1, padx=10)
        tk.Button(
            self.file_message_frame,
            text="Browse",
            font=("Arial", 10),
            command=self.browse_image,
            bg="#00FF00",
            fg="black",
            relief="flat",
        ).grid(row=0, column=2, padx=10)

        self.message_label = tk.Label(
            self.file_message_frame,
            text="Message to Encrypt:",
            font=("Arial", 12),
            bg="#1e1e1e",
            fg="#00FF00",
        )
        self.message_label.grid(row=1, column=0, sticky="w", padx=10)
        self.message_entry = tk.Entry(
            self.file_message_frame,
            width=50,
            font=("Arial", 10),
            bg="#333",
            fg="#00FF00",
        )
        self.message_entry.grid(row=1, column=1, padx=10, pady=5)

        # Radio Buttons for Operation
        self.operation = tk.StringVar(value="encrypt")
        operations_frame = tk.Frame(self.root, bg="#1e1e1e")
        operations_frame.grid(row=3, column=0, columnspan=3, pady=10)

        tk.Radiobutton(
            operations_frame,
            text="Encrypt",
            variable=self.operation,
            value="encrypt",
            font=("Arial", 12),
            bg="#1e1e1e",
            fg="#00FF00",
            selectcolor="#1e1e1e",
            command=self.toggle_mode,
        ).grid(row=0, column=0, padx=20)

        tk.Radiobutton(
            operations_frame,
            text="Decrypt",
            variable=self.operation,
            value="decrypt",
            font=("Arial", 12),
            bg="#1e1e1e",
            fg="#00FF00",
            selectcolor="#1e1e1e",
            command=self.toggle_mode,
        ).grid(row=0, column=1, padx=20)

        # Image Preview Section
        self.preview_frame = tk.Frame(self.root, bg="#1e1e1e", width=700, height=600)
        self.preview_frame.grid(row=4, column=0, columnspan=3, pady=10)
        self.preview_label = tk.Label(self.preview_frame, bg="#1e1e1e")
        self.preview_label.grid(row=0, column=0)

        # Action Button
        self.action_button = tk.Button(
            self.root,
            text="Encrypt",
            font=("Arial", 12),
            command=self.encrypt_action,
            bg="#00FF00",
            fg="black",
            relief="flat",
        )
        self.action_button.grid(row=5, column=0, columnspan=3, pady=20)

        # Tool Info Button
        self.tool_info_button = tk.Button(
            self.root,
            text="Tool Info",
            font=("Arial", 12),
            command=self.tool_info,
            bg="#00FF00",
            fg="black",
            relief="flat",
        )
        self.tool_info_button.grid(row=6, column=0, columnspan=3, pady=10)

        # Initialize mode
        self.toggle_mode()

    def toggle_mode(self):
        if self.operation.get() == "encrypt":
            self.action_button.config(text="Encrypt", command=self.encrypt_action)
            self.message_label.config(text="Message to Encrypt:")
            self.email_frame.grid(row=1, column=0, columnspan=3, pady=20, sticky="ew")
        else:
            self.action_button.config(text="Decrypt", command=self.decrypt_action)
            self.message_label.config(text="Key for Decryption:")
            self.email_frame.grid_forget()

    def browse_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.png *.jpg *.jpeg")]
        )
        if file_path:
            self.image_path.set(file_path)
            self.update_image_preview(file_path)

    def update_image_preview(self, image_path):
        try:
            image = Image.open(image_path)
            image.thumbnail((300, 300))
            photo = ImageTk.PhotoImage(image)
            self.preview_label.config(image=photo)
            self.preview_label.image = photo
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")

    def tool_info(self):
        # Generate the HTML content with the provided details
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Project Information</title>
        <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #1e1e1e;
            color: #00FF00;
            text-align: center;
            padding: 20px;
        }
        h1, h2 {
            font-size: 2em;
            margin-bottom: 20px;
        }
        p {
            font-size: 1.2em;
            line-height: 1.6;
            text-align: left;
            margin: 0 auto;
            width: 90%;
            max-width: 800px;
        }
        a {
            color: #00FF00;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        ul {
            text-align: left;
            margin: 0 auto;
            padding: 0;
            list-style-type: disc;
            width: 90%;
            max-width: 800px;
        }
        li {
            margin: 10px 0;
        }
        table {
            margin: 20px auto;
            border-collapse: collapse;
            width: 90%;
            max-width: 800px;
            color: #00FF00;
        }
        th, td {
            border: 1px solid #00FF00;
            padding: 10px;
            text-align: left;
        }
        th {
            background-color: #333;
        }
    </style>
</head>
<body>
    <h1>Project Information</h1>
    <p>This project was developed by Naresh G, Naveen T S, Dhanush S A, Ashwini B , Anagha M Hebbar, and Deepika  as part of a Cyber Security Internship. 
    It is designed to secure organizations in the real world from cyber frauds performed by hackers.</p>
    
    <h2>Project Details</h2>
    <table>
        <tr><th>Project Name</th><td>Image Steganography using LSB</td></tr>
        <tr><th>Project Description</th><td>Hiding Message with Encryption in Image using LSB Algorithm</td></tr>
        <tr><th>Project Start Date</th><td>16-Nov-2024</td></tr>
        <tr><th>Project End Date</th><td>21-DEC-2024</td></tr>
        <tr><th>Project Status</th><td>Completed</td></tr>
    </table>

    <h2>Developer Details</h2>
    <table>
        <tr><th>Name</th><th>Employee ID</th><th>Email</th></tr>
        <tr><td>Naresh G</td><td>ST#IS#7054</td><td>gnaresh3003@gmail.com</td></tr>
        <tr><td>Naveen T S</td><td>ST#IS#7055</td><td>tsnaveen@gmail.com</td></tr>
        <tr><td>Dhanush S A</td><td>ST#IS#7056</td><td>dhanushgowda007sa@gmail.com</td></tr>
        <tr><td>Anagha M Hebbar </td><td>ST#IS#7057</td><td>anagha5454@gmail.com</td></tr>
        <tr><td>Ashwini B</td><td>ST#IS#7058</td><td>ashb2224@gmail.com</td></tr>
        <tr><td>Deepika </td><td>ST#IS#7059</td><td>deepika3452622@gmail.com</td></tr>
    </table>

    <h2>Company Details</h2>
    <table>
        <tr><th>Company Name</th><td>Supraja Technologies</td></tr>
        <tr><th>Email</th><td>contact@suprajatechnologies.com</td></tr>
    </table>
</body>
</html>
"""

        # Save the HTML content to a temporary file
        html_file = "tool_info.html"
        with open(html_file, "w") as file:
            file.write(html_content)

        # Serve the file locally using a temporary HTTP server
        def serve_file():
            handler = http.server.SimpleHTTPRequestHandler
            with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
                # Get the dynamically assigned port and open the browser
                port = httpd.server_address[1]
                url = f"http://127.0.0.1:{port}/{html_file}"
                threading.Thread(target=webbrowser.open, args=(url,)).start()
                httpd.serve_forever()

        threading.Thread(target=serve_file, daemon=True).start()


    def encrypt_action(self):
        image_file = self.image_path.get()
        message = self.message_entry.get()
        sender_email = self.sender_email_entry.get()
        sender_password = self.sender_password_entry.get()
        recipient_email = self.recipient_email_entry.get()

        if not all([image_file, message, sender_email, sender_password, recipient_email]):
            messagebox.showerror("Error", "All fields are required.")
            return

        try:
            # Generate the encryption key
            key = Fernet.generate_key()
            f = Fernet(key)
            secret_message = f.encrypt(message.encode())

            # Open the image
            with Image.open(image_file) as image:
                if not self.check_image_capacity(image, secret_message):
                    return
                encoded_image = self.embed_message(image, secret_message)

            output_image_path = self.get_output_image_path(image_file)
            encoded_image.save(output_image_path, "PNG")

            # Send only the encrypted image. The key must be shared separately.
            if not self.send_email(
                output_image_path,
                sender_email,
                sender_password,
                recipient_email,
            ):
                return

            messagebox.showinfo(
                "Success",
                "Image encrypted and sent to "
                f"{recipient_email}.\n\nShare this decryption key through a separate channel:\n"
                f"{key.decode()}",
            )
            self.clear_fields()

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during encryption: {str(e)}")

    def prepare_image_for_lsb(self, image):
        if image.mode in ("RGB", "RGBA"):
            return image.copy()

        if "A" in image.getbands() or "transparency" in image.info:
            return image.convert("RGBA")

        return image.convert("RGB")

    def get_capacity_bits(self, image):
        return image.size[0] * image.size[1] * self.EMBED_CHANNELS

    def check_image_capacity(self, image, payload):
        payload_length = len(payload)
        required_bits = (self.LENGTH_HEADER_BYTES + payload_length) * 8
        capacity_bits = self.get_capacity_bits(image)

        if required_bits > capacity_bits:
            max_payload_bytes = max(
                (capacity_bits - self.LENGTH_HEADER_BYTES * 8) // 8,
                0,
            )
            messagebox.showerror(
                "Error",
                "The encrypted message is too long for this image. "
                f"It needs {required_bits} bits, but the image only has "
                f"{capacity_bits} usable bits. Maximum encrypted payload: "
                f"{max_payload_bytes} bytes.",
            )
            return False

        return True

    def get_output_image_path(self, image_file):
        directory = os.path.dirname(os.path.abspath(image_file))
        base_name = os.path.splitext(os.path.basename(image_file))[0]
        candidate = os.path.join(directory, f"{base_name}_encrypted.png")
        suffix = 1

        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base_name}_encrypted_{suffix}.png")
            suffix += 1

        return candidate

    def embed_message(self, image, payload):
        if not isinstance(payload, bytes):
            payload = str(payload).encode("utf-8")

        image = self.prepare_image_for_lsb(image)
        payload_with_header = (
            len(payload).to_bytes(self.LENGTH_HEADER_BYTES, "big") + payload
        )
        binary_payload = "".join(format(byte, "08b") for byte in payload_with_header)
        capacity_bits = self.get_capacity_bits(image)

        if len(binary_payload) > capacity_bits:
            raise ValueError(
                "The encrypted message is too long for this image. "
                f"Required bits: {len(binary_payload)}, available bits: {capacity_bits}."
            )

        new_pixels = []
        bit_index = 0

        for pixel in image.getdata():
            channels = list(pixel)

            for channel_index in range(self.EMBED_CHANNELS):
                if bit_index >= len(binary_payload):
                    break
                channels[channel_index] = (
                    channels[channel_index] & 0xFE
                ) | int(binary_payload[bit_index])
                bit_index += 1

            new_pixels.append(tuple(channels))

        image.putdata(new_pixels)
        return image

    def iter_lsb_bits(self, image):
        image = self.prepare_image_for_lsb(image)

        for pixel in image.getdata():
            for channel in pixel[: self.EMBED_CHANNELS]:
                yield channel & 1

    def read_lsb_bits(self, bit_iter, bit_count):
        bits = []

        for _ in range(bit_count):
            try:
                bits.append(str(next(bit_iter)))
            except StopIteration as exc:
                raise ValueError(
                    "The image does not contain a complete hidden payload."
                ) from exc

        return "".join(bits)

    def extract_message(self, image):
        capacity_bits = self.get_capacity_bits(image)
        header_bits_count = self.LENGTH_HEADER_BYTES * 8

        if capacity_bits < header_bits_count:
            raise ValueError("The image is too small to contain a hidden payload.")

        bit_iter = self.iter_lsb_bits(image)
        header_bits = self.read_lsb_bits(bit_iter, header_bits_count)
        payload_length = int(header_bits, 2)
        max_payload_length = (capacity_bits - header_bits_count) // 8

        if payload_length <= 0 or payload_length > max_payload_length:
            raise ValueError("The image does not contain a valid hidden payload length.")

        payload_bits = self.read_lsb_bits(bit_iter, payload_length * 8)
        return bytes(
            int(payload_bits[index : index + 8], 2)
            for index in range(0, len(payload_bits), 8)
        )

    def send_email(self, image_path, sender_email, sender_password, recipient_email):
        try:
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = recipient_email
            msg["Subject"] = "Encrypted Image"

            body = (
                "Please find the attached encrypted image.\n\n"
                "The decryption key is not included in this email. "
                "Share it through a separate secure channel."
            )
            msg.attach(MIMEText(body, "plain"))

            # Attach the image
            with open(image_path, "rb") as image_attachment:
                img_base = MIMEBase("application", "octet-stream")
                img_base.set_payload(image_attachment.read())
                encoders.encode_base64(img_base)
                img_base.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{os.path.basename(image_path)}"'
                )
                msg.attach(img_base)

            # Send the email
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            server.quit()
            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send email: {str(e)}")
            return False


    def decrypt_action(self):
        encrypted_image_path = self.image_path.get()
        key = self.message_entry.get()

        if not encrypted_image_path or not key:
            messagebox.showerror("Error", "Please select the encrypted image and provide the decryption key.")
            return

        # Run decryption in a separate thread to keep the UI responsive
        decryption_thread = threading.Thread(target=self.perform_decryption, args=(encrypted_image_path, key))
        decryption_thread.start()

    def perform_decryption(self, encrypted_image_path, key):
        try:
            # Convert the key from string to bytes for Fernet
            f = Fernet(key.encode())

            # Open the encrypted image and extract the pixel data
            with Image.open(encrypted_image_path) as encoded_image:
                encrypted_payload = self.extract_message(encoded_image)

            # Decrypt the message using Fernet
            original_message = f.decrypt(encrypted_payload).decode("utf-8")

            # Show the decrypted message in the main thread
            self.root.after(0, self.show_decryption_success, original_message)

        except Exception as e:
            error_message = str(e)
            self.root.after(0, self.show_decryption_error, error_message)

    def show_decryption_success(self, original_message):
        messagebox.showinfo("Success", "The Hidden Text is:\n" + original_message)
        self.clear_fields()

    def show_decryption_error(self, error_message):
        messagebox.showerror(
            "Error",
            f"An error occurred during decryption: {error_message}",
        )
        self.clear_fields()





    def clear_fields(self):
        self.image_path.set("")
        self.message_entry.delete(0, tk.END)
        self.sender_email_entry.delete(0, tk.END)
        self.sender_password_entry.delete(0, tk.END)
        self.recipient_email_entry.delete(0, tk.END)
        self.preview_label.config(image="")
        self.preview_label.image = None


# Main program execution
if __name__ == "__main__":
    root = tk.Tk()
    app = SteganographyApp(root)
    root.mainloop()
