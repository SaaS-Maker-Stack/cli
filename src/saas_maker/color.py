"""Hex color -> OKLCH hue, so the wizard accepts `#0066ff` as well as `262`.

The template derives its whole accent palette from one OKLCH hue angle
(`--brand-hue`). sRGB -> linear -> OKLab (Björn Ottosson's matrices) -> hue.
"""

import math
import re

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_hue(value: str) -> int:
    """`#0066ff` -> 262. Raises ValueError for anything that is not a hex color."""
    match = HEX_RE.match(value.strip())
    if not match:
        raise ValueError(f"'{value}' is not a hex color")
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    r, g, b = (_srgb_to_linear(int(digits[i : i + 2], 16) / 255) for i in (0, 2, 4))

    l_ = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m_ = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s_ = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(x) ** (1 / 3), x) for x in (l_, m_, s_))

    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    if math.hypot(a, b_) < 0.01:
        raise ValueError(f"'{value}' is a gray — it has no hue; pick a chromatic color")
    return round(math.degrees(math.atan2(b_, a))) % 360


def parse_brand(value: str) -> int:
    """Accepts a hue angle (0-360) or a hex color."""
    text = value.strip()
    if text.isdigit():  # a bare number is an angle; hex colors need the '#'
        if int(text) > 360:
            raise ValueError("hue angle must be between 0 and 360 (prefix hex colors with #)")
        return int(text)
    return hex_to_hue(text)
