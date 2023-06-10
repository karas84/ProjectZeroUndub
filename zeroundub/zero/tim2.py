import os
import io
import scipy
import struct
import numpy as np

from typing import Union, BinaryIO
from functools import lru_cache


class InvalidTim2FormatException(Exception):
    pass


class Tim2ImageData:
    bpp_map = {1: 16, 2: 24, 3: 32, 4: 4, 5: 8}
    bpp_map_inv = {v: k for k, v in bpp_map.items()}
    header_size = 48

    def __init__(
        self,
        total_length: int,
        palette_length: int,
        data_length: int,
        header_length: int,
        color_entries: int,
        image_format: int,
        mipmap_count: int,
        clut_format: int,
        bbp: int,
        width: int,
        height: int,
        gs_tex0: int,
        gs_tex1: int,
        gs_regs: int,
        gs_tex_clut: int,
    ):
        self.total_length: int = total_length  # 4 - Total Image Length
        self.palette_length: int = palette_length  # 4 - Palette Length
        self.data_length: int = data_length  # 4 - Image Data Length
        self.header_length: int = header_length  # 2 - Header Length
        self.color_entries: int = color_entries  # 2 - Color Entries
        self.image_format: int = image_format  # 1 - Image Format (0=8bpp w/ palette?)
        self.mipmap_count: int = mipmap_count  # 1 - Mipmap Count
        self.clut_format: int = clut_format  # 1 - CLUT Format
        self.bpp: int = bbp  # 1 - Bits Per Pixel (1=16bbp, 2=24bpp, 3=32bbp, 4=4bbp, 5=8bpp)
        self.width: int = width  # 2 - Image Width
        self.height: int = height  # 2 - Image Height
        self.gs_tex0: int = gs_tex0  # 8 - GsTEX0
        self.gs_tex1: int = gs_tex1  # 8 - GsTEX1
        self.gs_regs: int = gs_regs  # 4 - GsRegs
        self.gs_tex_clut: int = gs_tex_clut  # 4 - GsTexClut

        self.linear_palette: bool = False

        self.data: Union[bytearray, None] = None  # X - User Data (optional) (length = HeaderLength - 48)
        self.palette: Union[bytearray, None] = None

    def post_init(self, file_handle: BinaryIO):
        self.bpp = Tim2ImageData.bpp_map.get(self.bpp, self.bpp)

        data_len = self.total_length - Tim2ImageData.header_size

        data = file_handle.read(data_len)

        if len(data) != data_len:
            raise RuntimeError("wrong tim2 texture format")

        self.data = bytearray(data[: self.data_length])
        self.palette = bytearray(data[self.data_length :])

        if len(self.palette) != self.palette_length:
            raise InvalidTim2FormatException("unexpected palette size")

        self.linear_palette = self.clut_format & 0x80 != 0
        self.clut_format &= 0x7F


class Tim2Image:
    def __init__(self, file_handle):
        self.signature: bytes  # 4 - Signature (TIM2)
        self.version: int  # 2 - Version
        self.num_images: int  # 2 - Number of Images

        self.image: Union[Tim2ImageData, None] = None

        self.post_init(file_handle)

    def post_init(self, file_handle):
        sz = file_handle.seek(0, os.SEEK_END)
        file_handle.seek(0, os.SEEK_SET)

        if sz < 56:
            raise InvalidTim2FormatException("header too small")

        header = file_handle.read(16)
        if header[:4] != b"TIM2":
            raise InvalidTim2FormatException("invalid signature")

        self.signature = header
        self.version, self.num_images = struct.unpack("<HH", header[4:8])

        if self.num_images != 1:
            raise InvalidTim2FormatException("only one image per tim2 supported")

        img_meta = file_handle.read(48)

        if len(img_meta) != 48:
            raise InvalidTim2FormatException("not enough data to parse")

        tim2_image_data = Tim2ImageData(*struct.unpack("<IIIHHBBBBHHQQII", img_meta))
        tim2_image_data.post_init(file_handle)

        self.image = tim2_image_data

    def to_bytes(self):
        assert self.image and self.image.data and self.image.palette
        out_handle = io.BytesIO()
        out_handle.write(b"TIM2")
        out_handle.write(struct.pack("<H", self.version))
        out_handle.write(struct.pack("<H", self.num_images))
        out_handle.write(b"\x00" * 8)
        out_handle.write(struct.pack("<I", self.image.total_length))
        out_handle.write(struct.pack("<I", self.image.palette_length))
        out_handle.write(struct.pack("<I", self.image.data_length))
        out_handle.write(struct.pack("<H", self.image.header_length))
        out_handle.write(struct.pack("<H", self.image.color_entries))
        out_handle.write(struct.pack("<B", self.image.image_format))
        out_handle.write(struct.pack("<B", self.image.mipmap_count))
        out_handle.write(struct.pack("<B", self.image.clut_format | (self.image.linear_palette * 0x80)))
        out_handle.write(struct.pack("<B", self.image.bpp_map_inv[self.image.bpp]))
        out_handle.write(struct.pack("<H", self.image.width))
        out_handle.write(struct.pack("<H", self.image.height))
        out_handle.write(struct.pack("<Q", self.image.gs_tex0))
        out_handle.write(struct.pack("<Q", self.image.gs_tex1))
        out_handle.write(struct.pack("<I", self.image.gs_regs))
        out_handle.write(struct.pack("<I", self.image.gs_tex_clut))
        out_handle.write(self.image.data)
        out_handle.write(self.image.palette)
        return out_handle.getvalue()


first_row = 60
idx_start = (
    192,
    192,
    189,
    187,
    185,
    183,
    182,
    181,
    180,
    179,
    178,
    177,
    176,
    176,
    175,
    175,
    174,
    174,
    174,
    172,
    172,
    172,
    172,
    172,
    172,
    172,
    172,
    172,
    172,
    172,
    172,
    172,
    172,
    174,
    174,
    174,
    175,
    175,
    176,
    176,
    177,
    178,
    179,
    180,
    181,
    182,
    183,
    185,
    187,
    189,
    192,
    192,
)
idx_num = (
    15,
    15,
    21,
    25,
    29,
    33,
    35,
    37,
    39,
    41,
    43,
    45,
    47,
    47,
    49,
    49,
    51,
    51,
    51,
    55,
    55,
    55,
    55,
    55,
    55,
    55,
    55,
    55,
    55,
    55,
    55,
    55,
    55,
    51,
    51,
    51,
    49,
    49,
    47,
    47,
    45,
    43,
    41,
    39,
    37,
    35,
    33,
    29,
    25,
    21,
    15,
    15,
)


def patch_pl_mtop(tim2_eu_io: BinaryIO, tim2_jp_io: BinaryIO):
    tim2img_eu = Tim2Image(tim2_eu_io)
    assert tim2img_eu.image and tim2img_eu.image.data and tim2img_eu.image.palette

    tim2img_jp = Tim2Image(tim2_jp_io)
    assert tim2img_jp.image and tim2img_jp.image.data and tim2img_jp.image.palette

    indices = []
    for i, (s, n) in enumerate(zip(idx_start, idx_num)):
        r = (first_row + i) * tim2img_eu.image.width
        indices.extend(list(range(r + s, r + s + n + 1)))

    p_eu = list(struct.iter_unpack("<4B", tim2img_eu.image.palette))
    p_jp = list(struct.iter_unpack("<4B", tim2img_jp.image.palette))

    refilter_map = None
    if not tim2img_eu.image.linear_palette:
        p_eu, refilter_map = defilter_palette(p_eu)
    if not tim2img_jp.image.linear_palette:
        p_jp, _ = defilter_palette(p_jp)

    def np_take(pal: list, arr: bytearray):
        return np.take(pal, np.frombuffer(arr, dtype=np.uint8), axis=0).astype(np.uint8)

    img_eu = np_take(p_eu, tim2img_eu.image.data)
    img_jp = np_take(p_jp, tim2img_jp.image.data)

    def unique_colors(img: np.ndarray):
        return np.unique(img, axis=0)

    img_eu[indices] = img_eu[-1]
    colors_eu = unique_colors(img_eu)
    p_eu = colors_eu.tolist()

    color_errors: dict[tuple, list] = {}
    for idx in indices:
        jp_col = img_jp[idx]
        dists = np.power(p_eu - jp_col, 2).sum(axis=1)
        min_c_idx = dists.argmin()
        jp_col_tp = tuple(jp_col.tolist())
        if jp_col_tp not in color_errors:
            color_errors[jp_col_tp] = [0, []]
        color_errors[jp_col_tp][0] = dists[min_c_idx]
        color_errors[jp_col_tp][1].append(idx)
        img_eu[idx] = p_eu[min_c_idx]

    assert len(np.unique(img_eu, axis=0)) <= 256
    assert len(np.unique(img_jp, axis=0)) <= 256

    new_colors = unique_colors(img_eu)
    free_colors = 256 - len(new_colors)

    new_color_candidates = sorted(color_errors.items(), key=lambda x: x[1][0], reverse=True)[:free_colors]

    for color, (_, where_indices) in new_color_candidates:
        for idx in where_indices:
            img_eu[idx] = color

    new_palette_eu = unique_colors(img_eu)

    assert len(new_palette_eu) == 256

    @lru_cache(maxsize=None)
    def to_gray(color):
        r, g, b = color[:3]
        return (0.299 * r) + (0.587 * g) + (0.114 * b)

    new_palette_eu = sorted(new_palette_eu.tolist(), key=lambda x: to_gray(tuple(x)))

    img_eu_palettized = np.where(scipy.spatial.distance.cdist(img_eu, new_palette_eu) == 0)[1].astype(np.uint8)

    # refilter palette
    if not tim2img_eu.image.linear_palette:
        new_palette_eu = refilter_palette(new_palette_eu, refilter_map)

    or_palette_len = len(tim2img_eu.image.palette)
    or_data_len = len(tim2img_eu.image.data)

    tim2img_eu.image.palette = bytearray(np.array(new_palette_eu, dtype=np.uint8).tobytes())
    tim2img_eu.image.data = bytearray(img_eu_palettized.tobytes())

    assert len(tim2img_eu.image.palette) == or_palette_len
    assert len(tim2img_eu.image.data) == or_data_len

    return tim2img_eu.to_bytes()


def refilter_palette(palette, refilter_map=None):
    if refilter_map is None:
        _, refilter_map = defilter_palette(palette)

    length = len(palette)

    new_colors = [0] * length

    for i in range(length):
        new_colors[refilter_map[i]] = palette[i]

    return new_colors


def defilter_palette(palette):
    length = len(palette)

    parts = length // 32
    stripes = 2
    colors = 8
    blocks = 2

    new_colors = [0] * length

    refilter_map: list[int] = []

    i = 0
    for part in range(parts):
        for block in range(blocks):
            for stripe in range(stripes):
                for color in range(colors):
                    j = (part * colors * stripes * blocks) + (block * colors) + (stripe * stripes * colors) + color
                    new_colors[i] = palette[j]
                    refilter_map.append(j)
                    i += 1

    return new_colors, refilter_map
