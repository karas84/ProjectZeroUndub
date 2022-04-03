from typing import BinaryIO
from contextlib import contextmanager
from pycdlib.pycdlibexception import PyCdlibInvalidISO

from ...dvd import CDDVD
from .abstract import AbstractAdapter


class ISOAdapter(AbstractAdapter):

    def __init__(self, load_path: str):
        super().__init__(load_path)

        try:
            self.iso = CDDVD(load_path)
        except (IsADirectoryError, PermissionError, FileNotFoundError, PyCdlibInvalidISO):
            raise RuntimeError('cannot open iso')

    def test_file(self, file_path: str) -> bool:
        return self.iso.find_file(file_path)

    def read_file(self, file_name: str, size=-1, offset=0) -> bytes:
        return self.iso.read_file(file_name, size, offset)

    def get_img_db_size(self) -> int:
        return self.iso.get_file_size(self.img_bd_path)

    def find_file(self, file_name: str) -> str:
        return self.iso.find_file(file_name)

    @contextmanager
    def open(self, file_name: str) -> BinaryIO:
        with self.iso.open(file_name) as file_h:
            yield file_h
