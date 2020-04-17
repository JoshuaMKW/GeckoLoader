#Written by JoshuaMK 2020

import sys
import os
import time
import re

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

def geckoParser(geckoText, parseAll):

    geckoMagic = '00D0C0DE00D0C0DE'
    geckoTerminate = 'F000000000000000'
    with open(geckoText, 'rb') as gecko:
        result = chardet.detect(gecko.read())
        encodeType = result['encoding']

    with open(geckoText, 'r', encoding=encodeType) as gecko:
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
            
        geckoCodes = geckoMagic + geckoCodes + geckoTerminate
        geckoSize = '{:08X}'.format(len(bytes.fromhex(geckoCodes))).lstrip('0')

    return [bytes.fromhex(geckoCodes), geckoSize]

def build(gctFile, dolFile, size, isText):
    with open(resource_path('sme-code.bin'), 'rb') as code, open(r'{}'.format(dolFile), 'rb') as dol, open(r'{}'.format(gctFile), 'rb') as gecko, open(resource_path('codehandler.bin'), 'rb') as handler, open('tmp.bin', 'wb+') as tmp, open(os.path.join('BUILD', os.path.basename(dolFile)), 'wb+') as final:

        if int(get_size(dol).hex(), 16) < int('0x100', 16):
            os.remove('tmp.bin')
            parser.error('DOL header is corrupted. Please provide a clean file')

        dol.seek(0)

        '''Initialize the new DOL file'''

        final.write(dol.read())

        '''Initialize the sme-code loader'''
        
        tmp.write(code.read())
        code.seek(0, 0)
        tmp.seek(0, 0)

        '''Search for main entry of loader'''

        entryIndex = 0
        sample = tmp.read(4)
        while sample:
            if sample == ENTRY:
                tmp.seek(-4, 1)
                tmp.write(bytes.fromhex('7C0802A6'))
                break
            entryIndex += 4
            sample = tmp.read(4)
        tmp.seek(0)

        '''Get BSS section for insert'''
        
        final.seek(int('D8', 16))
        BSS = int(final.read(4).hex(), 16)
        BSS_length = int(final.read(4).hex(), 16)
        dump_address = '{:08X}'.format(int(BSS + (BSS_length / 2)))[:-2] + '00'
        _START = bytes.fromhex('{:08X}'.format(int(dump_address, 16) + entryIndex))
        cLoader = bytes.fromhex(dump_address)

        '''Get address split for later'''

        upperAddr, lowerAddr = dump_address[:int(len(dump_address)/2)], dump_address[int(len(dump_address)/2):]

        '''Get code initialize address'''
        
        final.seek(int('E0', 16))
        _init = [final.read(2), final.read(2)]

        '''Patch the values for the addresses and such'''
        
        heaped = False
        sized = False
        fsized = False

        gUpperAddr = bytes.fromhex(upperAddr)

        if isText == True:
            geckoCheats = geckoParser(gctFile, args.txtcodes)
        
        while heaped == False or sized == False or fsized == False:
            try:
                sample = tmp.read(4)
                if sample == HEAP: #Found keyword "HEAP". Goes with the resize of the heap
                    if not heaped:
                        tmp.seek(-4, 1)
                        gInfo = tmp.tell()
                        if int(lowerAddr, 16) + gInfo > int('7FFF', 16): #Absolute addressing
                            gUpperAddr = bytes.fromhex('{:04X}'.format(int(upperAddr, 16) + 1))
                        if size == '0' or size == '':
                            if isText == False:
                                size = get_size(gecko).hex().upper()
                            else:
                                size = geckoCheats[1]
                        else:
                            tmp.write(bytes.fromhex('{:08X}'.format(int(size, 16))))
                        heaped = True
                        
                elif sample == LOADERSIZE: #Found keyword "LSIZ". Goes with the size of the loader
                    if not sized:
                        tmp.seek(-4, 1)
                        tmp.write(get_size(code))
                        sized = True
                        
                elif sample == FULLSIZE: #Found keyword "FSIZ". Goes with the size of the loader + codes
                    if not fsized:
                        tmp.seek(-4, 1)
                        code.seek(0, 2)
                        gecko.seek(0, 2)
                        tmp.write(get_size(code, gecko.tell()))
                        fsized = True
            except TypeError as err:
                parser.error(err)
                sys.exit(1)

        '''Patch all load/store offsets to data'''

        tmp.seek(0)
        sample = tmp.read(2)
        while sample:
            if sample == GH:
                tmp.seek(-2, 1)
                tmp.write(gUpperAddr)
            elif sample == GL:
                tmp.seek(-2, 1)
                tmp.write(bytes.fromhex('{:04X}'.format(int(lowerAddr, 16) + gInfo)))
            elif sample == IH:
                tmp.seek(-2, 1)
                tmp.write(_init[0])
            elif sample == IL:
                tmp.seek(-2, 1)
                tmp.write(_init[1])
            sample = tmp.read(2)
                
        tmp.seek(0)
        gecko.seek(0)
        
        dol_handler_offset = get_size(final)
        final.write(handler.read())
        time.sleep(0.01)
        dol_sme_offset = get_size(final)
        
        final.write(tmp.read())
        time.sleep(0.01)

        if isText == False:
            final.write(gecko.read())
        else:
            final.write(geckoCheats[0])
        final.seek(0, 0)
        
        status = False
        i = 0
        
        while i < 6:
            textOffset = int(final.read(4).hex(), 16)
            if textOffset == 0:
                status = True
                offset = i * 4

                '''Write offset to each section in DOL file header'''
                final.seek(-4, 1)
                final.write(dol_handler_offset)
                final.write(dol_sme_offset)
                
                final.seek(int('48', 16) + offset)

                '''Write in game memory addresses for each section in DOL file header'''
                final.write(bytes.fromhex('80001800'))
                final.write(cLoader)
                final.seek(int('E0', 16))

                '''Write game entry in DOL file header'''
                final.write(_START)

                '''Get size of GeckoLoader + gecko codes, and the codehandler'''
                handler_size = get_size(handler)

                tmp.seek(0, 2)
                gecko.seek(0, 2)

                if isText == True:
                    sme_code_size = get_size(tmp, int(geckoCheats[1], 16))
                else:
                    sme_code_size = get_size(tmp, gecko.tell())

                '''Write size of each section into DOL file header'''
                final.seek(int('90', 16) + offset)
                final.write(handler_size)
                final.write(sme_code_size)
                break
            else:
                i += 1

        if status == False:
            os.remove('tmp.bin')
            parser.error(TREDLIT + 'Not enough text sections to patch the DOL file! Potentially due to previous mods?\n' + TRESET)
        
        if isText == False:
            if int(size, 16) < int(get_size(gecko).hex(), 16):
                print(TYELLOW + '\n  :: WARNING: Allocated codespace was smaller than the given codelist. The game will crash if run' + TRESET)
        else:
            if int(size, 16) < int(geckoCheats[1], 16):
                print(TYELLOW + '\n  :: WARNING: Allocated codespace was smaller than the given codelist. The game will crash if run' + TRESET)

        if args.quiet:
            return

        if int(size, 16) > int('70000', 16):
            print(TYELLOW + '\n  :: WARNING: Allocations beyond 70000 will crash certain games. You allocated 0x{}'.format(size)  + TRESET)
            
        elif int(size, 16) > int('40000', 16):
            print(TYELLOWLIT + '\n  :: HINT: Recommended allocation limit is 0x40000. You allocated 0x{}'.format(size)  + TRESET)

        if isText == False:
            codelistSize = get_size(gecko).hex().upper().lstrip('0')
        else:
            codelistSize = geckoCheats[1]
        
        if args.verbose >= 2:
            print('')
            info = [TGREENLIT + '  :: GeckoLoader set at address 0x{}, start of game modified to address 0x{}'.format(dump_address.upper(), _START.hex().upper()),
                    '  :: Game function "_init_registers" located at address 0x{}{}'.format(_init[0].hex(), _init[1].hex().upper()),
                    '  :: Code allocation is 0x{}; codelist size is 0x{}'.format(size.upper().lstrip('0'), codelistSize),
                    '  :: Of the 6 text sections in this DOL file, {} were already used'.format(i)  + TRESET]
            
            for bit in info:
                print(bit)
        
        elif args.verbose >= 1:
            print('')
            info = [TGREENLIT + '  :: GeckoLoader set at address 0x{}'.format(dump_address.upper()),
                    '  :: Code allocation is 0x{} in hex; codelist size is 0x{}'.format(size.upper().lstrip('0'), codelistSize) + TRESET]

            for bit in info:
                print(bit)
        return

def get_size(file, offset=0):
    """ Return a file's size in bytes """
    file.seek(0, 2)
    return(bytes.fromhex('{:08X}'.format(file.tell() + offset)))
    

if __name__ == "__main__":

    isText = False

    parser = argparse.ArgumentParser(description='Process files and allocations for GeckoLoader')
    parser.add_argument('file', help='First file')
    parser.add_argument('file2', help='Second file')
    parser.add_argument('--alloc', help='Define the size of the code allocation: --alloc hex')
    parser.add_argument('-tc', '--txtcodes', help='What codes get parsed when a txt file is used.\n"ALL" makes all codes get parsed,\n"ACTIVE" makes only activated codes get parsed.', default='active')
    parser.add_argument('-q', '--quiet', help='Print nothing to the console', action='store_true')
    parser.add_argument('-v', '--verbose', help='Print extra info to the console', default=0, action='count')

    args = parser.parse_args()
         
    if args.alloc:
        size = args.alloc.lstrip('0x')
        try:
            int(size, 16)
        except:
            parser.error('The allocation was invalid\n')
    else:
        size = '0'

    if os.path.splitext(args.file)[1].lower() == '.dol':
        dolFile = args.file
    elif os.path.splitext(args.file2)[1].lower() == '.dol':
        dolFile = args.file2
    else:
        parser.error('No dol file was passed\n')

    if os.path.splitext(args.file)[1].lower() == '.gct':
        gctFile = args.file
        isText = False
    elif os.path.splitext(args.file)[1].lower() == '.txt':
        gctFile = args.file
        isText = True
    elif os.path.splitext(args.file2)[1].lower() == '.gct':
        gctFile = args.file2
        isText = False
    elif os.path.splitext(args.file2)[1].lower() == '.txt':
        gctFile = args.file2
        isText = True
    else:
        parser.error('Neither a gct or gecko text file was passed\n')
    
    time1 = time.time()

    HEAP = bytes.fromhex('48454150')
    LOADERSIZE = bytes.fromhex('4C53495A')
    FULLSIZE = bytes.fromhex('4653495A')
    HOOK = bytes.fromhex('484F4F4B')
    ENTRY = bytes.fromhex('454E5452')
    GH = bytes.fromhex('4748')
    GL = bytes.fromhex('474C')
    CH = bytes.fromhex('4348')
    CL = bytes.fromhex('434C')
    IH = bytes.fromhex('4948')
    IL = bytes.fromhex('494C')
    JH = bytes.fromhex('4A48')
    JL = bytes.fromhex('4A4C')

    try:
        if not os.path.isdir('BUILD'):
            os.mkdir('BUILD')
            
        if not os.path.isfile(dolFile):
            parser.error(dolFile + ' Does not exist')
            
        if not os.path.isfile(gctFile):
            parser.error(gctFile + ' Does not exist')
            
        build(gctFile, dolFile, size, isText)
        
        os.remove('tmp.bin')
        if not args.quiet:
            print('\n  :: Compiled in {:0.4f} seconds!\n'.format(time.time() - time1))

    except FileNotFoundError as err:
        parser.error(err)
        sys.exit(1)
