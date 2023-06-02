import os
import io
import math
import struct

from typing import BinaryIO, Union
from dataclasses import dataclass

from ..utils.file import SubFile


data_types = {b"TIM2": "TM2", b"\x50\x10\x00\x00": "SGD"}


def parse_pk2_archive(pk2_file_h: BinaryIO):
    raise RuntimeError()


@dataclass
class PK2ArchiveEntry:
    offset: int
    size: int
    type: str


class PK2Archive:
    def __init__(self, pk2_data: BinaryIO, copy: bool = False):
        if copy:
            pk2_data = io.BytesIO(pk2_data.read())

        self.data = pk2_data
        self.entries: list[PK2ArchiveEntry] = []

        sz = pk2_data.seek(0, os.SEEK_END)
        pk2_data.seek(0, os.SEEK_SET)

        num_files: int = struct.unpack("<4I", pk2_data.read(16))[0]
        num_byte_addrs = int(math.ceil(num_files / 4) * 4) * 4

        file_addrs = pk2_data.read(num_byte_addrs)[: num_files * 4]
        offsets: list[int] = list(struct.unpack(f"<{num_files}I", file_addrs))

        sequential = len(offsets) > 1 and offsets[1] == 0

        if not sequential:
            sizes = [offsets[i + 1] - offsets[i] for i in range(len(offsets) - 1)]
            sizes.append(sz - offsets[-1])
            for addr, size in zip(offsets, sizes):
                pk2_data.seek(addr, os.SEEK_SET)
                data_type = data_types.get(pk2_data.read(4), "BIN")
                self.entries.append(PK2ArchiveEntry(addr, size, data_type))
        else:
            next_addr: int = 0x0
            while next_addr + 0x20 < sz:
                next_addr += 0x10
                pk2_data.seek(next_addr)
                file_size: int = struct.unpack("<4I", pk2_data.read(16))[0]
                file_addr = pk2_data.tell()
                next_addr += file_size
                data_type = data_types.get(pk2_data.read(4), "BIN")
                self.entries.append(PK2ArchiveEntry(file_addr, file_size, data_type))

            assert len(self.entries) == num_files

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __getitem__(self, item: int):
        assert item < len(self.entries)
        entry = self.entries[item]
        return SubFile(self.data, entry.offset, entry.size)

    def __setitem__(self, item: int, data: Union[bytes, bytearray, SubFile]):
        assert item < len(self.entries)
        entry = self.entries[item]
        if isinstance(data, SubFile):
            data.seek(0, os.SEEK_SET)
            data_bin = data.read()
        else:
            data_bin = data
        assert len(data_bin) == entry.size
        self.data.seek(entry.offset, os.SEEK_SET)
        self.data.write(data_bin)


def main():
    for lang in ("E", "F", "G", "I", "S"):
        pk2_file = f"/home/baecchi/Documents/PyCharm/ProjectZeroUndub/MODELS/PL_MTOP_{lang}.PK2"

        with open(pk2_file, "rb") as file_h:
            pk2_archive = PK2Archive(file_h)
            for i, entry in enumerate(pk2_archive):
                data = entry.read()
                out_dir_path = os.path.splitext(pk2_file)[0]
                os.makedirs(out_dir_path, exist_ok=True)
                with open(os.path.join(out_dir_path, f"file{i:04d}.tm2"), "wb") as tm2_out_h:
                    tm2_out_h.write(data)


if __name__ == "__main__":
    main()
