#Written by JoshuaMK 2020

import sys
import os
import time
import re
import shutil
import glob
import dolreader

from io import BytesIO, RawIOBase

try:
    import argparse
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

def resource_path(relative_path: str):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def getAlignment(number, align: int):
    if number % align != 0:
        return align - (number % align)
    else:
        return 0

def get_size(file, offset=0):
    """ Return a file's size in bytes """
    file.seek(0, 2)
    return file.tell() + offset

def getFileAlignment(file, alignment: int):
    """ Return file alignment, 0 = aligned, non zero = misaligned """
    size = get_size(file)
    return getAlignment(size, alignment)

def alignFile(file, alignment: int, fillchar='00'):
    """ Align a file to be the specified size """
    file.write(bytes.fromhex(fillchar * getFileAlignment(file, alignment)))

class GCT(object):

    def __init__(self, f):
        self.codelist = BytesIO(f.read())
        self.rawlinecount = get_size(f) >> 3
        self.linecount = self.rawlinecount - 2
        self.size = get_size(f)
        f.seek(0)

class CodeHandler(object):

    def __init__(self, f):
        self.codehandler = BytesIO(f.read())

        '''Get codelist pointer'''
        f.seek(0xFA)
        codelistUpper = f.read(2).hex()
        f.seek(0xFE)
        codelistLower = f.read(2).hex()

        self.codelistpointer = int(codelistUpper[2:] + codelistLower[2:], 16)
        self.handlerlength = get_size(f)
        self.initaddress = 0x80001800
        self.startaddress = 0x800018A8
        self.allocation = None
        self.hookaddress = None
        self.geckocodes = ''

        if self.handlerlength < 0x900:
            self.type = "Mini"
        else:
            self.type = "Full"

        f.seek(0)

    def geckoParser(self, geckoText, parseAll=False):
        with open(r'{}'.format(geckoText), 'rb') as gecko:
            result = chardet.detect(gecko.read())
            encodeType = result['encoding']

        with open(r'{}'.format(geckoText), 'r', encoding=encodeType) as gecko:
            data = gecko.readlines()
            geckoCodes = ''

            for line in data:
                if parseAll.lower() == 'all':
                    geckoLine = re.findall(r'[A-F0-9]{8}\s[A-F0-9]{8}', line, re.IGNORECASE)
                elif parseAll.lower() == 'active':
                    geckoLine = re.findall(r'\*\s[A-F0-9]{8}\s[A-F0-9]{8}', line, re.IGNORECASE)
                else:
                    geckoLine = re.findall(r'\*\s[A-F0-9]{8}\s[A-F0-9]{8}', line, re.IGNORECASE)

                geckoLine = ''.join(geckoLine)
                geckoLine = re.sub(r'\s+', '', geckoLine)
                geckoCodes = geckoCodes + geckoLine.replace('*', '')

        return geckoCodes

def build(gctFile, dolFile, codehandlerFile, allocation: int, codehook: int):
    with open(resource_path(os.path.join('bin', 'geckoloader.bin')), 'rb') as code, open(r'{}'.format(dolFile), 'rb') as dol, open(resource_path(os.path.join('bin', r'{}'.format(codehandlerFile))), 'rb') as handler, open(os.path.join('tmp', 'tmp.bin'), 'wb+') as tmp, open(os.path.join('BUILD', os.path.basename(dolFile)), 'wb+') as final:

        if get_size(dol) < 0x100:
            shutil.rmtree('tmp')
            parser.error('DOL header is corrupted. Please provide a clean file')
        
        dol.seek(0)

        '''Initialize the new DOL file'''

        final.write(dol.read())
        final.seek(0)
        
        dolfile = dolreader.DolFile(final)

        '''Initialize our codehandler + codes'''

        codehandler = CodeHandler(handler)
        codehandler.allocation = allocation
        codehandler.hookaddress = codehook

        if '.' in gctFile:
            if os.path.splitext(gctFile)[1].lower() == '.txt':
                with open(os.path.join('tmp', 'gct.bin'), 'wb+') as temp:
                    temp.write(bytes.fromhex('00D0C0DE'*2 + codehandler.geckoParser(gctFile, args.txtcodes) + 'F000000000000000'))
                    temp.seek(0)
                    codehandler.geckocodes = GCT(temp)    
            elif os.path.splitext(gctFile)[1].lower() == '.gct':
                with open(r'{}'.format(gctFile), 'rb') as gct:
                    codehandler.geckocodes = GCT(gct)
            else:
                parser.error('No valid gecko code file found')
        else:
            with open(os.path.join('tmp', 'gct.bin'), 'wb+') as temp:
                temp.write(bytes.fromhex('00D0C0DE'*2))
                for file in os.listdir(gctFile):
                    if os.path.isfile(os.path.join(gctFile, file)):
                        if os.path.splitext(file)[1].lower() == '.txt':
                            temp.write(bytes.fromhex(codehandler.geckoParser(os.path.join(gctFile, file), args.txtcodes)))  
                        elif os.path.splitext(file)[1].lower() == '.gct':
                            with open(os.path.join(gctFile, file), 'rb') as gct:
                                temp.write(gct.read()[8:-8])
                        else:
                            print(TYELLOW + '  :: WARNING: {} is not a .txt or .gct file'.format(file) + TRESET)
                temp.write(bytes.fromhex('F000000000000000'))
                temp.seek(0)
                print(temp.read())
                temp.seek(0)
                codehandler.geckocodes = GCT(temp)

        if args.optimize == True:
            optimizeCodelist(codehandler, dolfile)

        '''Get entrypoint (or BSS midpoint) for insert'''

        if args.init:
            dump_address = args.init.lstrip("0x").upper()
            try:
                dolfile._resolve_address(int(dump_address, 16))
                print(TYELLOW + '\n  :: WARNING: Init address specified for GeckoLoader (0x{}) clobbers existing dol sections'.format(dump_address) + TRESET)
            except RuntimeError:
                pass
        else:
            dump_address = '{:08X}'.format(dolfile._bssoffset + (dolfile._bsssize >> 1))[:-2] + '00'
            dump_address = '{:08X}'.format(dolfile.seekSafeAddress(int(dump_address, 16), get_size(code) + codehandler.handlerlength + codehandler.geckocodes.size))
            code.seek(0)

        '''Is insertion legacy?'''

        if codehandler.geckocodes.size <= 0x10:
            dolfile.save(final)
            if args.verbose >= 1:
                print(TGREENLIT + '\n  :: All codes have been successfully pre patched' + TRESET)
            return

        if args.movecodes == 'LEGACY':
            codehandler.allocation = 0x80003000 - (codehandler.initaddress + codehandler.handlerlength)
            patchLegacyHandler(codehandler, tmp, dolfile)
            legacy = True
        elif args.movecodes == 'ARENA':
            patchGeckoLoader(code, codehandler, tmp, dolfile, dump_address)
            legacy = False
        else: #Auto decide area
            if codehandler.initaddress + codehandler.handlerlength + codehandler.geckocodes.size > 0x80002FFF:
                patchGeckoLoader(code, codehandler, tmp, dolfile, dump_address)
                legacy = False
            else:
                codehandler.allocation = 0x80003000 - (codehandler.initaddress + codehandler.handlerlength)
                patchLegacyHandler(codehandler, tmp, dolfile)
                legacy = True

        dolfile.save(final)
        
        if codehandler.allocation < codehandler.geckocodes.size:
            print(TYELLOW + '\n  :: WARNING: Allocated codespace was smaller than the given codelist. The game will crash if run' + TRESET)

        if args.quiet:
            return

        if codehandler.allocation > 0x70000:
            print(TYELLOW + '\n  :: WARNING: Allocations beyond 0x70000 will crash certain games. You allocated 0x{:X}'.format(codehandler.allocation) + TRESET)
            
        elif codehandler.allocation > 0x40000:
            print(TYELLOWLIT + '\n  :: HINT: Recommended allocation limit is 0x40000. You allocated 0x{:X}'.format(codehandler.allocation) + TRESET)
        
        if args.verbose >= 2:
            print('')
            if legacy == False:
                info = [TGREENLIT + '  :: GeckoLoader set at address 0x{}, start of game modified to address 0x{}'.format(dump_address.upper().lstrip('0'), dump_address.upper().lstrip('0')),
                    '  :: Game function "__init_registers" located at address 0x{:X}'.format(dolfile._init),
                    '  :: Code allocation is 0x{:X}; codelist size is 0x{:X}'.format(codehandler.allocation, codehandler.geckocodes.size),
                    '  :: Codehandler is of type "{}"'.format(codehandler.type),
                    '  :: Of the 7 text sections in this DOL file, {} were already used'.format(len(dolfile._text)) + TRESET]
                if codehandler.hookaddress is not None:
                    info.insert(2, '  :: Codehandler hooked at 0x{:08X}'.format(codehandler.hookaddress))
            
            else:
                info = [TGREENLIT + '  :: Game function "__init_registers" located at address 0x{:X}'.format(dolfile._init),
                        '  :: Code allocation is 0x{:X}; codelist size is 0x{:X}'.format(codehandler.allocation, codehandler.geckocodes.size),
                        '  :: Codehandler is of type "{}"'.format(codehandler.type),
                        '  :: Of the 7 text sections in this DOL file, {} were already used'.format(len(dolfile._text)) + TRESET]
                if codehandler.hookaddress is not None:
                    info.insert(1, '  :: Codehandler hooked at 0x{:08X}'.format(codehandler.hookaddress))
            for bit in info:
                print(bit)
        
        elif args.verbose >= 1:
            print('')
            if legacy == False:
                info = [TGREENLIT + '  :: GeckoLoader set at address 0x{}'.format(dump_address.upper()),
                        '  :: Codehandler is of type "{}"'.format(args.handler),
                        '  :: Code allocation is 0x{} in hex; codelist size is 0x{:X}'.format(codehandler.allocation, codehandler.geckocodes.size) + TRESET]
            else:
                info = [TGREENLIT + '  :: Codehandler is of type "{}"'.format(args.handler),
                        '  :: Code allocation is 0x{} in hex; codelist size is 0x{:X}'.format(codehandler.allocation, codehandler.geckocodes.size) + TRESET]

            for bit in info:
                print(bit)
        return

def determineCodeLength(codetype, info):
    if codetype.startswith(b'\x06'):
        bytelength = int.from_bytes(info, byteorder='big', signed=False)
        padding = getAlignment(bytelength, 8)
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

def optimizeCodelist(codehandler, dolfile):
    codetype = b'DUMMY'
    codelist = b''
    skipcodes = 0
    while codetype:
        codetype = codehandler.geckocodes.codelist.read(4)
        info = codehandler.geckocodes.codelist.read(4)
        address = 0x80000000 | (int.from_bytes(codetype, byteorder='big', signed=False) & 0x01FFFFFF)
        try:
            if skipcodes <= 0:
                if (codetype.startswith(b'\x00') or codetype.startswith(b'\x01')
                    or codetype.startswith(b'\x10') or codetype.startswith(b'\x11')):
                    dolfile.seek(address)

                    counter = int.from_bytes(info[:-2], byteorder='big', signed=False)
                    value = info[2:]

                    while counter + 1 > 0:
                        dolfile.write(value[1:])
                        counter -= 1
                    continue

                elif (codetype.startswith(b'\x02') or codetype.startswith(b'\x03')
                    or codetype.startswith(b'\x12') or codetype.startswith(b'\x13')):
                    dolfile.seek(address)

                    counter = int.from_bytes(info[:-2], byteorder='big', signed=False)
                    value = info[2:]

                    while counter + 1 > 0:
                        dolfile.write(value)
                        counter -= 1
                    continue

                elif (codetype.startswith(b'\x04') or codetype.startswith(b'\x05')
                    or codetype.startswith(b'\x14') or codetype.startswith(b'\x15')):
                    dolfile.seek(address)
                    dolfile.write(info)
                    continue

                elif (codetype.startswith(b'\x06') or codetype.startswith(b'\x07')
                    or codetype.startswith(b'\x16') or codetype.startswith(b'\x17')):
                    dolfile.seek(address)

                    arraylength = int.from_bytes(info, byteorder='big', signed=False)
                    padding = getAlignment(arraylength, 8)
                    while arraylength > 0:
                        value = codehandler.geckocodes.codelist.read(1)
                        dolfile.write(value)
                        arraylength -= 1
                    codehandler.geckocodes.codelist.seek(padding, 1)
                    continue

                elif (codetype.startswith(b'\x08') or codetype.startswith(b'\x09')
                    or codetype.startswith(b'\x18') or codetype.startswith(b'\x19')):
                    dolfile.seek(address)

                    value = int.from_bytes(info, byteorder='big', signed=False)
                    data = codehandler.geckocodes.codelist.read(2).hex()
                    size = int(data[:-3], 16)
                    counter = int(data[1:], 16)
                    address_increment = int.from_bytes(codehandler.geckocodes.codelist.read(2), byteorder='big', signed=False)
                    value_increment = int.from_bytes(codehandler.geckocodes.codelist.read(4), byteorder='big', signed=False)

                    while counter + 1 > 0:
                        if size == 0:
                            dolfile.write(value.to_bytes(length=1, byteorder='big', signed=False))
                            dolfile.seek(-1, 1)
                        elif size == 1:
                            dolfile.write(value.to_bytes(length=2, byteorder='big', signed=False))
                            dolfile.seek(-2, 1)
                        elif size == 2:
                            dolfile.write(value.to_bytes(length=4, byteorder='big', signed=False))
                            dolfile.seek(-4, 1)
                        else:
                            raise ValueError('Size type {} does not match 08 codetype specs'.format(size))
                        
                        dolfile.seek(address_increment, 1)
                        value += value_increment
                        counter -= 1
                        if value > 0xFFFFFFFF:
                            value -= 0x100000000
                    continue

                elif (codetype.startswith(b'\xC6') or codetype.startswith(b'\xC7')
                    or codetype.startswith(b'\xC6') or codetype.startswith(b'\xC7')):
                    dolfile.seek(address)
                    dolfile.insertBranch(int.from_bytes(info, byteorder='big', signed=False), dolfile.tell())
                    continue

            if codetype.hex().startswith('2') or codetype.hex().startswith('3'):
                skipcodes += 1

            elif codetype.startswith(b'\xE0'):
                skipcodes -= 1

            elif codetype.startswith(b'\xF0'):
                codelist += b'\xF0\x00\x00\x00\x00\x00\x00\x00'
                break

            codehandler.geckocodes.codelist.seek(-8, 1)
            length = determineCodeLength(codetype, info)
            while length > 0:
                codelist += codehandler.geckocodes.codelist.read(1)
                length -= 1

        except RuntimeError:
            codehandler.geckocodes.codelist.seek(-8, 1)
            length = determineCodeLength(codetype, info)
            while length > 0:
                codelist += codehandler.geckocodes.codelist.read(1)
                length -= 1

    codehandler.geckocodes.codelist = BytesIO(codelist)
    codehandler.geckocodes.size = get_size(codehandler.geckocodes.codelist)

def patchGeckoLoader(fLoader, codehandler: CodeHandler, tmp, dolfile: dolreader.DolFile, entrypoint: str):
    tmp.write(fLoader.read())
    geckoloader_offset = dolfile.getsize()
    figureLoaderData(tmp, fLoader, codehandler, dolfile, entrypoint,
                     [((dolfile._init >> 16) & 0xFFFF).to_bytes(2, byteorder='big', signed=False),
                      (dolfile._init & 0xFFFF).to_bytes(2, byteorder='big', signed=False)])
    tmp.seek(0)
    dolfile._rawdata.seek(0, 2)
    dolfile._rawdata.write(tmp.read())
    dolfile.align(256)

    assertTextSections(dolfile, 6, [[int(entrypoint, 16), geckoloader_offset]])

    '''Write game entry in DOL file header'''
    dolfile.setInitPoint(int(entrypoint, 16))

def patchLegacyHandler(codehandler: CodeHandler, tmp, dolfile: dolreader.DolFile):
    handler_offset = dolfile.getsize()

    dolfile._rawdata.seek(0, 2)
    codehandler.codehandler.seek(0)
    codehandler.geckocodes.codelist.seek(0)
    
    dolfile._rawdata.write(codehandler.codehandler.read() + codehandler.geckocodes.codelist.read())
    dolfile.align(256)

    assertTextSections(dolfile, 6, [[codehandler.initaddress, handler_offset]])
    determineCodeHook(dolfile, codehandler)

def assertTextSections(dolfile: dolreader.DolFile, textsections: int, sections_list: list):
    offset = len(dolfile._text) << 2
    if len(sections_list) + len(dolfile._text) <= 7:
        '''Write offset to each section in DOL file header'''
        dolfile._rawdata.seek(offset)
        for section_offset in sections_list:
            dolfile._rawdata.write(bytes.fromhex('{:08X}'.format(section_offset[1]))) #offset in file
        
        dolfile._rawdata.seek(0x48 + offset)

        '''Write in game memory addresses for each section in DOL file header'''
        for section_addr in sections_list:
            dolfile._rawdata.write(bytes.fromhex('{:08X}'.format(section_addr[0]))) #absolute address in game

        '''Get size of GeckoLoader + gecko codes, and the codehandler'''
        size_list = []
        for i, section_offset in enumerate(sections_list, start=1):
            if i > len(sections_list) - 1:
                size_list.append(dolfile.getsize() - section_offset[1])
            else:
                size_list.append(sections_list[i][1] - section_offset[1])

        '''Write size of each section into DOL file header'''
        dolfile._rawdata.seek(0x90 + offset)
        for size in size_list:
            dolfile._rawdata.write(bytes.fromhex('{:08X}'.format(size)))
    else:
        shutil.rmtree('tmp')
        parser.error(TREDLIT + 'Not enough text sections to patch the DOL file! Potentially due to previous mods?\n' + TRESET)

def figureLoaderData(tmp, fLoader, codehandler: CodeHandler, dolfile: dolreader.DolFile, entrypoint: str, initpoint: list):
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
                codehandler.allocation = (codehandler.handlerlength + codehandler.geckocodes.size + 7) & 0xFFFFFFF8
            tmp.write(codehandler.allocation.to_bytes(4, byteorder='big', signed=False))
                
        elif sample == LOADERSIZE: #Found keyword "LSIZ". Goes with the size of the loader
            tmp.seek(-4, 1)
            tmp.write(get_size(fLoader).to_bytes(4, byteorder='big', signed=False))
                
        elif sample == HANDLERSIZE: #Found keyword "HSIZ". Goes with the size of the codehandler
            tmp.seek(-4, 1)
            tmp.write(codehandler.handlerlength.to_bytes(4, byteorder='big', signed=True))
        
        elif sample == CODESIZE: #Found keyword "CSIZ". Goes with the size of the codes
            tmp.seek(-4, 1)
            tmp.write(codehandler.geckocodes.size.to_bytes(4, byteorder='big', signed=True))
        
        elif sample == CODEHOOK:
            tmp.seek(-4, 1)
            if codehandler.hookaddress == None:
                tmp.write(b'\x00\x00\x00\x00')
            else:
                tmp.write(codehandler.hookaddress.to_bytes(4, byteorder='big', signed=False))
        
        sample = tmp.read(4)
        
    gpDiscOffset = get_size(tmp, -4)

    if int(lowerAddr, 16) + gpDiscOffset > 0x7FFF: #Absolute addressing
        gpDiscUpperAddr = (int(upperAddr, 16) + 1).to_bytes(2, byteorder='big', signed=False)
    else:
        gpDiscUpperAddr = int(upperAddr, 16).to_bytes(2, byteorder='big', signed=False)

    fillLoaderData(tmp, initpoint, int(lowerAddr, 16), [gpModUpperAddr, gpModInfoOffset], [gpDiscUpperAddr, gpDiscOffset])
    
    tmp.seek(0, 2)
    codehandler.codehandler.seek(0)
    codehandler.geckocodes.codelist.seek(0)

    tmp.write(codehandler.codehandler.read() + codehandler.geckocodes.codelist.read())

def fillLoaderData(tmp, _init: list, lowerAddr: int, gpModInfo: list, gpDiscInfo: list):
    tmp.seek(0)
    sample = tmp.read(2)
    while sample:
        if sample == DH:
            tmp.seek(-2, 1)
            tmp.write(gpDiscInfo[0])
        elif sample == DL:
            tmp.seek(-2, 1)
            tmp.write((lowerAddr + gpDiscInfo[1]).to_bytes(2, byteorder='big', signed=False))
        elif sample == GH:
            tmp.seek(-2, 1)
            tmp.write(gpModInfo[0])
        elif sample == GL:
            tmp.seek(-2, 1)
            tmp.write((lowerAddr + gpModInfo[1]).to_bytes(2, byteorder='big', signed=False))
        elif sample == IH:
            tmp.seek(-2, 1)
            tmp.write(_init[0])
        elif sample == IL:
            tmp.seek(-2, 1)
            tmp.write(_init[1])
        sample = tmp.read(2) 

def determineCodeHook(dolfile: dolreader.DolFile, codehandler: CodeHandler):
    if codehandler.hookaddress == None:
        assertCodeHook(dolfile, codehandler, GCNVIHOOK, WIIVIHOOK)
    else:
        insertCodeHook(dolfile, codehandler, codehandler.hookaddress)

def assertCodeHook(dolfile: dolreader.DolFile, codehandler: CodeHandler, gcnhook: bytes, wiihook: bytes):
    for offset, address, size in dolfile._text:
        dolfile.seek(address, 0)
        sample = dolfile.read(size)

        result = sample.find(gcnhook)
        if result >= 0:
            dolfile.seek(address, 0)
            dolfile.seek(result, 1)
        else:
            result = sample.find(wiihook)
            if result >= 0:
                dolfile.seek(address, 0)
                dolfile.seek(result, 1)
            else:
                continue

        sample = dolfile.read(4)
        while sample != b'\x4E\x80\x00\x20':
            sample = dolfile.read(4)

        dolfile.seek(-4, 1)
        codehandler.hookaddress = dolfile.tell()

        insertCodeHook(dolfile, codehandler, codehandler.hookaddress)
        return

    parser.error('Failed to find a hook address. Try using option --codehook to use your own address')

def insertCodeHook(dolfile: dolreader.DolFile, codehandler: CodeHandler, address: int):
    dolfile.seek(address)

    if dolfile.read(4) != b'\x4E\x80\x00\x20':
        parser.error("Codehandler hook given is not a blr")

    dolfile.seek(-4, 1)
    dolfile.insertBranch(codehandler.startaddress, address, lk=0)
    

def sortArgFiles(fileA, fileB):
    if os.path.splitext(fileA)[1].lower() == '.dol':
        dolFile = fileA
        gctFile = fileB
    elif os.path.splitext(fileB)[1].lower() == '.dol':
        dolFile = fileB
        gctFile = fileA
    else:
        parser.error('No dol file was passed\n')
    return dolFile, gctFile

if __name__ == "__main__":
    if not os.path.isdir('tmp'):
        os.mkdir('tmp')

    parser = argparse.ArgumentParser(prog='GeckoLoader',
                                     description='Process files and allocations for GeckoLoader',
                                     allow_abbrev=False)

    parser.add_argument('file', help='First file')
    parser.add_argument('file2', help='Second file')
    parser.add_argument('-a', '--alloc',
                        help='Define the size of the code allocation in hex, only applies when using the ARENA space',
                        metavar ='SIZE')
    parser.add_argument('-i', '--init',
                        help='Define where geckoloader is injected in hex',
                        metavar='ADDRESS')
    parser.add_argument('-m', '--movecodes',
                        help='''Choose if geckoloader moves the codes to OSArenaHi,
                        or the legacy space. Default is "AUTO",
                        which auto decides where to insert the codes''',
                        default='AUTO',
                        choices=['AUTO', 'LEGACY', 'ARENA'],
                        metavar='TYPE')
    parser.add_argument('-tc', '--txtcodes',
                        help='''What codes get parsed when a txt file is used.
                        "ALL" makes all codes get parsed,
                        "ACTIVE" makes only activated codes get parsed.''',
                        default='active',
                        metavar='TYPE')
    parser.add_argument('--handler',
                        help='''Which codehandler gets used. "MINI" uses a smaller codehandler
                        which only supports (0x, 2x, Cx, and E0 types) and supports up to
                        600 lines of gecko codes when using the legacy codespace.
                        "FULL" is the standard codehandler, supporting up to 350 lines of code
                        in the legacy codespace.
                        "MINI" should only be considered if using the legacy codespace''',
                        default='FULL',
                        choices=['MINI', 'FULL'],
                        metavar='TYPE')
    parser.add_argument('--codehook',
                        help='''Choose where the codehandler hooks to, needs to exist at a blr instruction''',
                        metavar='ADDRESS')
    parser.add_argument('-q', '--quiet',
                        help='Print nothing to the console',
                        action='store_true')
    parser.add_argument('-v', '--verbose',
                        help='Print extra info to the console',
                        default=0,
                        action='count')
    parser.add_argument('-o', '--optimize',
                        help='''Optimizes the codelist by directly patching qualifying
                        ram writes into the dol file, and removing them from the codelist''',
                        action='store_true')

    args = parser.parse_args()
         
    if args.alloc:
        try:
            _allocation = int(args.alloc.lstrip('0x'), 16)
        except:
            parser.error('The allocation was invalid\n')
    else:
        _allocation = None

    if args.codehook:
        if int(args.codehook, 16) < 0x80000000 or int(args.codehook, 16) >= 0x81800000:
            parser.error('The codehandler hook address was beyond bounds\n')
        else:
            try:
                _codehook = int(args.codehook.lstrip('0x'), 16)
            except:
                parser.error('The codehandler hook address was invalid\n')
    else:
        _codehook = None

    if args.handler:
        if args.handler == 'MINI':
            codehandlerFile = 'codehandler-mini.bin'
        else:
            codehandlerFile = 'codehandler.bin'
    else:
        codehandlerFile = 'codehandler.bin'

    dolFile, gctFile = sortArgFiles(args.file, args.file2)

    try:
        if not os.path.isdir('BUILD'):
            os.mkdir('BUILD')
            
        if not os.path.isfile(dolFile):
            parser.error('File "' + dolFile + '" does not exist')
            
        if not os.path.exists(gctFile):
            parser.error('File/folder "' + gctFile + '" does not exist')

        time1 = time.time()
            
        build(gctFile, dolFile, codehandlerFile, _allocation, _codehook)
        
        shutil.rmtree('tmp')
        if not args.quiet:
            print(TGREENLIT + '\n  :: Compiled in {:0.4f} seconds!\n'.format(time.time() - time1) + TRESET)

    except FileNotFoundError as err:
        parser.error(err)
        sys.exit(1)
