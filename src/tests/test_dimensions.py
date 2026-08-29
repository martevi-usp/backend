import pytest

from martevi.providers._internal.dimensions import parse_labeled, parse_positional, to_cm


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        pytest.param(154, "mm", 15.4, id="mm-to-cm"),
        pytest.param(0.806, "m", 80.6, id="m-to-cm"),
        pytest.param(10, "furlong", None, id="unknown-unit-returns-none"),
    ],
)
def test_to_cm(value, unit, expected):
    result = to_cm(value, unit)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    "text,height_labels,width_labels,default_unit,expected",
    [
        pytest.param(
            "height 154 mm x width 265 mm",
            ("height",),
            ("width",),
            None,
            (15.4, 26.5),
            id="extracts-height-and-width",
        ),
        pytest.param(
            "height 154 x width 265",
            ("height",),
            ("width",),
            "mm",
            (15.4, 26.5),
            id="uses-default-unit-when-missing",
        ),
        pytest.param(
            # Harvard-style: "h. 41.9 cm x diam. 28.5 cm" — no "w." label present.
            "h. 41.9 cm x diam. 28.5 cm",
            ("h.", "height"),
            ("w.", "width"),
            None,
            (None, None),
            id="bails-when-width-label-absent",
        ),
        pytest.param(None, ("h.",), ("w.",), None, (None, None), id="returns-none-for-empty-text"),
    ],
)
def test_parse_labeled(text, height_labels, width_labels, default_unit, expected):
    result = parse_labeled(
        text, height_labels=height_labels, width_labels=width_labels, default_unit=default_unit
    )
    if expected == (None, None):
        assert result == (None, None)
    else:
        height, width = result
        expected_height, expected_width = expected
        assert height == pytest.approx(expected_height)
        assert width == pytest.approx(expected_width)


@pytest.mark.parametrize(
    "text,expected",
    [
        pytest.param(
            "31.2 x 14.3 cm (12 5/16 x 5 5/8 in)",
            (31.2, 14.3),
            id="x-separator-with-trailing-unit",
        ),
        pytest.param('9.3 × 6.1 cm (3 11/16 × 2 3/8")', (9.3, 6.1), id="multiplication-sign"),
        pytest.param(
            '47.3 x 34.9 x 4.8cm (18 5/8 x 13 3/4 x 1 7/8")',
            (47.3, 34.9),
            id="no-space-before-unit-on-third-number",
        ),
        pytest.param(
            "<20> v. : ill. (some col.)", (None, None), id="bails-on-non-dimensional-text"
        ),
        pytest.param(None, (None, None), id="returns-none-for-empty-text"),
    ],
)
def test_parse_positional(text, expected):
    result = parse_positional(text)
    if expected == (None, None):
        assert result == (None, None)
    else:
        height, width = result
        expected_height, expected_width = expected
        assert height == pytest.approx(expected_height)
        assert width == pytest.approx(expected_width)
