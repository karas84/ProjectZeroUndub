import os
import re
import struct

from typing import BinaryIO, cast
from contextlib import contextmanager

from .entry import TOCEntry, FileEntry
from .adapter import FilesystemAdapter, ISOAdapter
from ...utils.file import SubFile


def is_iso_file(file_path):
    return os.path.isfile(file_path) and os.path.splitext(file_path)[1].upper() == ".ISO"


class PJZReader:
    re_dat_entry = re.compile(r"([A-Z0-9_]+)_([A-Z0-9]+):([0-9]+)")

    def __init__(self, load_path):
        self.load_path = load_path

        if is_iso_file(load_path):
            self.adapter = ISOAdapter(self.load_path)
        elif os.path.isdir(load_path):
            self.adapter = FilesystemAdapter(self.load_path)
        else:
            raise ValueError("load_path must be iso or filesystem path")

        self.adapter.setup()

        toc_entry_list = self.prepare_toc_and_entries()

        self.toc_entry_list = toc_entry_list

        self.file_name_index = self.make_file_name_index()

    def parse_cd_file_dat(self, elf_path):
        elf_bin = self.adapter.read_file(elf_path)

        if not elf_bin:
            return None

        try:
            cd_file_dat_start = elf_bin.index(b"CD_FILE_DAT:T")
            cd_file_dat_end = elf_bin.index(b",;", cd_file_dat_start)
            cd_file_dat = elf_bin[cd_file_dat_start:cd_file_dat_end]
        except ValueError:
            return None

        cd_file_dat = cd_file_dat.replace(b"\x2C\x5C\x00", b"\x2C").decode("ascii")
        section_name, file_list = cd_file_dat.split("=e", 1)

        file_list = file_list.rstrip(",").split(",")

        entry_matches = [self.re_dat_entry.match(entry) for entry in file_list]

        if not all(entry_matches):
            return None

        entry_matches = cast(list[re.Match[str]], entry_matches)

        toc_entry_list = [
            TOCEntry(f"{entry.group(1)}.{entry.group(2)}", int(entry.group(3))) for entry in entry_matches
        ]

        return toc_entry_list

    def parse_img_hd(self, img_hd_path):
        img_hd_bin = self.adapter.read_file(img_hd_path)

        if not img_hd_bin:
            return None

        if len(img_hd_bin) % 8 != 0:
            return None

        num_int32 = len(img_hd_bin) // 4
        file_data = struct.unpack(f"<{num_int32}I", img_hd_bin)

        file_entry_list = [FileEntry(file_data[i] * 0x800, file_data[i + 1]) for i in range(0, len(file_data), 2)]

        return file_entry_list

    @staticmethod
    def validate_toc(toc_entry_list, file_entry_list):
        return (
            toc_entry_list is not None and file_entry_list is not None and len(toc_entry_list) == len(file_entry_list)
        )

    def validate_image_bd_size(self, file_entry_list):
        max_file_entry_position = max([fe.offset + fe.size for fe in file_entry_list])
        image_bd_size = self.adapter.get_img_bd_size()
        return image_bd_size >= max_file_entry_position

    def print_files(self):
        for toc_entry in self.toc_entry_list:
            print(f"{toc_entry.name} {toc_entry.size}")

    def list_files(self) -> list[str]:
        return [toc_entry.name for toc_entry in self.toc_entry_list]

    def num_files(self):
        return len(self.toc_entry_list)

    def file_exist(self, file_name):
        return file_name in ("", ".") or file_name in self.file_name_index

    def find_entry(self, file_name) -> "TOCEntry | None":
        if file_name not in self.file_name_index:
            return None

        toc_entry = self.file_name_index[file_name]

        return toc_entry

    def read_file(self, file_name, size=-1, offset=0):
        assert self.adapter.img_bd_path is not None

        toc_entry = self.find_entry(file_name)

        if toc_entry is None:
            return RuntimeError("file not found")

        bytes_left = max(0, toc_entry.size - offset)
        if size == -1 or size > bytes_left:
            size = bytes_left

        return self.adapter.read_file(self.adapter.img_bd_path, size, toc_entry.offset + offset)

    @contextmanager
    def open(self, file_name):
        assert self.adapter.img_bd_path is not None

        toc_entry = self.find_entry(file_name)

        if toc_entry is None:
            return RuntimeError("file not found")

        with self.adapter.open(self.adapter.img_bd_path) as file_h:
            file_h = cast(BinaryIO, file_h)
            yield SubFile(file_h, toc_entry.offset, toc_entry.size)  # pylint: disable=abstract-class-instantiated

    def prepare_toc_and_entries(self):
        if not (self.adapter.elf_path and self.adapter.img_hd_path and self.adapter.img_bd_path):
            raise RuntimeError("missing adapter paths for elf or img_hd or img_bd")

        if not all(
            map(self.adapter.test_file, (self.adapter.elf_path, self.adapter.img_hd_path, self.adapter.img_bd_path))
        ):
            raise RuntimeError("wrong root folder")

        toc_entry_list = self.parse_cd_file_dat(self.adapter.elf_path)
        file_entry_list = self.parse_img_hd(self.adapter.img_hd_path)

        if not toc_entry_list or not file_entry_list:
            raise RuntimeError("cannot read elf for entries")

        if not self.validate_toc(toc_entry_list, file_entry_list) or not self.validate_image_bd_size(file_entry_list):
            raise RuntimeError("wrong format")

        for toc_entry, file_entry in zip(toc_entry_list, file_entry_list):
            toc_entry.offset = file_entry.offset
            toc_entry.size = file_entry.size

        return toc_entry_list

    def make_file_name_index(self) -> dict[str, TOCEntry]:
        return {entry.name: entry for entry in self.toc_entry_list}

    def __repr__(self):
        return (
            f"{self.__class__.__name__}[{self.adapter.__class__.__name__}="
            f"{os.path.basename(self.adapter.load_path)}]"
        )
