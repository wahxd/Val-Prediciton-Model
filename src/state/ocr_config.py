"""Tesseract OCR character whitelist configurations per field type.

Constrains raw OCR output to valid characters before any parsing occurs,
preventing garbage values like "1:3C" instead of "1:30".
"""

# Tesseract character whitelists per field type
# These are passed via tessedit_char_whitelist in Tesseract config
OCR_WHITELISTS: dict[str, str] = {
    "timer": "0123456789:",       # Timer only shows digits and colon (e.g., "1:30")
    "alive_left": "012345",       # Alive count is 0-5
    "alive_right": "012345",      # Alive count is 0-5
    "score_left": "0123456789",   # Score is 0-13 (needs all digits)
    "score_right": "0123456789",  # Score is 0-13 (needs all digits)
}


def get_tesseract_config(field: str, psm: int = 7) -> str:
    """Build Tesseract config string with field-specific character whitelist.

    Args:
        field: One of the keys in OCR_WHITELISTS
        psm: Page segmentation mode (7 = single text line, recommended for HUD fields)

    Returns:
        Tesseract config string like '--psm 7 -c tessedit_char_whitelist=0123456789:'
    """
    whitelist = OCR_WHITELISTS.get(field, "")
    if whitelist:
        return f"--psm {psm} -c tessedit_char_whitelist={whitelist}"
    return f"--psm {psm}"
