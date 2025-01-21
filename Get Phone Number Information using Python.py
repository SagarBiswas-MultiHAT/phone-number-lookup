# +8801727361077
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import tkinter as tk
from tkinter import messagebox

def lookup_phone_number():
    mobile_number = entry.get()
    try:
        mobile_number = phonenumbers.parse(mobile_number)
        if phonenumbers.is_valid_number(mobile_number):
            result_text.set('Service Provider: {}'.format(carrier.name_for_number(mobile_number, "en")))
            result_text.set(result_text.get() + '\nPhone number belongs to country: {}'.format(geocoder.description_for_number(mobile_number, "en")))
            result_text.set(result_text.get() + '\nPhone Number belongs to region: {}'.format(timezone.time_zones_for_number(mobile_number)))
        else:
            result_text.set("Please enter a valid mobile number")
    except Exception as e:
        result_text.set("Error: {}".format(e))

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

result_text = tk.StringVar()
result_label = tk.Label(window, textvariable=result_text)
result_label.pack(pady=10)

# Start the GUI event loop
window.mainloop()
