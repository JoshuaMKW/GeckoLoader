import functools
import random
import re
import sys
import time
from io import BytesIO
from pathlib import Path

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
        print(tools.color_text(f"\n  :: Completed in {(end - start):0.4f} seconds!\n", defaultColor=tools.TGREENLIT))
        return value
    return wrapper

class InvalidGeckoCodeError(Exception): pass

class GCT(object):

    def __init__(self, f):
        self.codeList = BytesIO(f.read())
        self.rawLineCount = tools.stream_size(self.codeList) >> 3
        self.lineCount = self.rawLineCount - 2
        f.seek(0)

    @property
    def size(self):
        return len(self.codeList.getbuffer())

    @staticmethod
    def determine_codelength(codetype, info: bytes) -> int:
        if codetype.startswith(b"\x06"):
            bytelength = int.from_bytes(info, byteorder="big", signed=False)
            padding = get_alignment(bytelength, 8)
            return 0x8 + bytelength + padding

        elif (codetype.startswith(b"\x08") or codetype.startswith(b"\x09")
            or codetype.startswith(b"\x18") or codetype.startswith(b"\x18")):
            return 0x16

        elif (codetype.startswith(b"\xC0") or codetype.startswith(b"\xC2") or codetype.startswith(b"\xC4")
            or codetype.startswith(b"\xC3") or codetype.startswith(b"\xC5") or codetype.startswith(b"\xD2")
            or codetype.startswith(b"\xD4") or codetype.startswith(b"\xD3") or codetype.startswith(b"\xD5")):
            return 0x8 + (int.from_bytes(info, byteorder="big", signed=False) << 3)

        elif (codetype.startswith(b"\xF2") or codetype.startswith(b"\xF3")
            or codetype.startswith(b"\xF4") or codetype.startswith(b"\xF5")):
            return 0x8 + (int.from_bytes(info[:2], byteorder="big", signed=False) << 3)

        elif codetype.startswith(b"\xF6"):
            return 0x8 + (int.from_bytes(info[:4], byteorder="big", signed=False) << 3)

        else:
            return 0x8

    def optimize_codelist(self, dolFile: DolFile):
        codelist = b"\x00\xD0\xC0\xDE"*2
        skipcodes = 0

        self.codeList.seek(8)
        while codetype := self.codeList.read(4):
            info = self.codeList.read(4)
            address = 0x80000000 | (int.from_bytes(codetype, byteorder="big", signed=False) & 0x1FFFFFF)
            try:
                if skipcodes <= 0:
                    if (codetype.startswith(b"\x00") or codetype.startswith(b"\x01")
                        or codetype.startswith(b"\x10") or codetype.startswith(b"\x11")):
                        dolFile.seek(address)

                        counter = int.from_bytes(info[:-2], byteorder="big", signed=False)
                        value = info[2:]

                        while counter + 1 > 0:
                            dolFile.write(value[1:])
                            counter -= 1
                        continue

                    elif (codetype.startswith(b"\x02") or codetype.startswith(b"\x03")
                        or codetype.startswith(b"\x12") or codetype.startswith(b"\x13")):
                        dolFile.seek(address)

                        counter = int.from_bytes(info[:-2], byteorder="big", signed=False)
                        value = info[2:]

                        while counter + 1 > 0:
                            dolFile.write(value)
                            counter -= 1
                        continue

                    elif (codetype.startswith(b"\x04") or codetype.startswith(b"\x05")
                        or codetype.startswith(b"\x14") or codetype.startswith(b"\x15")):
                        dolFile.seek(address)
                        dolFile.write(info)
                        continue

                    elif (codetype.startswith(b"\x06") or codetype.startswith(b"\x07")
                        or codetype.startswith(b"\x16") or codetype.startswith(b"\x17")):
                        dolFile.seek(address)

                        arraylength = int.from_bytes(info, byteorder="big", signed=False)
                        padding = get_alignment(arraylength, 8)
                        
                        dolFile.write(self.codeList.read(arraylength))

                        self.codeList.seek(padding, 1)
                        continue

                    elif (codetype.startswith(b"\x08") or codetype.startswith(b"\x09")
                        or codetype.startswith(b"\x18") or codetype.startswith(b"\x19")):
                        dolFile.seek(address)

                        value = int.from_bytes(info, byteorder="big", signed=False)
                        data = read_uint16(self.codeList)
                        size = (data & 0x3000) >> 12
                        counter = data & 0xFFF
                        address_increment = read_uint16(self.codeList)
                        value_increment = read_uint32(self.codeList)

                        while counter + 1 > 0:
                            if size == 0:
                                write_ubyte(dolFile, value & 0xFF)
                                dolFile.seek(-1, 1)
                            elif size == 1:
                                write_uint16(dolFile, value & 0xFFFF)
                                dolFile.seek(-2, 1)
                            elif size == 2:
                                write_uint32(dolFile, value)
                                dolFile.seek(-4, 1)
                            else:
                                raise ValueError("Size type {} does not match 08 codetype specs".format(size))
                            
                            dolFile.seek(address_increment, 1)
                            value += value_increment
                            counter -= 1
                            if value > 0xFFFFFFFF:
                                value -= 0x100000000
                        continue

                    elif (codetype.startswith(b"\xC6") or codetype.startswith(b"\xC7")
                        or codetype.startswith(b"\xC6") or codetype.startswith(b"\xC7")):
                        dolFile.insert_branch(int.from_bytes(info, byteorder="big", signed=False), address, lk=address&1)
                        continue

                if codetype.hex().startswith("2") or codetype.hex().startswith("3"):
                    skipcodes += 1

                elif codetype.startswith(b"\xE0"):
                    skipcodes -= 1

                elif codetype.startswith(b"\xF0"):
                    codelist += b"\xF0\x00\x00\x00\x00\x00\x00\x00"
                    break

                self.codeList.seek(-8, 1)
                codelist += self.codeList.read(GCT.determine_codelength(codetype, info))

            except (RuntimeError, UnmappedAddressError):
                self.codeList.seek(-8, 1)
                codelist += self.codeList.read(GCT.determine_codelength(codetype, info))

        self.codeList = BytesIO(codelist)

class CodeHandler(object):

    class Types:
        MINI = "MINI"
        FULL = "FULL"

    def __init__(self, f):
        self._rawData = BytesIO(f.read())

        """Get codelist pointer"""
        self._rawData.seek(0xFA)
        codelistUpper = self._rawData.read(2).hex()
        self._rawData.seek(0xFE)
        codelistLower = self._rawData.read(2).hex()

        self.codeListPointer = int(codelistUpper[2:] + codelistLower[2:], 16)
        self.handlerLength = tools.stream_size(self._rawData)
        self.initAddress = 0x80001800
        self.startAddress = 0x800018A8

        self.wiiVIHook = b"\x7C\xE3\x3B\x78\x38\x87\x00\x34\x38\xA7\x00\x38\x38\xC7\x00\x4C"
        self.gcnVIHook = b"\x7C\x03\x00\x34\x38\x83\x00\x20\x54\x85\x08\x3C\x7C\x7F\x2A\x14\xA0\x03\x00\x00\x7C\x7D\x2A\x14\x20\xA4\x00\x3F\xB0\x03\x00\x00"
        self.wiiGXDrawHook = b"\x3C\xA0\xCC\x01\x38\x00\x00\x61\x3C\x80\x45\x00\x98\x05\x80\x00"
        self.gcnGXDrawHook = b"\x38\x00\x00\x61\x3C\xA0\xCC\x01\x3C\x80\x45\x00\x98\x05\x80\x00"
        self.wiiPADHook = b"\x3A\xB5\x00\x01\x3A\x73\x00\x0C\x2C\x15\x00\x04\x3B\x18\x00\x0C"
        self.gcnPADHook = b"\x3A\xB5\x00\x01\x2C\x15\x00\x04\x3B\x18\x00\x0C\x3B\xFF\x00\x0C"

        self.allocation = None
        self.hookAddress = None
        self.hookType = None
        self.geckoCodes = None
        self.includeAll = False
        self.optimizeList = False

        if self.handlerLength < 0x900:
            self.type = CodeHandler.Types.MINI
        else:
            self.type = CodeHandler.Types.FULL

        f.seek(0)

    def init_gct(self, gctFile: Path, tmpdir: Path=None):
        if tmpdir is not None:
            _tmpGct = tmpdir / "gct.bin"
        else:
            _tmpGct = Path("gct.bin")

        if gctFile.suffix.lower() == ".txt":
            with _tmpGct.open("wb+") as temp:
                temp.write(bytes.fromhex("00D0C0DE"*2 + self.parse_input(gctFile) + "F000000000000000"))
                temp.seek(0)
                self.geckoCodes = GCT(temp)
        elif gctFile.suffix.lower() == ".gct":
            with gctFile.open("rb") as gct:
                self.geckoCodes = GCT(gct)
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
                            print(tools.color_text(f"  :: HINT: {file} is not a .txt or .gct file", defaultColor=tools.TYELLOWLIT))
            
                temp.write(b"\xF0\x00\x00\x00\x00\x00\x00\x00")
                temp.seek(0)
                self.geckoCodes = GCT(temp)
        else:
            raise NotImplementedError(f"Parsing file type `{gctFile.suffix}' as a GCT is unsupported")

    def parse_input(self, geckoText: Path) -> str:
        with geckoText.open("rb") as gecko:
            result = chardet.detect(gecko.read())
            encodeType = result["encoding"]

        with geckoText.open("r", encoding=encodeType) as gecko:
            geckoCodes = ""
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
                            geckoLine = re.findall(r"[A-F0-9]{8}[\t\f ][A-F0-9]{8}", line, re.IGNORECASE)[0]
                        else:
                            geckoLine = re.findall(r"(?:\*\s*)([A-F0-9]{8}[\t\f ][A-F0-9]{8})", line, re.IGNORECASE)[0]
                    else:
                        geckoLine = re.findall(r"(?<![$\*])[A-F0-9]{8}[\t\f ][A-F0-9]{8}", line, re.IGNORECASE)[0]
                except IndexError:
                    continue

                geckoCodes += geckoLine.replace(" ", "").strip()

        return geckoCodes

    @staticmethod
    def encrypt_key(key: int)  -> int:
        b1 = key & 0xFF
        b2 = (key >> 8) & 0xFF
        b3 = (key >> 16) & 0xFF
        b4 = (key >> 24) & 0xFF
        b3 ^= b4
        b2 ^= b3
        b1 ^= b2
        return (b1 << 24) | (b2 << 16) | (b3 << 8) | b4

    def encrypt_codes(self, key: int):
        self.geckoCodes.codeList.seek(0)
        i = 0
        while True:
            try:
                packet = read_uint32(self.geckoCodes.codeList)
                self.geckoCodes.codeList.seek(-4, 1)
                write_uint32(self.geckoCodes.codeList, (packet^key) & 0xFFFFFFFF)
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
                raise NotImplementedError("Hooking to a conditional non spr branch is unsupported")
            write_uint32(self._rawData, (to - (self.initAddress + varOffset)) & 0x3FFFFFD | 0x48000000 | lk)
        else:
            write_uint32(self._rawData, ppc)
 
    def set_variables(self, dolFile: DolFile):
        varOffset = self.find_variable_data(b"\x00\xDE\xDE\xDE")
        if varOffset is None:
            raise RuntimeError(tools.color_text("Variable codehandler data not found\n", defaultColor=tools.TREDLIT))

        self.set_hook_instruction(dolFile, self.hookAddress, varOffset, 0)

        self._rawData.seek(varOffset + 4)
        write_uint32(self._rawData, ((self.hookAddress + 4) - (self.initAddress + (varOffset + 4))) & 0x3FFFFFD | 0x48000000 | 0)

class KernelLoader(object):

    def __init__(self, f, cli: tools.CommandLineParser=None):
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

    def set_variables(self, entryPoint: list, baseOffset: int=0):
        self._rawData.seek(0)

        if self._gpModDataList is None:
            return
        
        while sample := self._rawData.read(2):
            if sample == b"GH":
                self._rawData.seek(-2, 1)
                write_uint16(self._rawData, self._gpModDataList[0])
            elif sample == b"GL":
                self._rawData.seek(-2, 1)
                write_uint16(self._rawData, baseOffset + self._gpModDataList[1])
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
                write_uint16(self._rawData, baseOffset + self._gpKeyAddrList[1])

    def complete_data(self, codeHandler: CodeHandler, initpoint: list):
        _upperAddr, _lowerAddr = ((self.initAddress >> 16) & 0xFFFF, self.initAddress & 0xFFFF)
        _key = random.randrange(0x100000000)
        self._rawData.seek(0)

        while sample := self._rawData.read(4):
            if sample == b"HEAP": #Found keyword "HEAP". Goes with the resize of the heap
                self._rawData.seek(-4, 1)

                gpModInfoOffset = self._rawData.tell()
                gpModUpperAddr = _upperAddr + 1 if (_lowerAddr + gpModInfoOffset) > 0x7FFF else _upperAddr #Absolute addressing
                    
                if codeHandler.allocation == None:
                    codeHandler.allocation = (codeHandler.handlerLength + codeHandler.geckoCodes.size + 7) & -8
                    
                write_uint32(self._rawData, codeHandler.allocation)
                    
            elif sample == b"LSIZ": #Found keyword "LSIZ". Goes with the size of the loader
                self._rawData.seek(-4, 1)
                write_uint32(self._rawData, len(self._rawData.getbuffer()))
                    
            elif sample == b"HSIZ": #Found keyword "HSIZ". Goes with the size of the codehandler
                self._rawData.seek(-4, 1)
                write_sint32(self._rawData, codeHandler.handlerLength)
            
            elif sample == b"CSIZ": #Found keyword "CSIZ". Goes with the size of the codes
                self._rawData.seek(-4, 1)
                write_sint32(self._rawData, codeHandler.geckoCodes.size)
            
            elif sample == b"HOOK": #Found keyword "HOOK". Goes with the codehandler hook
                self._rawData.seek(-4, 1)
                write_uint32(self._rawData, codeHandler.hookAddress)

            elif sample == b"CRPT": #Found keyword "CRPT". Boolean of the encryption
                self._rawData.seek(-4, 1)
                write_bool(self._rawData, self.encrypt, 4)

            elif sample == b"CYPT": #Found keyword "CYPT". Encryption Key
                self._rawData.seek(-4, 1)

                gpKeyOffset = self._rawData.tell()
                gpKeyUpperAddr = _upperAddr + 1 if (_lowerAddr + gpKeyOffset) > 0x7FFF else _upperAddr #Absolute addressing

                write_uint32(self._rawData, CodeHandler.encrypt_key(_key))

        if _lowerAddr + gpModInfoOffset > 0xFFFF:
            _lowerAddr -= 0x10000

        self._gpModDataList = (gpModUpperAddr, gpModInfoOffset)
        self._gpKeyAddrList = (gpKeyUpperAddr, gpKeyOffset)

        self.set_variables(initpoint, _lowerAddr)
        
        if self.encrypt:
            codeHandler.encrypt_codes(_key)

    def patch_arena(self, codeHandler: CodeHandler, dolFile: DolFile) -> tuple:
        self.complete_data(codeHandler, [(dolFile.entryPoint >> 16) & 0xFFFF, dolFile.entryPoint & 0xFFFF])

        self._rawData.seek(0, 2)
        self._rawData.write(codeHandler._rawData.getvalue() + codeHandler.geckoCodes.codeList.getvalue())

        self._rawData.seek(0)
        _kernelData = self._rawData.getvalue()

        try:
            dolFile.append_text_sections([(_kernelData, self.initAddress)])
        except SectionCountFullError:
            try:
                dolFile.append_data_sections([(_kernelData, self.initAddress)])
            except SectionCountFullError:
                self.error(tools.color_text("There are no unused sections left for GeckoLoader to use!\n", defaultColor=tools.TREDLIT))

        dolFile.entryPoint = self.initAddress
        return True, None

    def patch_legacy(self, codeHandler: CodeHandler, dolFile: DolFile) -> tuple:
        codeHandler._rawData.seek(0)
        codeHandler.geckoCodes.codeList.seek(0)
        
        _handlerData = codeHandler._rawData.getvalue() + codeHandler.geckoCodes.codeList.getvalue()

        try:
            dolFile.append_text_sections([(_handlerData, codeHandler.initAddress)])
        except SectionCountFullError:
            try:
                dolFile.append_data_sections([(_handlerData, codeHandler.initAddress)])
            except SectionCountFullError:
                self.error(tools.color_text("There are no unused sections left for GeckoLoader to use!\n", defaultColor=tools.TREDLIT))

        return True, None

    def protect_game(self, codeHandler: CodeHandler):
        _oldpos = codeHandler.geckoCodes.codeList.tell()

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

        codeHandler.geckoCodes.codeList.seek(-8, 2)

        for line in protectdata:
            codeHandler.geckoCodes.codeList.write(line)

        codeHandler.geckoCodes.codeList.write(b"\xF0\x00\x00\x00\x00\x00\x00\x00")
        codeHandler.geckoCodes.codeList.seek(_oldpos)

    @timer
    def build(self, gctFile: Path, dolFile: DolFile, codeHandler: CodeHandler, tmpdir: Path, dump: Path):
        _oldStart = dolFile.entryPoint

        """Initialize our codes"""

        codeHandler.init_gct(gctFile, tmpdir)

        if codeHandler.geckoCodes is None:
            self.error(tools.color_text("Valid codelist not found. Please provide a .txt/.gct file, or a folder of .txt/.gct files\n", defaultColor=tools.TREDLIT))
        
        if self.protect:
            self.protect_game(codeHandler)

        """Get entrypoint (or BSS midpoint) for insert"""

        if self.initAddress:
            try:
                dolFile.resolve_address(self.initAddress)
                self.error(tools.color_text(f"Init address specified for GeckoLoader (0x{self.initAddress:X}) clobbers existing dol sections", defaultColor=tools.TREDLIT))
            except UnmappedAddressError:
                pass
        else:
            self.initAddress = dolFile.seek_nearest_unmapped(dolFile.bssAddress, len(self._rawData.getbuffer()) + codeHandler.handlerLength + codeHandler.geckoCodes.size)
            self._rawData.seek(0)

        if codeHandler.optimizeList:
            codeHandler.geckoCodes.optimize_codelist(dolFile)

        """Is codelist optimized away?"""

        if codeHandler.geckoCodes.codeList.getvalue() == b"\x00\xD0\xC0\xDE\x00\xD0\xC0\xDE\xF0\x00\x00\x00\x00\x00\x00\x00":
            with dump.open("wb") as final:
                dolFile.save(final)

            if not self.quiet:
                if self.verbosity >= 3:
                    dolFile.print_info()
                    print("-"*64)
                if self.verbosity >= 1:
                    print(tools.color_text("\n  :: All codes have been successfully pre patched", defaultColor=tools.TGREENLIT))
            return

        hooked = determine_codehook(dolFile, codeHandler, False)
        if hooked:
            _status, _msg = self.patch_arena(codeHandler, dolFile)
        else:
            self.error(tools.color_text("Failed to find a hook address. Try using option --codehook to use your own address\n", defaultColor=tools.TREDLIT))

        if _status is False:
            self.error(tools.color_text(_msg + "\n", defaultColor=tools.TREDLIT))
        elif codeHandler.allocation < codeHandler.geckoCodes.size:
            self.error(tools.color_text("Allocated codespace was smaller than the given codelist\n", defaultColor=tools.TYELLOW))

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
                    f"  :: Allocation is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.geckoCodes.size:X}",
                    f"  :: Codehandler hooked at 0x{codeHandler.hookAddress:X}",
                    f"  :: Codehandler is of type `{codeHandler.type}'",
                    f"  :: Of the {DolFile.maxTextSections} text sections in this DOL file, {len(dolFile.textSections)} are now being used",
                    f"  :: Of the {DolFile.maxDataSections} data sections in this DOL file, {len(dolFile.dataSections)} are now being used"]

            for bit in info:
                print(tools.color_text(bit, defaultColor=tools.TGREENLIT))
    
        elif self.verbosity >= 1:
            print("")
            info = [f"  :: GeckoLoader set at address 0x{self.initAddress:X}",
                    f"  :: Legacy size is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.geckoCodes.size:X}",
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
            result = sample.find(codeHandler.gcnVIHook)
        elif codeHandler.hookType == "GX":
            result = sample.find(codeHandler.gcnGXDrawHook)
        elif codeHandler.hookType == "PAD":
            result = sample.find(codeHandler.gcnPADHook)
        else:
            raise NotImplementedError(tools.color_text(f"Unsupported hook type specified ({codeHandler.hookType})", defaultColor=tools.TREDLIT))

        if result >= 0:
            dolFile.seek(section["address"] + result)
        else:
            if codeHandler.hookType == "VI":
                result = sample.find(codeHandler.wiiVIHook)
            elif codeHandler.hookType == "GX":
                result = sample.find(codeHandler.wiiGXDrawHook)
            elif codeHandler.hookType == "PAD":
                result = sample.find(codeHandler.wiiPADHook)
            else:
                raise NotImplementedError(tools.color_text(f"Unsupported hook type specified ({codeHandler.hookType})", defaultColor=tools.TREDLIT))

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
        raise NotImplementedError(tools.color_text("Hooking the codehandler to a conditional non spr branch is unsupported", defaultColor=tools.TREDLIT))

    dolFile.seek(-4, 1)
    dolFile.insert_branch(codeHandler.startAddress, address, lk=0)
