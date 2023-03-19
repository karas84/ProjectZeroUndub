import os
import math


def copy_file(src, dst, callback=None):
    with open(src, "rb") as src_fh:
        src_size = src_fh.seek(0, os.SEEK_END)
        src_fh.seek(0, os.SEEK_SET)

        block_size = 2**20

        if callback:
            block_num = int(math.ceil(src_size / block_size))
            callback(block_num)

        with open(dst, "wb") as dst_fh:
            while True:
                data = src_fh.read(block_size)

                if not data:
                    break

                dst_fh.write(data)

                if callback:
                    callback()
