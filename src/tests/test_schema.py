from martevi.schema import Artwork, ArtworkSummary


def _summary(height_cm: float | None, width_cm: float | None) -> ArtworkSummary:
    return ArtworkSummary(
        id="x:1",
        provider_id="x",
        title="t",
        date=None,
        thumbnail_url=None,
        height_cm=height_cm,
        width_cm=width_cm,
    )


def test_dimensions_round_away_float_conversion_noise():
    # e.g. Cleveland reports meters; 0.07 * 100 lands on 6.999999999999999
    # in plain float arithmetic, not a clean 7.0.
    summary = _summary(0.07 * 100, 2.755905511811024 * 2.54)

    assert summary.height_cm == 7.0
    assert summary.width_cm == 7.0


def test_dimensions_round_to_one_decimal_place():
    summary = _summary(12.34, 56.789)

    assert summary.height_cm == 12.3
    assert summary.width_cm == 56.8


def test_none_dimensions_stay_none():
    summary = _summary(None, None)

    assert summary.height_cm is None
    assert summary.width_cm is None


def test_artwork_inherits_the_same_rounding():
    artwork = Artwork(
        id="x:1",
        provider_id="x",
        title="t",
        date=None,
        thumbnail_url=None,
        height_cm=0.07 * 100,
        width_cm=None,
        description=None,
        medium=None,
        culture=None,
        department=None,
        image_url=None,
        image_zoom_url=None,
        source_url=None,
    )

    assert artwork.height_cm == 7.0
