import requests
import threading
import datetime
from phonenumbers import NumberParseException, is_valid_number, parse
from spellchecker import SpellChecker

api_key = "prj_test_sk_b3c2e2f2baeaecbad71675ce2d3bf43ff9d9f038"


spell = SpellChecker()
def suggest_typo_correction(text: str):
    words = text.split()
    corrections = []
    for word in words:
        corrected = spell.correction(word)
        if corrected and corrected != word:
            corrections.append((word, corrected))
    return corrections


def is_valid_date(date_str, formats=None, no_future_allowed=False, no_past_allowed=False):
    if formats is None:
        formats = ["%Y-%m-%d"]

    for fmt in formats:
        try:
            parsed_date = datetime.datetime.strptime(date_str.strip(), fmt)

            # Check if date is before datetime.min (usually 0001-01-01)
            if parsed_date < datetime.datetime.min:
                return False, "Date is too early to be valid."

            today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if no_future_allowed:
                if parsed_date >= today:
                    return False, "For this field, date cannot be today or in the future."
            if no_past_allowed:
                if parsed_date < today:
                    return False, "For this field, date cannot be in the past."

            return True, parsed_date

        except ValueError:
            continue

    return False, "Please enter a valid date in YYYY-MM-DD format."


def is_valid_location(address):
    """
    Validates an address using the Radar API.
    Returns (True, address_dict) if valid, else (False, error_message).
    """
    if not address.strip():
        return False, "Address input is empty."

    url = "https://api.radar.io/v1/geocode/forward"
    headers = {
        "Authorization": api_key
    }
    params = {
        "query": address,
        "limit": 1
    }

    def make_request():
        return requests.get(url, headers=headers, params=params, timeout=10)

    try:
        warning_timer = threading.Timer(5, lambda: print("Waiting for Radar API response..."))
        warning_timer.start()

        try:
            response = make_request()
        except requests.exceptions.Timeout:
            print("First attempt timed out after 10 seconds. Retrying...")
            response = make_request()

        finally:
            warning_timer.cancel()

        data = response.json()

        if response.status_code != 200:
            return False, f"Radar API error: {data.get('message', 'Unknown error')}"

        results = data.get("addresses", [])
        if results:
            return True, results[0]
        else:
            return False, "No address found for your input. Please double-check and enter a valid address."

    except Exception as e:
        return False, f"Error connecting to Radar API: {str(e)}"


def get_normalized_address(user_input, field_name):
    """
    Validates and normalizes a user input address using the Radar API.
    Asks for user confirmation if a corrected version is found.
    Returns the confirmed and normalized value or None if validation fails.
    """
    import requests

    def confirm_with_user(original, suggested, field_desc):
        while True:
            confirm = input(f"Did you mean '{suggested}' instead of '{original}' for {field_desc}? (yes/no): ").strip().lower()
            if confirm == 'yes':
                return suggested
            elif confirm == 'no':
                return None
            else:
                print("Please answer 'yes' or 'no'.")

    # Try initial validation
    is_valid, result = is_valid_location(user_input)
    if not is_valid:
        print(f"❌ {result}")
        return None

    address_obj = result
    # Determine expected component based on field suffix
    if field_name.endswith("_city"):
        component = "city"
    elif field_name.endswith("_country"):
        component = "country"
    elif field_name.endswith("_state"):
        component = "state"
    else:
        component = "formattedAddress"

    suggested_value = address_obj.get(component, user_input)

    if suggested_value.strip().lower() != user_input.strip().lower():
        confirmed = confirm_with_user(user_input, suggested_value, field_name.replace('_', ' '))
        if confirmed:
            return confirmed
        else:
            return None
    else:
        return suggested_value


def is_valid_phone_number(phone_number: str) -> bool:
    """
    Validates the phone number using the phonenumbers library.
    Supports optional extensions in the format ' ext <extension>'.

    Args:
        phone_number: full phone number string to validate (e.g. "+1234567890 ext 123")

    Returns:
        True if valid phone number, False otherwise.
    """
    if not phone_number:
        return False

    # Separate main number and extension if present
    parts = phone_number.split(' ext ')
    main_number = parts[0].strip()
    # We don't need to validate extension format here; just the main number

    try:
        # parse requires a region code or None if number includes country code
        parsed_number = parse(main_number, None)
        return is_valid_number(parsed_number)
    except NumberParseException:
        return False


def validate_full_phone_number(answers: dict, current_field: str) -> tuple[bool, str, list[str]]:
    """
    Handles validation of a full phone number based on the current field updated.

    Args:
        answers: dict of all form answers
        current_field: the field just updated, e.g. 'primary_phone_number' or 'primary_full_phone_number'

    Returns:
        is_valid: bool - if full phone number is valid
        full_number: str - the combined full phone number or empty string if incomplete
        fields_to_clear: list of str - fields to clear if invalid (empty if valid or incomplete)
    """
    # Case 1: field is a full phone number input
    if current_field.endswith('_full_phone_number'):
        full_number = answers.get(current_field, '').strip()
        if not full_number:
            return False, '', []
        is_valid = is_valid_phone_number(full_number)
        if not is_valid:
            # Clear the full phone number field for retry
            return False, full_number, [current_field]
        return True, full_number, []

    # Case 2: separate country code, number, extension fields
    prefix = current_field.split('_phone_')[0]

    needed_fields = [
        f"{prefix}_phone_country_code",
        f"{prefix}_phone_number",
        f"{prefix}_phone_extension"
    ]

    # Check if required fields exist and are non-empty (extension optional)
    if not all(field in answers and answers[field] != '' for field in needed_fields[:2]):
        # Required fields incomplete - no validation done
        return False, '', []

    country_code = answers.get(f'{prefix}_phone_country_code', '').lstrip('+')
    number = answers.get(f'{prefix}_phone_number', '').strip()
    extension = answers.get(f'{prefix}_phone_extension', '').strip()

    full_number = f"+{country_code}{number}"
    if extension:
        full_number += f" ext {extension}"

    is_valid = is_valid_phone_number(full_number)

    if not is_valid:
        # Clear these fields for retry
        return False, full_number, needed_fields

    return True, full_number, []



