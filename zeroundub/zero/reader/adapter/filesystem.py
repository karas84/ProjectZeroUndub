import os

from typing import BinaryIO, cast
from contextlib import contextmanager

from .abstract import AbstractAdapter


class FilesystemAdapter(AbstractAdapter):
    def test_file(self, file_path: str) -> bool:
        return os.path.isfile(file_path) and os.access(file_path, os.R_OK)

    def read_file(self, file_name: str, size=-1, offset=0) -> bytes:
        with self.open(file_name) as file_h:
            file_h = cast(BinaryIO, file_h)
            file_h.seek(offset)
            return file_h.read(size)

    def get_img_bd_size(self) -> int:
        assert self.img_bd_path is not None
        return os.stat(self.img_bd_path).st_size

    def find_file(self, file_name: str) -> "str | None":
        all_files = next(os.walk(self.load_path))[2]
        file_name_upper = file_name.upper()
        file_match_gen = (file_name for file_name in all_files if file_name.upper() == file_name_upper)
        file_name_match = next(file_match_gen, None)

        if file_name_match is not None:
            file_name_match = os.path.join(self.load_path, file_name_match)

        return file_name_match

    @contextmanager
    def open(self, file_name: str) -> BinaryIO:  # pyright: ignore[reportGeneralTypeIssues]
        with open(file_name, "rb") as file_h:
            yield cast(BinaryIO, file_h)
