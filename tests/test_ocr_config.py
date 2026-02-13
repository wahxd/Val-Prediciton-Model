"""Tests for OCR character whitelist configuration.

Validates that Tesseract OCR character whitelists constrain extraction to
valid characters per field type, preventing garbage like "1:3C" instead of "1:30".
"""

from src.state.ocr_config import OCR_WHITELISTS, get_tesseract_config


class TestOCRWhitelists:
    """Test OCR_WHITELISTS dict contains correct character sets per field."""

    def test_timer_whitelist_contains_digits_and_colon(self):
        assert OCR_WHITELISTS["timer"] == "0123456789:"

    def test_alive_whitelist_contains_zero_to_five(self):
        assert OCR_WHITELISTS["alive_left"] == "012345"
        assert OCR_WHITELISTS["alive_right"] == "012345"

    def test_score_whitelist_contains_all_digits(self):
        assert OCR_WHITELISTS["score_left"] == "0123456789"
        assert OCR_WHITELISTS["score_right"] == "0123456789"


class TestGetTesseractConfig:
    """Test get_tesseract_config() builds correct Tesseract CLI strings."""

    def test_get_tesseract_config_timer(self):
        config = get_tesseract_config("timer")
        assert "tessedit_char_whitelist=0123456789:" in config

    def test_get_tesseract_config_alive(self):
        config = get_tesseract_config("alive_left")
        assert "tessedit_char_whitelist=012345" in config

    def test_get_tesseract_config_unknown_field(self):
        config = get_tesseract_config("unknown")
        assert "tessedit_char_whitelist" not in config
        assert "--psm" in config

    def test_get_tesseract_config_custom_psm(self):
        config = get_tesseract_config("timer", psm=13)
        assert "--psm 13" in config
        assert "tessedit_char_whitelist=0123456789:" in config

    def test_get_tesseract_config_default_psm_is_7(self):
        config = get_tesseract_config("timer")
        assert "--psm 7" in config

    def test_get_tesseract_config_score_right(self):
        config = get_tesseract_config("score_right")
        assert "tessedit_char_whitelist=0123456789" in config

    def test_get_tesseract_config_alive_right(self):
        config = get_tesseract_config("alive_right")
        assert "tessedit_char_whitelist=012345" in config
