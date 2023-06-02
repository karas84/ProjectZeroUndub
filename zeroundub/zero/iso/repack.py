import os
import io
import re
import math
import struct
import pycdlib
import hashlib
import itertools

from abc import ABC, abstractmethod
from typing import BinaryIO, cast
from functools import reduce

from ..pk2 import PK2Archive
from ..tim2 import patch_pl_mtop
from ...utils.file import SubFile
from ..text.parser import inject_english_subtitles
from ..reader.entry import TOCEntry
from ..reader.pjzreader import PJZReader
from ...wagrenier.pssmux import pss_mux_from_bytes_io


class AbstractUndubEntry(ABC):
    @property
    @abstractmethod
    def name(self):
        ...

    @property
    @abstractmethod
    def number(self):
        ...

    @property
    @abstractmethod
    def data_size(self):
        ...

    @property
    @abstractmethod
    def new_size(self):
        ...

    @abstractmethod
    def read(self, size=-1):
        ...

    @abstractmethod
    def seek(self, offset: int):
        ...

    def close(self):
        pass


class ReaderUndubEntry(AbstractUndubEntry):
    @property
    def name(self):
        return self._name

    @property
    def number(self):
        return self._number

    @property
    def data_size(self):
        return self._toc_entry.size

    @property
    def new_size(self):
        return self._new_size

    def __init__(self, reader: PJZReader, toc_entry: TOCEntry, name: str, number: int, new_size=0, japanese=False):
        self._reader: PJZReader = reader
        self._toc_entry: TOCEntry = toc_entry
        self._name: str = name
        self._number: int = number
        self.japanese: bool = japanese

        if new_size == 0:
            self._new_size = toc_entry.size
        elif new_size > 0:
            self._new_size = max(new_size, toc_entry.size)

        self._offset = 0

    def read(self, size=-1):
        return self._reader.read_file(self._toc_entry.name, size=size, offset=self._offset)

    def seek(self, offset: int):
        self._offset = offset


class ExternalFileEntry(AbstractUndubEntry):
    @property
    def name(self):
        return self._name

    @property
    def number(self):
        return self._number

    @property
    def data_size(self):
        return self._data_size

    @property
    def new_size(self):
        return self._new_size

    def __init__(self, file: "str | bytes | BinaryIO", name: str, number: int, new_size=0):
        if isinstance(file, io.IOBase):
            self._file_h = file
        elif isinstance(file, bytes):
            self._file_h = io.BytesIO(file)
        else:
            self._file_h = open(  # pylint: disable=consider-using-with
                file,  # pyright: ignore[reportGeneralTypeIssues]
                "rb",
            )

        self._name = name
        self._number = number
        self._data_size = self._get_file_size()

        if new_size == 0:
            self._new_size = self._data_size
        elif new_size > 0:
            self._new_size = max(new_size, self._data_size)

    def _get_file_size(self):
        pos = self._file_h.tell()
        size = self._file_h.seek(0, os.SEEK_END)
        self._file_h.seek(pos, os.SEEK_SET)
        return size

    def close(self):
        self._file_h.close()

    def read(self, size=-1):
        return self._file_h.read(size)

    def seek(self, offset: int):
        return self._file_h.seek(offset, os.SEEK_SET)


def recalculate_img_bin_offsets(all_sizes, align=16):
    offsets = [0]
    for size in all_sizes:
        current_offset = offsets[-1]
        next_offset = current_offset + int(math.ceil(size / align / 2048)) * align
        offsets.append(next_offset)

    offset, img_bd_size = offsets[:-1], offsets[-1] * 2048

    return offset, img_bd_size


def compute_elf_crc(file_h: BinaryIO):
    pos = file_h.tell()
    file_h.seek(0, os.SEEK_SET)
    elf = file_h.read()
    u32s = struct.unpack(f"<{len(elf) // 4}I", elf)
    crc = reduce(lambda x, y: x ^ y, u32s, 0x00000000)
    file_h.seek(pos, os.SEEK_SET)
    return crc


def restore_elf_crc(file_h: BinaryIO, target: int):
    pos = file_h.tell()
    crc = compute_elf_crc(file_h)
    crc_fix = struct.pack("<I", crc ^ target)
    file_h.seek(0x08, os.SEEK_SET)
    file_h.write(crc_fix)
    file_h.seek(pos, os.SEEK_SET)


def patch_elf_inplace(
    iso_path: str,
    fix_kirie_camera_bug=True,
    force_lang=False,
    no_bloom=False,
    dark_filter=False,
    ingame_noise=False,
    menu_noise=False,
    force_16_9_game=False,
    force_16_9_movies=False,
    callback=None,
):
    iso = pycdlib.PyCdlib()
    iso.open(iso_path, mode="rb")

    record = iso.get_record(iso_path="/SLES_508.21;1")
    offset = record.fp_offset
    size = record.data_length

    iso.close()

    if callback:
        callback(
            2
            + int(fix_kirie_camera_bug)
            + int(force_lang)
            + int(no_bloom)
            + int(dark_filter)
            + int(ingame_noise)
            + int(menu_noise)
            + int(force_16_9_game)
            + int(force_16_9_movies)
        )

    with open(iso_path, mode="rb+") as iso_fh:
        file_h = SubFile(iso_fh, offset, size)  # pylint: disable=abstract-class-instantiated

        original_crc = compute_elf_crc(file_h)

        # enable english subtitles
        file_h.seek(0x0005691A)
        file_h.write(b"\x00\x14")
        file_h.seek(0x00056952)
        file_h.write(b"\x00\x14")
        file_h.seek(0x00056B12)
        file_h.write(b"\x00\x10")
        file_h.seek(0x000613B2)
        file_h.write(b"\x00\x14")

        if callback:
            callback()

        if force_lang:
            file_h.seek(0x001202CE)
            file_h.write(b"\x00\x14")

            if callback:
                callback()

        if fix_kirie_camera_bug:
            file_h.seek(0x000203B4)
            file_h.write(b"\x32\x60\x15\x46\x02\x00\x01\x45")

            if callback:
                callback()

        if no_bloom:
            file_h.seek(0x00251C0E)
            file_h.write(b"\x00\x00")

            if callback:
                callback()

        if dark_filter:
            file_h.seek(0x0025208E)
            file_h.write(b"\x00\x00")

            if callback:
                callback()

        if ingame_noise:
            file_h.seek(0x00251F1E)
            file_h.write(b"\x00\x00")

            if callback:
                callback()

        if menu_noise:
            file_h.seek(0x0025A05E)
            file_h.write(b"\x00\x00")

            if callback:
                callback()

        if force_16_9_game:
            file_h.seek(0x00036B18)
            file_h.write(b"\x8C")
            file_h.seek(0x00036B80)
            file_h.write(b"\xA8")
            file_h.seek(0x00036BC4)
            file_h.write(b"\x28")
            file_h.seek(0x00036BFC)
            file_h.write(b"\x0C")
            file_h.seek(0x0003815C)
            file_h.write(b"\x12")
            file_h.seek(0x00086B40)
            file_h.write(b"\xC0")
            file_h.seek(0x00086B4C)
            file_h.write(b"\x40")
            file_h.seek(0x0008B2CC)
            file_h.write(b"\x40")

            if callback:
                callback()

        if force_16_9_movies:
            file_h.seek(0x00083731)
            file_h.write(b"\x71")
            file_h.seek(0x00083741)
            file_h.write(b"\x71")
            file_h.seek(0x00083749)
            file_h.write(b"\x1E")

            if callback:
                callback()

        restore_elf_crc(file_h, target=original_crc)

        if callback:
            callback()


def patch_english_subtitles(reader: PJZReader, ig_msg_entry: TOCEntry):
    with reader.open(ig_msg_entry.name) as file_h:
        patched_ig_msg = inject_english_subtitles(file_h)
        return ExternalFileEntry(patched_ig_msg, ig_msg_entry.name, ig_msg_entry.number)


def replace_movies_in_iso_inplace(iso_jp_path, iso_undub_path, callback=None):
    iso_jp = pycdlib.PyCdlib()
    iso_jp.open(iso_jp_path, mode="rb")

    iso_undub = pycdlib.PyCdlib()
    iso_undub.open(iso_undub_path, mode="rb")

    jp_video_movie = [f"/MOVIE/{f}" for f in next(iso_jp.walk(iso_path="/MOVIE"))[2] if ".PSS;" in f]
    jp_video_movie2 = [f"/MOVIE2/{f}" for f in next(iso_jp.walk(iso_path="/MOVIE2"))[2] if ".PSS;" in f]

    en_video_movie = [f"/MOVIE/{f}" for f in next(iso_undub.walk(iso_path="/MOVIE"))[2] if ".PSS;" in f]
    en_video_movie2 = [f"/MOVIE2/{f}" for f in next(iso_undub.walk(iso_path="/MOVIE2"))[2] if ".PSS;" in f]
    en_video_movie3 = [f"/MOVIE3/{f}" for f in next(iso_undub.walk(iso_path="/MOVIE3"))[2] if ".PSS;" in f]
    en_video_movie4 = [f"/MOVIE4/{f}" for f in next(iso_undub.walk(iso_path="/MOVIE4"))[2] if ".PSS;" in f]

    # en_video_movie5 = [f'/MOVIE5/{f}' for f in next(iso_undub.walk(iso_path='/MOVIE5'))[2] if '.PSS;' in f]

    def find_matches(_jp_list, _en_list):
        def basename(p):
            return os.path.splitext(os.path.basename(p))[0].rstrip("P")

        matches = list()
        for _jp_movie in _jp_list:
            en_match = next((_en_movie for _en_movie in _en_list if basename(_en_movie) == basename(_jp_movie)), None)
            if en_match:
                matches.append((_jp_movie, en_match))

        return matches

    matches_movie = find_matches(jp_video_movie, en_video_movie)
    matches_movie_p = find_matches(jp_video_movie, en_video_movie3)

    matches_movie2 = find_matches(jp_video_movie2, en_video_movie2)
    matches_movie2_p = find_matches(jp_video_movie2, en_video_movie4)

    all_matches = matches_movie + matches_movie_p + matches_movie2 + matches_movie2_p

    if callback:
        callback(len(all_matches))

    for jp_movie, en_movie in all_matches:
        record_undub = iso_undub.get_record(iso_path=en_movie)
        offset_undub = record_undub.fp_offset
        size_undub = record_undub.data_length

        with iso_jp.open_file_from_iso(iso_path=jp_movie) as jp_movie_fh:
            with open(iso_undub_path, "rb+") as iso_undub_fh:
                en_movie_fh = SubFile(  # pylint: disable=abstract-class-instantiated
                    iso_undub_fh, offset=offset_undub, size=size_undub
                )
                pss_mux_from_bytes_io(jp_movie_fh, en_movie_fh)  # pyright: ignore[reportGeneralTypeIssues]

        if callback:
            callback()


def compute_file_hash(iso_path: str, file_name: str):
    iso = pycdlib.PyCdlib()
    iso.open(iso_path, mode="rb")

    with iso.open_file_from_iso(iso_path=f"/{file_name.upper()};1") as f:
        sha256_hash = hashlib.sha256()
        for byte_block in iter(lambda: f.read(16 * 1024), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def check_iso_hashes(iso_file: str, lang: str, callback=None):
    known_hashes_eu = {
        "SLES_508.21": "cb7c8b5552c245ec17b28a26347e1801c9e90eee4a99c7b3d86bbdea088fbb3a",
        "IMG_HD.BIN": "ab3c26678d42458405e753715d820df766e332a5027f43b2f9e1c8901d0e0657",
        "IMG_BD.BIN": "f18aeff01761e539aea41f830a94d0468c80a2a9cf8bb700e51aba0752fe8bca",
        "MOVIE/DUMMY.PSS": "010cc1efb67bbf21491b3a53043ffeef71f8fea4d2450393488ba1cd67a34775",
        "MOVIE/SCN0010.PSS": "3961be41d6a14f27622c2b21e5bed57f3c8238d0fdefe402a8bf917c9cffe702",
        "MOVIE/SCN0031.PSS": "c2ccb7e5a9c1d8226fb642d4f89b64ac5d0ca92cf07649af7697323281b1833e",
        "MOVIE/SCN1000.PSS": "dcb5638cd634b11af724bef2a11e11e0518ddebf5d211a9b9b8504072ac9aa13",
        "MOVIE/SCN1031.PSS": "17e30f7795f8c97056924268e011fa07d2a66f82252f7486ec1bb4a02579316a",
        "MOVIE/SCN1101.PSS": "02359a28a2bbec031723bbe80d37aa89329c601da0f5f112b751d4b67f1e3680",
        "MOVIE/SCN1240.PSS": "36e809797659ab961e41058c924fb852407913c25ce873acc69a3d6e6dc4a332",
        "MOVIE/SCN1300.PSS": "d01f44847d12ceea635492a81ece713ab28947137d9a5764f359d7dd83b1198c",
        "MOVIE/SCN1331.PSS": "c5fdde597f64bae03870f9d08a46a7b4d28814c739fca07ecbd6d17ad4786643",
        "MOVIE/SCN1332.PSS": "6533f79b4bd2056bea8eb2d7969c27ed8919231cf13160b4afd91a9e41a5adab",
        "MOVIE/SCN2010.PSS": "d254cd8b0b5da2e6442d6e14d8fdf613e00354366d49691ddddf28f62702b235",
        "MOVIE/SCN2050.PSS": "b548d6678ceb453755adc5deaaa5a7a631bdc280bb8190fabebdbd034ab221b6",
        "MOVIE/SCN2061.PSS": "3cb9b77baaa3370283fc42c5d5a3897086c50366f9d015184cd654c300b26e38",
        "MOVIE/SCN2071.PSS": "5a4d8d33ef7b1df63a1132e1e7057d995c1144bccef3ba1feaa5d8f81284cdb4",
        "MOVIE/SCN2091.PSS": "cff8b9fad2f4b2648cb53b4671960bd4031f561512c048d05e7e5aaf8015bc06",
        "MOVIE/SCN2110.PSS": "0f58f0b1b8948ad30dc35768f8ca966febeeec50b653d3052f963532fae76e74",
        "MOVIE/SCN2131.PSS": "35814d1e8b617e3a1fc9f08ce25af7ac94bb3fa5fc25bb17ea91c9c6a694bc64",
        "MOVIE/SCN2142.PSS": "675bfe9f6cd8236c74c00a2a9ec5c420126b519285e971e1b45e6b8b7ddc5673",
        "MOVIE/SCN2143.PSS": "2cb68bec2ece0bc64e3a976865cb5d93fc757d52ccf3226c6f1923d20afdab14",
        "MOVIE/SCN2171.PSS": "d730b85838be4eb2077566eec1a3a5d6ad0d92b5b666570679c2a88aa171edd3",
        "MOVIE/SCN9000.PSS": "ea18c9cbf9ecb3b320926e5cf57020032fe005e9c6b8bf8ce3d6a5d3d1ef18a6",
        "MOVIE/SCN9001.PSS": "ebf2220545675640c0a51161bdd748677f571385b41992704a497594f653d4e8",
        "MOVIE/SCN9100.PSS": "5e75d4f60c61b69185f496b35753b0eb5f77c07720cdcc89e7049e69a3161d03",
        "MOVIE/SCN9200.PSS": "990c35a26ff1fe5fe237f28b98d5d132dd4c52847dfee6cd789734f8980f2b65",
        "MOVIE/TECMO.PSS": "c5f6aee96d9fb8729cfd65a44fd56548001613e9a8a7c0d25f89c7b5e1b078ec",
        "MOVIE2/SCN3010.PSS": "06bb0a76f5c6e894287d67d6c6ef805c338a1a4dceda76f4b30616020651a68f",
        "MOVIE2/SCN3040.PSS": "54762d5275d873e90398cbbf0c48113965c2830ad7e98341857545d3d6efe37e",
        "MOVIE2/SCN3080.PSS": "373e013ed60a604f59e290f376989783e7e7198f067f48bf15258450cdb3083e",
        "MOVIE2/SCN3081.PSS": "778405b1aa23c1b3e04b14b7d9b0bb79a2036b35cbcf57d193024110b61602ed",
        "MOVIE2/SCN3090.PSS": "82bcb89ca31c9ad28d6ff6e336986969807374447eb9629e9ba2cbcac1e68281",
        "MOVIE2/SCN4010.PSS": "55f31b6ec122a63c28694a7f210f930632edf1fc1f76f0682e218626efcd09f2",
        "MOVIE2/SCN4031.PSS": "1f5ef156e1bef2092d828ad671e8df9f86f0b46a9d9b010cd309aa123e526428",
        "MOVIE2/SCN4041.PSS": "8b859a2844db2826bb68aae453ec2cdc5847d51c93dbf0392367cabd66b5b66d",
        "MOVIE2/SCN4060.PSS": "d83fb519c5d8f26f1877f081535974bc7352d25ec445f1e73bf306ae2095b9d4",
        "MOVIE2/SCN4080.PSS": "94e06f3d1cddd975ab6711b79565a7ab6267f0fddd0ffb7e688b3b09f59345bd",
        "MOVIE2/SCN4090.PSS": "b162b0fd61231de7ff3cfbfd89436969e2058dcc90022c1bf916ab88be2283b5",
        "MOVIE2/SCN4100.PSS": "00c8883983235c2bea06cda23385da2c6ade3f9a8959e78a19469002ef75628d",
        "MOVIE2/SCN4110.PSS": "32e80c5cd3e21e96fc2ea6b8daf5f2f3fa0ae42818cf2015b0ca7c347932a4d8",
        "MOVIE2/SCN4120.PSS": "d00000f98514cd9d65ce0d5ae627235f0d0b658480e489d870642eb6ac283c09",
        "MOVIE2/SCN5010.PSS": "2403c40b1e9619e9eb0d1c4f1d56ef82aeb42d566f2ef51cff7b0b72b837fac5",
        "MOVIE2/SCN5020.PSS": "e1319796e3757a31a55d3012d54dc2d7d04d6410a1f2471b9de8c5c48fc03469",
        "MOVIE3/SCN0010P.PSS": "f8b163ed827afff9aefb8d4b25651bfd4cfcef7cc4757bc9ce26314ba30f5cb4",
        "MOVIE3/SCN0031P.PSS": "ed191c4fb9392e413681dce24f26edd14cbe91943f6d10fe2182386f299b5a92",
        "MOVIE3/SCN1000P.PSS": "8871f436fe1fa9073272cee28a095bee951411fb3afb7b49da5a5b99322078bb",
        "MOVIE3/SCN1031P.PSS": "27871f71baa934450f118e0ebeb93f4914c418f687b5d5a7c08684d0ec976c97",
        "MOVIE3/SCN1101P.PSS": "06719a2db5997c67f251cba62d7932e1ae2aa1ef574b92a634515c6fa6deeeaf",
        "MOVIE3/SCN1240P.PSS": "04995368626b01307f028ddf2dc8fc0e37e1a98817ddde4436b13748f83354f1",
        "MOVIE3/SCN1300P.PSS": "260081eff01df63fe083df2435013a46bc0d3587810257f6472c83b20d00200d",
        "MOVIE3/SCN1331P.PSS": "39f8af7fbc81800bc1502616e66e1e58a979dd9d02db0bf3331d3b1ea9bb3f4b",
        "MOVIE3/SCN1332P.PSS": "bcba19a5cfceb7bbba264eaa7c0e542fb939c8d41cd70f60038a343495750742",
        "MOVIE3/SCN2010P.PSS": "bb0ac5e3d3d6323e53c1877fbfa11e73a496ae12acb00d74ce54f94e25a12f30",
        "MOVIE3/SCN2050P.PSS": "f44172e4c167f75b86dbd66ce83ec6a16935261dbc27ad5b028f6057f014a158",
        "MOVIE3/SCN2061P.PSS": "c873fa8271dd51490eddfda4ab58d64e3764f5d4c01f085e4b9cde507aac1d42",
        "MOVIE3/SCN2071P.PSS": "9bb1f424e6333044296f866c41e18c73bf18e5099674bfeda825d17e53e8f475",
        "MOVIE3/SCN2091P.PSS": "e4a35bcf27c2a55b572b28a28c3008228f9b73393ecc05c6507787a3b66e4285",
        "MOVIE3/SCN2110P.PSS": "39294e3c2147b033c034e8f579311048fe0fa72f00bf83ba04537ad463b3c5ea",
        "MOVIE3/SCN2131P.PSS": "5aff6ffb03f7a288e720b0168278c33fd1ec2556796b597d6d47867c63439836",
        "MOVIE3/SCN2142P.PSS": "0c673d6629b9460149e789872615702e5dfd0fd25a9c27207b1de4a3b72aab8e",
        "MOVIE3/SCN2143P.PSS": "36c530a33e224223ee808e8d983c34800ef6a4f5993996b016ef38715405a86f",
        "MOVIE3/SCN2171P.PSS": "4332e33ac86798e5cdeb41c93b13d62f3413a2a5c830c1ed61ea80f3ee7ec15f",
        "MOVIE3/SCN9000P.PSS": "2862d253ad97cb744199e65e04dd16131d2bd7e03aa758b6b96392304f894267",
        "MOVIE3/SCN9001P.PSS": "ebf2220545675640c0a51161bdd748677f571385b41992704a497594f653d4e8",
        "MOVIE3/SCN9100P.PSS": "b5313245d245cb7fe7d4822eccd3b1730789975a5fa750d925c2629145872c20",
        "MOVIE3/SCN9200P.PSS": "978210c7ceb4b271498a83b8bfe7ed912e72c78fcb64c5df23063a69afd10b22",
        "MOVIE3/TECMOP.PSS": "c5f6aee96d9fb8729cfd65a44fd56548001613e9a8a7c0d25f89c7b5e1b078ec",
        "MOVIE4/SCN3010P.PSS": "ec148a5ecb562d312652a039d0632f1c39aef7b89cd1a208ed0e0e0065000968",
        "MOVIE4/SCN3040P.PSS": "ca0928f5b6b2ef759e909ece89656b7c166831ccdb54fe84147c2f38665fd339",
        "MOVIE4/SCN3080P.PSS": "86325fa8b50f782cc7fe367e9d891d8c41d47d4de34e1c8d95048c86ad915e3c",
        "MOVIE4/SCN3081P.PSS": "2dace3583c771adccb4e6fcf338baec49b8dab08bb1a13c3ad6f3c6b780605e6",
        "MOVIE4/SCN3090P.PSS": "2d8e7d6fc06bd6f0a993463554ca7248341b1a4d8630b3d3921571d4957124cb",
        "MOVIE4/SCN4010P.PSS": "5473b20e920c47a2e5a364872859043360c4be432da66b0c9da76b7ea0f46504",
        "MOVIE4/SCN4031P.PSS": "c6f853f8751837f120b55dc14e23b2ec2aac4b69e3a5b2698875fff7e7cee065",
        "MOVIE4/SCN4041P.PSS": "17ccb610d914b41305b0b93f0746b2175396cc830bb63d2739b3e638532964d6",
        "MOVIE4/SCN4060P.PSS": "ac9ba38399df64bf57a915fe65beb288cb865502993e39f16321f6bcc91523e6",
        "MOVIE4/SCN4080P.PSS": "da5ae8364ee38048f62bdd716a422e38980936a0397bd804609a810acfbd27cd",
        "MOVIE4/SCN4090P.PSS": "ea609e551421d47dc17a56d9d3df72247a75d794c7037bbd0b57d315f5c56dd0",
        "MOVIE4/SCN4100P.PSS": "f6d90cee4348e74c547bd2ca2f9ca1fdca4c12c11a923044e25cac4949a28314",
        "MOVIE4/SCN4110P.PSS": "6099093b39044aea2fd6ec728600ff073c08f684f8078881fa3f6001982e7bd9",
        "MOVIE4/SCN4120P.PSS": "367e807d6435c2f3a1231c2d0eb5002021db626611e8911e9132fa99aedf2849",
        "MOVIE4/SCN5010P.PSS": "58c3c4af2c34bc5d5bb005ef2d93604e6da6e60909db0ecf578fa6a38128527e",
        "MOVIE4/SCN5020P.PSS": "fe4b2a0b210f9f5197d3b7151313bae2ce4c6d4b7326b6a46d73cb682986319b",
        "MOVIE5/SCN900EP.PSS": "e0f9317e5102c3951ec2f2ccdeaa35dd2005a4f5bbba17244a9a28be43725545",
        "MOVIE5/SCN900E.PSS": "4a2cfd688f51411a1bb23d2e3571dce4bc70935dda15f60d7811df21dfcdc703",
        "MOVIE5/SCN900FP.PSS": "b18c01a03cddcdfdb96d228ac673a5285c8aea6167d623a2d9e9d8d623686758",
        "MOVIE5/SCN900F.PSS": "b162c72674111152ecc7c331363869668d6da0d54473eda63f2a88f831f8d3b6",
        "MOVIE5/SCN900GP.PSS": "d7ef0d6f5a27e6b51fab8dd175b809bffed5f5d8304e8f9f6922ec0f1dd17410",
        "MOVIE5/SCN900G.PSS": "0256e8ecff005d95cf149ab97c9c0fe6c85e5f709f7fe1515ec4f547b0486f00",
        "MOVIE5/SCN900IP.PSS": "b0f8fb270a119c68e37e9958f4773a72e0fd81a8fed3e35e66ef7de549edffc1",
        "MOVIE5/SCN900I.PSS": "24e2d1d297d2ec2e1e11bb1d975a442fef7f6019bd1aa2fbb0d65d82797ac2d0",
        "MOVIE5/SCN900SP.PSS": "1d260910bc3476842edfeeb319e9409979a6707849c2dabdae59b34581c30d24",
        "MOVIE5/SCN900S.PSS": "f6115b89eeb200c637739491aa51b533d0523d5c008280b300cfbd5149b174e9",
    }
    known_hashes_jp = {
        "SLPS_250.74": "feb283ac7d09cc2f06275890885f3538c6267cdafd3f82249b8a44fed1fb8005",
        "IMG_HD.BIN": "9c8f270e15a78707251ea641bac8199d5f792e682e53e5e3400c71ab5e6a14fc",
        "IMG_BD.BIN": "e90cbc48f6f977acbbffc6107618ce1b86db03d08a54cefa9f52d903a9fa065d",
        "MOVIE/DUMMY.PSS": "010cc1efb67bbf21491b3a53043ffeef71f8fea4d2450393488ba1cd67a34775",
        "MOVIE/SCN0010.PSS": "f5c08c998f1d4b1c06a1756c60226a05cd654e926d51b32b0dccbc2f8565f6c3",
        "MOVIE/SCN0031.PSS": "3e537cc0b52d1c9ba2df384d2e34243fa9a80067f8db78518653af0c6ba1aeb3",
        "MOVIE/SCN1000.PSS": "a2d17acea663ef455c4b03214cd7056973ab09e00bf4c6345ada83f47536c212",
        "MOVIE/SCN1031.PSS": "a5385e9606e726a168f9f453fb3528231ed8507a50802edbddd1954406de8750",
        "MOVIE/SCN1101.PSS": "02359a28a2bbec031723bbe80d37aa89329c601da0f5f112b751d4b67f1e3680",
        "MOVIE/SCN1240.PSS": "b83ff53710719de785f695835fa5ea792412b60366155c1f687e8459aa4adc88",
        "MOVIE/SCN1300.PSS": "c07fa58905beb326e25001a3ac5b1ba745010b32f1e930839a976514c40f733a",
        "MOVIE/SCN1331.PSS": "c5fdde597f64bae03870f9d08a46a7b4d28814c739fca07ecbd6d17ad4786643",
        "MOVIE/SCN1332.PSS": "f2f0d3a1811089befd9b7cbec730fd842e436c542a39d4894ffeacaf55e99864",
        "MOVIE/SCN2010.PSS": "44a476e0a4d3370b67ee6c0a5de31ca2515c13bd58dae9c0068b290d228a8cb2",
        "MOVIE/SCN2050.PSS": "7a7fe5c45141999a151b46aa64daa102c99fee5fc73a180d70371b8bb7f6f29e",
        "MOVIE/SCN2061.PSS": "6946bb31edb03bdf72a7971b6540128745d0bf3f66bad6b19a376a978e5b5484",
        "MOVIE/SCN2071.PSS": "6f75e8942d29fceaa2166a8fe87f5eec1848e9db547b039396bd45d105f812ac",
        "MOVIE/SCN2091.PSS": "b5f0d34547881002f681b8a03ad029f9d3382e4d49714619c1ecc73935bde794",
        "MOVIE/SCN2110.PSS": "486aa3c8ccf73506216404d0e726e09bf97a74b7cd4429e9e825d5c2328ee094",
        "MOVIE/SCN2131.PSS": "02181cf19ac6617daa45faba5350ce7515f6da808ef11c40cdfcd22b65514193",
        "MOVIE/SCN2142.PSS": "4a1d8f5f57d816d71fb7a8b721f7c02da752777177b6dc0bb864f3ce852a886a",
        "MOVIE/SCN2143.PSS": "2cb68bec2ece0bc64e3a976865cb5d93fc757d52ccf3226c6f1923d20afdab14",
        "MOVIE/SCN2171.PSS": "5cb6fedb5cc43b4bfd22a71b3c4ec447ad7a8cc9dfe29f4efaa9ee94dc0af8b4",
        "MOVIE/SCN9000.PSS": "d1b5bbe6eb591f56b30fa80805d1dd9663ab1c5fcc76515ac3652f80604ba4db",
        "MOVIE/SCN9001.PSS": "120c7f8562e27e3c08f0159e54e05d0a91f5ab45937ce1cd54913b760dd214c4",
        "MOVIE/SCN9100.PSS": "f6972ea47cb6288a3e8021918f613361cd5e719da3648d9108440dce6d8baad4",
        "MOVIE/SCN9200.PSS": "bf29120de363ddc5e57c600736cf069e9c8fb89ec34fc4ba50531ad362668c4e",
        "MOVIE/TECMO.PSS": "c5f6aee96d9fb8729cfd65a44fd56548001613e9a8a7c0d25f89c7b5e1b078ec",
        "MOVIE2/SCN3010.PSS": "1523b503e3689c3e0375f30a3bec2c210a256f75d2a260c506958dbb529fbcc9",
        "MOVIE2/SCN3040.PSS": "3cabd74d2b4f79585ea88fe8dd89457afac8f09d46cc0ee0a9209e3270b35447",
        "MOVIE2/SCN3080.PSS": "3e4354dc7a94a6f47dc77391301bae434cea3933e865417e3d55b20205b830cb",
        "MOVIE2/SCN3081.PSS": "778405b1aa23c1b3e04b14b7d9b0bb79a2036b35cbcf57d193024110b61602ed",
        "MOVIE2/SCN3090.PSS": "82bcb89ca31c9ad28d6ff6e336986969807374447eb9629e9ba2cbcac1e68281",
        "MOVIE2/SCN4010.PSS": "8cb0c25f7c9a8eb9df93d7b93bf9bb20bdc7412d3a7d2b5f9eb07d1b3b25c381",
        "MOVIE2/SCN4031.PSS": "cfe1ff3f6b0e860ce512cc6b450578ebec741f4f5ffde516cae7b934361b45c3",
        "MOVIE2/SCN4041.PSS": "8b859a2844db2826bb68aae453ec2cdc5847d51c93dbf0392367cabd66b5b66d",
        "MOVIE2/SCN4060.PSS": "d83fb519c5d8f26f1877f081535974bc7352d25ec445f1e73bf306ae2095b9d4",
        "MOVIE2/SCN4080.PSS": "c0a6784fe206a4ea45c02cdecb568017e3d84d04e048d6f67dee81be6d48d6f0",
        "MOVIE2/SCN4090.PSS": "ca9f126e4d834275fe5996c79a9032208ccbce6fb518908d329586cf095be821",
        "MOVIE2/SCN4100.PSS": "00c8883983235c2bea06cda23385da2c6ade3f9a8959e78a19469002ef75628d",
        "MOVIE2/SCN4110.PSS": "0f932713a51e724b9eb9263e72e0fcccaee6927a4d41bf789e7668909a965daf",
        "MOVIE2/SCN4120.PSS": "1bbc5312dce70306e0bf5e1aa77995aef77f1d704cc0b45aa15f59c8297ac7ac",
        "MOVIE2/SCN5010.PSS": "fcbae8cbad3ac085299fce60487d959dd046a649d126dd4514fefa84b618eda5",
        "MOVIE2/SCN5020.PSS": "74a9e9e5574f1a5fcd62a6a86f5bb5420590e0fa3a5ef53ed9226af4ad6cb798",
    }

    if lang.upper() == "EU":
        known_hashes = known_hashes_eu
    elif lang.upper() == "JP":
        known_hashes = known_hashes_jp
    else:
        raise ValueError("lang must be EU or JP")

    if callback:
        callback(len(known_hashes))

    for file_name, hash_good in known_hashes.items():
        digest = compute_file_hash(iso_file, file_name)
        good = digest == hash_good

        if not good:
            raise RuntimeError

        if callback:
            callback()


def merge_iso_img_bd_contents(
    eu_iso_path: str,
    jp_iso_path: str,
    out_iso_path: str,
    replace_title_jp,
    replace_models,
    replace_sfx,
    callback=None,
):
    reader_eu = PJZReader(eu_iso_path)
    reader_jp = PJZReader(jp_iso_path)

    entries_eu_: list["TOCEntry | None"] = [reader_eu.find_entry(name) for name in reader_eu.list_files()]
    entries_jp_: list["TOCEntry | None"] = [reader_jp.find_entry(name) for name in reader_jp.list_files()]

    if not all(entries_eu_) or not all(entries_jp_):
        raise RuntimeError("cannot find all entries in ISO(s)")

    entries_eu = cast(list[TOCEntry], entries_eu_)
    entries_jp = cast(list[TOCEntry], entries_jp_)

    file_name_list_eu = [toc.name for toc in entries_eu]

    def filter_jp_entries_common(_pattern, pad=False):
        _eujp_entries: dict[str, ReaderUndubEntry] = {}
        for toc_jp in entries_jp:
            if re.match(_pattern, toc_jp.name) and toc_jp.name in file_name_list_eu:
                toc_eu = entries_eu[file_name_list_eu.index(toc_jp.name)]
                size = 0 if not pad else toc_eu.size
                _eujp_entries[toc_eu.name] = ReaderUndubEntry(
                    reader_jp, toc_jp, toc_eu.name, toc_eu.number, new_size=size, japanese=True
                )
        return _eujp_entries

    def filter_ingame_text_en():
        return next(_toc for _toc in entries_eu if _toc.name == "IG_MSG_E.OBJ")

    def repack_title():
        title_jp_toc = next((toc_jp for toc_jp in entries_jp if toc_jp.name == "TITLE.PK2"), None)
        if not title_jp_toc:
            raise RuntimeError("cannot find title image in japanese iso")

        titles_eu_toc = [toc_eu for toc_eu in entries_eu if re.match(r"TITLE_[EFGSI]\.PK2", toc_eu.name)]
        if len(titles_eu_toc) != 5:
            raise RuntimeError("cannot find title images in european iso")

        NUM_TIM2_IN_TITLE = 11

        new_titles: dict[str, ExternalFileEntry] = {}

        with reader_jp.open(title_jp_toc.name) as fh:
            title_jp_toc = PK2Archive(fh)

            for title_eu_toc in titles_eu_toc:
                with reader_eu.open(title_eu_toc.name) as fh:
                    title_eu = PK2Archive(fh, copy=True)

                    for i in range(NUM_TIM2_IN_TITLE):
                        title_eu[i] = title_jp_toc[i]

                    new_titles[title_eu_toc.name] = ExternalFileEntry(
                        file=title_eu.data,
                        name=title_eu_toc.name,
                        number=title_eu_toc.number,
                    )

        return new_titles

    def repack_pl_mtop():
        pl_mtop_jp = next((toc_jp for toc_jp in entries_jp if toc_jp.name == "PL_MTOP.PK2"), None)
        if not pl_mtop_jp:
            raise RuntimeError("cannot find pl_mtop image in japanese iso")

        pl_mtops_eu = [toc_eu for toc_eu in entries_eu if re.match(r"PL_MTOP_[EFGSI]\.PK2", toc_eu.name)]
        if len(pl_mtops_eu) != 5:
            raise RuntimeError("cannot find pl_mtop images in european iso")

        new_pl_mtop_eu: dict[str, ExternalFileEntry] = {}

        with reader_jp.open(pl_mtop_jp.name) as fh:
            archive = PK2Archive(fh)
            pl_mtop_jp_data_io = archive[1]

            for pl_mtop_eu in pl_mtops_eu:
                with reader_eu.open(pl_mtop_eu.name) as fh:
                    archive = PK2Archive(fh, copy=True)
                    pl_mtop_eu_data_io = archive[1]
                    archive[1] = patch_pl_mtop(pl_mtop_eu_data_io, pl_mtop_jp_data_io)

                    new_pl_mtop_eu[pl_mtop_eu.name] = ExternalFileEntry(
                        file=archive.data,
                        name=pl_mtop_eu.name,
                        number=pl_mtop_eu.number,
                    )

        return new_pl_mtop_eu

    def replace_models_untouched():
        untouched_model_names = (
            "M000_MIKU.MDL",
            "M000_MIKU.MPK",
            "M000_MIKU.PK2",
            "M000_SPE1.PK2",
            "M000_SPE2.PK2",
            "M000_SPE3.PK2",
            "REL11_MIKU.TM2",
            "TX_BTL_RES.PK2",
        )

        models_jp = {toc_jp.name: toc_jp for toc_jp in entries_jp if toc_jp.name in untouched_model_names}
        if len(models_jp) != len(untouched_model_names):
            raise RuntimeError("cannot find all M000 models in japanese iso")

        models_eu = {toc_eu.name: toc_eu for toc_eu in entries_eu if toc_eu.name in untouched_model_names}
        if len(models_eu) != len(untouched_model_names):
            raise RuntimeError("cannot find all M000 models in european iso")

        untouched_jp_entries: dict[str, ReaderUndubEntry] = {}

        for model_name in untouched_model_names:
            model_jp = models_jp[model_name]
            model_eu = models_eu[model_name]
            untouched_jp_entries[model_name] = ReaderUndubEntry(
                reader_jp,
                model_jp,
                model_eu.name,
                model_eu.number,
                new_size=model_jp.size,
                japanese=True,
            )

        return untouched_jp_entries

    def replace_night_titles_jp():
        msn_titles_jp: dict[str, TOCEntry] = {}
        for toc_jp in entries_jp:
            if re.match(r"MSN0[1234]TTL\.PK2", toc_jp.name):
                name, _, ext = toc_jp.name.partition(".")
                for lang in ("E", "F", "G", "S", "I"):
                    eu_name = f"{name}_{lang}.{ext}"
                    msn_titles_jp[eu_name] = toc_jp
        if len(msn_titles_jp) != 5 * 4:
            raise RuntimeError("cannot find night titles images in japanese iso")

        msn_titles_eu = {
            toc_eu.name: toc_eu for toc_eu in entries_eu if re.match(r"MSN0[1234]TTL_[EFGSI]\.PK2", toc_eu.name)
        }
        if len(msn_titles_eu) != 5 * 4:
            raise RuntimeError("cannot find night titles images in european iso")

        NUM_TIM2_IN_TITLE = 11

        new_msn_titles: dict[str, ExternalFileEntry] = {}

        for msn_title_name in msn_titles_eu:
            msn_title_jp = msn_titles_jp[msn_title_name]
            msn_title_eu = msn_titles_eu[msn_title_name]
            with reader_jp.open(msn_title_jp.name) as fh_jp, reader_eu.open(msn_title_eu.name) as fh_eu:
                archive_jp = PK2Archive(fh_jp)
                archive_eu = PK2Archive(fh_eu, copy=True)
                for i in range(NUM_TIM2_IN_TITLE):
                    archive_eu[i] = archive_jp[i]

                new_msn_titles[msn_title_eu.name] = ExternalFileEntry(
                    file=archive_eu.data,
                    name=msn_title_eu.name,
                    number=msn_title_eu.number,
                )

        return new_msn_titles

    scene_audio_entries = filter_jp_entries_common(r"SCENE.*\.STR", pad=True)
    sfx_audio_entries = filter_jp_entries_common(r"^((?!SCENE).).*\.STR", pad=True) if replace_sfx else {}
    bd_audio_entries = filter_jp_entries_common(r"^.*\.BD", pad=True) if replace_sfx else {}
    ingame_text_en = filter_ingame_text_en()
    title_entries = repack_title() if replace_title_jp else {}

    jp_model_entries: dict[str, AbstractUndubEntry] = {}
    if replace_models:
        jp_model_entries.update(repack_pl_mtop())
        jp_model_entries.update(replace_models_untouched())
        jp_model_entries.update(replace_night_titles_jp())

    undub_entries: list[AbstractUndubEntry] = []

    for toc in entries_eu:
        if toc.name == ingame_text_en.name:
            undub_entries.append(patch_english_subtitles(reader_eu, toc))

        elif toc.name in scene_audio_entries:
            undub_entries.append(scene_audio_entries[toc.name])

        elif toc.name in bd_audio_entries:
            undub_entries.append(bd_audio_entries[toc.name])

        elif replace_sfx and toc.name in sfx_audio_entries:
            undub_entries.append(sfx_audio_entries[toc.name])

        elif toc.name in title_entries:
            undub_entries.append(title_entries[toc.name])

        elif toc.name in jp_model_entries:
            undub_entries.append(jp_model_entries[toc.name])

        else:
            undub_entries.append(ReaderUndubEntry(reader_eu, toc, toc.name, toc.number))

    sizes = [
        entry.new_size
        for entry in sorted(undub_entries, key=lambda e: e.number)  # pyright: ignore[reportGeneralTypeIssues]
    ]

    max_img_bd_size = reader_eu.adapter.get_img_bd_size()

    if max_img_bd_size is None:
        raise RuntimeError("cannot get max img_bd size")

    found = False
    offsets: list[int] = []
    img_bd_size = -1
    align_values = [16, 8, 4, 2, 1, 0]
    align = align_values[0]
    while not found and align > 0:
        align = align_values.pop(0)
        offsets, img_bd_size = recalculate_img_bin_offsets(sizes, align=align)
        found = img_bd_size <= max_img_bd_size

    if not found:
        raise RuntimeError("cannot repack img_bd")

    if callback:
        callback(len(undub_entries) + 1)

    iso = pycdlib.PyCdlib()
    iso.open(out_iso_path, mode="rb")

    # ############ write IMG_HD.BIN ############
    img_hd_offset = iso.get_record(iso_path="/IMG_HD.BIN;1").fp_offset

    with open(out_iso_path, "rb+") as iso_fh:
        img_hd_bin = struct.pack(f"<{len(offsets) * 2}I", *list(itertools.chain(*zip(offsets, sizes))))

        iso_fh.seek(img_hd_offset, os.SEEK_SET)
        iso_fh.write(img_hd_bin)

    if callback:
        callback()

    # ############ write IMG_BD.BIN ############
    img_bd_offset = iso.get_record(iso_path="/IMG_BD.BIN;1").fp_offset

    with open(out_iso_path, "rb+") as iso_fh:
        for n, (entry, offset) in enumerate(zip(undub_entries, offsets)):
            # compute offset for current entry and padding value to zero out up to the next entry
            current_offset = offset * 2048
            next_offset = offsets[n + 1] * 2048 if len(offsets) > n + 1 else img_bd_size
            zero_padding = next_offset - (current_offset + cast(int, entry.data_size))

            # write current entry
            iso_fh.seek(img_bd_offset + current_offset, os.SEEK_SET)
            data = 1
            entry_file_offset = 0
            while data:
                entry.seek(entry_file_offset)
                data = entry.read(size=16 * 1024)
                entry_file_offset += len(data)  # pyright: ignore[reportGeneralTypeIssues]
                iso_fh.write(data)  # pyright: ignore[reportGeneralTypeIssues]

            # fill with zeros up to the next entry
            while zero_padding > 0:
                padding_to_write = min(16 * 1024, zero_padding)
                iso_fh.write(bytearray(padding_to_write))
                zero_padding -= padding_to_write

            if callback:
                callback()
