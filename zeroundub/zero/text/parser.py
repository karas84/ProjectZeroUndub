import io
import os
import re
import struct

from abc import ABC, abstractmethod
from typing import BinaryIO

from .tables.subtitles import decode_english_subtitles
from .tables import table_eu, table_jp, LASTCH, COLOR, NEWLINE


class Serializable(ABC):
    @abstractmethod
    def encode(self, offset=0):
        ...


class InGameMessageTable(Serializable):
    def __init__(
        self,
        number: int,
        offset: int,
        size: int,
        parent: "InGameMessageTable | None" = None,
        tables: "list[InGameMessageTable] | None" = None,
        messages: "list[InGameMessage] | None" = None,
    ):
        self.number = number
        self.offset = offset
        self.size = size
        self._parent = parent
        self.tables = tables if tables is not None else []
        self.messages: list["InGameMessage"] = messages if messages is not None else []

    def add_table(self, table: "InGameMessageTable"):
        if self.messages:
            raise RuntimeError("cannot add table while messages exist")

        self.tables.append(table)

    def add_message(self, message: "InGameMessage"):
        if self.tables:
            raise RuntimeError("cannot add message while tables exists")

        self.messages.append(message)

    def __str__(self):
        if self.tables:
            return f'{len(self.tables)} Table{"s" if len(self.tables) != 1 else ""}'
        else:
            return f'{len(self.messages)} Message{"s" if len(self.messages) != 1 else ""}'

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return id(self) == id(other)

    def __getitem__(self, item):
        if self.tables:
            return self.tables[item]
        else:
            return self.messages[item]

    def has_overlap(self, other):
        r1 = range(self.offset, self.offset + self.size)
        r2 = range(other.offset, other.offset + other.size)
        return len(list(set(r1) & set(r2))) != 0

    def encode(self, offset=0):
        table = self.tables if self.tables else self.messages

        encoded = io.BytesIO()
        offsets = []

        encoded.write(bytearray(len(table * 4)))
        offset += len(table) * 4

        for entry in table:
            offsets.append(offset)
            enc = entry.encode(offset)
            encoded.write(enc)
            offset += len(enc)

        encoded.seek(0, os.SEEK_SET)

        table_bin = struct.pack(f"<{len(offsets)}I", *offsets)
        encoded.write(table_bin)

        encoded.seek(0, os.SEEK_SET)

        return encoded.read()


class InGameMessage(Serializable):
    def __init__(
        self, number: int, offset: int, parent: "InGameMessageTable | None" = None, japanese: "bool | None" = False
    ):
        self.number: int = number
        self.offset: int = offset
        self._parent: "InGameMessageTable | None" = parent
        self.size: int = 0
        self.message: str = ""
        self.suffix: bytes = b""
        self.data: bytes = b""
        self.data_hex_str: str = ""
        self.japanese = japanese

    @classmethod
    def from_message(
        cls, number: int, parent: InGameMessageTable, message: str, offset=-1, suffix=b"\xff", japanese=False
    ):
        msg = cls(number, offset, parent, japanese)
        msg.message = message
        msg.suffix = suffix
        msg.encode()
        return msg

    @classmethod
    def from_data(cls, number, parent, data: bytes, offset=-1, japanese=False):
        msg = cls(number, offset, parent, japanese)
        msg._parse_data(data)
        return msg

    @staticmethod
    def _maybe_japanese(data):
        has_jp_symbols_iter = (True for x in data if x in table_jp)
        return next(has_jp_symbols_iter, False)

    @staticmethod
    def _separate_suffix(data: bytes) -> tuple[bytes, bytes]:
        match = re.match(b"^(.*?)(\xFA?\xFF*)$", data, re.DOTALL)
        assert match is not None
        data, suffix = match.groups()
        return data, suffix

    def parse_text(self, file_h: BinaryIO, size: int):
        file_h.seek(self.offset)
        data = file_h.read(size)
        return self._parse_data(data)

    def _parse_data(self, data: bytes):
        self.size = len(data)
        self.data_hex_str = " ".join(f"{x:02X}" for x in data)
        self.data, self.suffix = self._separate_suffix(data)

        text_bin = self.data

        if self.japanese is None:
            self.japanese = self._maybe_japanese(text_bin)

        font_table = table_eu if not self.japanese else table_jp

        idx = 0
        while idx < len(text_bin):
            x = text_bin[idx]

            if x == COLOR:
                idx_left = len(text_bin) - 1 - idx
                if idx_left >= 3:
                    # pylint: disable=consider-using-f-string
                    self.message += "{Color#%02X%02X%02X}" % (text_bin[idx + 1], text_bin[idx + 2], text_bin[idx + 3])
                    idx += 3
                else:
                    self.message += "{Color}"

            elif x == NEWLINE:
                self.message += "\n"

            elif self.japanese and x in font_table:
                table = font_table[x]
                idx += 1
                self.message += table[text_bin[idx]]

            elif x <= LASTCH:
                self.message += font_table["default"][x]

            else:
                self.message += f"{{0x{x:02X}}}"

            idx += 1

    @staticmethod
    def _encode_color(color_str):
        return re.sub(
            r"{Color#([A-F0-9]{2})([A-F0-9]{2})([A-F0-9]{2})}",
            f"{{0x{COLOR:02X}}}{{0x\\1}}{{0x\\2}}{{0x\\3}}",
            color_str,
        )

    def encode(self, offset=0):
        message = (
            self._encode_color(self.message)
            .replace("{Color}", f"{{0x{COLOR:02X}}}")
            .replace("\n", f"{{0x{NEWLINE:02X}}}")
        )

        encoded = io.BytesIO()

        char_table = table_jp if self.japanese is True else table_eu

        characters = re.findall(r"({0x[A-F0-9]{2}}|{.*?}|.)", message)
        for ch in characters:
            enc = None
            if len(ch) != 6:
                for name, table in char_table.items():
                    if ch in table:
                        enc = table.index(ch).to_bytes(1, "little")
                    if enc is not None and name != "default" and isinstance(name, int):
                        enc = name.to_bytes(1, "little") + enc
                    if enc is not None:
                        break
            else:
                enc = bytes.fromhex(ch[3:5])

            assert enc is not None

            encoded.write(enc)

        encoded.write(self.suffix)

        encoded.seek(0, os.SEEK_SET)
        encoded = encoded.read()
        encoded_hex_str = " ".join(f"{x:02X}" for x in encoded)

        self.data, self.suffix = self._separate_suffix(encoded)
        self.size = len(encoded)
        self.data_hex_str = encoded_hex_str

        return encoded

    def __str__(self):
        suffix_hex = "".join(f"{x:02X}" for x in self.suffix)
        return f'"{self.message}" ({suffix_hex})'

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if isinstance(other, InGameMessage):
            return self.offset == other.offset and self.size == other.size
        else:
            return id(self) == id(other)

    def has_overlap(self, other):
        r1 = range(self.offset, self.offset + self.size)
        r2 = range(other.offset, other.offset + other.size)
        return len(list(set(r1) & set(r2))) != 0


class InGameMessageParser:
    def __init__(self, file: "str | bytes | BinaryIO", table_names: "list[str] | None" = None, japanese=False):
        if isinstance(file, str):
            with open(file, "rb") as fh:
                self.file_h = io.BytesIO(fh.read())
        elif isinstance(file, bytes):
            self.file_h = io.BytesIO(file)
        elif isinstance(file, io.IOBase):
            pos = file.tell()
            file.seek(0, os.SEEK_SET)
            self.file_h = io.BytesIO(file.read())
            file.seek(pos, os.SEEK_SET)
        else:
            raise ValueError("input must be filename or open file handle")

        self.file_size = self.file_h.getbuffer().nbytes
        self.japanese = japanese

        self._boundaries: list[int] = []
        self._byte_address_read = []

        self.msg_tables = self._parse_obj(japanese=japanese)

        self.table_names = None

        if isinstance(table_names, list) and len(table_names) == len(self.msg_tables.tables):
            self.table_names = table_names

    def __getitem__(self, item):
        assert self.msg_tables is not None

        if isinstance(item, int):
            return self.msg_tables.tables[item]

        assert self.table_names is not None
        table_idx = self.table_names.index(item)
        return self.msg_tables.tables[table_idx]

    @staticmethod
    def _read_dword(f):
        return struct.unpack("<I", f.read(4))[0], f.tell()

    def next_boundary(self, offset):
        return next(b for b in self._boundaries if b > offset)

    def _parse_obj_rec(self, msg_table: InGameMessageTable):
        file_has_table = len(msg_table.tables) > 0

        if file_has_table:
            for sub_table in msg_table.tables:
                self._parse_obj_rec(sub_table)

            return

        for message in msg_table.messages:
            size = self.next_boundary(message.offset) - message.offset
            addresses = [x for x in range(message.offset, message.offset + message.size)]
            self._byte_address_read.extend(addresses)
            message.parse_text(self.file_h, size)
            message.encode()

    def _find_table_size(self, offset):
        max_offset = self.file_size
        position = -1
        maybe_table = []
        address_read = []
        while max_offset > position:
            address_read.extend([x for x in range(self.file_h.tell(), self.file_h.tell() + 4)])
            if self.file_h.tell() + 4 >= self.file_size:
                return False, 0
            address, position = self._read_dword(self.file_h)
            max_offset = min(address, max_offset)
            if address > self.file_size or max_offset < offset:
                return False, 0
            maybe_table.append(address)
        self._byte_address_read.extend(address_read)
        return maybe_table, max_offset - offset

    def _parse_obj_tables(
        self, number, offset=0, msg_table: "InGameMessageTable | None" = None, japanese: "bool | None" = False
    ):
        self.file_h.seek(offset, os.SEEK_SET)

        table, tbl_size = self._find_table_size(offset)

        if table is False:
            return

        cur_msg_table = InGameMessageTable(number, offset, tbl_size, msg_table)
        self._boundaries.append(offset)

        if msg_table is not None:
            msg_table.add_table(cur_msg_table)

        for n, offset_start in enumerate(table):
            has_subtable = self._parse_obj_tables(n, offset_start, cur_msg_table, japanese) is not None
            if not has_subtable:
                cur_msg_table.add_message(InGameMessage(n, offset_start, cur_msg_table, japanese))
                self._boundaries.append(offset_start)

        return cur_msg_table

    def _parse_obj(self, japanese: "bool | None" = None):
        msg_tables = self._parse_obj_tables(number=0, japanese=japanese)
        assert msg_tables is not None

        self._boundaries.append(self.file_size)
        self._boundaries = list(set(self._boundaries))
        self._boundaries.sort()

        for table in msg_tables.tables:
            self._parse_obj_rec(table)

        return msg_tables

    def encode(self):
        assert self.msg_tables is not None
        return self.msg_tables.encode()


def inject_english_subtitles(file_h: BinaryIO):
    ig_msg_parser = InGameMessageParser(file_h, japanese=False)

    parent = ig_msg_parser[53]
    parent.messages = []

    subtitles_en = decode_english_subtitles(file_h)

    for n, sub in subtitles_en.items():
        msg = InGameMessage.from_message(n, parent, sub)
        parent.messages.append(msg)

    return ig_msg_parser.encode()
