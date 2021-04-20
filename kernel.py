import functools
import random
import re
import sys
import time
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Generator, IO, List, Optional, Union

import tools
from dolreader import DolFile, SectionCountFullError, UnmappedAddressError
from fileutils import (get_alignment, read_uint16, read_uint32, write_bool,
                       write_sint32, write_ubyte, write_uint16, write_uint32)

try:
    import chardet
except ImportError as IE:
    print(IE)
    sys.exit(1)


def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        value = func(*args, **kwargs)
        end = time.perf_counter()
        print(tools.color_text(
            f"\n  :: Completed in {(end - start):0.4f} seconds!\n", defaultColor=tools.TGREENLIT))
        return value
    return wrapper




class GCT(object):

    def __init__(self):
        self.codelist: List[GeckoCode] = []

    def __len__(self):
        return self.byteSize

    @classmethod
    def from_bytes(cls, f: IO):
        gct = cls()
        gct.bytes_to_codelist(f)
        return gct

    @property
    def byteSize(self):
        return sum([len(c) for c in self.codelist])

    @property
    def groupSize(self):
        return (self.byteSize >> 3)

    @property
    def virtualSize(self):
        return len(self.codelist)

    def add_geckocode(self, code: GeckoCode):
        self.codelist.append(code)

    def remove_geckocode(self, code: GeckoCode):
        self.codelist.remove(code)

    def bytes_to_codelist(self, f: IO):
        while metadata := f.read(4):
            info = self._rawData.read(4)
            address = 0x80000000 | (int.from_bytes(
                metadata, byteorder="big", signed=False) & 0x1FFFFFF)
            codetype = (int.from_bytes(
                metadata, "big", signed=False) >> 24) & 0xFF
            isPointerType = (codetype & 0x10 != 0)

            if ((codetype & 0xEF) <= 0x0F):
                self.add_geckocode(
                    GeckoCode(GeckoCode.Type.WRITE, info, address, isPointerType))
            elif ((codetype & 0xEF) <= 0x2F):
                ifBlock = GeckoCode(GeckoCode.Type.IF, info,
                                    address, isPointerType)
                ifBlock.populate_from_bytes(f)
                self.add_geckocode(
                    GeckoCode(GeckoCode.Type.IF, info, address, isPointerType))
            elif ((codetype & 0xEF) <= 0xC5):
                self.add_geckocode(
                    GeckoCode(GeckoCode.Type.ASM, info, address, isPointerType))
            elif ((codetype & 0xEF) <= 0xC7):
                self.add_geckocode(
                    GeckoCode(GeckoCode.Type.BRANCH, info, address, isPointerType))
            elif codetype == 0xF0:
                break

    def to_bytes(self) -> bytes:
        rawCodelist = b"\x00\xD0\xC0\xDE"*2
        for code in self.codelist:
            if code._type == GeckoCode.Type.WRITE_8:
                metadata = (code.address & 0x17FFFFF).to_bytes(4, "big", signed=False)
                rawCodelist += metadata + code.info
                rawCodelist += code.value

    def apply_to_dol(self, dol: DolFile):
        for code in self.codelist:
            if code.is_preprocess_allowed():
                code.apply(dol)
                self.remove_geckocode(code)


class CodeHandler(object):

    class Types:
        MINI = "MINI"
        FULL = "FULL"

    WiiVIHook = b"\x7C\xE3\x3B\x78\x38\x87\x00\x34\x38\xA7\x00\x38\x38\xC7\x00\x4C"
    GCNVIHook = b"\x7C\x03\x00\x34\x38\x83\x00\x20\x54\x85\x08\x3C\x7C\x7F\x2A\x14\xA0\x03\x00\x00\x7C\x7D\x2A\x14\x20\xA4\x00\x3F\xB0\x03\x00\x00"
    WiiGXDrawHook = b"\x3C\xA0\xCC\x01\x38\x00\x00\x61\x3C\x80\x45\x00\x98\x05\x80\x00"
    GCNGXDrawHook = b"\x38\x00\x00\x61\x3C\xA0\xCC\x01\x3C\x80\x45\x00\x98\x05\x80\x00"
    WiiPADHook = b"\x3A\xB5\x00\x01\x3A\x73\x00\x0C\x2C\x15\x00\x04\x3B\x18\x00\x0C"
    GCNPADHook = b"\x3A\xB5\x00\x01\x2C\x15\x00\x04\x3B\x18\x00\x0C\x3B\xFF\x00\x0C"

    def __init__(self, f):
        self._rawData = BytesIO(f.read())

        """Get codelist pointer"""
        self._rawData.seek(0xFA)
        codelistUpper = self._rawData.read(2).hex()
        self._rawData.seek(0xFE)
        codelistLower = self._rawData.read(2).hex()

        self._rawDataPointer = int(codelistUpper[2:] + codelistLower[2:], 16)
        self.handlerLength = tools.stream_size(self._rawData)
        self.initAddress = 0x80001800
        self.startAddress = 0x800018A8

        self.allocation = None
        self.hookAddress = None
        self.hookType = None
        self.gct = GCT()
        self.includeAll = False
        self.optimizeList = False

        if self.handlerLength < 0x900:
            self.type = CodeHandler.Types.MINI
        else:
            self.type = CodeHandler.Types.FULL

        f.seek(0)

    def init_gct(self, gctFile: Path, tmpdir: Path = None):
        if tmpdir is not None:
            _tmpGct = tmpdir / "gct.bin"
        else:
            _tmpGct = Path("gct.bin")

        if gctFile.suffix.lower() == ".txt":
            with _tmpGct.open("wb+") as temp:
                temp.write(bytes.fromhex("00D0C0DE"*2 +
                                         self.parse_input(gctFile) + "F000000000000000"))
                temp.seek(0)
                self.gct = GCT(temp)
        elif gctFile.suffix.lower() == ".gct":
            with gctFile.open("rb") as gct:
                self.gct = GCT(gct)
        elif gctFile.suffix == "":
            with _tmpGct.open("wb+") as temp:
                temp.write(b"\x00\xD0\xC0\xDE"*2)

                for file in gctFile.iterdir():
                    if file.is_file():
                        if file.suffix.lower() == ".txt":
                            temp.write(bytes.fromhex(self.parse_input(file)))
                        elif file.suffix.lower() == ".gct":
                            with file.open("rb") as gct:
                                temp.write(gct.read()[8:-8])
                        else:
                            print(tools.color_text(
                                f"  :: HINT: {file} is not a .txt or .gct file", defaultColor=tools.TYELLOWLIT))

                temp.write(b"\xF0\x00\x00\x00\x00\x00\x00\x00")
                temp.seek(0)
                self.gct = GCT(temp)
        else:
            raise NotImplementedError(
                f"Parsing file type `{gctFile.suffix}' as a GCT is unsupported")

    def parse_input(self, geckoText: Path) -> str:
        with geckoText.open("rb") as gecko:
            result = chardet.detect(gecko.read())
            encodeType = result["encoding"]

        with geckoText.open("r", encoding=encodeType) as gecko:
            gct = ""
            state = None

            for line in gecko.readlines():
                if line in ("", "\n"):
                    continue

                if state is None:
                    if line.startswith("$") or line.startswith("["):
                        state = "Dolphin"
                    else:
                        state = "OcarinaM"

                try:
                    if state == "OcarinaM":
                        if self.includeAll:
                            geckoLine = re.findall(
                                r"[A-F0-9]{8}[\t\f ][A-F0-9]{8}", line, re.IGNORECASE)[0]
                        else:
                            geckoLine = re.findall(
                                r"(?:\*\s*)([A-F0-9]{8}[\t\f ][A-F0-9]{8})", line, re.IGNORECASE)[0]
                    else:
                        geckoLine = re.findall(
                            r"(?<![$\*])[A-F0-9]{8}[\t\f ][A-F0-9]{8}", line, re.IGNORECASE)[0]
                except IndexError:
                    continue

                gct += geckoLine.replace(" ", "").strip()

        return gct

    @staticmethod
    def encrypt_key(key: int) -> int:
        b1 = key & 0xFF
        b2 = (key >> 8) & 0xFF
        b3 = (key >> 16) & 0xFF
        b4 = (key >> 24) & 0xFF
        b3 ^= b4
        b2 ^= b3
        b1 ^= b2
        return (b1 << 24) | (b2 << 16) | (b3 << 8) | b4

    def encrypt_codes(self, key: int):
        self.gct._rawData.seek(0)
        i = 0
        while True:
            try:
                packet = read_uint32(self.gct._rawData)
                self.gct._rawData.seek(-4, 1)
                write_uint32(self.gct._rawData, (packet ^ key) & 0xFFFFFFFF)
                key += (i << 3) & 0xFFFFFFFF
                if key > 0xFFFFFFFF:
                    key -= 0x100000000
                i += 1
            except:
                break

    def find_variable_data(self, variable) -> int:
        self._rawData.seek(0)

        while sample := self._rawData.read(4):
            if sample == variable:
                return self._rawData.tell() - 4

        return None

    def set_hook_instruction(self, dolFile: DolFile, address: int, varOffset: int, lk=0):
        self._rawData.seek(varOffset)
        dolFile.seek(address)
        ppc = read_uint32(dolFile)

        if ((((ppc >> 24) & 0xFF) > 0x47 and ((ppc >> 24) & 0xFF) < 0x4C) or (((ppc >> 24) & 0xFF) > 0x3F and ((ppc >> 24) & 0xFF) < 0x44)):
            to, conditional = dolFile.extract_branch_addr(address)
            if conditional:
                raise NotImplementedError(
                    "Hooking to a conditional non spr branch is unsupported")
            write_uint32(self._rawData, (to - (self.initAddress +
                                               varOffset)) & 0x3FFFFFD | 0x48000000 | lk)
        else:
            write_uint32(self._rawData, ppc)

    def set_variables(self, dolFile: DolFile):
        varOffset = self.find_variable_data(b"\x00\xDE\xDE\xDE")
        if varOffset is None:
            raise RuntimeError(tools.color_text(
                "Variable codehandler data not found\n", defaultColor=tools.TREDLIT))

        self.set_hook_instruction(dolFile, self.hookAddress, varOffset, 0)

        self._rawData.seek(varOffset + 4)
        write_uint32(self._rawData, ((self.hookAddress + 4) -
                                     (self.initAddress + (varOffset + 4))) & 0x3FFFFFD | 0x48000000 | 0)


class KernelLoader(object):

    def __init__(self, f, cli: tools.CommandLineParser = None):
        self._rawData = BytesIO(f.read())
        self._initDataList = None
        self._gpModDataList = None
        self._gpDiscDataList = None
        self._gpKeyAddrList = None
        self._cli = cli
        self.initAddress = None
        self.protect = False
        self.verbosity = 0
        self.quiet = False
        self.encrypt = False

    def error(self, msg: str):
        if self._cli is not None:
            self._cli.error(msg)
        else:
            print(msg)
            sys.exit(1)

    def set_variables(self, entryPoint: list, baseOffset: int = 0):
        self._rawData.seek(0)

        if self._gpModDataList is None:
            return

        while sample := self._rawData.read(2):
            if sample == b"GH":
                self._rawData.seek(-2, 1)
                write_uint16(self._rawData, self._gpModDataList[0])
            elif sample == b"GL":
                self._rawData.seek(-2, 1)
                write_uint16(self._rawData, baseOffset +
                             self._gpModDataList[1])
            elif sample == b"IH":
                self._rawData.seek(-2, 1)
                write_uint16(self._rawData, entryPoint[0])
            elif sample == b"IL":
                self._rawData.seek(-2, 1)
                write_uint16(self._rawData, entryPoint[1])
            elif sample == b"KH":
                self._rawData.seek(-2, 1)
                write_uint16(self._rawData, self._gpKeyAddrList[0])
            elif sample == b"KL":
                self._rawData.seek(-2, 1)
                write_uint16(self._rawData, baseOffset +
                             self._gpKeyAddrList[1])

    def complete_data(self, codeHandler: CodeHandler, initpoint: list):
        _upperAddr, _lowerAddr = (
            (self.initAddress >> 16) & 0xFFFF, self.initAddress & 0xFFFF)
        _key = random.randrange(0x100000000)
        self._rawData.seek(0)

        while sample := self._rawData.read(4):
            if sample == b"HEAP":  # Found keyword "HEAP". Goes with the resize of the heap
                self._rawData.seek(-4, 1)

                gpModInfoOffset = self._rawData.tell()
                gpModUpperAddr = _upperAddr + \
                    1 if (
                        _lowerAddr + gpModInfoOffset) > 0x7FFF else _upperAddr  # Absolute addressing

                if codeHandler.allocation == None:
                    codeHandler.allocation = (
                        codeHandler.handlerLength + codeHandler.gct.byteSize + 7) & -8

                write_uint32(self._rawData, codeHandler.allocation)

            elif sample == b"LSIZ":  # Found keyword "LSIZ". Goes with the size of the loader
                self._rawData.seek(-4, 1)
                write_uint32(self._rawData, len(self._rawData.getbuffer()))

            elif sample == b"HSIZ":  # Found keyword "HSIZ". Goes with the size of the codehandler
                self._rawData.seek(-4, 1)
                write_sint32(self._rawData, codeHandler.handlerLength)

            elif sample == b"CSIZ":  # Found keyword "CSIZ". Goes with the size of the codes
                self._rawData.seek(-4, 1)
                write_sint32(self._rawData, codeHandler.gct.byteSize)

            elif sample == b"HOOK":  # Found keyword "HOOK". Goes with the codehandler hook
                self._rawData.seek(-4, 1)
                write_uint32(self._rawData, codeHandler.hookAddress)

            elif sample == b"CRPT":  # Found keyword "CRPT". Boolean of the encryption
                self._rawData.seek(-4, 1)
                write_bool(self._rawData, self.encrypt, 4)

            elif sample == b"CYPT":  # Found keyword "CYPT". Encryption Key
                self._rawData.seek(-4, 1)

                gpKeyOffset = self._rawData.tell()
                gpKeyUpperAddr = _upperAddr + \
                    1 if (
                        _lowerAddr + gpKeyOffset) > 0x7FFF else _upperAddr  # Absolute addressing

                write_uint32(self._rawData, CodeHandler.encrypt_key(_key))

        if _lowerAddr + gpModInfoOffset > 0xFFFF:
            _lowerAddr -= 0x10000

        self._gpModDataList = (gpModUpperAddr, gpModInfoOffset)
        self._gpKeyAddrList = (gpKeyUpperAddr, gpKeyOffset)

        self.set_variables(initpoint, _lowerAddr)

        if self.encrypt:
            codeHandler.encrypt_codes(_key)

    def patch_arena(self, codeHandler: CodeHandler, dolFile: DolFile) -> tuple:
        self.complete_data(
            codeHandler, [(dolFile.entryPoint >> 16) & 0xFFFF, dolFile.entryPoint & 0xFFFF])

        self._rawData.seek(0, 2)
        self._rawData.write(codeHandler._rawData.getvalue() +
                            codeHandler.gct._rawData.getvalue())

        self._rawData.seek(0)
        _kernelData = self._rawData.getvalue()

        try:
            dolFile.append_text_sections([(_kernelData, self.initAddress)])
        except SectionCountFullError:
            try:
                dolFile.append_data_sections([(_kernelData, self.initAddress)])
            except SectionCountFullError:
                self.error(tools.color_text(
                    "There are no unused sections left for GeckoLoader to use!\n", defaultColor=tools.TREDLIT))

        dolFile.entryPoint = self.initAddress
        return True, None

    def patch_legacy(self, codeHandler: CodeHandler, dolFile: DolFile) -> tuple:
        codeHandler._rawData.seek(0)
        codeHandler.gct._rawData.seek(0)

        _handlerData = codeHandler._rawData.getvalue() + codeHandler.gct._rawData.getvalue()

        try:
            dolFile.append_text_sections(
                [(_handlerData, codeHandler.initAddress)])
        except SectionCountFullError:
            try:
                dolFile.append_data_sections(
                    [(_handlerData, codeHandler.initAddress)])
            except SectionCountFullError:
                self.error(tools.color_text(
                    "There are no unused sections left for GeckoLoader to use!\n", defaultColor=tools.TREDLIT))

        return True, None

    def protect_game(self, codeHandler: CodeHandler):
        _oldpos = codeHandler.gct._rawData.tell()

        protectdata = (b"\xC0\x00\x00\x00\x00\x00\x00\x17",
                       b"\x7C\x08\x02\xA6\x94\x21\xFF\x70",
                       b"\x90\x01\x00\x08\xBC\x61\x00\x0C",
                       b"\x48\x00\x00\x0D\x00\xD0\xC0\xDE",
                       b"\x00\xD0\xDE\xAD\x7F\xE8\x02\xA6",
                       b"\x3B\xDF\x00\x08\x3C\x60\x80\x00",
                       b"\x38\x80\x11\x00\x38\xA0\x00\x00",
                       b"\x60\x63\x1E\xF8\x7C\x89\x03\xA6",
                       b"\x38\x80\x00\x00\x7D\x03\x22\x14",
                       b"\x54\xE9\x06\x3E\x89\x08\x00\x08",
                       b"\x7D\x3F\x48\xAE\x38\xE7\x00\x01",
                       b"\x7C\x08\x48\x40\x41\x82\x00\x0C",
                       b"\x60\xA7\x00\x00\x48\x00\x00\x04",
                       b"\x54\xE8\x06\x3E\x28\x08\x00\x03",
                       b"\x41\x81\x00\x10\x38\x84\x00\x01",
                       b"\x42\x00\xFF\xCC\x48\x00\x00\x2C",
                       b"\x38\xA0\x00\x08\x7C\x84\x1A\x14",
                       b"\x7C\xA9\x03\xA6\x38\x60\x00\x00",
                       b"\x38\x84\xFF\xFF\x54\x66\x07\xBE",
                       b"\x7C\xDE\x30\xAE\x38\x63\x00\x01",
                       b"\x9C\xC4\x00\x01\x42\x00\xFF\xF0",
                       b"\xB8\x61\x00\x0C\x80\x01\x00\x08",
                       b"\x38\x21\x00\x90\x7C\x08\x03\xA6",
                       b"\x4E\x80\x00\x20\x00\x00\x00\x00")

        codeHandler.gct._rawData.seek(-8, 2)

        for line in protectdata:
            codeHandler.gct._rawData.write(line)

        codeHandler.gct._rawData.write(b"\xF0\x00\x00\x00\x00\x00\x00\x00")
        codeHandler.gct._rawData.seek(_oldpos)

    @timer
    def build(self, gctFile: Path, dolFile: DolFile, codeHandler: CodeHandler, tmpdir: Path, dump: Path):
        _oldStart = dolFile.entryPoint

        """Initialize our codes"""

        codeHandler.init_gct(gctFile, tmpdir)

        if codeHandler.gct is None:
            self.error(tools.color_text(
                "Valid codelist not found. Please provide a .txt/.gct file, or a folder of .txt/.gct files\n", defaultColor=tools.TREDLIT))

        if self.protect:
            self.protect_game(codeHandler)

        """Get entrypoint (or BSS midpoint) for insert"""

        if self.initAddress:
            try:
                dolFile.resolve_address(self.initAddress)
                self.error(tools.color_text(
                    f"Init address specified for GeckoLoader (0x{self.initAddress:X}) clobbers existing dol sections", defaultColor=tools.TREDLIT))
            except UnmappedAddressError:
                pass
        else:
            self.initAddress = dolFile.seek_nearest_unmapped(dolFile.bssAddress, len(
                self._rawData.getbuffer()) + codeHandler.handlerLength + codeHandler.gct.byteSize)
            self._rawData.seek(0)

        if codeHandler.optimizeList:
            codeHandler.gct.optimize_codelist(dolFile)

        """Is codelist optimized away?"""

        if codeHandler.gct._rawData.getvalue() == b"\x00\xD0\xC0\xDE\x00\xD0\xC0\xDE\xF0\x00\x00\x00\x00\x00\x00\x00":
            with dump.open("wb") as final:
                dolFile.save(final)

            if not self.quiet:
                if self.verbosity >= 3:
                    dolFile.print_info()
                    print("-"*64)
                if self.verbosity >= 1:
                    print(tools.color_text(
                        "\n  :: All codes have been successfully pre patched", defaultColor=tools.TGREENLIT))
            return

        hooked = determine_codehook(dolFile, codeHandler, False)
        if hooked:
            _status, _msg = self.patch_arena(codeHandler, dolFile)
        else:
            self.error(tools.color_text(
                "Failed to find a hook address. Try using option --codehook to use your own address\n", defaultColor=tools.TREDLIT))

        if _status is False:
            self.error(tools.color_text(
                _msg + "\n", defaultColor=tools.TREDLIT))
        elif codeHandler.allocation < codeHandler.gct.byteSize:
            self.error(tools.color_text(
                "Allocated codespace was smaller than the given codelist\n", defaultColor=tools.TYELLOW))

        with dump.open("wb") as final:
            dolFile.save(final)

        if self.quiet:
            return

        if self.verbosity >= 3:
            dolFile.print_info()
            print("-"*64)

        if self.verbosity >= 2:
            print("")
            info = [f"  :: Start of game modified to address 0x{self.initAddress:X}",
                    f"  :: Game function `__start()' located at address 0x{_oldStart:X}",
                    f"  :: Allocation is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.gct.byteSize:X}",
                    f"  :: Codehandler hooked at 0x{codeHandler.hookAddress:X}",
                    f"  :: Codehandler is of type `{codeHandler.type}'",
                    f"  :: Of the {DolFile.maxTextSections} text sections in this DOL file, {len(dolFile.textSections)} are now being used",
                    f"  :: Of the {DolFile.maxDataSections} text sections in this DOL file, {len(dolFile.dataSections)} are now being used"]

            for bit in info:
                print(tools.color_text(bit, defaultColor=tools.TGREENLIT))

        elif self.verbosity >= 1:
            print("")
            info = [f"  :: GeckoLoader set at address 0x{self.initAddress:X}",
                    f"  :: Legacy size is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.gct.byteSize:X}",
                    f"  :: Codehandler is of type `{codeHandler.type}'"]
            for bit in info:
                print(tools.color_text(bit, defaultColor=tools.TGREENLIT))


def determine_codehook(dolFile: DolFile, codeHandler: CodeHandler, hook=False) -> bool:
    if codeHandler.hookAddress is None:
        if not assert_code_hook(dolFile, codeHandler):
            return False

    if hook:
        codeHandler.set_variables(dolFile)
        insert_code_hook(dolFile, codeHandler, codeHandler.hookAddress)

    return True


def assert_code_hook(dolFile: DolFile, codeHandler: CodeHandler) -> bool:
    for section in dolFile.textSections:
        dolFile.seek(section["address"])
        sample = dolFile.read(section["size"])

        if codeHandler.hookType == "VI":
            result = sample.find(codeHandler.GCNVIHook)
        elif codeHandler.hookType == "GX":
            result = sample.find(codeHandler.GCNGXDrawHook)
        elif codeHandler.hookType == "PAD":
            result = sample.find(codeHandler.GCNPADHook)
        else:
            raise NotImplementedError(tools.color_text(
                f"Unsupported hook type specified ({codeHandler.hookType})", defaultColor=tools.TREDLIT))

        if result >= 0:
            dolFile.seek(section["address"] + result)
        else:
            if codeHandler.hookType == "VI":
                result = sample.find(codeHandler.WiiVIHook)
            elif codeHandler.hookType == "GX":
                result = sample.find(codeHandler.WiiGXDrawHook)
            elif codeHandler.hookType == "PAD":
                result = sample.find(codeHandler.WiiPADHook)
            else:
                raise NotImplementedError(tools.color_text(
                    f"Unsupported hook type specified ({codeHandler.hookType})", defaultColor=tools.TREDLIT))

            if result >= 0:
                dolFile.seek(section["address"] + result)
            else:
                continue

        while (sample := read_uint32(dolFile)) != 0x4E800020:
            pass

        dolFile.seek(-4, 1)
        codeHandler.hookAddress = dolFile.tell()

        return True
    return False


def insert_code_hook(dolFile: DolFile, codeHandler: CodeHandler, address: int):
    dolFile.seek(address)
    ppc = read_uint32(dolFile)

    if ((ppc >> 24) & 0xFF) > 0x3F and ((ppc >> 24) & 0xFF) < 0x48:
        raise NotImplementedError(tools.color_text(
            "Hooking the codehandler to a conditional non spr branch is unsupported", defaultColor=tools.TREDLIT))

    dolFile.seek(-4, 1)
    dolFile.insert_branch(codeHandler.startAddress, address, lk=0)
