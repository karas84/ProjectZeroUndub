# This file is copyright of William Adam-Grenier and is released
# under the GNU General Public License v3.0. The following is a
# slightly modified version of the original, which can be found
# in the author's github repository: https://github.com/wagrenier/PssMux

import os
import io
import glob

from shutil import copyfile
from typing import BinaryIO


audio_segment = b"\x00\x00\x01\xBD"
pack_start = b"\x00\x00\x01\xBA"
end_file = b"\x00\x00\x01\xB9"


first_header_size = 0x3F
header_size = 0x17


def seek_next_audio(file):
    pos = file.tell()
    file.seek(0, os.SEEK_SET)
    sz = file.seek(0, os.SEEK_END)
    file.seek(pos)

    while True:
        block_id = file.read(0x4)

        if block_id == pack_start:
            file.seek(0xA, os.SEEK_CUR)
        elif block_id == audio_segment:
            return False
        elif block_id == end_file:
            return True
        elif file.tell() >= sz:
            return True
        else:
            block_size = file.read(0x2)
            file.seek(int.from_bytes(block_size, "big"), os.SEEK_CUR)


def initial_audio_block(file):
    b_size = int.from_bytes(file.read(0x2), "big")

    file.seek(0x3B - 0x6, os.SEEK_CUR)

    audio_total_size = int.from_bytes(file.read(0x4), "little")
    data_size = b_size - first_header_size + 0x6

    return audio_total_size, data_size


def audio_block(file):
    b_size = int.from_bytes(file.read(0x2), "big")

    file.seek(-0x6, os.SEEK_CUR)
    file.seek(header_size, os.SEEK_CUR)

    data_size = b_size - header_size + 0x6

    return data_size


def build_full_audio_buffer_io(file):
    seek_next_audio(file)
    total_size, curr_block_size = initial_audio_block(file)
    buff = io.BytesIO()
    buff.write(file.read(curr_block_size))

    while True:
        if seek_next_audio(file):
            break

        curr_block_size = audio_block(file)
        buff.write(file.read(curr_block_size))

    file.seek(0)
    buff.seek(0)
    return buff


def pss_mux(source: str, target: str, output: str):
    copyfile(target, output)

    with open(source, "rb") as source_file:
        with open(output, "rb+") as target_file:
            pss_mux_from_bytes_io(source_file, target_file)


def pss_mux_inplace(source: str, target: str):
    with open(source, "rb") as source_file:
        with open(target, "rb+") as target_file:
            pss_mux_from_bytes_io(source_file, target_file)


def pss_mux_in_memory(source: str, target: str):
    with open(source, "rb") as source_file:
        with open(target, "rb") as target_file:
            target_buffer_io = io.BytesIO(target_file.read())

            pss_mux_from_bytes_io(source_file, target_buffer_io)

            target_buffer_io.seek(0)
            return target_buffer_io


def pss_mux_from_bytes_io(source_io: BinaryIO, target_io: BinaryIO):
    total_buffer_written = 0x0
    source_full_buff_io = build_full_audio_buffer_io(source_io)

    seek_next_audio(target_io)
    seek_next_audio(source_io)

    target_total_size, target_curr_block_size = initial_audio_block(target_io)
    source_total_size, source_curr_block_size = initial_audio_block(source_io)

    source_io.seek(source_curr_block_size, os.SEEK_CUR)

    data = source_full_buff_io.read(target_curr_block_size)
    target_io.write(data)

    total_buffer_written += target_curr_block_size

    while True:
        target_done = seek_next_audio(target_io)
        source_done = seek_next_audio(source_io)

        if target_done or source_done:
            break

        target_curr_block_size = audio_block(target_io)
        source_curr_block_size = audio_block(source_io)

        source_io.seek(source_curr_block_size, os.SEEK_CUR)

        data = source_full_buff_io.read(target_curr_block_size)
        target_io.write(data)

        total_buffer_written += target_curr_block_size

    return_value = target_io.read()

    return return_value


def parse_all_videos(jp_path, en_path, out_path):
    jp_video_movie = [f for f in glob.glob(os.path.join(jp_path, "MOVIE", "*.*")) if f.upper().endswith(".PSS")]
    jp_video_movie2 = [f for f in glob.glob(os.path.join(jp_path, "MOVIE2", "*.*")) if f.upper().endswith(".PSS")]

    en_video_movie = [f for f in glob.glob(os.path.join(en_path, "MOVIE", "*.*")) if f.upper().endswith(".PSS")]
    en_video_movie2 = [f for f in glob.glob(os.path.join(en_path, "MOVIE2", "*.*")) if f.upper().endswith(".PSS")]
    en_video_movie3 = [f for f in glob.glob(os.path.join(en_path, "MOVIE3", "*.*")) if f.upper().endswith(".PSS")]
    en_video_movie4 = [f for f in glob.glob(os.path.join(en_path, "MOVIE4", "*.*")) if f.upper().endswith(".PSS")]

    en_video_movie5 = [f for f in glob.glob(os.path.join(en_path, "MOVIE5", "*.*")) if f.upper().endswith(".PSS")]

    def find_matches(_jp_list, _en_list):
        def basename(p):
            return os.path.splitext(os.path.basename(p))[0].rstrip("p")

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

    def basedir(p):
        return os.path.basename(os.path.dirname(p))

    def st_size(f):
        return os.stat(f).st_size

    for jp_movie, en_movie in matches_movie + matches_movie_p + matches_movie2 + matches_movie2_p:
        out_movie = os.path.join(out_path, basedir(en_movie), os.path.basename(en_movie))
        os.makedirs(os.path.dirname(out_movie), exist_ok=True)
        pss_mux(jp_movie, en_movie, out_movie)
        print(out_movie)
        assert st_size(en_movie) == st_size(out_movie)

    for en_movie in en_video_movie5:
        out_movie = os.path.join(out_path, basedir(en_movie), os.path.basename(en_movie))
        os.makedirs(os.path.dirname(out_movie), exist_ok=True)
        print(out_movie)
        copyfile(en_movie, out_movie)
