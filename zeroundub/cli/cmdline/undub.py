import os
import sys
import argparse

from dataclasses import dataclass

from ..error import AbstractProgressError
from ..progress import Progress
from ..utils import copy_file
from ...zero.iso import (
    check_iso_hashes,
    replace_movies_in_iso_inplace,
    patch_elf_inplace,
    merge_iso_img_bd_contents,
)


@dataclass
class ProgressErrorFileExist(AbstractProgressError):
    error_msg = "Error while accessing ISO files"
    explanation = "Some input ISO files cannot be accessed or read"
    suggestion = "Please check that the provided files exist and that they can be read"


@dataclass
class ProgressErrorCRCEU(AbstractProgressError):
    error_msg = "Error while checking EU ISO files"
    explanation = "Some files are not how they are supposed to be. This may be due to a bad dump"
    suggestion = "Please re-dump the game and try again"


@dataclass
class ProgressErrorCRCJP(AbstractProgressError):
    error_msg = "Error while checking JP ISO files"
    explanation = "Some files are not how they are supposed to be. This may be due to a bad dump"
    suggestion = "Please re-dump the game and try again"


@dataclass
class ProgressErrorISOCopy(AbstractProgressError):
    error_msg = "Error while copying ISO file"
    explanation = "Disk may be full or you may be trying to write somewhere you are not allowed to"
    suggestion = "Check disk space and destination folder and try again"


@dataclass
class ProgressErrorMoviePatch(AbstractProgressError):
    error_msg = "Error while patching Movies"
    explanation = "This is not supposed to happen if previous ISO checks were completed successfully"
    suggestion = "Please report this issue on the GitHub page"


@dataclass
class ProgressErrorELFPatch(AbstractProgressError):
    error_msg = "Error while patching ELF file"
    explanation = "This is not supposed to happen if previous ISO checks were completed successfully"
    suggestion = "Please report this issue on the GitHub page"


@dataclass
class ProgressErrorGamePatch(AbstractProgressError):
    error_msg = "Error while patching game contents"
    explanation = "This is not supposed to happen if previous ISO checks were completed successfully"
    suggestion = "Please report this issue on the GitHub page"


def main():
    parser = argparse.ArgumentParser(description="Project Zero Undub Tool")

    parser.add_argument("iso_eu", type=str, help="path to the European ISO (SLES508.21)")
    parser.add_argument("iso_jp", type=str, help="path to the Japanese ISO (SLPS250.74)")
    parser.add_argument("iso_out", type=str, help="output path for the undubbed ISO (file MUST NOT exist")

    parser.add_argument(
        "--fix-kirie-camera-bug",
        dest="fix_kirie_camera_bug",
        action="store_true",
        help="Fixes a bug where the game could freeze during the last battle with Kirie",
    )
    parser.add_argument(
        "--jp-title",
        dest="replace_title_jp",
        action="store_true",
        help="Replace the title screen background with the one in the japanese version",
    )
    parser.add_argument(
        "--replace-models",
        dest="replace_models",
        action="store_true",
        help="Replace all Miku models with the original Japanese version",
    )
    parser.add_argument(
        "--force-language-selection",
        dest="force_lang",
        action="store_true",
        help="Force the language selection menu to appear every time",
    )
    parser.add_argument("--disable-bloom", dest="no_bloom", action="store_true", help="Remove in-game bloom effect")
    parser.add_argument(
        "--remove-dark-filter",
        dest="dark_filter",
        action="store_true",
        help="Remove in-game dark filter (makes the game slightly brighter)",
    )
    parser.add_argument(
        "--remove-ingame-noise", dest="ingame_noise", action="store_true", help="Remove in-game noise effect"
    )
    parser.add_argument(
        "--remove-title-noise", dest="menu_noise", action="store_true", help="Remove noise effect in title menu"
    )
    parser.add_argument(
        "--force-16-9-ingame",
        dest="force_16_9_game",
        action="store_true",
        help="Force game to render graphics in 16:9 format",
    )
    parser.add_argument(
        "--force-16-9-movies",
        dest="force_16_9_movies",
        action="store_true",
        help="Force movies to render in 16:9 format (to be used in conjunction with the 16:9 "
        "in-game flag to add black bars around movies, otherwise they will be stretched)",
    )

    args = parser.parse_args()

    if os.path.exists(args.iso_out):
        print()
        print("  Output ISO already exists. This program will not overwrite any")
        print("  existing file. You should specify a new path for the output.")
        print()
        sys.exit(1)

    args.force_16_9_movies &= args.force_16_9_game

    if not os.path.exists(args.iso_eu) or not os.path.exists(args.iso_jp):
        ProgressErrorFileExist.print()
        sys.exit(1)

    print()
    print("  Welcome to the Project Zero undubbing process (by karas84)!")
    print("  Please wait while your game is being undubbed...")
    print()

    with Progress("Checking EU ISO", ProgressErrorCRCEU) as pbar:
        check_iso_hashes(args.iso_eu, lang="EU", callback=pbar)

    with Progress("Checking JP ISO", ProgressErrorCRCJP) as pbar:
        check_iso_hashes(args.iso_jp, lang="JP", callback=pbar)

    with Progress("Copying ISO", ProgressErrorISOCopy) as pbar:
        copy_file(args.iso_eu, args.iso_out, pbar)

    with Progress("Patching Movies", ProgressErrorMoviePatch) as pbar:
        replace_movies_in_iso_inplace(args.iso_jp, args.iso_out, pbar)

    with Progress("Patching ELF", ProgressErrorELFPatch) as pbar:
        patch_elf_inplace(
            args.iso_out,
            fix_kirie_camera_bug=args.fix_kirie_camera_bug,
            force_lang=args.force_lang,
            no_bloom=args.no_bloom,
            dark_filter=args.dark_filter,
            ingame_noise=args.ingame_noise,
            menu_noise=args.menu_noise,
            force_16_9_game=args.force_16_9_game,
            force_16_9_movies=args.force_16_9_movies,
            callback=pbar,
        )

    with Progress("Patching Contents", ProgressErrorGamePatch) as pbar:
        merge_iso_img_bd_contents(
            eu_iso_path=args.iso_eu,
            jp_iso_path=args.iso_jp,
            out_iso_path=args.iso_out,
            replace_title_jp=args.replace_title_jp,
            replace_models=args.replace_models,
            replace_sfx=True,
            callback=pbar,
        )

    print()
    print("  All done. Enjoy the game!")
    print()


if __name__ == "__main__":
    main()
