from contextlib import contextmanager

import pycdlib


class CDDVD:
    def __init__(self, iso_path: str):
        self.iso = pycdlib.PyCdlib()
        self.iso.open(iso_path, mode="rb")
        self.iso9660_facade = self.iso.get_iso9660_facade()

        # name to iso name (e.g. README.TXT -> README.TXT;1)
        self.files = {file_name.rsplit(";", 1)[0]: file_name for file_name in next(self.iso9660_facade.walk("/"))[2]}

    def find_file(self, file_name: str):
        upper_name = file_name.upper()

        if upper_name in self.files:
            file_name = self.files[upper_name]

        elif file_name not in self.files.values():
            return None

        return file_name

    def read_file(self, file_name: str, size=-1, offset=0):
        try:
            with self.open(file_name) as file_h:
                file_h.seek(offset)
                return file_h.read(size)
        except FileNotFoundError:
            return None

    @contextmanager
    def open(self, file_name: str):
        _file_name = self.find_file(file_name)

        if not _file_name:
            raise FileNotFoundError(file_name)

        with self.iso9660_facade.open_file_from_iso(f"/{_file_name}") as file_h:
            yield file_h

    def get_file_size(self, file_name):
        file_name = self.find_file(file_name)

        if file_name is None:
            return None

        return self.iso9660_facade.get_record(f"/{file_name}").get_data_length()

    def __delete__(self, instance):
        self.iso.close()
