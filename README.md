
# Phone Number Lookup

A Python application that validates and retrieves details about phone numbers, including the service provider, country, and timezone. The app also displays the corresponding country flag using a graphical user interface (GUI) built with Tkinter.

## Features

- Validate phone numbers.
- Retrieve carrier, country, and timezone information.
- Display the corresponding country flag.
- Clear input and result.
- Copy result to clipboard.

## Requirements

- Python 3.x
- `phonenumbers`
- `tkinter`
- `pyperclip`
- `Pillow`
- `requests`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/SagarBiswas-MultiHAT/phone-number-lookup.git
   ```
2. Navigate to the project directory:
   ```bash
   cd phone-number-lookup
   ```
3. Install the required dependencies:
   ```bash
   pip install phonenumbers pyperclip Pillow requests
   ```

## Usage

1. Run the script:
   ```bash
   python script.py
   ```
2. Enter a phone number with the country code (e.g., `+8801727361077`) and click "Lookup".
3. View the details and flag image.
4. Use the "Clear" button to reset the input and result.
5. Use the "Copy" button to copy the result to the clipboard.

## Example

Input: `+8801727361077`

Output:
- Service Provider: [Carrier Name]
- Country: Bangladesh
- Timezone: Asia/Dhaka
- Displays the flag of Bangladesh.

---

Contributions are welcome! Feel free to open issues or submit pull requests.
