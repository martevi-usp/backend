def blank_to_none(value: str | None) -> str | None:
    """Some provider APIs use "" rather than null for an absent free-text field."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
