from abc import ABC, abstractmethod

_PUZZLE_PIECES = (12, 24, 54, 96)


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _http_url(value: str, field: str) -> str:
    if not _text(value, field).startswith(("http://", "https://")):
        raise ValueError(f"{field} must be an http(s) URL, got {value!r}")
    return value


class CuratedItem(ABC):
    """Base of everything curated by hand rather than fetched from a museum
    provider. Validation lives in ``__init__`` so an invalid object cannot
    exist; attributes are private and exposed read-only."""

    def __init__(self, id: str | int) -> None:
        if isinstance(id, str):
            _text(id, "id")
        self._id = id

    @property
    def id(self) -> str | int:
        return self._id

    @property
    @abstractmethod
    def kind(self) -> str: ...


class Puzzle(CuratedItem):
    def __init__(
        self,
        id: str,
        title: str,
        credit: str,
        src: str,
        rights: str,
        verified: bool,
        movement: str,
        pieces: int,
    ) -> None:
        super().__init__(id)
        if pieces not in _PUZZLE_PIECES:
            raise ValueError(f"pieces must be one of {_PUZZLE_PIECES}, got {pieces}")
        self._title = _text(title, "title")
        self._credit = _text(credit, "credit")
        self._src = _http_url(src, "src")
        self._rights = _text(rights, "rights")
        self._verified = bool(verified)
        self._movement = _text(movement, "movement")
        self._pieces = pieces

    kind = "puzzle"

    title = property(lambda self: self._title)
    credit = property(lambda self: self._credit)
    src = property(lambda self: self._src)
    rights = property(lambda self: self._rights)
    verified = property(lambda self: self._verified)
    movement = property(lambda self: self._movement)
    pieces = property(lambda self: self._pieces)

    def progress_pct(self, placed: int) -> int:
        if not 0 <= placed <= self._pieces:
            raise ValueError(f"placed must be within 0..{self._pieces}, got {placed}")
        return placed * 100 // self._pieces


class PuzzleStory(CuratedItem):
    def __init__(
        self, id: int, puzzle_id: str, unlock_pct: int, lede: str, body: str
    ) -> None:
        super().__init__(id)
        if not 0 <= unlock_pct <= 100:
            raise ValueError(f"unlock_pct must be within 0..100, got {unlock_pct}")
        self._puzzle_id = _text(puzzle_id, "puzzle_id")
        self._unlock_pct = unlock_pct
        self._lede = _text(lede, "lede")
        self._body = _text(body, "body")

    kind = "puzzle_story"

    puzzle_id = property(lambda self: self._puzzle_id)
    unlock_pct = property(lambda self: self._unlock_pct)
    lede = property(lambda self: self._lede)
    body = property(lambda self: self._body)

    def unlocked_at(self, progress_pct: int) -> bool:
        return progress_pct >= self._unlock_pct


class TourLink(CuratedItem):
    def __init__(
        self, id: int, museum: str, title: str, url: str, country: str | None = None
    ) -> None:
        super().__init__(id)
        self._museum = _text(museum, "museum")
        self._country = None if country is None else _text(country, "country")
        self._title = _text(title, "title")
        self._url = _http_url(url, "url")

    kind = "tour_link"

    museum = property(lambda self: self._museum)
    country = property(lambda self: self._country)
    title = property(lambda self: self._title)
    url = property(lambda self: self._url)
