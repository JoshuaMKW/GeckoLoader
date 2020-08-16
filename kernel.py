import sys
import re
from io import BytesIO
from dolreader import *
from access import *

try:
    import chardet
except ImportError as IE:
    print(IE)
    sys.exit(1)

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

class GCT(object):

    def __init__(self, f):
        self.codelist = BytesIO(f.read())
        self.rawlinecount = get_size(f) >> 3
        self.linecount = self.rawlinecount - 2
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

    def optimize_codelist(self, dolfile):
        codelist = b''
        skipcodes = 0
        while codetype := self.codelist.read(4):
            info = self.codelist.read(4)
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
                        padding = get_alignment(arraylength, 8)
                        
                        while arraylength > 0:
                            value = self.codelist.read(1)
                            dolfile.write(value)
                            arraylength -= 1

                        self.codelist.seek(padding, 1)
                        continue

                    elif (codetype.startswith(b'\x08') or codetype.startswith(b'\x09')
                        or codetype.startswith(b'\x18') or codetype.startswith(b'\x19')):
                        dolfile.seek(address)

                        value = int.from_bytes(info, byteorder='big', signed=False)
                        data = self.codelist.read(2).hex()
                        size = int(data[:-3], 16)
                        counter = int(data[1:], 16)
                        address_increment = int.from_bytes(self.codelist.read(2), byteorder='big', signed=False)
                        value_increment = int.from_bytes(self.codelist.read(4), byteorder='big', signed=False)

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

                self.codelist.seek(-8, 1)
                length = self.determine_codelength(codetype, info)
                while length > 0:
                    codelist += self.codelist.read(1)
                    length -= 1

            except RuntimeError:
                self.codelist.seek(-8, 1)
                length = self.determine_codelength(codetype, info)
                while length > 0:
                    codelist += self.codelist.read(1)
                    length -= 1

        self.codelist = BytesIO(codelist)
        self.size = get_size(self.codelist)

class CodeHandler(object):

    def _entryPoint__(self, f):
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
        self.geckocodes = None

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

    def fill_loader_data(self, tmp, entryPoint: list, lowerAddr: int):
        tmp.seek(0)
        if self.gpModDataList is None or self.gpDiscDataList is None:
            return
        
        while sample := tmp.read(2):
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

    def figure_loader_data(self, tmp, codehandler: CodeHandler, dolfile: DolFile, entrypoint: str, initpoint: list):
        upperAddr, lowerAddr = entrypoint[:int(len(entrypoint)/2)], entrypoint[int(len(entrypoint)/2):]
        tmp.seek(0)

        while sample := tmp.read(4):
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
                tmp.write(get_size(self).to_bytes(4, byteorder='big', signed=False))
                    
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

        self.gpModDataList = (gpModUpperAddr, gpModInfoOffset)
        self.gpDiscDataList = (gpDiscUpperAddr, gpDiscOffset)

        self.fill_loader_data(tmp, initpoint, int(lowerAddr, 16))
        
        tmp.seek(0, 2)
        codehandler.codehandler.seek(0)
        codehandler.geckocodes.codelist.seek(0)

        tmp.write(codehandler.codehandler.read() + codehandler.geckocodes.codelist.read())

    def patch_arena(self, codehandler: CodeHandler, tmp, dolfile: DolFile, entrypoint: str):
        tmp.write(self.read())
        geckoloader_offset = dolfile.get_size()
        self.figure_loader_data(tmp, codehandler, dolfile, entrypoint,
                                [((dolfile.entryPoint >> 16) & 0xFFFF).to_bytes(2, byteorder='big', signed=False),
                                    (dolfile.entryPoint & 0xFFFF).to_bytes(2, byteorder='big', signed=False)])
        tmp.seek(0)
        dolfile.rawData.seek(0, 2)
        dolfile.rawData.write(tmp.read())
        dolfile.align(256)

        status = dolfile.append_text_sections([(int(entrypoint, 16), geckoloader_offset)])

        if status is True:
            dolfile.set_entry_point(int(entrypoint, 16))

        return status

    def patch_legacy(self, codehandler: CodeHandler, tmp, dolfile: DolFile):
        handlerOffset = dolfile.getsize()

        dolfile.rawData.seek(0, 2)
        codehandler.codehandler.seek(0)
        codehandler.geckocodes.codelist.seek(0)
        
        dolfile.rawData.write(codehandler.codehandler.read() + codehandler.geckocodes.codelist.read())
        dolfile.align(256)

        status = dolfile.append_text_sections([(codehandler.initaddress, handlerOffset)])

        return status