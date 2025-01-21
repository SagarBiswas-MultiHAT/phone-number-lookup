# +8801*2*361077
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import tkinter as tk
from tkinter import messagebox
import pyperclip
from PIL import Image, ImageTk
import requests
from io import BytesIO

def lookup_phone_number():
    mobile_number = entry.get()
    try:
        mobile_number = phonenumbers.parse(mobile_number)
        if phonenumbers.is_valid_number(mobile_number):
            result_text.set('Service Provider: {}'.format(carrier.name_for_number(mobile_number, "en")))
            result_text.set(result_text.get() + '\nPhone number belongs to country: {}'.format(geocoder.description_for_number(mobile_number, "en")))
            result_text.set(result_text.get() + '\nPhone Number belongs to region: {}'.format(timezone.time_zones_for_number(mobile_number)))
            display_country_flag(mobile_number.country_code)
        else:
            result_text.set("Please enter a valid mobile number")
    except Exception as e:
        result_text.set("Error: {}".format(e))

def clear_input():
    entry.delete(0, tk.END)
    result_text.set("")
    flag_label.config(image='')

def copy_to_clipboard():
    pyperclip.copy(result_text.get())
    messagebox.showinfo("Copied", "Result copied to clipboard")

def display_country_flag(country_code):
    try:
        country_code_str = phonenumbers.region_code_for_country_code(country_code).lower()
        url = f"https://flagcdn.com/w320/{country_code_str}.png"
        response = requests.get(url)
        img_data = response.content
        img = Image.open(BytesIO(img_data))
        img = ImageTk.PhotoImage(img)
        flag_label.config(image=img)
        flag_label.image = img
    except Exception as e:
        flag_label.config(image='')
        messagebox.showerror("Error", "Could not load country flag")

# Create the main window
window = tk.Tk()
window.title("Phone Number Lookup")

# Create and pack widgets
label = tk.Label(window, text="Enter Phone number with country code (+xx xxxxxxxxx):")
label.pack(pady=10)

entry = tk.Entry(window)
entry.pack(pady=10)

lookup_button = tk.Button(window, text="Lookup", command=lookup_phone_number)
lookup_button.pack(pady=10)

clear_button = tk.Button(window, text="Clear", command=clear_input)
clear_button.pack(pady=10)

copy_button = tk.Button(window, text="Copy", command=copy_to_clipboard)
copy_button.pack(pady=10)

result_text = tk.StringVar()
result_label = tk.Label(window, textvariable=result_text)
result_label.pack(pady=10)

flag_label = tk.Label(window)
flag_label.pack(pady=10)

# Start the GUI event loop
window.mainloop()
