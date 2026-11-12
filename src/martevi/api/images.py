import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response

from martevi.api.deps import get_http_client
from martevi.providers.adapters.aic import aic_headers

router = APIRouter(prefix="/images", tags=["images"])

_AIC_IIIF = "https://www.artic.edu/iiif/2"
# Strict allow-lists: this route fetches a third-party URL on a caller's
# behalf, so every path segment is validated and nothing else is forwarded.
_IMAGE_ID = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_REGION = re.compile(r"^(full|square)$")
_SIZE = re.compile(r"^(full|max|\d{1,4},|,\d{1,4}|\d{1,4},\d{1,4}|!\d{1,4},\d{1,4})$")
_FILENAME = re.compile(r"^default\.(jpg|png|webp)$")
_MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


@router.get("/aic/{image_id}/{region}/{size}/0/{filename}")
async def aic_image(
    image_id: str,
    region: str,
    size: str,
    filename: str,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    """Serves an AIC IIIF image. AIC's image server only answers requests that
    carry its identifying AIC-User-Agent header, which browsers can't send."""
    if not (
        _IMAGE_ID.match(image_id)
        and _REGION.match(region)
        and _SIZE.match(size)
        and _FILENAME.match(filename)
    ):
        raise HTTPException(404, "Unknown image")

    try:
        upstream = await client.get(
            f"{_AIC_IIIF}/{image_id}/{region}/{size}/0/{filename}", headers=aic_headers()
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Image source unavailable") from exc
    if upstream.status_code == 404:
        raise HTTPException(404, "Unknown image")
    if upstream.status_code != 200:
        raise HTTPException(502, "Image source unavailable")

    return Response(
        content=upstream.content,
        media_type=_MEDIA_TYPES[filename.rsplit(".", 1)[1]],
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
