import os
import random
import re
import sys
import time
from io import BytesIO

import tools
from dolreader import DolFile

try:
    import chardet
except ImportError as IE:
    print(IE)
    sys.exit(1)

class GCT:

    def __init__(self, f):
        self.codeList = BytesIO(f.read())
        self.rawLineCount = tools.get_size(f) >> 3
        self.lineCount = self.rawLineCount - 2
        self.size = tools.get_size(f)
        f.seek(0)

    def determine_codelength(self, codetype, info):
        if codetype.startswith(b'\x06'):
            bytelength = int.from_bytes(info, byteorder='big', signed=False)
            padding = tools.get_alignment(bytelength, 8)
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
                        padding = tools.get_alignment(arraylength, 8)
                        
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
                        address_increment = tools.read_uint16(self.codeList)
                        value_increment = tools.read_uint32(self.codeList)

                        while counter + 1 > 0:
                            if size == 0:
                                tools.write_ubyte(dolFile, value)
                                dolFile.seek(-1, 1)
                            elif size == 1:
                                tools.write_uint16(dolFile, value)
                                dolFile.seek(-2, 1)
                            elif size == 2:
                                tools.write_uint32(dolFile, value)
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
        self.size = tools.get_size(self.codeList)

class CodeHandler:

    def __init__(self, f):
        self._rawData = BytesIO(f.read())

        '''Get codelist pointer'''
        f.seek(0xFA)
        codelistUpper = f.read(2).hex()
        f.seek(0xFE)
        codelistLower = f.read(2).hex()

        self.codeListPointer = int(codelistUpper[2:] + codelistLower[2:], 16)
        self.handlerLength = tools.get_size(f)
        self.initAddress = 0x80001800
        self.startAddress = 0x800018A8
        self.wiiVIHook = b'\x7C\xE3\x3B\x78\x38\x87\x00\x34\x38\xA7\x00\x38\x38\xC7\x00\x4C'
        self.gcnVIHook = b'\x7C\x03\x00\x34\x38\x83\x00\x20\x54\x85\x08\x3C\x7C\x7F\x2A\x14\xA0\x03\x00\x00\x7C\x7D\x2A\x14\x20\xA4\x00\x3F\xB0\x03\x00\x00'
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

    def encrypt_key(self, key: int):
        b1 = key & 0xFF
        b2 = (key >> 8) & 0xFF
        b3 = (key >> 16) & 0xFF
        b4 = (key >> 24) & 0xFF
        b3 ^= b4
        b2 ^= b3
        b1 ^= b2
        return (b1 << 24) | (b2 << 16) | (b3 << 8) | b4

    def encrypt_data(self, key: int):
        self.geckoCodes.codeList.seek(0)
        i = 0
        while True:
            try:
                packet = tools.read_uint32(self.geckoCodes.codeList)
                self.geckoCodes.codeList.seek(-4, 1)
                tools.write_uint32(self.geckoCodes.codeList, (packet^key) & 0xFFFFFFFF)
                key += (i ^ key) & 0xFFFFFFFF
                if key > 0xFFFFFFFF:
                    key -= 0x100000000
                i += 1
            except:
                break

class KernelLoader:

    def __init__(self, f):
        self._rawData = BytesIO(f.read())
        self.initDataList = None
        self.gpModDataList = None
        self.gpDiscDataList = None
        self.gpKeyAddrList = None
        self.codeLocation = None
        self.initAddress = None
        self.protect = False
        self.verbosity = 0
        self.quiet = False
        self.encrypt = False

    def set_variables(self, entryPoint: list, baseOffset: int=0):
        self._rawData.seek(0)
        if self.gpModDataList is None:
            return

        sample = self._rawData.read(2)
        
        while sample:
            if sample == b'GH':
                self._rawData.seek(-2, 1)
                tools.write_uint16(self._rawData, self.gpModDataList[0])
            elif sample == b'GL':
                self._rawData.seek(-2, 1)
                tools.write_uint16(self._rawData, baseOffset + self.gpModDataList[1])
            elif sample == b'IH':
                self._rawData.seek(-2, 1)
                tools.write_uint16(self._rawData, entryPoint[0])
            elif sample == b'IL':
                self._rawData.seek(-2, 1)
                tools.write_uint16(self._rawData, entryPoint[1])
            elif sample == b'KH':
                self._rawData.seek(-2, 1)
                tools.write_uint16(self._rawData, self.gpKeyAddrList[0])
            elif sample == b'KL':
                self._rawData.seek(-2, 1)
                tools.write_uint16(self._rawData, baseOffset + self.gpKeyAddrList[1])

            sample = self._rawData.read(2)

    def complete_data(self, codeHandler: CodeHandler, initpoint: list):
        upperAddr, lowerAddr = ((self.initAddress >> 16) & 0xFFFF, self.initAddress & 0xFFFF)
        key = random.randrange(0x100000000)
        self._rawData.seek(0)

        sample = self._rawData.read(4)

        while sample:
            if sample == b'HEAP': #Found keyword "HEAP". Goes with the resize of the heap
                self._rawData.seek(-4, 1)

                gpModInfoOffset = self._rawData.tell()
                if lowerAddr + gpModInfoOffset > 0x7FFF: #Absolute addressing
                    gpModUpperAddr = upperAddr + 1
                else:
                    gpModUpperAddr = upperAddr

                if codeHandler.allocation == None:
                    codeHandler.allocation = (codeHandler.handlerLength + codeHandler.geckoCodes.size + 7) & -8
                    
                tools.write_uint32(self._rawData, codeHandler.allocation)
                    
            elif sample == b'LSIZ': #Found keyword "LSIZ". Goes with the size of the loader
                self._rawData.seek(-4, 1)
                tools.write_uint32(self._rawData, len(self._rawData.getbuffer()))
                    
            elif sample == b'HSIZ': #Found keyword "HSIZ". Goes with the size of the codeHandler
                self._rawData.seek(-4, 1)
                tools.write_sint32(self._rawData, codeHandler.handlerLength)
            
            elif sample == b'CSIZ': #Found keyword "CSIZ". Goes with the size of the codes
                self._rawData.seek(-4, 1)
                tools.write_sint32(self._rawData, codeHandler.geckoCodes.size)
            
            elif sample == b'HOOK': #Found keyword "HOOK". Goes with the codehandler hook
                self._rawData.seek(-4, 1)
                if codeHandler.hookAddress == None:
                    tools.write_uint32(self._rawData, 0)
                else:
                    tools.write_uint32(self._rawData, codeHandler.hookAddress)

            elif sample == b'CRPT': #Found keyword "CRPT". Boolean of the encryption
                self._rawData.seek(-4, 1)
                tools.write_bool(self._rawData, self.encrypt, 4)

            elif sample == b'CYPT': #Found keyword "CYPT". Encryption Key
                self._rawData.seek(-4, 1)

                gpKeyOffset = self._rawData.tell()
                if lowerAddr + gpKeyOffset > 0x7FFF: #Absolute addressing
                    gpKeyUpperAddr = upperAddr + 1
                else:
                    gpKeyUpperAddr = upperAddr

                tools.write_uint32(self._rawData, codeHandler.encrypt_key(key))
            
            sample = self._rawData.read(4)

        self.gpModDataList = (gpModUpperAddr, gpModInfoOffset)
        self.gpKeyAddrList = (gpKeyUpperAddr, gpKeyOffset)

        self.set_variables(initpoint, lowerAddr)
        
        if self.encrypt:
            codeHandler.encrypt_data(key)


    def patch_arena(self, codeHandler: CodeHandler, dolFile: DolFile):
        self.complete_data(codeHandler, [(dolFile.entryPoint >> 16) & 0xFFFF, dolFile.entryPoint & 0xFFFF])

        self._rawData.seek(0, 2)
        self._rawData.write(codeHandler._rawData.getvalue() + codeHandler.geckoCodes.codeList.getvalue())

        self._rawData.seek(0)
        kernelData = self._rawData.getvalue()

        status = dolFile.append_text_sections([(kernelData, self.initAddress)])

        if status is True:
            dolFile.entryPoint = self.initAddress

        return status

    def patch_legacy(self, codeHandler: CodeHandler, dolFile: DolFile):
        codeHandler._rawData.seek(0)
        codeHandler.geckoCodes.codeList.seek(0)
        
        handlerData = codeHandler._rawData.getvalue() + codeHandler.geckoCodes.codeList.getvalue()

        status = dolFile.append_text_sections([(handlerData, codeHandler.initAddress)])
        return status

    def protect_game(self, codeHandler: CodeHandler):
        oldpos = codeHandler.geckoCodes.codeList.tell()

        protectdata = [b'\xC0\x00\x00\x00\x00\x00\x00\x17',
					   b'\x7C\x08\x02\xA6\x94\x21\xFF\x70',
                       b'\x90\x01\x00\x08\xBC\x61\x00\x0C',
                       b'\x48\x00\x00\x0D\x00\xD0\xC0\xDE',
                       b'\x00\xD0\xDE\xAD\x7F\xE8\x02\xA6',
                       b'\x3B\xDF\x00\x08\x3C\x60\x80\x00',
                       b'\x38\x80\x11\x00\x38\xA0\x00\x00',
                       b'\x60\x63\x1E\xF8\x7C\x89\x03\xA6',
                       b'\x38\x80\x00\x00\x7D\x03\x22\x14',
                       b'\x54\xE9\x06\x3E\x89\x08\x00\x08',
                       b'\x7D\x3F\x48\xAE\x38\xE7\x00\x01',
                       b'\x7C\x08\x48\x40\x41\x82\x00\x0C',
                       b'\x60\xA7\x00\x00\x48\x00\x00\x04',
                       b'\x54\xE8\x06\x3E\x28\x08\x00\x03',
                       b'\x41\x81\x00\x10\x38\x84\x00\x01',
                       b'\x42\x00\xFF\xCC\x48\x00\x00\x2C',
                       b'\x38\xA0\x00\x08\x7C\x84\x1A\x14',
                       b'\x7C\xA9\x03\xA6\x38\x60\x00\x00',
                       b'\x38\x84\xFF\xFF\x54\x66\x07\xBE',
                       b'\x7C\xDE\x30\xAE\x38\x63\x00\x01',
                       b'\x9C\xC4\x00\x01\x42\x00\xFF\xF0',
                       b'\xB8\x61\x00\x0C\x80\x01\x00\x08',
                       b'\x38\x21\x00\x90\x7C\x08\x03\xA6',
                       b'\x4E\x80\x00\x20\x00\x00\x00\x00']

        codeHandler.geckoCodes.codeList.seek(-8, 2)
        for chunk in protectdata:
            codeHandler.geckoCodes.codeList.write(chunk)
        codeHandler.geckoCodes.codeList.write(b'\xF0\x00\x00\x00\x00\x00\x00\x00')
        codeHandler.geckoCodes.codeList.seek(0, 2)
        codeHandler.geckoCodes.size = codeHandler.geckoCodes.codeList.tell()
        codeHandler.geckoCodes.codeList.seek(oldpos)

    def build(self, parser: tools.CommandLineParser, gctFile, dolFile: DolFile, codeHandler: CodeHandler, tmpdir, dump):
        beginTime = time.time()

        with open(dump, 'wb+') as final:

            if dolFile.get_full_size() < 0x100:
                parser.error(tools.color_text('DOL header is corrupted. Please provide a clean file\n', defaultColor=tools.TREDLIT), exit=False)
                return

            '''Initialize our codes'''

            foundData = False

            if '.' in gctFile:
                if os.path.splitext(gctFile)[1].lower() == '.txt':
                    with open(os.path.join(tmpdir, 'gct.bin'), 'wb+') as temp:
                        temp.write(bytes.fromhex('00D0C0DE'*2 + codeHandler.gecko_parser(gctFile, codeHandler.includeAll) + 'F000000000000000'))
                        temp.seek(0)
                        codeHandler.geckoCodes = GCT(temp)
                    foundData = True
                elif os.path.splitext(gctFile)[1].lower() == '.gct':
                    with open(gctFile, 'rb') as gct:
                        codeHandler.geckoCodes = GCT(gct)
                    foundData = True
                    
            else:
                with open(os.path.join(tmpdir, 'gct.bin'), 'wb+') as temp:
                    temp.write(bytes.fromhex('00D0C0DE'*2))

                    for file in os.listdir(gctFile):
                        if os.path.isfile(os.path.join(gctFile, file)):
                            if os.path.splitext(file)[1].lower() == '.txt':
                                temp.write(bytes.fromhex(codeHandler.gecko_parser(os.path.join(gctFile, file), codeHandler.includeAll)))  
                                foundData = True
                            elif os.path.splitext(file)[1].lower() == '.gct':
                                with open(os.path.join(gctFile, file), 'rb') as gct:
                                    temp.write(gct.read()[8:-8])
                                foundData = True
                            else:
                                print(tools.color_text(f'  :: HINT: {file} is not a .txt or .gct file', defaultColor=tools.TYELLOWLIT))
                
                    temp.write(bytes.fromhex('F000000000000000'))
                    temp.seek(0)
                    codeHandler.geckoCodes = GCT(temp)

            if not foundData:
                parser.error(tools.color_text('No valid gecko code file found\n', defaultColor=tools.TREDLIT), exit=False)
                return

            if self.protect and self.codeLocation == "ARENA":
                self.protect_game(codeHandler)

            if self.codeLocation == 'AUTO':
                if codeHandler.initAddress + codeHandler.handlerLength + codeHandler.geckoCodes.size > 0x80002FFF:
                    self.codeLocation = 'ARENA'
                else:
                    self.codeLocation = 'LEGACY'

            '''Get entrypoint (or BSS midpoint) for insert'''

            if self.initAddress:
                try:
                    dolFile.resolve_address(self.initAddress)
                    print(tools.color_text(f'\n  :: WARNING: Init address specified for GeckoLoader (0x{self.initAddress:X}) clobbers existing dol sections', defaultColor=tools.TYELLOW))
                except RuntimeError:
                    pass
            else:
                self.initAddress = dolFile.seek_nearest_unmapped(dolFile.bssAddress, tools.get_size(self._rawData) + codeHandler.handlerLength + codeHandler.geckoCodes.size)
                self._rawData.seek(0)

            '''Is insertion legacy?'''

            if codeHandler.geckoCodes.size <= 0x10:
                dolFile.save(final)
                if self.verbosity >= 1:
                    print(tools.color_text('\n  :: All codes have been successfully pre patched', defaultColor=tools.TGREENLIT))
                return

            if self.codeLocation == 'LEGACY':
                codeHandler.allocation = 0x80003000 - (codeHandler.initAddress + codeHandler.handlerLength)
                status = self.patch_legacy(codeHandler, dolFile)
                if status is False:
                    hooked, msg = determine_codehook(dolFile, codeHandler)
                    if not hooked:
                        parser.error(tools.color_text(msg, defaultColor=tools.TREDLIT))
                legacy = True
            else:
                status = self.patch_arena(codeHandler, dolFile)
                legacy = False

            if status is False:
                parser.error(tools.color_text('Not enough text sections to patch the DOL file! Potentially due to previous mods?\n', defaultColor=tools.TREDLIT), exit=False)
                return

            dolFile.save(final)
        
            if codeHandler.allocation < codeHandler.geckoCodes.size:
                print(tools.color_text('\n  :: WARNING: Allocated codespace was smaller than the given codelist. The game will crash if run', defaultColor=tools.TYELLOW))
                
            if self.quiet:
                return

            if codeHandler.allocation > 0x70000:
                print(tools.color_text(f'\n  :: WARNING: Allocations beyond 0x70000 will crash certain games. You allocated 0x{codeHandler.allocation:X}', defaultColor=tools.TYELLOW))
            
            elif codeHandler.allocation > 0x40000:
                print(tools.color_text(f'\n  :: HINT: Recommended allocation limit is 0x40000. You allocated 0x{codeHandler.allocation:X}', defaultColor=tools.TYELLOWLIT))
        
            if self.verbosity >= 2:
                print('')
                if legacy == False:
                    info = [f'  :: GeckoLoader set at address 0x{self.initAddress:X}, start of game modified to address 0x{self.initAddress:X}',
                            f'  :: Game function "__init_registers()" located at address 0x{dolFile.entryPoint:X}',
                            f'  :: Code allocation is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.geckoCodes.size:X}',
                            f'  :: Codehandler is of type "{codeHandler.type}"',
                            f'  :: Of the 7 text sections in this DOL file, {len(dolFile.textSections)} were already used']
                    if codeHandler.hookAddress is not None:
                        info.insert(2, f'  :: Codehandler hooked at 0x{codeHandler.hookAddress:08X}')
            
                else:
                    info = [f'  :: Game function "__init_registers()" located at address 0x{dolFile.entryPoint:X}',
                            f'  :: Code allocation is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.geckoCodes.size:X}',
                            f'  :: Codehandler is of type "{codeHandler.type}"',
                            f'  :: Of the 7 text sections in this DOL file, {len(dolFile.textSections)} were already used']
                    if codeHandler.hookAddress is not None:
                        info.insert(1, f'  :: Codehandler hooked at 0x{codeHandler.hookAddress:08X}')
                for bit in info:
                    print(tools.color_text(bit, defaultColor=tools.TGREENLIT))
        
            elif self.verbosity >= 1:
                print('')
                if legacy == False:
                    info = [f'  :: GeckoLoader set at address 0x{self.initAddress:X}',
                            f'  :: Codehandler is of type "{codeHandler.type}"',
                            f'  :: Code allocation is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.geckoCodes.size:X}']
                else:
                    info = [f'  :: Codehandler is of type "{codeHandler.type}"',
                            f'  :: Code allocation is 0x{codeHandler.allocation:X}; codelist size is 0x{codeHandler.geckoCodes.size:X}']

                for bit in info:
                    print(tools.color_text(bit, defaultColor=tools.TGREENLIT))

            print(tools.color_text(f'\n  :: Compiled in {(time.time() - beginTime):0.4f} seconds!\n', defaultColor=tools.TGREENLIT))


def resource_path(relative_path: str):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def determine_codehook(dolFile: DolFile, codeHandler: CodeHandler):
    if codeHandler.hookAddress == None:
        return assert_code_hook(dolFile, codeHandler)
    else:
        return insert_code_hook(dolFile, codeHandler, codeHandler.hookAddress)


def assert_code_hook(dolFile: DolFile, codeHandler: CodeHandler):
    for _, address, size in dolFile.textSections:
        dolFile.seek(address, 0)
        sample = dolFile.read(size)

        result = sample.find(codeHandler.gcnVIHook)
        if result >= 0:
            dolFile.seek(address, 0)
            dolFile.seek(result, 1)
        else:
            result = sample.find(codeHandler.wiiVIHook)
            if result >= 0:
                dolFile.seek(address, 0)
                dolFile.seek(result, 1)
            else:
                continue

        sample = tools.read_uint32(dolFile)
        while sample != 0x4E800020:
            sample = tools.read_uint32(dolFile)

        dolFile.seek(-4, 1)
        codeHandler.hookAddress = dolFile.tell()

        return insert_code_hook(dolFile, codeHandler, codeHandler.hookAddress)
    return False, 'Failed to find a hook address. Try using option --codehook to use your own address\n'

def insert_code_hook(dolFile: DolFile, codeHandler: CodeHandler, address: int):
    dolFile.seek(address)

    if tools.read_uint32(dolFile) != 0x4E800020:
        return False, 'Codehandler hook given is not a blr\n'

    dolFile.seek(-4, 1)
    dolFile.insert_branch(codeHandler.startAddress, address, lk=0)
    return True, ''