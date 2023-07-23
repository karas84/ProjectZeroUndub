import os
import re
import sys
import inspect
import argparse
import threading
import tkinter as tk

from typing import Type
from tkinter import ttk
from tkinter import filedialog as fd
from pycdlib.pycdlibexception import PyCdlibInvalidInput

from zeroundub.cli.utils import copy_file
from zeroundub.zero.iso import (
    check_iso_hashes,
    replace_movies_in_iso_inplace,
    patch_elf_inplace,
    merge_iso_img_bd_contents,
)

from zeroundub.cli.error import AbstractProgressError
from zeroundub.cli.cmdline.undub import (
    ProgressErrorCRCEU,
    ProgressErrorCRCJP,
    ProgressErrorISOCopy,
    ProgressErrorMoviePatch,
    ProgressErrorELFPatch,
    ProgressErrorGamePatch,
)


class Progress:
    # ignore: reportOptionalSubscript
    def __init__(self, app: "App", label_name: ttk.Label, label_perc: ttk.Label, error: Type[AbstractProgressError]):
        self.app = app
        self.label_name = label_name
        self.label_perc = label_perc
        self.error = error
        self._make_red = getattr(self.app, "_make_red")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type is not None:
            self._make_red(self.label_name)
            self._make_red(self.label_perc)
            self._make_red(self.app.label_info)
            self.app.label_info["text"] = (
                ".\n\n".join((self.error.error_msg, self.error.explanation, self.error.suggestion)) + "."
            )


def format_help_text(text):
    return re.sub(r"^(:?( *)$|( *))", r"", text.strip(), flags=re.MULTILINE).replace("$", " ")


class UndubThread(threading.Thread):
    def __init__(self, app: "App"):
        super().__init__()
        self.app = app
        self.total = 0
        self.current = 0

    def __getattribute__(self, name: str):
        attribute = super().__getattribute__(name)

        if inspect.ismethod(attribute) and name.startswith("do_"):

            def outer(*args, **kwargs):
                def inner():
                    attribute(*args, **kwargs)

                self.app.after(0, inner)

            return outer

        return attribute

    def do_close(self):
        self.app.quit()

    def _update_progress(self, var_progress: tk.DoubleVar, label: ttk.Label, label_perc: ttk.Label, total=None):
        if total:
            self.current = 0
            self.total = total
            label.state(["!disabled"])
            label_perc.state(["!disabled"])
            label_perc["text"] = f"0/{total}"
            var_progress.set(0)
        else:
            self.current += 1
            value = 100 * self.current / self.total
            label_perc["text"] = f"{self.current}/{self.total}"
            var_progress.set(value)

    def do_eu_check_cb(self, total=None):
        self._update_progress(
            self.app.var_progress_eu_check, self.app.label_eu_check, self.app.label_eu_check_perc, total
        )

    def do_jp_check_cb(self, total=None):
        self._update_progress(
            self.app.var_progress_jp_check, self.app.label_jp_check, self.app.label_jp_check_perc, total
        )

    def do_copy_file_cp(self, total=None):
        self._update_progress(self.app.var_progress_copy, self.app.label_copy, self.app.label_copy_perc, total)

    def do_replace_movies_cp(self, total=None):
        self._update_progress(self.app.var_progress_movies, self.app.label_movies, self.app.label_movies_perc, total)

    def do_patch_elf_cp(self, total=None):
        self._update_progress(self.app.var_progress_elf, self.app.label_elf, self.app.label_elf_perc, total)

    def do_merge_iso_cp(self, total=None):
        self._update_progress(
            self.app.var_progress_contents, self.app.label_contents, self.app.label_contents_perc, total
        )

    def do_done(self):
        self.app.label_info["text"] = format_help_text(
            """
            Undubbing completed successfully.

            Please enjoy the game.
        """
        )

        self.app.button_done.state(["!disabled"])

    def run(self) -> None:
        try:
            with Progress(self.app, self.app.label_eu_check, self.app.label_eu_check_perc, ProgressErrorCRCEU):
                check_iso_hashes(
                    self.app.eu_iso_path,
                    lang="EU",
                    callback=self.do_eu_check_cb,
                )

            with Progress(self.app, self.app.label_jp_check, self.app.label_jp_check_perc, ProgressErrorCRCJP):
                check_iso_hashes(
                    self.app.jp_iso_path,
                    lang="JP",
                    callback=self.do_jp_check_cb,
                )

            with Progress(self.app, self.app.label_copy, self.app.label_copy_perc, ProgressErrorISOCopy):
                copy_file(
                    self.app.eu_iso_path,
                    self.app.undub_iso_path,
                    self.do_copy_file_cp,
                )

            with Progress(self.app, self.app.label_movies, self.app.label_movies_perc, ProgressErrorMoviePatch):
                replace_movies_in_iso_inplace(
                    self.app.jp_iso_path,
                    self.app.undub_iso_path,
                    self.do_replace_movies_cp,
                )

            with Progress(self.app, self.app.label_elf, self.app.label_elf_perc, ProgressErrorELFPatch):
                patch_elf_inplace(
                    self.app.undub_iso_path,
                    fix_kirie_camera_bug=self.app.var_fix_kirie_camera_bug.get(),
                    force_lang=self.app.var_force_language_selection.get(),
                    no_bloom=self.app.var_disable_bloom.get(),
                    dark_filter=self.app.var_remove_dark_filter.get(),
                    ingame_noise=self.app.var_remove_ingame_noise.get(),
                    menu_noise=self.app.var_remove_title_noise.get(),
                    force_16_9_game=self.app.var_16_9.get(),
                    force_16_9_movies=self.app.var_16_9.get(),
                    callback=self.do_patch_elf_cp,
                )

            with Progress(self.app, self.app.label_contents, self.app.label_contents_perc, ProgressErrorGamePatch):
                merge_iso_img_bd_contents(
                    eu_iso_path=self.app.eu_iso_path,
                    jp_iso_path=self.app.jp_iso_path,
                    out_iso_path=self.app.undub_iso_path,
                    replace_title_jp=self.app.var_replace_title_jp.get(),
                    replace_models=self.app.var_replace_models.get(),
                    replace_sfx=True,
                    callback=self.do_merge_iso_cp,
                )

            self.do_done()
        except (RuntimeError, PyCdlibInvalidInput):
            return


class App(ttk.Frame):
    filetypes = (("ISO Files", "*.iso"),)

    # noinspection PyUnusedLocal
    def __init__(self, parent):
        ttk.Frame.__init__(self)

        self._undub_started = False

        self.patch_frame: ttk.LabelFrame

        self.check_fix_kirie_camera_bug: ttk.Checkbutton
        self.check_16_9: ttk.Checkbutton
        self.check_disable_bloom: ttk.Checkbutton
        self.check_remove_dark_filter: ttk.Checkbutton
        self.check_remove_ingame_noise: ttk.Checkbutton
        self.check_remove_title_noise: ttk.Checkbutton
        self.check_force_language_selection: ttk.Checkbutton
        self.check_replace_title_jp: ttk.Checkbutton
        self.check_replace_models: ttk.Checkbutton

        self.widgets_frame: ttk.Frame

        self.button_iso_eu: ttk.Button
        self.button_iso_jp: ttk.Button
        self.button_iso_undub: ttk.Button

        self.progress_frame: ttk.Frame
        self.pb_frame_box: ttk.Frame

        self.button_start_undub: ttk.Button

        self.label_eu_check: ttk.Label
        self.label_jp_check: ttk.Label
        self.label_copy: ttk.Label
        self.label_movies: ttk.Label
        self.label_elf: ttk.Label
        self.label_contents: ttk.Label

        self.label_eu_check_perc: ttk.Label
        self.label_jp_check_perc: ttk.Label
        self.label_copy_perc: ttk.Label
        self.label_movies_perc: ttk.Label
        self.label_elf_perc: ttk.Label
        self.label_contents_perc: ttk.Label

        self.progress_eu_check: ttk.Progressbar
        self.progress_jp_check: ttk.Progressbar
        self.progress_copy: ttk.Progressbar
        self.progress_movies: ttk.Progressbar
        self.progress_elf: ttk.Progressbar
        self.progress_contents: ttk.Progressbar

        self.button_done: ttk.Button

        self.info_frame: ttk.LabelFrame
        self.label_info: ttk.Label

        self.sizegrip: ttk.Sizegrip

        # Create control variables
        self.var_fix_kirie_camera_bug = tk.BooleanVar(value=True)
        self.var_16_9 = tk.BooleanVar()
        self.var_disable_bloom = tk.BooleanVar()
        self.var_remove_dark_filter = tk.BooleanVar()
        self.var_remove_ingame_noise = tk.BooleanVar()
        self.var_remove_title_noise = tk.BooleanVar()
        self.var_force_language_selection = tk.BooleanVar()
        self.var_replace_title_jp = tk.BooleanVar()
        self.var_replace_models = tk.BooleanVar()

        self.var_progress_eu_check = tk.DoubleVar(value=0.0)  # 0.0 - 100.0
        self.var_progress_jp_check = tk.DoubleVar(value=0.0)  # 0.0 - 100.0
        self.var_progress_copy = tk.DoubleVar(value=0.0)  # 0.0 - 100.0
        self.var_progress_movies = tk.DoubleVar(value=0.0)  # 0.0 - 100.0
        self.var_progress_elf = tk.DoubleVar(value=0.0)  # 0.0 - 100.0
        self.var_progress_contents = tk.DoubleVar(value=0.0)  # 0.0 - 100.0

        # variables
        self.eu_iso_path: str
        self.jp_iso_path: str
        self.undub_iso_path: str

        # Create widgets :)
        self.setup_widgets()

        self.undub_thread: threading.Thread

    def setup_widgets(self):
        self.columnconfigure(index=0, weight=0)
        self.columnconfigure(index=1, weight=0)
        self.columnconfigure(index=2, weight=1)

        self.rowconfigure(index=0, weight=0)
        self.rowconfigure(index=1, weight=1)
        self.rowconfigure(index=2, weight=0)

        # ################################
        # Create a Frame for input widgets
        self.widgets_frame = ttk.Frame(self, padding=(0, 0, 0, 0))
        self.widgets_frame.grid(row=0, column=0, padx=(20, 0), pady=(29, 0), sticky="nsew", rowspan=1)
        self.widgets_frame.columnconfigure(index=0, weight=1)

        # Button ISO EU
        self.button_iso_eu = ttk.Button(self.widgets_frame, text="(1) Select European ISO", command=self.select_eu_iso)
        self.button_iso_eu.grid(row=0, column=0, padx=0, pady=0, sticky="nsew", ipadx=10)
        self.add_help(
            self.button_iso_eu,
            """
            Select an untouched European ISO file.
            
            This file will be used as base for the undub.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        # Button ISO JP
        self.button_iso_jp = ttk.Button(
            self.widgets_frame, text="(2) Select Japanese ISO", state="disabled", command=self.select_jp_iso
        )
        self.button_iso_jp.grid(row=1, column=0, padx=0, pady=(10, 0), sticky="nsew", ipadx=10)
        self.add_help(
            self.button_iso_jp,
            """
            Select an untouched Japanese ISO file.

            This file will be used to extract japanese voices.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        # Button ISO Undub
        self.button_iso_undub = ttk.Button(
            self.widgets_frame, text="(3) Choose Output Undub ISO", state="disabled", command=self.select_undub_iso
        )
        self.button_iso_undub.grid(row=2, column=0, padx=0, pady=(10, 0), sticky="nsew", ipadx=10)
        self.add_help(
            self.button_iso_undub,
            """
            Choose the output path for the undub ISO file.
            
            This will be the path where the undub ISO will be written to.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        # ################################
        # Create a Frame for the Hack Checkbuttons
        self.patch_frame = ttk.LabelFrame(self, text="(4) Select Patches", padding=(20, 0))
        self.patch_frame.grid(row=0, column=1, padx=(20, 20), pady=(20, 0), sticky="nsew", rowspan=1)
        self.patch_frame.columnconfigure(index=0, weight=1)

        check_pad_top = 4

        # Checkbuttons
        self.check_fix_kirie_camera_bug = ttk.Checkbutton(
            self.patch_frame, text="Fix Kirie Camera Bug", variable=self.var_fix_kirie_camera_bug, state="disabled"
        )
        self.check_fix_kirie_camera_bug.grid(row=0, column=0, padx=0, pady=(10, check_pad_top), sticky="nsew")
        self.add_help(
            self.check_fix_kirie_camera_bug,
            """
            Fix Kirie Camera Bug.
            
            Fix for the Kirie Camera Bug, where aiming the camera to a certain spot during the last battle with
            Kirie may result in a game freeze.

            Thanks to weirdbeardgame for the fix.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        self.check_16_9 = ttk.Checkbutton(self.patch_frame, text="Force 16:9", variable=self.var_16_9, state="disabled")
        self.check_16_9.grid(row=1, column=0, padx=0, pady=check_pad_top, sticky="nsew")
        self.add_help(
            self.check_16_9,
            """
            Enable the 16:9 aspect ratio patch.
            
            Ingame will be rendered in 16:9 and movies will have black bars to preserve the original aspect ratio.
            
            Menus, on screen text and graphics, and the title screen will be stretched.
            
            Remember to force 16:9 aspect ratio in you TV!
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        self.check_disable_bloom = ttk.Checkbutton(
            self.patch_frame, text="Disable Bloom Effect", variable=self.var_disable_bloom, state="disabled"
        )
        self.check_disable_bloom.grid(row=2, column=0, padx=0, pady=check_pad_top, sticky="nsew")
        self.add_help(
            self.check_disable_bloom,
            """
            Disable ingame bloom effect.
            
            Ingame bloom effect will be disabled.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        self.check_remove_dark_filter = ttk.Checkbutton(
            self.patch_frame, text="Remove Dark Filter", variable=self.var_remove_dark_filter, state="disabled"
        )
        self.check_remove_dark_filter.grid(row=3, column=0, padx=0, pady=check_pad_top, sticky="nsew")
        self.add_help(
            self.check_remove_dark_filter,
            """
            Removes ingame dark filter.
            
            Ingame dark filter will be disabled.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        self.check_remove_ingame_noise = ttk.Checkbutton(
            self.patch_frame, text="Remove Ingame Noise", variable=self.var_remove_ingame_noise, state="disabled"
        )
        self.check_remove_ingame_noise.grid(row=4, column=0, padx=0, pady=check_pad_top, sticky="nsew")
        self.add_help(
            self.check_remove_ingame_noise,
            """
            Remove ingame noise.
            
            Ingame noise effect will be removed.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        self.check_remove_title_noise = ttk.Checkbutton(
            self.patch_frame, text="Remove Title Noise", variable=self.var_remove_title_noise, state="disabled"
        )
        self.check_remove_title_noise.grid(row=5, column=0, padx=0, pady=check_pad_top, sticky="nsew")
        self.add_help(
            self.check_remove_title_noise,
            """
            Remove title noise.
            
            Title noise effect will be removed
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        self.check_force_language_selection = ttk.Checkbutton(
            self.patch_frame,
            text="Force Language Selection",
            variable=self.var_force_language_selection,
            state="disabled",
        )
        self.check_force_language_selection.grid(row=6, column=0, padx=0, pady=check_pad_top, sticky="nsew")
        self.add_help(
            self.check_force_language_selection,
            """
            Force language selection on launch.
            
            Language selection will be shown at every game launch.
            
            Note that this hack disables loading user preferences at startup completely (as language is one of the preferences).
            This means that settings such as brightness and volume would also be reset to default every time.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        self.check_replace_title_jp = ttk.Checkbutton(
            self.patch_frame,
            text="Japanese Title Screen",
            variable=self.var_replace_title_jp,
            state="disabled",
        )
        self.check_replace_title_jp.grid(row=7, column=0, padx=0, pady=check_pad_top, sticky="nsew")
        self.add_help(
            self.check_replace_title_jp,
            """
            Replace title screen with the Japanese one.
            
            The title screen will be replaced with the one found in the Japanese version.
            
            Menu entries and menu fonts will not change as the Japanese ones are not compatible and cannot be replaced.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        self.check_replace_models = ttk.Checkbutton(
            self.patch_frame,
            text="Replace Models",
            variable=self.var_replace_models,
            state="disabled",
        )
        self.check_replace_models.grid(row=8, column=0, padx=0, pady=(check_pad_top, 10), sticky="nsew")
        self.add_help(
            self.check_replace_models,
            """
            Replace all Miku models with the original Japanese version.
            
            All Miku models, including both 3D and 2D ones such as the menu portrait and the background image
            displayed at the beginning of each night, will be replaced with the ones found in the Japanese version.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        # ################################
        # Progress Frame
        self.progress_frame = ttk.Frame(self, padding=(0, 0, 0, 0))
        self.progress_frame.grid(row=0, column=2, padx=(0, 20), pady=(20, 0), sticky="nsew", rowspan=1, ipadx=0)
        self.progress_frame.columnconfigure(index=0, weight=1)

        # Button Start Undub
        self.button_start_undub = ttk.Button(
            self.progress_frame, text="(5) Start Undub", state="disabled", command=self.start_undub
        )
        self.button_start_undub.grid(row=0, column=0, padx=0, pady=(9, 10), sticky="nsew", ipadx=10)
        self.add_help(
            self.button_start_undub,
            """
            Starts the undub process.
            
            Progress will be shown below by the 6 progress bars. If an error occurs at any point, the corresponding progress bar's text
            will become red, and an error description will be shown here.
        """,  # noqa: E501 # pylint: disable=line-too-long
        )

        # Progressbar
        self.pb_frame_box = ttk.Frame(self.progress_frame, padding=(0, 0, 0, 0))
        self.pb_frame_box.grid(row=1, column=0, padx=(0, 0), pady=(20, 10), sticky="nsew", rowspan=3, ipadx=50)
        self.pb_frame_box.columnconfigure(index=0, weight=0)
        self.pb_frame_box.columnconfigure(index=1, weight=1)
        self.pb_frame_box.columnconfigure(index=2, weight=0, minsize=75)

        def add_pb(_text, i, var, _pady=10):
            label = ttk.Label(self.pb_frame_box, text=_text, state="disabled")
            label.grid(row=i, column=0, pady=(0, _pady), sticky="w")

            progress_undub = ttk.Progressbar(self.pb_frame_box, value=0, variable=var, mode="determinate")
            progress_undub.grid(row=i, column=1, padx=(10, 10), pady=(0, _pady), sticky="ew")

            # Label
            label_progress = ttk.Label(self.pb_frame_box, text="?/?", state="disabled")
            label_progress.grid(row=i, column=2, pady=(0, _pady), sticky="e")

            return label, progress_undub, label_progress

        self.label_eu_check, self.progress_eu_check, self.label_eu_check_perc = add_pb(
            "Checking EU ISO", 0, self.var_progress_eu_check
        )

        self.label_jp_check, self.progress_jp_check, self.label_jp_check_perc = add_pb(
            "Checking JP ISO", 1, self.var_progress_jp_check
        )

        self.label_copy, self.progress_copy, self.label_copy_perc = add_pb("Copying ISO", 2, self.var_progress_copy)

        self.label_movies, self.progress_movies, self.label_movies_perc = add_pb(
            "Patching Movies", 3, self.var_progress_movies
        )

        self.label_elf, self.progress_elf, self.label_elf_perc = add_pb("Patching ELF", 4, self.var_progress_elf)

        self.label_contents, self.progress_contents, self.label_contents_perc = add_pb(
            "Patching Contents", 5, self.var_progress_contents
        )

        # Button Done
        self.button_done = ttk.Button(self.progress_frame, text="Done", state="disabled", command=self.undub_done)
        self.button_done.grid(row=6, column=0, padx=0, pady=(9, 10), sticky="nsew", ipadx=10)

        # ################################
        self.info_frame = ttk.LabelFrame(self, text="Info", padding=(20, 0))
        self.info_frame.grid(row=1, column=0, padx=(20, 20), pady=(0, 0), sticky="nsew", rowspan=1, columnspan=3)
        self.info_frame.columnconfigure(index=0, weight=1)
        self.info_frame.rowconfigure(index=0, weight=1, minsize=200)

        _default_text = format_help_text(
            """
            Welcome to karas84's Project Zero Undubber!
            
            Follow the 5 steps to create your custom undub. You will need:
            
            $ - An original and untouched European ISO of Project Zero (SLES 508.21)
            $ - An original and untouched Japanese ISO of Zero (SLPS 250.74)
            
            If you like, you can choose to apply extra patches such as the 16:9 aspect ratio or removing the ingame bloom effect.
            
            You can obtain more help by hovering the mouse on each component (e.g., a button or a checkbox) of this window.
            You'll see here the help for that specific component.
        """  # noqa: E501 # pylint: disable=line-too-long
        )
        self.label_info = ttk.Label(self.info_frame, text=_default_text)
        self.label_info.configure(anchor="nw")
        self.label_info.grid(row=0, column=0, pady=(0, 10), sticky="nsew")
        setattr(self.label_info, "_default_text", _default_text)

        # ################################
        # Sizegrip
        self.sizegrip = ttk.Sizegrip(self)
        self.sizegrip.grid(row=3, column=2, padx=(0, 5), pady=(0, 5), sticky="e")

    def select_eu_iso(self):
        eu_iso_path = fd.askopenfilename(
            title="Select European ISO",
            initialdir=os.path.expanduser("~"),
            filetypes=self.filetypes,
        )

        if eu_iso_path:
            self.eu_iso_path = eu_iso_path
            self.button_iso_jp.state(["!disabled"])

    def select_jp_iso(self):
        jp_iso_path = fd.askopenfilename(
            title="Select Japanese ISO",
            initialdir=os.path.dirname(self.eu_iso_path),
            filetypes=self.filetypes,
        )

        if jp_iso_path:
            self.jp_iso_path = jp_iso_path
            self.button_iso_undub.state(["!disabled"])

    def select_undub_iso(self):
        undub_iso_path = fd.asksaveasfilename(
            title="Choose Output Undub ISO",
            initialdir=os.path.dirname(self.eu_iso_path),
            filetypes=self.filetypes,
        )

        if undub_iso_path:
            if os.path.splitext(undub_iso_path.lower())[1] != ".iso":
                undub_iso_path += ".iso"
            self.undub_iso_path = undub_iso_path
            self.check_fix_kirie_camera_bug.state(["!disabled"])
            self.check_16_9.state(["!disabled"])
            self.check_disable_bloom.state(["!disabled"])
            self.check_remove_dark_filter.state(["!disabled"])
            self.check_remove_ingame_noise.state(["!disabled"])
            self.check_remove_title_noise.state(["!disabled"])
            self.check_force_language_selection.state(["!disabled"])
            self.check_replace_title_jp.state(["!disabled"])
            self.check_replace_models.state(["!disabled"])
            self.button_start_undub.state(["!disabled"])

    def start_undub(self):
        self.button_iso_eu.state(["disabled"])
        self.button_iso_jp.state(["disabled"])
        self.button_iso_undub.state(["disabled"])
        self.check_fix_kirie_camera_bug.state(["disabled"])
        self.check_16_9.state(["disabled"])
        self.check_disable_bloom.state(["disabled"])
        self.check_remove_dark_filter.state(["disabled"])
        self.check_remove_ingame_noise.state(["disabled"])
        self.check_remove_title_noise.state(["disabled"])
        self.check_force_language_selection.state(["disabled"])
        self.check_replace_title_jp.state(["disabled"])
        self.check_replace_models.state(["disabled"])
        self.button_start_undub.state(["disabled"])

        self._undub_started = True
        self.label_info["text"] = format_help_text(
            """
            Undubbing process started.
            
            Please wait while the game is being patched.
        """
        )

        self.undub_thread = UndubThread(self)
        self.undub_thread.daemon = True
        self.undub_thread.start()

    def undub_done(self):
        self.quit()

    def add_help(self, widget, help_text):
        setattr(widget, "_help_text", format_help_text(help_text))
        widget.bind("<Enter>", self._show_help)
        widget.bind("<Leave>", self._show_help)

    def _show_help(self, event: tk.Event):
        if self._undub_started:
            return

        text = getattr(self.label_info, "_default_text")
        if event.type == tk.EventType.Enter:
            text = getattr(event.widget, "_help_text", text)
        # elif event.type == tk.EventType.Leave:
        self.label_info["text"] = text

    @staticmethod
    def _make_red(widget):
        widget.configure(foreground="#E30B5C")


def main():
    parser = argparse.ArgumentParser(description="Project Zero Undub GUI")

    parser.add_argument(
        "-f",
        "--foreground",
        dest="foreground",
        action="store_true",
        help="do not detach from shell (unix only; on windows always run in foreground)",
    )

    args = parser.parse_args()

    if not args.foreground and hasattr(os, "fork") and os.fork():
        sys.exit()

    root = tk.Tk()
    root.title("Project Zero Undub by karas84")

    style = ttk.Style(root)
    style.theme_use("default")

    app = App(root)
    app.pack(fill="both", expand=True)

    # Set a minsize for the window, and place it in the middle
    root.update()
    root.minsize(root.winfo_width(), root.winfo_height())
    x_coordinate = int((root.winfo_screenwidth() / 2) - (root.winfo_width() / 2))
    y_coordinate = int((root.winfo_screenheight() / 2) - (root.winfo_height() / 2))
    root.geometry(f"+{x_coordinate}+{y_coordinate - 20}")

    root.mainloop()
