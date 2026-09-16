from pydantic import BaseModel, field_validator


class ArtworkSummary(BaseModel):
    id: str                       # "{provider_id}:{external_id}"
    provider_id: str
    title: str
    date: str | None              # translated where free-text
    thumbnail_url: str | None
    height_cm: float | None
    width_cm: float | None

    # Adapters convert dimensions from whatever unit a provider reports
    # (inches, meters, free-text labels — see providers/_internal/dimensions.py)
    # and that arithmetic routinely leaves float noise (e.g. a Cleveland
    # meters value times 100 landing on 6.999999999999999 instead of 7.0).
    # Rounding once here, at the schema boundary every adapter's output
    # passes through, means no adapter has to remember to do it itself.
    @field_validator("height_cm", "width_cm")
    @classmethod
    def _round_cm(cls, value: float | None) -> float | None:
        return round(value, 1) if value is not None else None


class Artwork(ArtworkSummary):
    description: str | None       # wall note / history — translated
    medium: str | None            # translated
    culture: str | None           # translated
    department: str | None        # section/department, only when the provider exposes one
    image_url: str | None         # highest-resolution image the provider offers
    image_zoom_url: str | None    # IIIF base URL / deep-zoom source, when the provider offers one
    source_url: str | None        # link back to the museum's own object page
