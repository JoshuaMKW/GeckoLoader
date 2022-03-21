import functools
import random
import re
import string
import sys
import time
from enum import Enum
from io import BytesIO, StringIO
from pathlib import Path
from typing import BinaryIO, Dict, Generator, IO, Iterable, List, Optional, Set, TextIO, Tuple, Union

import tools
from dolreader.dol import DolFile, SectionCountFullError, UnmappedAddressError
from fileutils import (get_alignment, read_uint16, read_uint32, write_bool,
                       write_sint32, write_ubyte, write_uint16, write_uint32)
from geckolibs.gct import GeckoCodeTable
from geckolibs.geckocode import AsmExecute, GeckoCode

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


def create_branch(to: int, _from: int, lk: bool = False) -> int:
    """ Create a branch instruction at `_from`\n
        to:    address to branch to\n
        _from: address to branch from\n
        lk:    is branch linking? """

    _from &= 0xFFFFFFFC
    to &= 0xFFFFFFFC
    return (to - _from) & 0x3FFFFFD | 0x48000000 | (1 if lk else 0)


class CodeHandler(object):
    class Types(Enum):
        MINI = "MINI"
        FULL = "FULL"

    WiiVIHook = b"\x7C\xE3\x3B\x78\x38\x87\x00\x34\x38\xA7\x00\x38\x38\xC7\x00\x4C"
    GCNVIHook = b"\x7C\x03\x00\x34\x38\x83\x00\x20\x54\x85\x08\x3C\x7C\x7F\x2A\x14\xA0\x03\x00\x00\x7C\x7D\x2A\x14\x20\xA4\x00\x3F\xB0\x03\x00\x00"
    WiiGXDrawHook = b"\x3C\xA0\xCC\x01\x38\x00\x00\x61\x3C\x80\x45\x00\x98\x05\x80\x00"
    GCNGXDrawHook = b"\x38\x00\x00\x61\x3C\xA0\xCC\x01\x3C\x80\x45\x00\x98\x05\x80\x00"
    WiiPADHook = b"\x3A\xB5\x00\x01\x3A\x73\x00\x0C\x2C\x15\x00\x04\x3B\x18\x00\x0C"
    GCNPADHook = b"\x3A\xB5\x00\x01\x2C\x15\x00\x04\x3B\x18\x00\x0C\x3B\xFF\x00\x0C"

    def __init__(self, f: BinaryIO):
        self.baseAddress = int.from_bytes(f.read(4), "big", signed=False)
        self._rawData = BytesIO(f.read())
        self.gct: GeckoCodeTable = None

        # Get codelist pointer
        self._rawData.seek(0xFA)
        codelistUpper = self._rawData.read(2).hex()
        self._rawData.seek(0xFE)
        codelistLower = self._rawData.read(2).hex()

        self._rawDataPointer = int(codelistUpper[2:] + codelistLower[2:], 16)
        self.handlerLength = tools.stream_size(self._rawData)

        self.allocation = None
        self.hookAddress = None
        self.hookType = None
        self.includeAll = False
        self.optimizeList = False

        self.type = KernelLoader.HandlerType.MINI if self.handlerLength < 0x900 else KernelLoader.HandlerType.FULL

        f.seek(0)

    def init_gct(self, gctPath: Path):
        if gctPath.suffix.lower() == ".txt":
            self.gct = GeckoCodeTable.from_text(gctPath.read_text())
        elif gctPath.suffix.lower() == ".gct":
            self.gct = GeckoCodeTable.from_bytes(gctPath.read_bytes())
        elif gctPath.suffix == "":
            gct = GeckoCodeTable()
            for file in gctPath.iterdir():
                if not file.is_file():
                    continue

                if file.suffix.lower() == ".txt":
                    nextGCT = GeckoCodeTable.from_text(gctPath.read_text())
                    if gct.gameID == "GECK01":
                        gct.gameID = nextGCT.gameID
                        gct.gameName = nextGCT.gameName
                    gct += nextGCT
                elif file.suffix.lower() == ".gct":
                    nextGCT = GeckoCodeTable.from_bytes(gctPath.read_bytes())
                    gct += nextGCT
                else:
                    print(tools.color_text(
                        f"  :: HINT: {file} is not a .txt or .gct file", defaultColor=tools.TYELLOWLIT))
            self.gct = gct
        else:
            raise NotImplementedError(
                f"Parsing file type `{gctPath.suffix}' as a GCT is unsupported")

    def set_variables(self, dol: DolFile):
        varOffset = self.__find_variable_data(b"\x00\xDE\xDE\xDE")
        if varOffset is None:
            raise RuntimeError(tools.color_text(
                "Variable codehandler data not found\n", defaultColor=tools.TREDLIT))

        self.__set_hook_instruction(dol, self.hookAddress, varOffset, 0)

        self._rawData.seek(varOffset + 4)
        write_uint32(self._rawData, create_branch(self.hookAddress + 4,
                                                  self.baseAddress + (varOffset + 4), False))

    def __find_variable_data(self, variable) -> int:
        self._rawData.seek(0)

        while sample := self._rawData.read(4):
            if sample == variable:
                return self._rawData.tell() - 4

        return None

    def __set_hook_instruction(self, dol: DolFile, hookAddress: int, returnOffset: int, lk: bool = False):
        self._rawData.seek(returnOffset)
        dol.seek(hookAddress)
        ppc = read_uint32(dol)

        if ((((ppc >> 24) & 0xFF) > 0x47 and ((ppc >> 24) & 0xFF) < 0x4C) or (((ppc >> 24) & 0xFF) > 0x3F and ((ppc >> 24) & 0xFF) < 0x44)):
            to, conditional = dol.extract_branch_addr(hookAddress)
            if conditional:
                raise NotImplementedError(
                    "Hooking to a conditional non spr branch is unsupported")
            dol.insert_branch
            write_uint32(
                self._rawData,
                create_branch(to, self.baseAddress + returnOffset, lk)
            )
        else:
            write_uint32(self._rawData, ppc)


class KernelLoader(object):
    class DataCryptor(object):
        @ staticmethod
        def encrypt_key(key: int) -> int:
            b1 = key & 0xFF
            b2 = (key >> 8) & 0xFF
            b3 = (key >> 16) & 0xFF
            b4 = (key >> 24) & 0xFF
            b3 ^= b4
            b2 ^= b3
            b1 ^= b2
            return (b1 << 24) | (b2 << 16) | (b3 << 8) | b4

        @ staticmethod
        def decrypt_key(key: int) -> int:
            b1 = (key >> 24) & 0xFF
            b2 = (key >> 16) & 0xFF
            b3 = (key >> 8) & 0xFF
            b4 = key & 0xFF
            b1 ^= b2
            b2 ^= b3
            b3 ^= b4
            return (b4 << 24) | (b3 << 16) | (b2 << 8) | b1

        def __init__(self, key: int):
            self.key = key

        @ property
        def encryptedKey(self) -> int:
            return self.encrypt_key(self.key)

        def xorcrypt_data(self, data: bytes) -> bytes:
            stream = BytesIO(data)
            streamLength = len(stream.getbuffer())
            i = 0
            try:
                while (stream.tell() < streamLength):
                    packet = read_uint32(stream)
                    stream.seek(-4, 1)
                    write_uint32(stream, (packet ^ self.key) & 0xFFFFFFFF)
                    self.key += (i << 3) & 0xFFFFFFFF
                    if self.key > 0xFFFFFFFF:
                        self.key -= 0x100000000
                    i += 1
            except Exception:
                pass
            return stream.getvalue()

    class HandlerType(Enum):
        MINI = "MINI"
        FULL = "FULL"

    GeckoProtector = AsmExecute(
        b"                               \
        \x7C\x08\x02\xA6\x94\x21\xFF\x70 \
        \x90\x01\x00\x08\xBC\x61\x00\x0C \
        \x48\x00\x00\x0D\x00\xD0\xC0\xDE \
        \x00\xD0\xDE\xAD\x7F\xE8\x02\xA6 \
        \x3B\xDF\x00\x08\x3C\x60\x80\x00 \
        \x38\x80\x11\x00\x38\xA0\x00\x00 \
        \x60\x63\x1E\xF8\x7C\x89\x03\xA6 \
        \x38\x80\x00\x00\x7D\x03\x22\x14 \
        \x54\xE9\x06\x3E\x89\x08\x00\x08 \
        \x7D\x3F\x48\xAE\x38\xE7\x00\x01 \
        \x7C\x08\x48\x40\x41\x82\x00\x0C \
        \x60\xA7\x00\x00\x48\x00\x00\x04 \
        \x54\xE8\x06\x3E\x28\x08\x00\x03 \
        \x41\x81\x00\x10\x38\x84\x00\x01 \
        \x42\x00\xFF\xCC\x48\x00\x00\x2C \
        \x38\xA0\x00\x08\x7C\x84\x1A\x14 \
        \x7C\xA9\x03\xA6\x38\x60\x00\x00 \
        \x38\x84\xFF\xFF\x54\x66\x07\xBE \
        \x7C\xDE\x30\xAE\x38\x63\x00\x01 \
        \x9C\xC4\x00\x01\x42\x00\xFF\xF0 \
        \xB8\x61\x00\x0C\x80\x01\x00\x08 \
        \x38\x21\x00\x90\x7C\x08\x03\xA6 \
        \x4E\x80\x00\x20\x00\x00\x00\x00 \
        "
    )

    def __init__(self, f: BinaryIO, hookType: CodeHandler.Hook, hookAddress: int, initAddress: int,
                 allocation: Optional[int] = None, includeAllCodes: bool = False, optimizeCodes: bool = False,
                 protectGame: bool = False, encryptCodes: bool = False, cli: Optional[tools.CommandLineParser] = None):
        self.hookHandler = HookHandler(hookType)
        self.hookAddress = hookAddress
        self.initAddress = initAddress
        self.allocation = allocation
        self.includeAll = includeAllCodes
        self.optimize = optimizeCodes
        self.protect = protectGame
        self.encrypt = encryptCodes

        self._rawData = BytesIO(f.read())
        self._initDataList = None
        self._gpModDataList: Tuple[int, int] = None
        self._gpDiscDataList: Tuple[int, int] = None
        self._gpKeyAddrList: Tuple[int, int] = None

        self._cli = cli
        self._verbosity = 0
        self._quiet = False

    @ property
    def verbosity(self) -> int:
        return self._verbosity

    @ verbosity.setter
    def verbosity(self, level: int):
        self._verbosity = max(min(level, 0), 3)

    def silence(self):
        self._quiet = True

    def desilence(self):
        self._quiet = False

    def error(self, msg: str, buffer: TextIO = sys.stderr):
        if self._cli is not None:
            self._cli.error(msg)
        else:
            print(msg, file=buffer)
            sys.exit(1)

    def apply_reloc(self, key: bytes, value: int):
        keylen = len(key)
        self._rawData.seek(0)
        while (offset := self._rawData.getvalue().find(key)) >= 0:
            self._rawData.seek(offset)
            if keylen == 1:
                _bytes = (value & 0xFF).to_bytes(1, "big", signed=False)
            elif keylen == 2:
                _bytes = (value & 0xFFFF).to_bytes(2, "big", signed=False)
            elif keylen == 4:
                _bytes = (value & 0xFFFFFFFF).to_bytes(4, "big", signed=False)
            self._rawData.write(_bytes)

    def do_data_relocs(self, entryAddress: int, modAddress: int, encryptKeyAddress: int, baseOffset: int = 0):
        self.apply_reloc(b"GH", ((modAddress >> 16) & 0xFFFF))
        self.apply_reloc(b"GL", (modAddress & 0xFFFF) + baseOffset)
        self.apply_reloc(b"IH", (entryAddress >> 16) & 0xFFFF)
        self.apply_reloc(b"IL", entryAddress & 0xFFFF)
        self.apply_reloc(b"GH", ((encryptKeyAddress >> 16) & 0xFFFF))
        self.apply_reloc(b"GL", (encryptKeyAddress & 0xFFFF) + baseOffset)

    def complete_data(self, codeHandler: CodeHandler, initAddress: int):
        _upperAddr, _lowerAddr = (
            (self.initAddress >> 16) & 0xFFFF, self.initAddress & 0xFFFF)
        _key = random.randrange(0x100000000)
        self._rawData.seek(0)

        self.apply_reloc(b"HEAP", len(codeHandler) + len(codeHandler.gct))
        self.apply_reloc(b"LSIZ", len(self._rawData.getbuffer()))
        self.apply_reloc(b"HSIZ", len(codeHandler))
        self.apply_reloc(b"CSIZ", len(codeHandler.gct))
        self.apply_reloc(b"HOOK", self.hookAddress)
        self.apply_reloc(b"CRPT", int(self.encrypt))
        self.apply_reloc(b"CYPT", KernelLoader.DataCryptor.encrypt_key(_key))

        gpModInfoOffset = (self._rawData.getvalue().find(b"HEAP") << 16)
        gpModUpperAddr = _upperAddr + \
            1 if (
                _lowerAddr + gpModInfoOffset) > 0x7FFF else _upperAddr  # Absolute addressing
        gpKeyOffset = self._rawData.getvalue().find(b"CYPT")
        gpKeyUpperAddr = _upperAddr + \
            1 if (
                _lowerAddr + gpKeyOffset) > 0x7FFF else _upperAddr  # Absolute addressing

        if _lowerAddr + gpModInfoOffset > 0xFFFF:
            _lowerAddr -= 0x10000

        self.do_data_relocs(initAddress, ((gpModUpperAddr << 16) | gpModInfoOffset) & 0xFFFFFFFF, ((
            gpKeyUpperAddr << 16) | gpKeyOffset) & 0xFFFFFFFF, _lowerAddr)

        if self.encrypt:
            codeHandler.encrypt_codes(_key)

    def patch_arena(self, codeHandler: CodeHandler, dol: DolFile) -> tuple:
        self.complete_data(
            codeHandler, [(dol.entryPoint >> 16) & 0xFFFF, dol.entryPoint & 0xFFFF])

        self._rawData.seek(0, 2)
        self._rawData.write(codeHandler._rawData.getvalue() +
                            codeHandler.gct._rawData.getvalue())

        self._rawData.seek(0)
        _kernelData = self._rawData.getvalue()

        try:
            dol.append_text_sections([(_kernelData, self.initAddress)])
        except SectionCountFullError:
            try:
                dol.append_data_sections([(_kernelData, self.initAddress)])
            except SectionCountFullError:
                self.error(tools.color_text(
                    "There are no unused sections left for GeckoLoader to use!\n", defaultColor=tools.TREDLIT))

        dol.entryPoint = self.initAddress
        return True, None

    def patch_legacy(self, codeHandler: CodeHandler, dol: DolFile) -> tuple:
        codeHandler._rawData.seek(0)
        codeHandler.gct._rawData.seek(0)

        _handlerData = codeHandler._rawData.getvalue() + codeHandler.gct._rawData.getvalue()

        try:
            dol.append_text_sections(
                [(_handlerData, codeHandler.initAddress)])
        except SectionCountFullError:
            try:
                dol.append_data_sections(
                    [(_handlerData, codeHandler.initAddress)])
            except SectionCountFullError:
                self.error(tools.color_text(
                    "There are no unused sections left for GeckoLoader to use!\n", defaultColor=tools.TREDLIT))

        return True, None

    def protect_game(self, codeHandler: CodeHandler):
        codeHandler.gct.add_child(KernelLoader.GeckoProtector)

    @ timer
    def build(self, gctPath: Path, dol: DolFile, codeHandler: CodeHandler, tmpdir: Path, dump: Path):
        _oldStart = dol.entryPoint

        # Initialize our codes
        codeHandler.gct = self.load_gct_from(gctPath)

        if codeHandler.gct is None:
            self.error(tools.color_text(
                "Valid codelist not found. Please provide a .txt/.gct file, or a folder of .txt/.gct files\n", defaultColor=tools.TREDLIT))

        if self.protect:
            self.protect_game(codeHandler)

        # Get entrypoint (or BSS midpoint) for insert

        if self.initAddress:
            try:
                dol.resolve_address(self.initAddress)
                self.error(tools.color_text(
                    f"Init address specified for GeckoLoader (0x{self.initAddress:X}) clobbers existing dol sections", defaultColor=tools.TREDLIT))
            except UnmappedAddressError:
                pass
        else:
            self.initAddress = dol.seek_nearest_unmapped(dol.bssAddress, len(
                self._rawData.getbuffer()) + len(codeHandler) + len(codeHandler.gct))
            self._rawData.seek(0)

        if codeHandler.optimizeList:
            codeHandler.gct.optimize_codelist(dol)

        # Is codelist optimized away?

        if codeHandler.gct._rawData.getvalue() == b"\x00\xD0\xC0\xDE\x00\xD0\xC0\xDE\xF0\x00\x00\x00\x00\x00\x00\x00":
            with dump.open("wb") as final:
                dol.save(final)

            if not self.quiet:
                if self.verbosity >= 3:
                    dol.print_info()
                    print("-"*64)
                if self.verbosity >= 1:
                    print(tools.color_text(
                        "\n  :: All codes have been successfully pre patched", defaultColor=tools.TGREENLIT))
            return

        hooked = determine_codehook(dol, codeHandler, False)
        if hooked:
            _status, _msg = self.patch_arena(codeHandler, dol)
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
            dol.save(final)

        if self.quiet:
            return

        if self.verbosity >= 3:
            dol.print_info()
            print("-"*64)

        if self.verbosity >= 2:
            print("")
            info = [f"  :: Start of game modified to address 0x{self.initAddress:X}",
                    f"  :: Game function `__start()' located at address 0x{_oldStart:X}",
                    f"  :: Allocation is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.gct.byteSize:X}",
                    f"  :: Codehandler hooked at 0x{codeHandler.hookAddress:X}",
                    f"  :: Codehandler is of type `{codeHandler.type}'",
                    f"  :: Of the {DolFile.maxTextSections} text sections in this DOL file, {len(dol.textSections)} are now being used",
                    f"  :: Of the {DolFile.maxDataSections} text sections in this DOL file, {len(dol.dataSections)} are now being used"]

            for bit in info:
                print(tools.color_text(bit, defaultColor=tools.TGREENLIT))

        elif self.verbosity >= 1:
            print("")
            info = [f"  :: GeckoLoader set at address 0x{self.initAddress:X}",
                    f"  :: Legacy size is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.gct.byteSize:X}",
                    f"  :: Codehandler is of type `{codeHandler.type}'"]
            for bit in info:
                print(tools.color_text(bit, defaultColor=tools.TGREENLIT))

    def load_gct_from(self, gctPath: Path) -> GeckoCodeTable:
        def load_data(gctFile: Path) -> GeckoCodeTable:
            if gctFile.suffix.lower() == ".txt":
                return GeckoCodeTable.from_text(gctFile.read_text())
            elif gctFile.suffix.lower() == ".gct":
                return GeckoCodeTable.from_bytes(gctFile.read_bytes())
            else:
                print(tools.color_text(
                    f"  :: HINT: {file} is not a .txt or .gct file, and will be ignored", defaultColor=tools.TYELLOWLIT))

        gct = GeckoCodeTable()
        if gctPath.is_dir():
            for file in gctPath.iterdir():
                gct += load_data(file)
        elif gctPath.is_file():
            gct += load_data(gctPath)

        return gct


def determine_codehook(dol: DolFile, codeHandler: CodeHandler, hook=False) -> bool:
    if codeHandler.hookAddress is None:
        if not assert_code_hook(dol, codeHandler):
            return False

    if hook:
        codeHandler.set_variables(dol)
        insert_code_hook(dol, codeHandler, codeHandler.hookAddress)

    return True


def assert_code_hook(dol: DolFile, codeHandler: CodeHandler) -> bool:
    for section in dol.textSections:
        dol.seek(section["address"])
        sample = dol.read(section["size"])

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
            dol.seek(section["address"] + result)
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
                dol.seek(section["address"] + result)
            else:
                continue

        while (sample := read_uint32(dol)) != 0x4E800020:
            pass

        dol.seek(-4, 1)
        codeHandler.hookAddress = dol.tell()

        return True
    return False


def insert_code_hook(dol: DolFile, codeHandler: CodeHandler, address: int):
    dol.seek(address)
    ppc = read_uint32(dol)

    if ((ppc >> 24) & 0xFF) > 0x3F and ((ppc >> 24) & 0xFF) < 0x48:
        raise NotImplementedError(tools.color_text(
            "Hooking the codehandler to a conditional non spr branch is unsupported", defaultColor=tools.TREDLIT))

    dol.seek(-4, 1)
    dol.insert_branch(codeHandler.startAddress, address, lk=0)
