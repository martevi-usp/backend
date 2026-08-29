from pydantic import BaseModel


class ArtworkSummary(BaseModel):
    id: str                       # "{provider_id}:{external_id}"
    provider_id: str
    title: str
    date: str | None              # translated where free-text
    thumbnail_url: str | None
    height_cm: float | None
    width_cm: float | None


class Artwork(ArtworkSummary):
    description: str | None       # wall note / history — translated
    medium: str | None            # translated
    culture: str | None           # translated
    department: str | None        # section/department, only when the provider exposes one
    image_url: str | None         # highest-resolution image the provider offers
    image_zoom_url: str | None    # IIIF base URL / deep-zoom source, when the provider offers one
    source_url: str | None        # link back to the museum's own object page
