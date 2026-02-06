import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import tkinter as tk
from tkinter import messagebox
import pyperclip
from PIL import Image, ImageTk
import requests
from io import BytesIO

def lookup_phone_number():
    number = entry.get().strip()

    try:
        parsed = phonenumbers.parse(number, None)

        if not phonenumbers.is_valid_number(parsed):
            result_text.set("Please enter a valid phone number")
            return

        lines = [
            f"Service Provider: {carrier.name_for_number(parsed, 'en')}",
            f"Country: {geocoder.description_for_number(parsed, 'en')}",
            f"Time Zones: {', '.join(timezone.time_zones_for_number(parsed))}",
        ]

        result_text.set("\n".join(lines))
        display_country_flag(parsed.country_code)

    except phonenumbers.NumberParseException:
        result_text.set("Invalid phone number format")
    except Exception as e:
        result_text.set(f"Error: {e}")

def clear_input():
    entry.delete(0, tk.END)
    result_text.set("")
    flag_label.config(image=None)
    flag_label.image = None

def copy_to_clipboard():
    if result_text.get():
        pyperclip.copy(result_text.get())
        messagebox.showinfo("Copied", "Result copied to clipboard")

def display_country_flag(country_code):
    try:
        region = phonenumbers.region_code_for_country_code(country_code)
        if not region:
            return

        url = f"https://flagcdn.com/w320/{region.lower()}.png"
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content))
        img = ImageTk.PhotoImage(img)

        flag_label.config(image=img)
        flag_label.image = img

    except Exception:
        flag_label.config(image=None)
        flag_label.image = None

# GUI
window = tk.Tk()
window.title("Phone Number Lookup")

tk.Label(window, text="Enter phone number with country code (+xx...)").pack(pady=10)

entry = tk.Entry(window, width=30)
entry.pack(pady=5)

tk.Button(window, text="Lookup", command=lookup_phone_number).pack(pady=5)
tk.Button(window, text="Clear", command=clear_input).pack(pady=5)
tk.Button(window, text="Copy", command=copy_to_clipboard).pack(pady=5)

result_text = tk.StringVar()
tk.Label(window, textvariable=result_text, justify="left").pack(pady=10)

flag_label = tk.Label(window)
flag_label.pack(pady=10)

window.mainloop()
