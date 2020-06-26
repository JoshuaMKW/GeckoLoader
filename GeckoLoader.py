#Written by JoshuaMK 2020

import sys
import os
import time
import re
import shutil
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

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def getAlignment(number, align):
    if number % align != 0:
        return align - (number % align)
    else:
        return 0

def get_size(file, offset=0):
    """ Return a file's size in bytes """
    file.seek(0, 2)
    return(bytes.fromhex('{:08X}'.format(file.tell() + offset)))

def getFileAlignment(file, alignment):
    """ Return file alignment, 0 = aligned, non zero = misaligned """
    size = int.from_bytes(get_size(file), byteorder='big', signed=False)

    return getAlignment(size, alignment)

def alignFile(file, alignment):
    """ Align a file to be the specified size """
    file.write(bytes.fromhex("00" * getFileAlignment(file, alignment)))

class GCT(object):

    def __init__(self, f):
        self.codelist = BytesIO(f.read())
        self.rawlinecount = int.from_bytes(get_size(f), byteorder='big', signed=True) >> 3
        self.linecount = self.rawlinecount - 2
        self.size = int.from_bytes(get_size(f), byteorder='big', signed=True)
        f.seek(0)

class CodeHandler(object):

    def __init__(self, f, gctFile, isText):
        self.codehandler = BytesIO(f.read())

        '''Get codelist pointer'''
        f.seek(0xFA, 0)
        codelistUpper = f.read(2).hex()
        f.seek(0xFE, 0)
        codelistLower = f.read(2).hex()

        self.codelistpointer = int(codelistUpper[2:] + codelistLower[2:], 16)
        self.handlerlength = int.from_bytes(get_size(f), byteorder='big', signed=True)
        self.initaddress = 0x80001800
        self.startaddress = 0x800018A8

        if self.handlerlength < 0x900:
            self.type = "Mini"
        else:
            self.type = "Full"

        if isText == True:
            self.geckocodes = self.geckoParser(gctFile, args.txtcodes)
        else:
            with open(r'{}'.format(gctFile), 'rb') as gct:
                self.geckocodes = GCT(gct)

        f.seek(0)

    def geckoParser(self, geckoText, parseAll):
        geckoMagic = '00D0C0DE00D0C0DE'
        geckoTerminate = 'F000000000000000'
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
                
            with open(os.path.join('tmp', 'gct.bin'), 'wb+') as code:
                code.write(bytes.fromhex(geckoMagic + geckoCodes + geckoTerminate))
                code.seek(0)
                gct = GCT(code)

        return gct

def build(gctFile, dolFile, codehandlerFile, size):
    global isText, _allocation, _codehook
    with open(resource_path(os.path.join('bin', 'geckoloader.bin')), 'rb') as code, open(r'{}'.format(dolFile), 'rb') as dol, open(resource_path(os.path.join('bin', r'{}'.format(codehandlerFile))), 'rb') as handler, open(os.path.join('tmp', 'tmp.bin'), 'wb+') as tmp, open(os.path.join('BUILD', os.path.basename(dolFile)), 'wb+') as final:

        if int(get_size(dol).hex(), 16) < 0x100:
            shutil.rmtree('tmp')
            parser.error('DOL header is corrupted. Please provide a clean file')
        
        dol.seek(0)

        '''Initialize the new DOL file'''

        final.write(dol.read())
        final.seek(0)
        
        dolfile = dolreader.DolFile(final)

        '''Initialize our codehandler + codes'''

        codehandler = CodeHandler(handler, gctFile, isText)

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
            dump_address = '{:08X}'.format(dolfile.seekSafeAddress(int(dump_address, 16), int.from_bytes(get_size(code), byteorder='big', signed=False) + codehandler.handlerlength + codehandler.geckocodes.size))
            code.seek(0)

        '''Is insertion legacy?'''

        if args.movecodes == 'LEGACY':
            _allocation = '{:X}'.format(0x80003000 - (codehandler.initaddress + codehandler.handlerlength))
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
                _allocation = '{:X}'.format(0x80003000 - (codehandler.initaddress + codehandler.handlerlength))
                patchLegacyHandler(codehandler, tmp, dolfile)
                legacy = True

        dolfile.save(final)
        
        if int(_allocation, 16) < codehandler.geckocodes.size:
            print(TYELLOW + '\n  :: WARNING: Allocated codespace was smaller than the given codelist. The game will crash if run' + TRESET)

        if args.quiet:
            return

        if int(_allocation, 16) > int('70000', 16):
            print(TYELLOW + '\n  :: WARNING: Allocations beyond 0x70000 will crash certain games. You allocated 0x{}'.format(_allocation.upper().lstrip('0'))  + TRESET)
            
        elif int(_allocation, 16) > int('40000', 16):
            print(TYELLOWLIT + '\n  :: HINT: Recommended allocation limit is 0x40000. You allocated 0x{}'.format(_allocation.upper().lstrip('0'))  + TRESET)
        
        if args.verbose >= 2:
            print('')
            if legacy == False:
                info = [TGREENLIT + '  :: GeckoLoader set at address 0x{}, start of game modified to address 0x{}'.format(dump_address.upper().lstrip('0'), dump_address.upper().lstrip('0')),
                    '  :: Game function "__init_registers" located at address 0x{:X}'.format(dolfile._init),
                    '  :: Codehandler hooked at 0x{}'.format(_codehook.upper().lstrip('0')),
                    '  :: Code allocation is 0x{}; codelist size is 0x{:X}'.format(_allocation.upper().lstrip('0'), codehandler.geckocodes.size),
                    '  :: Codehandler is of type "{}"'.format(codehandler.type),
                    '  :: Of the 7 text sections in this DOL file, {} were already used'.format(len(dolfile._text)) + TRESET]
            else:
                info = [TGREENLIT + '  :: Game function "__init_registers" located at address 0x{:X}'.format(dolfile._init),
                        '  :: Codehandler hooked at 0x{}'.format(_codehook.upper().lstrip('0')),
                        '  :: Code allocation is 0x{}; codelist size is 0x{:X}'.format(_allocation.upper().lstrip('0'), codehandler.geckocodes.size),
                        '  :: Codehandler is of type "{}"'.format(codehandler.type),
                        '  :: Of the 7 text sections in this DOL file, {} were already used'.format(len(dolfile._text)) + TRESET]
            
            for bit in info:
                print(bit)
        
        elif args.verbose >= 1:
            print('')
            if legacy == False:
                info = [TGREENLIT + '  :: GeckoLoader set at address 0x{}'.format(dump_address.upper()),
                        '  :: Codehandler is of type "{}"'.format(args.handler),
                        '  :: Code allocation is 0x{} in hex; codelist size is 0x{:X}'.format(_allocation.upper().lstrip('0'), codehandler.geckocodes.size) + TRESET]
            else:
                info = [TGREENLIT + '  :: Codehandler is of type "{}"'.format(args.handler),
                        '  :: Code allocation is 0x{} in hex; codelist size is 0x{:X}'.format(_allocation.upper().lstrip('0'), codehandler.geckocodes.size) + TRESET]

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
                codelist += b'\xF0\x00\x00\x00'
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
    codehandler.geckocodes.size = int.from_bytes(get_size(codehandler.geckocodes.codelist), byteorder='big', signed=True)

def patchGeckoLoader(fLoader, codehandler, tmp, dolfile, entrypoint):
    tmp.write(fLoader.read())
    geckoloader_offset = dolfile.getsize()
    figureLoaderData(tmp, fLoader, codehandler, dolfile, entrypoint,
                     [bytes.fromhex('{:X}'.format(dolfile._init)[:4]), bytes.fromhex('{:X}'.format(dolfile._init)[4:])])
    tmp.seek(0)
    dolfile._rawdata.seek(0, 2)
    dolfile._rawdata.write(tmp.read())
    dolfile.align(256)

    assertTextSections(dolfile, 6, [[int(entrypoint, 16), geckoloader_offset]])

    '''Write game entry in DOL file header'''
    dolfile.setInitPoint(int(entrypoint, 16))

def patchLegacyHandler(codehandler, tmp, dolfile):
    handler_offset = dolfile.getsize()

    dolfile._rawdata.seek(0, 2)
    codehandler.codehandler.seek(0)
    codehandler.geckocodes.codelist.seek(0)
    
    dolfile._rawdata.write(codehandler.codehandler.read() + codehandler.geckocodes.codelist.read())
    dolfile.align(256)

    assertTextSections(dolfile, 6, [[0x80001800, handler_offset]])
    determineCodeHook(dolfile, codehandler)

def assertTextSections(dolfile, textsections, sections_list):
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

def figureLoaderData(tmp, fLoader, codehandler, dolfile, entrypoint, initpoint):
    global _allocation, _codehook

    upperAddr, lowerAddr = entrypoint[:int(len(entrypoint)/2)], entrypoint[int(len(entrypoint)/2):]
    
    tmp.seek(0)
    sample = tmp.read(4)
    while sample:
        if sample == HEAP: #Found keyword "HEAP". Goes with the resize of the heap
            tmp.seek(-4, 1)
            gpModInfoOffset = tmp.tell()
            if int(lowerAddr, 16) + gpModInfoOffset > 0x7FFF: #Absolute addressing
                gpModUpperAddr = bytes.fromhex('{:04X}'.format(int(upperAddr, 16) + 1))
            else:
                gpModUpperAddr = bytes.fromhex('{:04X}'.format(int(upperAddr, 16)))
            if _allocation == None:
                _allocation = '{:08X}'.format((codehandler.handlerlength + codehandler.geckocodes.size + 7) & 0xFFFFFFF8)
            tmp.write(bytes.fromhex(_allocation))
                
        elif sample == LOADERSIZE: #Found keyword "LSIZ". Goes with the size of the loader
            tmp.seek(-4, 1)
            tmp.write(get_size(fLoader))
                
        elif sample == HANDLERSIZE: #Found keyword "HSIZ". Goes with the size of the codehandler
            tmp.seek(-4, 1)
            tmp.write(codehandler.handlerlength.to_bytes(4, byteorder='big', signed=True))
        
        elif sample == CODESIZE: #Found keyword "CSIZ". Goes with the size of the codes
            tmp.seek(-4, 1)
            tmp.write(codehandler.geckocodes.size.to_bytes(4, byteorder='big', signed=True))
        
        elif sample == CODEHOOK:
            tmp.seek(-4, 1)
            if _codehook == None:
                tmp.write(b'\x00\x00\x00\x00')
            else:
                tmp.write(bytes.fromhex(_codehook))
        
        sample = tmp.read(4)
        
    gpDiscOffset = int.from_bytes(get_size(tmp, -4), byteorder="big", signed=False)

    if int(lowerAddr, 16) + gpDiscOffset > 0x7FFF: #Absolute addressing
        gpDiscUpperAddr = bytes.fromhex('{:04X}'.format(int(upperAddr, 16) + 1))
    else:
        gpDiscUpperAddr = bytes.fromhex('{:04X}'.format(int(upperAddr, 16)))

    fillLoaderData(tmp, initpoint, lowerAddr, [gpModUpperAddr, gpModInfoOffset], [gpDiscUpperAddr, gpDiscOffset])
    
    tmp.seek(0, 2)
    codehandler.codehandler.seek(0)
    codehandler.geckocodes.codelist.seek(0)

    tmp.write(codehandler.codehandler.read() + codehandler.geckocodes.codelist.read())

def fillLoaderData(tmp, _init, lowerAddr, gpModInfo, gpDiscInfo):
    tmp.seek(0)
    sample = tmp.read(2)
    while sample:
        if sample == DH:
            tmp.seek(-2, 1)
            tmp.write(gpDiscInfo[0])
        elif sample == DL:
            tmp.seek(-2, 1)
            tmp.write(bytes.fromhex('{:04X}'.format(int(lowerAddr, 16) + gpDiscInfo[1])))
        elif sample == GH:
            tmp.seek(-2, 1)
            tmp.write(gpModInfo[0])
        elif sample == GL:
            tmp.seek(-2, 1)
            tmp.write(bytes.fromhex('{:04X}'.format(int(lowerAddr, 16) + gpModInfo[1])))
        elif sample == IH:
            tmp.seek(-2, 1)
            tmp.write(_init[0])
        elif sample == IL:
            tmp.seek(-2, 1)
            tmp.write(_init[1])
        sample = tmp.read(2)

def sortArgFiles(fileA, fileB):
    global isText
    if os.path.splitext(fileA)[1].lower() == '.dol':
        dolFile = fileA
    elif os.path.splitext(fileB)[1].lower() == '.dol':
        dolFile = fileB
    else:
        parser.error('No dol file was passed\n')

    if os.path.splitext(fileA)[1].lower() == '.gct':
        gctFile = fileA
        isText = False
    elif os.path.splitext(fileA)[1].lower() == '.txt':
        gctFile = fileA
        isText = True
    elif os.path.splitext(fileB)[1].lower() == '.gct':
        gctFile = fileB
        isText = False
    elif os.path.splitext(fileB)[1].lower() == '.txt':
        gctFile = fileB
        isText = True
    else:
        parser.error('Neither a gct or gecko text file was passed\n')
    return dolFile, gctFile    

def determineCodeHook(dolfile, codehandler):
    global GCNVIHOOK, WIIVIHOOK, _codehook
    if _codehook == None:
        assertCodeHook(dolfile, codehandler, GCNVIHOOK, WIIVIHOOK)
    else:
        insertCodeHook(dolfile, codehandler, int(_codehook, 16))

def assertCodeHook(dolfile, codehandler, GCNVIHOOK, WIIVIHOOK):
    for offset, address, size in dolfile._text:
        dolfile.seek(address, 0)
        sample = dolfile.read(size)
        if sample.find(GCNVIHOOK) != -1 or sample.find(WIIVIHOOK):
            sample = dolfile.read(4)
            while sample != b'4E800020':
                sample = dolfile.read(4)
            dolfile.seek(-4, 1)
            insertCodeHook(dolfile, codehandler, dolfile.tell())

def insertCodeHook(dolfile, codehandler, address):
    dolfile.seek(address)

    if dolfile.read(4) != bytes.fromhex('4E800020'):
        parser.error("Codehandler hook given is not a blr")

    dolfile.seek(-4, 1)
    dolfile.insertBranch(codehandler.startaddress, address, lk=0)

if __name__ == "__main__":
    isText = False
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
            _allocation = '{:08X}'.format(int(args.alloc.lstrip('0x'), 16))
        except:
            parser.error('The allocation was invalid\n')
    else:
        _allocation = None

    if args.codehook:
        if int(args.codehook, 16) < 0x80000000 or int(args.codehook, 16) >= 0x81800000:
            parser.error('The codehandler hook address was beyond bounds\n')
        else:
            try:
                _codehook = '{:08X}'.format(int(args.codehook.lstrip('0x'), 16))
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


    WIIVIHOOK = b'7CE33B783887003438A7003838C7004C'
    GCNVIHOOK = b'7C030034388300205485083C7C7F2A14A00300007C7D2A1420A4003FB0030000'

    try:
        if not os.path.isdir('BUILD'):
            os.mkdir('BUILD')
            
        if not os.path.isfile(dolFile):
            parser.error(dolFile + ' Does not exist')
            
        if not os.path.isfile(gctFile):
            parser.error(gctFile + ' Does not exist')

        time1 = time.time()
            
        build(gctFile, dolFile, codehandlerFile, _allocation)
        
        shutil.rmtree('tmp')
        if not args.quiet:
            print(TGREENLIT + '\n  :: Compiled in {:0.4f} seconds!\n'.format(time.time() - time1) + TRESET)

    except FileNotFoundError as err:
        parser.error(err)
        sys.exit(1)
