from abc import ABC, abstractmethod

from martevi.domain import Puzzle, PuzzleStory, TourLink


class PuzzleRepository(ABC):
    @abstractmethod
    def list_all(self) -> list[Puzzle]: ...

    @abstractmethod
    def get(self, puzzle_id: str) -> Puzzle | None: ...

    @abstractmethod
    def stories(self, puzzle_id: str) -> list[PuzzleStory]: ...


class TourLinkRepository(ABC):
    @abstractmethod
    def list_all(self, museum: str | None = None) -> list[TourLink]: ...
