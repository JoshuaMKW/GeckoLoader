#Written by JoshuaMK 2020

import sys
import os
import re
import time
import shutil
import random
import argparse

from kernel import *

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

def resource_path(relative_path: str):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def build(gctFile, dolFile, codehandlerFile, tmpdir, allocation: int, codehook: int):
    with open(resource_path(os.path.join('bin', 'geckoloader.bin')), 'rb') as kernel, open(r'{}'.format(dolFile), 'rb') as dol, open(resource_path(os.path.join('bin', r'{}'.format(codehandlerFile))), 'rb') as handler, open(os.path.join(tmpdir, 'tmp.bin'), 'wb+') as tmp, open(os.path.join('BUILD', os.path.basename(dolFile)), 'wb+') as final:

        if get_size(dol) < 0x100:
            shutil.rmtree(tmpdir)
            parser.error('DOL header is corrupted. Please provide a clean file')
        
        dol.seek(0)
        geckoKernel = KernelLoader(kernel)

        '''Initialize the new DOL file'''

        final.write(dol.read())
        final.seek(0)
        
        dolfile = DolFile(final)

        '''Initialize our codehandler + codes'''

        codehandler = CodeHandler(handler)
        codehandler.allocation = allocation
        codehandler.hookaddress = codehook

        if '.' in gctFile:
            if os.path.splitext(gctFile)[1].lower() == '.txt':
                with open(os.path.join(tmpdir, 'gct.bin'), 'wb+') as temp:
                    temp.write(bytes.fromhex('00D0C0DE'*2 + codehandler.geckoParser(gctFile, args.txtcodes) + 'F000000000000000'))
                    temp.seek(0)
                    codehandler.geckocodes = GCT(temp)    
            elif os.path.splitext(gctFile)[1].lower() == '.gct':
                with open(r'{}'.format(gctFile), 'rb') as gct:
                    codehandler.geckocodes = GCT(gct)
            else:
                parser.error('No valid gecko code file found')
        else:
            with open(os.path.join(tmpdir, 'gct.bin'), 'wb+') as temp:
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
                codehandler.geckocodes = GCT(temp)

        if args.optimize == True:
            codehandler.geckocodes.optimize_codelist(dolfile)

        '''Get entrypoint (or BSS midpoint) for insert'''

        if args.init:
            dump_address = args.init.lstrip("0x").upper()
            try:
                dolfile.resolve_address(int(dump_address, 16))
                print(TYELLOW + '\n  :: WARNING: Init address specified for GeckoLoader (0x{}) clobbers existing dol sections'.format(dump_address) + TRESET)
            except RuntimeError:
                pass
        else:
            dump_address = '{:08X}'.format(dolfile.bssOffset + (dolfile.bssSize >> 1))[:-2] + '00'
            dump_address = '{:08X}'.format(dolfile.seek_safe_address(int(dump_address, 16), get_size(geckoKernel.rawData) + codehandler.handlerlength + codehandler.geckocodes.size))
            geckoKernel.rawData.seek(0)

        '''Is insertion legacy?'''

        if codehandler.geckocodes.size <= 0x10:
            dolfile.save(final)
            if args.verbose >= 1:
                print(TGREENLIT + '\n  :: All codes have been successfully pre patched' + TRESET)
            return

        if args.movecodes == 'LEGACY':
            codehandler.allocation = 0x80003000 - (codehandler.initaddress + codehandler.handlerlength)
            status = geckoKernel.patch_legacy(codehandler, tmp, dolfile)
            if status is False:
                determine_codehook(dolfile, codehandler)
            legacy = True
        elif args.movecodes == 'ARENA':
            status = geckoKernel.patch_arena(codehandler, tmp, dolfile, dump_address)
            legacy = False
        else: #Auto decide area
            if codehandler.initaddress + codehandler.handlerlength + codehandler.geckocodes.size > 0x80002FFF:
                status = geckoKernel.patch_arena(codehandler, tmp, dolfile, dump_address)
                legacy = False
            else:
                codehandler.allocation = 0x80003000 - (codehandler.initaddress + codehandler.handlerlength)
                status = geckoKernel.patch_legacy(codehandler, tmp, dolfile)
                if status is False:
                    determine_codehook(dolfile, codehandler)
                legacy = True

        if status is False:
            shutil.rmtree(tmpdir)
            parser.error(TREDLIT + 'Not enough text sections to patch the DOL file! Potentially due to previous mods?\n' + TRESET)

        dolfile.save(final)
        
        if codehandler.allocation < codehandler.geckocodes.size:
            print(TYELLOW + '\n  :: WARNING: Allocated codespace was smaller than the given codelist. The game will crash if run' + TRESET)

        if args.quiet:
            return

        if codehandler.allocation > 0x70000:
            print(TYELLOW + f'\n  :: WARNING: Allocations beyond 0x70000 will crash certain games. You allocated 0x{codehandler.allocation:X}' + TRESET)
            
        elif codehandler.allocation > 0x40000:
            print(TYELLOWLIT + f'\n  :: HINT: Recommended allocation limit is 0x40000. You allocated 0x{codehandler.allocation:X}' + TRESET)
        
        if args.verbose >= 2:
            print('')
            if legacy == False:
                info = [TGREENLIT + f'  :: GeckoLoader set at address 0x{dump_address.upper()}, start of game modified to address 0x{dump_address.upper()}',
                                    f'  :: Game function "_entryPoint_registers" located at address 0x{dolfile.entryPoint:X}'.format(),
                                    f'  :: Code allocation is 0x{codehandler.allocation:X}; codelist size is 0x{codehandler.geckocodes.size:X}',
                                    f'  :: Codehandler is of type "{codehandler.type}"'
                                    f'  :: Of the 7 text sections in this DOL file, {len(dolfile.textSections)} were already used' + TRESET]
                if codehandler.hookaddress is not None:
                    info.insert(2, f'  :: Codehandler hooked at 0x{codehandler.hookaddress:08X}')
            
            else:
                info = [TGREENLIT + f'  :: Game function "_entryPoint_registers" located at address 0x{dolfile.entryPoint:X}',
                                    f'  :: Code allocation is 0x{codehandler.allocation:X}; codelist size is 0x{codehandler.geckocodes.size:X}',
                                    f'  :: Codehandler is of type "{codehandler.type}"',
                                    f'  :: Of the 7 text sections in this DOL file, {len(dolfile.textSections)} were already used' + TRESET]
                if codehandler.hookaddress is not None:
                    info.insert(1, f'  :: Codehandler hooked at 0x{codehandler.hookaddress:08X}')
            for bit in info:
                print(bit)
        
        elif args.verbose >= 1:
            print('')
            if legacy == False:
                info = [TGREENLIT + f'  :: GeckoLoader set at address 0x{dump_address.upper()}',
                                    f'  :: Codehandler is of type "{args.handler}"',
                                    f'  :: Code allocation is 0x{codehandler.allocation} in hex; codelist size is 0x{codehandler.geckocodes.size:X}' + TRESET]
            else:
                info = [TGREENLIT + f'  :: Codehandler is of type "{args.handler}"',
                                    f'  :: Code allocation is 0x{codehandler.allocation} in hex; codelist size is 0x{codehandler.geckocodes.size:X}' + TRESET]

            for bit in info:
                print(bit) 

def determine_codehook(dolfile: DolFile, codehandler: CodeHandler):
    if codehandler.hookaddress == None:
        assert_code_hook(dolfile, codehandler, GCNVIHOOK, WIIVIHOOK)
    else:
        insert_code_hook(dolfile, codehandler, codehandler.hookaddress)

def assert_code_hook(dolfile: DolFile, codehandler: CodeHandler, gcnhook: bytes, wiihook: bytes):
    for offset, address, size in dolfile.textSections:
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

        insert_code_hook(dolfile, codehandler, codehandler.hookaddress)
        return

    parser.error('Failed to find a hook address. Try using option --codehook to use your own address')

def insert_code_hook(dolfile: DolFile, codehandler: CodeHandler, address: int):
    dolfile.seek(address)

    if dolfile.read(4) != b'\x4E\x80\x00\x20':
        parser.error("Codehandler hook given is not a blr")

    dolfile.seek(-4, 1)
    dolfile.insert_branch(codehandler.startaddress, address, lk=0)
    

def sort_file_args(fileA, fileB):
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

    dolFile, gctFile = sort_file_args(args.file, args.file2)

    try:
        if not os.path.isdir('BUILD'):
            os.mkdir('BUILD')
            
        if not os.path.isfile(dolFile):
            parser.error('File "' + dolFile + '" does not exist')
            
        if not os.path.exists(gctFile):
            parser.error('File/folder "' + gctFile + '" does not exist')

        time1 = time.time()

        tmpdir = ''.join(random.choice('1234567890-_abcdefghijklomnpqrstuvwxyz') for i in range(6)) + '-GeckoLoader'

        if not os.path.isdir(tmpdir):
            os.mkdir(tmpdir)
            
        build(gctFile, dolFile, codehandlerFile, tmpdir, _allocation, _codehook)
        
        shutil.rmtree(tmpdir)
        if not args.quiet:
            print(TGREENLIT + f'\n  :: Compiled in {(time.time() - time1):0.4f} seconds!\n' + TRESET)

    except FileNotFoundError as err:
        parser.error(err)
        sys.exit(1)
