import re

_UNIT_TO_CM: dict[str, float] = {
    "mm": 0.1,
    "cm": 1.0,
    "m": 100.0,
    "in": 2.54,
    "inches": 2.54,
    '"': 2.54,
    "'": 2.54,
}

_NUMBER = r"(\d+(?:\.\d+)?)"
_UNIT = r"(mm|cm|m|in(?:ches)?|\"|')"

_PAIR = re.compile(rf"{_NUMBER}\s*{_UNIT}?\s*[x×]\s*{_NUMBER}\s*{_UNIT}?", re.IGNORECASE)
_UNIT_AFTER_NUMBER = re.compile(r"\d+(?:\.\d+)?\s*(mm|cm|m)\b", re.IGNORECASE)


def to_cm(value: float, unit: str) -> float | None:
    factor = _UNIT_TO_CM.get(unit.lower())
    if factor is None:
        return None
    return value * factor


def _label_pattern(label: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z]){re.escape(label)}\s*{_NUMBER}\s*{_UNIT}?", re.IGNORECASE)


def _find_labeled(text: str, labels: tuple[str, ...], default_unit: str | None) -> float | None:
    for label in labels:
        match = _label_pattern(label).search(text)
        if match:
            unit = match.group(2) or default_unit
            if unit is None:
                return None
            return to_cm(float(match.group(1)), unit)
    return None


def parse_labeled(
    text: str | None,
    *,
    height_labels: tuple[str, ...],
    width_labels: tuple[str, ...],
    default_unit: str | None = None,
) -> tuple[float | None, float | None]:
    """Finds a '<label> <number> <unit?>' match independently for height and width.
    Returns (None, None) the moment either label is absent — never returns one
    dimension without the other."""
    if not text:
        return (None, None)
    height = _find_labeled(text, height_labels, default_unit)
    width = _find_labeled(text, width_labels, default_unit)
    if height is None or width is None:
        return (None, None)
    return (height, width)


def _first_metric_unit(text: str) -> str | None:
    match = _UNIT_AFTER_NUMBER.search(text)
    return match.group(1) if match else None


def parse_positional(text: str | None) -> tuple[float | None, float | None]:
    """First '<num> [unit] (x|×) <num> [unit]' match. Tolerates 'x'/'×' and optional
    space before the unit; if neither number carries a unit inline, falls back to the
    first metric unit found anywhere later in the string. Returns (None, None) if no
    clean pair (or no resolvable unit) is found."""
    if not text:
        return (None, None)
    match = _PAIR.search(text)
    if not match:
        return (None, None)
    num1, unit1, num2, unit2 = match.groups()
    unit = unit2 or unit1 or _first_metric_unit(text)
    if unit is None:
        return (None, None)
    height = to_cm(float(num1), unit)
    width = to_cm(float(num2), unit)
    return (height, width)
