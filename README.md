# ProjectZero Undub

Undub project for Tecmo's Project Zero - the EU version (the first one) for the PS2.

![Undub Process](docs/undub.gif)

## Why?

I first played Project Zero in 2010 and fell in love with everything about the game ...
well, everything except the English audio. I soon started making my own undubbed version
by merging the Japanese release (Zero) with the European one. At the time, it was an
entertaining journey of nights spent disassembling the main ELF, reverse-engineering
the game data, and transcribing the game audio from FMVs, and cutscenes. It was fun,
and I can safely say that I learned a lot from that experience.

## So, why now?

By chance, I stumbled on [wagrenier's GitHub page](https://github.com/wagrenier/ZeroUndub)
of the very same project more than 10 years later. That made me remember the good old
times, and I suddenly felt the urge to rewrite my old and ugly C code into modern python,
with a lot more additions! In fact, initially, the code was a mess of uncoordinated tools
that had to be run by hand. It produced a bunch of files (not a nice bootable ISO) that
required a not so easy to find program to be converted into an ISO image. Luckily, things
are a lot better now!

## What can it do?

With this code, it's possible to merge the European and Japanese versions of the game into
an undubbed European version. That is a European version but with all the audio / voices /
FMVs taken from the Japanese one. The original game was localized into 5 languages: English,
French, German, Spanish, and Italian. All languages share the same English audio but have
localized text and graphics. All languages except English have subtitles because, for some
reason, the developers decided not to include English subtitles in the English localization.
That is understandable but leaves the undubber with a severe problem since, once the English
audio is replaced with the Japanese one, subtitles become slightly necessary unless you are
fluent in Japanese. Still, I would argue that you are probably better off playing the original
Japanese game at that point.

This code re-enables the English subtitles and re-constructs the localized English file from
scratch, re-injecting the subtitles. I say re-injecting because the original English
localization does not have the English text of each FMV or in-game cutscene. Since they were
not to be shown in the first place, why bother? So a part of the allocated space for the text
has been filled with dummy text. But only a part of it. There are, in fact, 271 text entries
in each localization, but the English one has only 225 in it. By simply forcing the English
subtitles to show, the game WILL crash when trying to display the missing ones. By
reverse-engineering the localization binary file, it is possible to unpack it, replace the 225
dummy texts with the whole 271 English subtitles, and rebuild it into a perfectly working
English localization.

## Features

The idea of unpacking and re-constructing is a crucial aspect of this tool. This first
iteration of the Project Zero franchise packs all game-related files (except for FMVs) into
a huge 1.2GB binary file (IMG*BD.BIN). The file is accompanied by a small file (IMG_HD.BIN)
that serves as table of contents. From what I understand, the standard undubbing procedure
consists in replacing the specific bytes of each content to undub into the ISO at the correct
position. For example, to replace the English localization, one would need to find the exact
offset in the iso where the original one is stored and replace it, being very careful not to
exceed the original size. Doing so would overwrite data of other files, rendering the ISO
corrupted or not properly working. On the contrary, this tool takes a similar yet different
approach, by recreating and replacing the whole IMG_BD.BIN binary file with a new one containing
the patched contents. To do so, it parses the original IMG_BD.BIN binary file and extracts
all the necessary files for the undub process (localization files, audio, etc.). These files are
then replaced with the Japanese ones (or patched ones like for the English localization),
and a new binary file that can be replaced into the ISO is rebuilt from scratch. The only
constraint, as previously said, is that the new binary file has to be smaller or equal in size
to the original one. Luckily, the guys at Tecmo decided to align each file in the IMG_BD.BIN
file not just to an LBA multiple of 2048 (the size of a sector in an ISO) but to an LBA
multiple of 16 times 2048! The reason probably lies in DVD access timings, but according
to my tests, aligning the files to a smaller multiple of 2048 does not incur in access
timing problems. The only effect is the reduction in size of the resulting IMG_BD.BIN. In fact,
by aligning the files to LBAs just multiple of 2048, it is possible to save around 30MB, which
is plenty enough to compensate for the extra few kB of the English localization and the
difference in size that some Japanese audio files have with respect to the equivalent
English ones. This method effectively removes \_any* limitation to what can be injected into
the European version! So, contrary to other tools, this one does not need to sacrifice anything
in the original game, say a non-English language containing all 271 subtitles, to accommodate
the extra English subtitles. This results in a clean undubbed ISO where all the languages are
fully functional!

### In summary:

- The main ELF is patched to show the English subtitles
- English subtitles have been transcribed and injected into the English localization
- FMVs (both PAL and NTSC) have been remuxed with the Japanese audio track
- All other languages are left unchanged and functional
- The ELF can be further patched to add extra nice features! (see below)

### Extra features:

Usually, the game asks to choose a language only the first time, when no save data is
present. The following times the game starts in the previous language, forcing anyone
who would like to change the language to start the game without the memory card inserted. The
ELF can be patched to restore the language selection screen at every boot. The only
downside is that the game does not remember the video format preference. Meaning that if
previously the game was being played in NTSC format, that option must be reselected every
time. This is an optional feature, so it is left to the user's preference.

Given the recent progress in PS2 emulation, specifically regarding [PCSX2](https://pcsx2.net/)
emulator, the great community behind it has come up with nice enhancements, such as 16:9
(not stretched, but actual 16:9 in-game rendering) widescreen patches. Thanks to a tool
called "PS2 Patch Engine" developed by
[pelvicthrustman](https://www.psx-place.com/threads/ps2-patch-engine-by-pelvicthrustman.19167/)
and later ported to Linux ([PS2_Pnacher](https://github.com/Snaggly/PS2_Pnacher)) by
[Snaggly](https://github.com/Snaggly), it is possible to patch the ELF to incorporate some
of these patches. Obviously, I decided to include the relevant bits into the game ELF,
allowing to:

- Enable 16:9 aspect ratio in-game
- Enable 19:9 aspect ratio in FMVs via adding black borders instead of stretching (strongly
  suggested if the 19:9 in-game patch is enabled, but the user is free to leave them stretched
  if against the pillarbox effect)
- Remove in-game bloom effect
- Remove in-game dark filter
- Remove in-game noise effect
- Remove main menu noise effect

All the above community patches are optional, and the choice of which to enable is left
to the user of this software (although I recommend enabling them all, except for the main menu
noise effect which I actually prefer to leave it enabled).

## What's next?

During the complete rewrite of my old code, I rediscovered a lot of stuff about the game
files and their format. With a bit of effort, this information can be found on the internet,
but there is not a centralized source for it all. With time, I would like to create a small
compendium of what I ended up researching about PK2 (game packages), STR (game audio), OBJ
Localization files, Font files, and other stuff as well. This repository already contains a
lot of code to handle a good part of them. Still, if possible, I would like to release
specific tools to address each one of them and the relative documentation.

#### *Small Update*
*I've published some of the tools I used for the undub together with an initial documentation for some game formats here: [https://github.com/karas84/ProjectZeroTools](https://github.com/karas84/ProjectZeroTools).*

## Usage

The program comes as both a python3 command-line tool (with very few dependencies) or as a tkinter GUI.
To run it, you will need:

- A European Project Zero (SLES508.21) ISO image dumped from your own original copy of the game
- A Japanese Zero (SLPS250.74) ISO image dumped from your own original copy of the game
- Python 3.7 or newer

The program has been developed on Linux, but it also works on Windows if both python
and the needed dependencies are correctly installed (both natively or on WSL, although in
the first versions of WSL the disk access is quite slower than the native one and the
undubbing process may require more time to complete).

### Command Line Interface (CLI)

The command-line interface (CLI) can be launched using the `undub.py` file. It accepts 3
mandatory arguments:

- The path to the European ISO
- The path to the Japanese ISO
- The output path for the undubbed ISO

Additionally, several flags can be specified to patch the ELF with extra features. Please
refer to the program's help for further details.

### Graphical User Interface (GUI)

The graphical user interface (GUI) can be launched using the `undub_gui.py` file. It is
built upon the tkinter library, which should be installed manually (but often comes
preinstalled with python3).

Instructions on how to preform the undub are shown in the "Info" section of the GUI.

## Copyright Disclaimer

This tool is supposed to be used with ISO files obtained from your own legally owned copies
of the games (both European and Japanese versions). I do not condone piracy and strongly
believe that game developers MUST be supported. It is for this precise reason that this
tool does not contain any asset whatsoever of the original game. Because I believe that
only the copyright holder has the right to distribute the files. For the very same reason,
the missing English subtitles are not stored as plaintext English but are kept as
hex strings of the bitwise or operation with the original English localization binary file.
This way, only by using the original ISO file, the subtitles can be reconstructed and
injected into the final ISO.

## Final Notes

I've tested the undubbed version on both PCSX2 and my own PS2. I've played it through
various spots using several save files and never encountered a problem. This does not
mean that there are no bugs, so if you find anything, please submit an issue here, and
I will try to address it!

Moreover, I decided to release this tool to let other people, who share the same love
for this game like me, be able to enjoy it to the fullest. I do not seek recognition, so
there are no modifications in the undubbed version that carry my name or any way to
trace back the undubbed game to me. What you get is an exact copy of the European version,
but with Japanese audio.

## Acknowledgements

This tool would not exist if it wasn't for the hard work of many individuals, to whom
I'd like to give my thanks:

- First, [wagrenier](https://github.com/wagrenier), for his
  [ZeroUndub](https://github.com/wagrenier/ZeroUndub) project, who inspired me again
  to work on this software
- [wagrenier](https://github.com/wagrenier) again, for his excellent python version of
  [PssMux](https://github.com/wagrenier/PssMux), which makes this tool able to automatically
  undub all FMVs in the game!
- [wagrenier](https://github.com/wagrenier) again, for his help with replacing all game models with the Japanese ones
- [pgert](https://forums.pcsx2.net/Thread-PCSX2-Widescreen-Game-Patches?pid=240786#pid240786)
  and the whole [PCSX2 community](https://forums.pcsx2.net/) for the great patches that can
  be injected into the game
- [pelvicthrustman](https://www.psx-place.com/threads/ps2-patch-engine-by-pelvicthrustman.19167/)
  and [Snaggly](https://github.com/Snaggly) for their tools to inject patches into the ELF
- [weirdbeardgame](https://github.com/weirdbeardgame/), for the Kirie camera bug fix
- [FlamePurge](https://www.romhacking.net/community/1523/) for proofreading the subtitles
- All the guys out there on so many forums I've lost track of, that released bits of
  information about many game file formats
- Finally, to 2010 me, who painstakingly spent weeks building his own undub, reversed-engineered
  the game data and transcribed all FMVs and cutscenes
