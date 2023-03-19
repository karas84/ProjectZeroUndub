import os
import io
import errno

from typing import BinaryIO


class SubFile(io.BufferedIOBase, BinaryIO):  # pylint: disable=abstract-method
    def __init__(self, file_h: BinaryIO, offset: int, size: int):
        self.file_h: BinaryIO = file_h
        self.offset: int = offset
        self.size: int = size
        self.position: int = 0

    def tell(self):
        return self.position

    def seek(self, position: int, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            next_position = min(self.size, position)
        elif whence == os.SEEK_CUR:
            next_position = min(self.size, self.position + position)
        elif whence == os.SEEK_END:
            next_position = min(self.size, self.size + position)
        else:
            raise OSError(errno.ENXIO, os.strerror(errno.ENXIO))

        if next_position < 0:
            raise OSError(errno.EINVAL, os.strerror(errno.EINVAL))

        self.position = next_position

        return self.position

    def read(self, size=-1, offset=0):
        if offset > 0:
            self.seek(self.position + offset)

        if (isinstance(size, int) and size == -1) or size is None:
            size = self.size - self.position
        elif isinstance(size, int) and size >= 0:
            size = min(size, self.size - self.position)
        else:
            raise TypeError(f"argument should be integer or None, not '{type(size)}'")

        self.file_h.seek(self.offset + self.position)
        self.position += size

        return self.file_h.read(size)

    def write(self, data):
        self.file_h.seek(self.offset + self.position)
        bytes_to_write = min(self.size - self.position, len(data))
        data_to_write = data[:bytes_to_write]
        self.file_h.write(data_to_write)
        self.position += bytes_to_write
