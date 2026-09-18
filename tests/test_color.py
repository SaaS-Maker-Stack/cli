import pytest

from saas_maker.color import hex_to_hue, parse_brand


@pytest.mark.parametrize(
    "hex_value, expected",
    [
        ("#0066ff", 262),  # electric blue -> sits next to the indigo default
        ("#ff0000", 29),  # red
        ("#00ff00", 142),  # green
        ("#f97316", 48),  # tailwind orange-500
        ("#06f", 262),  # short form
    ],
)
def test_hex_to_hue(hex_value, expected):
    assert abs(hex_to_hue(hex_value) - expected) <= 2


def test_parse_brand_accepts_angles_and_hex():
    assert parse_brand("265") == 265
    assert parse_brand(" #0066ff ") == hex_to_hue("#0066ff")


@pytest.mark.parametrize("bad", ["", "blue", "#12345", "400", "#808080"])
def test_parse_brand_rejects(bad):
    with pytest.raises(ValueError):
        parse_brand(bad)
