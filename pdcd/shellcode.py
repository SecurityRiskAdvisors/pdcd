def sc_to_hexstr(shellcode) -> str:
    # convert binary shellcode to a hex string (e.g. \x00)
    # https://github.com/byt3bl33d3r/SILENTTRINITY/blob/master/silenttrinity/core/utils.py -> shellcode_to_hex_string
    byte_array = []
    shellcode_hex = shellcode.hex()
    for i in range(0, len(shellcode_hex), 2):
        byte = shellcode_hex[i : i + 2]
        byte_array.append(f"\\x{byte.upper()}")

    return "".join(byte_array)


def hexstr_to_sc_arr(shellcode: str, delimter: str = "\\x") -> list:
    # decodes a hex shellcode string (e.g. \\x00\\x00) to a list
    return [int(dec, 16) for dec in shellcode.split(delimter) if len(dec) == 2]


def hexstr_to_sc_file(path: str, **kwargs) -> None:
    # Calls hexstr_to_sc_arr on shellcode then writes to a file
    sc = bytearray(hexstr_to_sc_arr(**kwargs))

    with open(path, "wb") as f:
        f.write(sc)


class Shellcode:
    def __init__(self, shellcode: bytes = None, arch: str = None):
        self._shellcode: bytes = bytes()
        if shellcode:
            self._shellcode: bytes = shellcode
        self.arch: str = arch if arch else None

    @property
    def shellcode(self) -> bytes:
        return self._shellcode

    @shellcode.setter
    def shellcode(self, value: bytes):
        self._shellcode = value

    @property
    def hexstr(self):
        # shellcode represented as a hex str (e.g. \\x00\\x00)
        return sc_to_hexstr(shellcode=self.shellcode)

    @classmethod
    def from_file(cls, src: str, **kwargs) -> "ShellcodeInput":
        # create shellcode object from a .bin-type file
        sc = cls(**kwargs)
        sc.set_from_file(src=src)
        return sc

    def set_from_file(self, src: str):
        # update shellcode contents by reading from a file
        with open(src, "rb") as f:
            sc = f.read()
        self.shellcode = sc
        return self

    @classmethod
    def from_string(cls, string: str, **kwargs) -> "ShellcodeInput":
        # create shellcode object from a hex string (e.g. \\x00\\x00)
        return cls(shellcode=bytes(hexstr_to_sc_arr(shellcode=string)), **kwargs)

    def to_file(self, path: str):
        # write shellcode to a file as bytes
        with open(path, "wb") as f:
            f.write(self.shellcode)
