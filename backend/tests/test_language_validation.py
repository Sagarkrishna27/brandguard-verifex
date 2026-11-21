import pytest
from fastapi import HTTPException

from main import ALL_LANGUAGES, SUPPORTED_LANGUAGES, validate_languages


def test_empty_language_defaults_to_english():
    assert validate_languages("") == "eng"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("eng+kan", "eng+kan"),
        ("eng,kan", "eng+kan"),
        ("eng kan", "eng+kan"),
        ("ENG+KAN", "eng+kan"),
        ("eng+kan+eng", "eng+kan"),
    ],
)
def test_language_input_formats(value, expected):
    assert validate_languages(value) == expected


def test_all_returns_every_supported_language():
    assert validate_languages("all") == "+".join(ALL_LANGUAGES)
    assert set(ALL_LANGUAGES) == set(SUPPORTED_LANGUAGES)


def test_unsupported_language_returns_clear_http_error():
    with pytest.raises(HTTPException) as error:
        validate_languages("eng+not-a-language")
    assert error.value.status_code == 400
    assert "Unsupported language" in error.value.detail


def test_language_list_with_no_codes_is_rejected():
    with pytest.raises(HTTPException) as error:
        validate_languages(" + , ")
    assert error.value.status_code == 400
