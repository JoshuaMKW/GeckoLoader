import sys
import os
import re
import time

from io import BytesIO
from dolreader import *
from access import *

try:
    import chardet
except ImportError as IE:
    print(IE)
    sys.exit(1)

try:
    import colorama
    from colorama import Fore, Style
    colorama.init()
    TRESET = Style.RESET_ALL
    TGREEN = Fore.GREEN
    TGREENLIT = Style.BRIGHT + Fore.GREEN
    TYELLOW = Fore.YELLOW
    TYELLOWLIT = Style.BRIGHT + Fore.YELLOW
    TRED = Fore.RED
    TREDLIT = Style.BRIGHT + Fore.RED

except ImportError:
    TRESET = ''
    TGREEN = ''
    TGREENLIT = ''
    TYELLOW = ''
    TYELLOWLIT = ''
    TRED = ''
    TREDLIT = ''

HEAP = b'HEAP'
LOADERSIZE = b'LSIZ'
HANDLERSIZE = b'HSIZ'
CODESIZE = b'CSIZ'
CODEHOOK = b'HOOK'
DH = b'DH'
DL = b'DL'
GH = b'GH'
GL = b'GL'
IH = b'IH'
IL = b'IL'
WIIVIHOOK = b'\x7C\xE3\x3B\x78\x38\x87\x00\x34\x38\xA7\x00\x38\x38\xC7\x00\x4C'
GCNVIHOOK = b'\x7C\x03\x00\x34\x38\x83\x00\x20\x54\x85\x08\x3C\x7C\x7F\x2A\x14\xA0\x03\x00\x00\x7C\x7D\x2A\x14\x20\xA4\x00\x3F\xB0\x03\x00\x00'

def get_alignment(number, align: int):
    if number % align != 0:
        return align - (number % align)
    else:
        return 0

def get_size(file, offset=0):
    """ Return a file's size in bytes """
    file.seek(0, 2)
    return file.tell() + offset

def get_file_alignment(file, alignment: int):
    """ Return file alignment, 0 = aligned, non zero = misaligned """
    size = get_size(file)
    return get_alignment(size, alignment)

def align_file(file, alignment: int, fillchar='00'):
    """ Align a file to be the specified size """
    file.write(bytes.fromhex(fillchar * get_file_alignment(file, alignment)))

class GCT:

    def __init__(self, f):
        self.codeList = BytesIO(f.read())
        self.rawLineCount = get_size(f) >> 3
        self.lineCount = self.rawLineCount - 2
        self.size = get_size(f)
        f.seek(0)

    def determine_codelength(self, codetype, info):
        if codetype.startswith(b'\x06'):
            bytelength = int.from_bytes(info, byteorder='big', signed=False)
            padding = get_alignment(bytelength, 8)
            return 0x8 + bytelength + padding

        elif (codetype.startswith(b'\x08') or codetype.startswith(b'\x09')
            or codetype.startswith(b'\x18') or codetype.startswith(b'\x18')):
            return 0x16

        elif (codetype.startswith(b'\xC2') or codetype.startswith(b'\xC4')
            or codetype.startswith(b'\xC3') or codetype.startswith(b'\xC5')
            or codetype.startswith(b'\xD2') or codetype.startswith(b'\xD4')
            or codetype.startswith(b'\xD3') or codetype.startswith(b'\xD5')):
            return 0x8 + (int.from_bytes(info, byteorder='big', signed=False) << 3)

        elif (codetype.startswith(b'\xF2') or codetype.startswith(b'\xF3')
            or codetype.startswith(b'\xF4') or codetype.startswith(b'\xF5')):
            return 0x8 + (int.from_bytes(info[:2], byteorder='big', signed=False) << 3)

        elif codetype.startswith(b'\xF6'):
            return 0x8 + (int.from_bytes(info[:4], byteorder='big', signed=False) << 3)

        else:
            return 0x8

    def optimize_codelist(self, dolFile: DolFile):
        codelist = b''
        codetype = b'temp'
        skipcodes = 0
        while codetype:
            codetype = self.codeList.read(4)
            info = self.codeList.read(4)
            address = 0x80000000 | (int.from_bytes(codetype, byteorder='big', signed=False) & 0x01FFFFFF)
            try:
                if skipcodes <= 0:
                    if (codetype.startswith(b'\x00') or codetype.startswith(b'\x01')
                        or codetype.startswith(b'\x10') or codetype.startswith(b'\x11')):
                        dolFile.seek(address)

                        counter = int.from_bytes(info[:-2], byteorder='big', signed=False)
                        value = info[2:]

                        while counter + 1 > 0:
                            dolFile.write(value[1:])
                            counter -= 1
                        continue

                    elif (codetype.startswith(b'\x02') or codetype.startswith(b'\x03')
                        or codetype.startswith(b'\x12') or codetype.startswith(b'\x13')):
                        dolFile.seek(address)

                        counter = int.from_bytes(info[:-2], byteorder='big', signed=False)
                        value = info[2:]

                        while counter + 1 > 0:
                            dolFile.write(value)
                            counter -= 1
                        continue

                    elif (codetype.startswith(b'\x04') or codetype.startswith(b'\x05')
                        or codetype.startswith(b'\x14') or codetype.startswith(b'\x15')):
                        dolFile.seek(address)
                        dolFile.write(info)
                        continue

                    elif (codetype.startswith(b'\x06') or codetype.startswith(b'\x07')
                        or codetype.startswith(b'\x16') or codetype.startswith(b'\x17')):
                        dolFile.seek(address)

                        arraylength = int.from_bytes(info, byteorder='big', signed=False)
                        padding = get_alignment(arraylength, 8)
                        
                        while arraylength > 0:
                            value = self.codeList.read(1)
                            dolFile.write(value)
                            arraylength -= 1

                        self.codeList.seek(padding, 1)
                        continue

                    elif (codetype.startswith(b'\x08') or codetype.startswith(b'\x09')
                        or codetype.startswith(b'\x18') or codetype.startswith(b'\x19')):
                        dolFile.seek(address)

                        value = int.from_bytes(info, byteorder='big', signed=False)
                        data = self.codeList.read(2).hex()
                        size = int(data[:-3], 16)
                        counter = int(data[1:], 16)
                        address_increment = int.from_bytes(self.codeList.read(2), byteorder='big', signed=False)
                        value_increment = int.from_bytes(self.codeList.read(4), byteorder='big', signed=False)

                        while counter + 1 > 0:
                            if size == 0:
                                dolFile.write(value.to_bytes(length=1, byteorder='big', signed=False))
                                dolFile.seek(-1, 1)
                            elif size == 1:
                                dolFile.write(value.to_bytes(length=2, byteorder='big', signed=False))
                                dolFile.seek(-2, 1)
                            elif size == 2:
                                dolFile.write(value.to_bytes(length=4, byteorder='big', signed=False))
                                dolFile.seek(-4, 1)
                            else:
                                raise ValueError('Size type {} does not match 08 codetype specs'.format(size))
                            
                            dolFile.seek(address_increment, 1)
                            value += value_increment
                            counter -= 1
                            if value > 0xFFFFFFFF:
                                value -= 0x100000000
                        continue

                    elif (codetype.startswith(b'\xC6') or codetype.startswith(b'\xC7')
                        or codetype.startswith(b'\xC6') or codetype.startswith(b'\xC7')):
                        dolFile.seek(address)
                        dolFile.insertBranch(int.from_bytes(info, byteorder='big', signed=False), dolFile.tell())
                        continue

                if codetype.hex().startswith('2') or codetype.hex().startswith('3'):
                    skipcodes += 1

                elif codetype.startswith(b'\xE0'):
                    skipcodes -= 1

                elif codetype.startswith(b'\xF0'):
                    codelist += b'\xF0\x00\x00\x00\x00\x00\x00\x00'
                    break

                self.codeList.seek(-8, 1)
                length = self.determine_codelength(codetype, info)
                while length > 0:
                    codelist += self.codeList.read(1)
                    length -= 1

            except RuntimeError:
                self.codeList.seek(-8, 1)
                length = self.determine_codelength(codetype, info)
                while length > 0:
                    codelist += self.codeList.read(1)
                    length -= 1

        self.codeList = BytesIO(codelist)
        self.size = get_size(self.codeList)

class CodeHandler:

    def __init__(self, f):
        self.rawData = BytesIO(f.read())

        '''Get codelist pointer'''
        f.seek(0xFA)
        codelistUpper = f.read(2).hex()
        f.seek(0xFE)
        codelistLower = f.read(2).hex()

        self.codeListPointer = int(codelistUpper[2:] + codelistLower[2:], 16)
        self.handlerLength = get_size(f)
        self.initAddress = 0x80001800
        self.startAddress = 0x800018A8
        self.allocation = None
        self.hookAddress = None
        self.geckoCodes = None
        self.includeAll = False
        self.optimizeList = False

        if self.handlerLength < 0x900:
            self.type = "Mini"
        else:
            self.type = "Full"

        f.seek(0)

    def gecko_parser(self, geckoText, parseAll=False):
        with open(r'{}'.format(geckoText), 'rb') as gecko:
            result = chardet.detect(gecko.read())
            encodeType = result['encoding']

        with open(r'{}'.format(geckoText), 'r', encoding=encodeType) as gecko:
            geckoCodes = ''
            state = None

            for line in gecko.readlines():
                if line in ('', '\n'):
                    continue

                if state is None:
                    if line.startswith('$'):
                        state = 'Dolphin'
                    else:
                        state = 'OcarinaM'
                
                try:
                    if state == 'OcarinaM':
                        if parseAll.lower() == 'all':
                            geckoLine = re.findall(r'[A-F0-9]{8}[\t\f ][A-F0-9]{8}', line, re.IGNORECASE)[0]
                        elif parseAll.lower() == 'active':
                            geckoLine = re.findall(r'(?:\*\s*)([A-F0-9]{8}[\t\f ][A-F0-9]{8})', line, re.IGNORECASE)[0]
                        else:
                            geckoLine = re.findall(r'(?:\*\s*)([A-F0-9]{8}[\t\f ][A-F0-9]{8})', line, re.IGNORECASE)[0]
                    else:
                        geckoLine = re.findall(r'(?<![$\*])[A-F0-9]{8}[\t\f ][A-F0-9]{8}', line, re.IGNORECASE)[0]
                except IndexError:
                    continue

                geckoCodes += geckoLine.replace(' ', '').strip()

        return geckoCodes

class KernelLoader:

    def __init__(self, f):
        self.rawData = BytesIO(f.read())
        self.initDataList = None
        self.gpModDataList = None
        self.gpDiscDataList = None
        self.codeLocation = None
        self.initAddress = None
        self.protect = False
        self.verbosity = 0
        self.quiet = False

    def fill_loader_data(self, tmp, entryPoint: list, lowerAddr: int):
        tmp.seek(0)
        if self.gpModDataList is None or self.gpDiscDataList is None:
            return

        sample = tmp.read(2)
        
        while sample:
            if sample == DH:
                tmp.seek(-2, 1)
                tmp.write(self.gpDiscDataList[0])
            elif sample == DL:
                tmp.seek(-2, 1)
                tmp.write((lowerAddr + self.gpDiscDataList[1]).to_bytes(2, byteorder='big', signed=False))
            elif sample == GH:
                tmp.seek(-2, 1)
                tmp.write(self.gpModDataList[0])
            elif sample == GL:
                tmp.seek(-2, 1)
                tmp.write((lowerAddr + self.gpModDataList[1]).to_bytes(2, byteorder='big', signed=False))
            elif sample == IH:
                tmp.seek(-2, 1)
                tmp.write(entryPoint[0])
            elif sample == IL:
                tmp.seek(-2, 1)
                tmp.write(entryPoint[1])
            sample = tmp.read(2)

    def figure_loader_data(self, tmp, codehandler: CodeHandler, dolFile: DolFile, entrypoint: str, initpoint: list):
        upperAddr, lowerAddr = entrypoint[:int(len(entrypoint)/2)], entrypoint[int(len(entrypoint)/2):]
        tmp.seek(0)

        sample = tmp.read(4)

        while sample:
            if sample == HEAP: #Found keyword "HEAP". Goes with the resize of the heap
                tmp.seek(-4, 1)
                gpModInfoOffset = tmp.tell()
                if int(lowerAddr, 16) + gpModInfoOffset > 0x7FFF: #Absolute addressing
                    gpModUpperAddr = (int(upperAddr, 16) + 1).to_bytes(2, byteorder='big', signed=False)
                else:
                    gpModUpperAddr = int(upperAddr, 16).to_bytes(2, byteorder='big', signed=False)
                if codehandler.allocation == None:
                    codehandler.allocation = (codehandler.handlerLength + codehandler.geckoCodes.size + 7) & 0xFFFFFFF8
                tmp.write(codehandler.allocation.to_bytes(4, byteorder='big', signed=False))
                    
            elif sample == LOADERSIZE: #Found keyword "LSIZ". Goes with the size of the loader
                tmp.seek(-4, 1)
                tmp.write(get_size(self.rawData).to_bytes(4, byteorder='big', signed=False))
                    
            elif sample == HANDLERSIZE: #Found keyword "HSIZ". Goes with the size of the codehandler
                tmp.seek(-4, 1)
                tmp.write(codehandler.handlerLength.to_bytes(4, byteorder='big', signed=True))
            
            elif sample == CODESIZE: #Found keyword "CSIZ". Goes with the size of the codes
                tmp.seek(-4, 1)
                tmp.write(codehandler.geckoCodes.size.to_bytes(4, byteorder='big', signed=True))
            
            elif sample == CODEHOOK:
                tmp.seek(-4, 1)
                if codehandler.hookAddress == None:
                    tmp.write(b'\x00\x00\x00\x00')
                else:
                    tmp.write(codehandler.hookAddress.to_bytes(4, byteorder='big', signed=False))
            
            sample = tmp.read(4)
            
        gpDiscOffset = get_size(tmp, -4)

        if int(lowerAddr, 16) + gpDiscOffset > 0x7FFF: #Absolute addressing
            gpDiscUpperAddr = (int(upperAddr, 16) + 1).to_bytes(2, byteorder='big', signed=False)
        else:
            gpDiscUpperAddr = int(upperAddr, 16).to_bytes(2, byteorder='big', signed=False)

        self.gpModDataList = (gpModUpperAddr, gpModInfoOffset)
        self.gpDiscDataList = (gpDiscUpperAddr, gpDiscOffset)

        self.fill_loader_data(tmp, initpoint, int(lowerAddr, 16))
        
        tmp.seek(0, 2)
        codehandler.rawData.seek(0)
        codehandler.geckoCodes.codeList.seek(0)

        tmp.write(codehandler.rawData.read() + codehandler.geckoCodes.codeList.read())

    def patch_arena(self, codehandler: CodeHandler, dolFile: DolFile, entrypoint: str, tmp):
        tmp.write(self.rawData.getbuffer())
        geckoloader_offset = dolFile.get_size()
        self.figure_loader_data(tmp, codehandler, dolFile, entrypoint,
                                [((dolFile.entryPoint >> 16) & 0xFFFF).to_bytes(2, byteorder='big', signed=False),
                                    (dolFile.entryPoint & 0xFFFF).to_bytes(2, byteorder='big', signed=False)])
        tmp.seek(0)
        dolFile.rawData.seek(0, 2)
        dolFile.rawData.write(tmp.read())
        dolFile.align(256)

        status = dolFile.append_text_sections([(int(entrypoint, 16), geckoloader_offset)])

        if status is True:
            dolFile.set_entry_point(int(entrypoint, 16))

        return status

    def patch_legacy(self, codehandler: CodeHandler, dolFile: DolFile, tmp):
        handlerOffset = dolFile.get_size()

        dolFile.rawData.seek(0, 2)
        codehandler.rawData.seek(0)
        codehandler.geckoCodes.codeList.seek(0)
        
        dolFile.rawData.write(codehandler.rawData.read() + codehandler.geckoCodes.codeList.read())
        dolFile.align(256)

        status = dolFile.append_text_sections([(codehandler.initAddress, handlerOffset)])

        return status

    def protect_game(self, codehandler: CodeHandler):
        oldpos = codehandler.geckoCodes.codeList.tell()

        protectdata = [b'\xC0\x00\x00\x00\x00\x00\x00\x17',
                       b'\x7C\x08\x02\xA6\x94\x21\xFF\x80',
                       b'\x90\x01\x00\x08\xBC\x61\x00\x0C',
                       b'\x48\x00\x00\x0D\x00\xD0\xC0\xDE',
                       b'\x00\xD0\xDE\xAD\x7F\xE8\x02\xA6',
                       b'\x3B\xDF\x00\x04\x3C\x60\x80\x00',
                       b'\x38\x80\x11\x00\x38\xA0\x00\x00',
                       b'\x60\x63\x1E\xF8\x7C\x89\x03\xA6',
                       b'\x38\x80\x00\x00\x7D\x03\x22\x14',
                       b'\x54\xE9\x06\x3E\x89\x08\x00\x08',
                       b'\x7D\x3F\x48\xAE\x38\xE7\x00\x01',
                       b'\x7C\x08\x48\x40\x41\x82\x00\x0C',
                       b'\x60\xA7\x00\x00\x48\x00\x00\x04',
                       b'\x54\xE8\x06\x3E\x28\x08\x00\x03',
                       b'\x41\x81\x00\x10\x38\x84\x00\x01',
                       b'\x42\x00\xFF\xCC\x38\x80\x11\x00',
                       b'\x38\xA0\x00\x08\x7C\x84\x1A\x14',
                       b'\x7C\xA9\x03\xA6\x38\x60\x00\x00',
                       b'\x54\x66\x07\xBE\x7C\xDE\x30\xAE',
                       b'\x38\x63\x00\x01\x9C\xC4\x00\x01',
                       b'\x42\x00\xFF\xF0\x83\xE1\x00\x10',
                       b'\xB8\x61\x00\x0C\x80\x01\x00\x08',
                       b'\x38\x21\x00\x80\x7C\x08\x03\xA6',
                       b'\x4E\x80\x00\x20\x00\x00\x00\x00',
                       b'\xF0\x00\x00\x00\x00\x00\x00\x00']

        codehandler.geckoCodes.codeList.seek(-8, 2)
        for chunk in protectdata:
            codehandler.geckoCodes.codeList.write(chunk)
        codehandler.geckoCodes.codeList.seek(oldpos)

    def build(self, gctFile, dolFile: DolFile, codehandler: CodeHandler, tmpdir, dump):
        beginTime = time.time()

        with open(os.path.join(tmpdir, 'tmp.bin'), 'wb+') as tmp, open(dump, 'wb+') as final:

            if dolFile.get_size() < 0x100:
                shutil.rmtree(tmpdir)
                parser.error('DOL header is corrupted. Please provide a clean file')

            '''Initialize our codes'''

            if '.' in gctFile:
                if os.path.splitext(gctFile)[1].lower() == '.txt':
                    with open(os.path.join(tmpdir, 'gct.bin'), 'wb+') as temp:
                        temp.write(bytes.fromhex('00D0C0DE'*2 + codehandler.gecko_parser(gctFile, codehandler.includeAll) + 'F000000000000000'))
                        temp.seek(0)
                        codehandler.geckoCodes = GCT(temp)    
                elif os.path.splitext(gctFile)[1].lower() == '.gct':
                    with open(r'{}'.format(gctFile), 'rb') as gct:
                        codehandler.geckoCodes = GCT(gct)
                else:
                    parser.error('No valid gecko code file found')
            else:
                with open(os.path.join(tmpdir, 'gct.bin'), 'wb+') as temp:
                    temp.write(bytes.fromhex('00D0C0DE'*2))

                    for file in os.listdir(gctFile):
                        if os.path.isfile(os.path.join(gctFile, file)):
                            if os.path.splitext(file)[1].lower() == '.txt':
                                temp.write(bytes.fromhex(codehandler.gecko_parser(os.path.join(gctFile, file), codehandler.includeAll)))  
                            elif os.path.splitext(file)[1].lower() == '.gct':
                                with open(os.path.join(gctFile, file), 'rb') as gct:
                                    temp.write(gct.read()[8:-8])
                            else:
                                print(TYELLOW + '  :: WARNING: {} is not a .txt or .gct file'.format(file) + TRESET)
                
                    temp.write(bytes.fromhex('F000000000000000'))
                    temp.seek(0)
                    codehandler.geckoCodes = GCT(temp)

            

            if self.protect and self.build == "ARENA":
                self.protect_game(codehandler)

            if self.codeLocation == 'AUTO':
                if codehandler.initAddress + codehandler.handlerLength + codehandler.geckoCodes.size > 0x80002FFF:
                    self.codeLocation = 'ARENA'
                else:
                    self.codeLocation = 'LEGACY'

            '''Get entrypoint (or BSS midpoint) for insert'''

            if self.initAddress:
                dump_address = self.initAddress.lstrip("0x").upper()
                try:
                    dolFile.resolve_address(int(dump_address, 16))
                    print(TYELLOW + '\n  :: WARNING: Init address specified for GeckoLoader (0x{}) clobbers existing dol sections'.format(dump_address) + TRESET)
                except RuntimeError:
                    pass
            else:
                dump_address = '{:08X}'.format(dolFile.seek_safe_address((dolFile.bssOffset + (dolFile.bssSize >> 1)) & 0xFFFFFF00,
                                                                         get_size(self.rawData) + codehandler.handlerLength + codehandler.geckoCodes.size))
                self.rawData.seek(0)

            '''Is insertion legacy?'''

            if codehandler.geckoCodes.size <= 0x10:
                dolFile.save(final)
                if self.verbosity >= 1:
                    print(TGREENLIT + '\n  :: All codes have been successfully pre patched' + TRESET)
                return

            if self.codeLocation == 'LEGACY':
                codehandler.allocation = 0x80003000 - (codehandler.initAddress + codehandler.handlerLength)
                status = self.patch_legacy(codehandler, dolFile, tmp)
                if status is False:
                    determine_codehook(dolFile, codehandler)
                legacy = True
            else:
                status = self.patch_arena(codehandler, dolFile, dump_address, tmp)
                legacy = False

            if status is False:
                shutil.rmtree(tmpdir)
                parser.error(TREDLIT + 'Not enough text sections to patch the DOL file! Potentially due to previous mods?\n' + TRESET)

            dolFile.save(final)
        
            if codehandler.allocation < codehandler.geckoCodes.size:
                print(TYELLOW + '\n  :: WARNING: Allocated codespace was smaller than the given codelist. The game will crash if run' + TRESET)

            if self.quiet:
                return

            if codehandler.allocation > 0x70000:
                print(TYELLOW + f'\n  :: WARNING: Allocations beyond 0x70000 will crash certain games. You allocated 0x{codehandler.allocation:X}' + TRESET)
            
            elif codehandler.allocation > 0x40000:
                print(TYELLOWLIT + f'\n  :: HINT: Recommended allocation limit is 0x40000. You allocated 0x{codehandler.allocation:X}' + TRESET)
        
            if self.verbosity >= 2:
                print('')
                if legacy == False:
                    info = [TGREENLIT + f'  :: GeckoLoader set at address 0x{dump_address.upper()}, start of game modified to address 0x{dump_address.upper()}',
                                        f'  :: Game function "__init_registers" located at address 0x{dolFile.entryPoint:X}'.format(),
                                        f'  :: Code allocation is 0x{codehandler.allocation:X}; codelist size is 0x{codehandler.geckoCodes.size:X}',
                                        f'  :: Codehandler is of type "{codehandler.type}"',
                                        f'  :: Of the 7 text sections in this DOL file, {len(dolFile.textSections)} were already used' + TRESET]
                    if codehandler.hookAddress is not None:
                        info.insert(2, f'  :: Codehandler hooked at 0x{codehandler.hookAddress:08X}')
            
                else:
                    info = [TGREENLIT + f'  :: Game function "__init_registers" located at address 0x{dolFile.entryPoint:X}',
                                        f'  :: Code allocation is 0x{codehandler.allocation:X}; codelist size is 0x{codehandler.geckoCodes.size:X}',
                                        f'  :: Codehandler is of type "{codehandler.type}"',
                                        f'  :: Of the 7 text sections in this DOL file, {len(dolFile.textSections)} were already used' + TRESET]
                    if codehandler.hookAddress is not None:
                        info.insert(1, f'  :: Codehandler hooked at 0x{codehandler.hookAddress:08X}')
                for bit in info:
                    print(bit)
        
            elif self.verbosity >= 1:
                print('')
                if legacy == False:
                    info = [TGREENLIT + f'  :: GeckoLoader set at address 0x{dump_address.upper()}',
                                        f'  :: Codehandler is of type "{codehandler.type}"',
                                        f'  :: Code allocation is 0x{codehandler.allocation:X}; codelist size is 0x{codehandler.geckoCodes.size:X}' + TRESET]
                else:
                    info = [TGREENLIT + f'  :: Codehandler is of type "{codehandler.type}"',
                                        f'  :: Code allocation is 0x{codehandler.allocation:X}; codelist size is 0x{codehandler.geckoCodes.size:X}' + TRESET]

                for bit in info:
                    print(bit)

            print(TGREENLIT + f'\n  :: Compiled in {(time.time() - beginTime):0.4f} seconds!\n' + TRESET)
