from dataclasses import dataclass


@dataclass
class TOCEntry:
    name: str
    number: int
    offset: int = 0
    size: int = -1


@dataclass
class FileEntry:
    offset: int
    size: int
