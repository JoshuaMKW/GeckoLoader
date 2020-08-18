#Written by JoshuaMK 2020
#Start.dol EclipseCodes -m ARENA --codehook 802A80D0 -o -vv

import sys
import os
import re
import shutil
import random
import argparse

from kernel import *
from access import *

_VERSION_ = "v5.0.0"

def determine_codehook(dolFile: DolFile, codehandler: CodeHandler):
    if codehandler.hookAddress == None:
        assert_code_hook(dolFile, codehandler, GCNVIHOOK, WIIVIHOOK)
    else:
        insert_code_hook(dolFile, codehandler, codehandler.hookAddress)

def assert_code_hook(dolFile: DolFile, codehandler: CodeHandler, gcnhook: bytes, wiihook: bytes):
    for offset, address, size in dolFile.textSections:
        dolFile.seek(address, 0)
        sample = dolFile.read(size)

        result = sample.find(gcnhook)
        if result >= 0:
            dolFile.seek(address, 0)
            dolFile.seek(result, 1)
        else:
            result = sample.find(wiihook)
            if result >= 0:
                dolFile.seek(address, 0)
                dolFile.seek(result, 1)
            else:
                continue

        sample = dolFile.read(4)
        while sample != b'\x4E\x80\x00\x20':
            sample = dolFile.read(4)

        dolFile.seek(-4, 1)
        codehandler.hookAddress = dolFile.tell()

        insert_code_hook(dolFile, codehandler, codehandler.hookAddress)
        return

    parser.error('Failed to find a hook address. Try using option --codehook to use your own address')

def insert_code_hook(dolFile: DolFile, codehandler: CodeHandler, address: int):
    dolFile.seek(address)

    if dolFile.read(4) != b'\x4E\x80\x00\x20':
        parser.error("Codehandler hook given is not a blr")

    dolFile.seek(-4, 1)
    dolFile.insert_branch(codehandler.startAddress, address, lk=0)
    
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
    parser = argparse.ArgumentParser(prog='GeckoLoader ' + _VERSION_,
                                     description='Process files and allocations for GeckoLoader',
                                     allow_abbrev=False)

    parser.add_argument('dolFile', help='DOL file')
    parser.add_argument('codelist', help='Folder or Gecko GCT|TXT file')
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
    parser.add_argument('-p', '--protect',
                        help='''Targets and nullifies the standard codehandler provided by loaders and Dolphin Emulator,
                        only applies when the ARENA is used (Can be forced using option (-m|--movecodes))''',
                        action='store_true')
    parser.add_argument('--dest',
                        help='Target path to put the modified DOL, can be a folder or file',
                        metavar='PATH')

    if len(sys.argv) == 1:
        version = _VERSION_.rjust(9, ' ')
        logo = ['                                                                ',
                '       ╔═════════════════════════════════════════════════╗      ',
                '       ║                                                 ║      ',
                '       ║  ┌───┬───┬───┬┐┌─┬───┬┐  ┌───┬───┬───┬───┬───┐  ║      ',
                '       ║  │┌─┐│┌──┤┌─┐│││┌┤┌─┐││  │┌─┐│┌─┐├┐┌┐│┌──┤┌─┐│  ║      ',
                '       ║  ││ └┤└──┤│ └┤└┘┘││ │││  ││ │││ ││││││└──┤└─┘│  ║      ',
                '       ║  ││┌─┤┌──┤│ ┌┤┌┐│││ │││ ┌┤│ ││└─┘│││││┌──┤┌┐┌┘  ║      ',
                '       ║  │└┴─│└──┤└─┘│││└┤└─┘│└─┘│└─┘│┌─┐├┘└┘│└──┤││└┐  ║      ',
                '       ║  └───┴───┴───┴┘└─┴───┴───┴───┴┘ └┴───┴───┴┘└─┘  ║      ',
                '       ║                                                 ║      ',
                '       ║          ┌┬───┬───┬┐ ┌┬┐ ┌┬───┬─┐┌─┬┐┌─┐        ║      ',
                '       ║          ││┌─┐│┌─┐││ │││ ││┌─┐│ └┘ │││┌┘        ║      ',
                '       ║          │││ ││└──┤└─┘││ │││ ││┌┐┌┐│└┘┘         ║      ',
                '       ║    ┌──┐┌┐│││ │├──┐│┌─┐││ ││└─┘││││││┌┐│ ┌──┐    ║      ',
                '       ║    └──┘│└┘│└─┘│└─┘││ ││└─┘│┌─┐││││││││└┐└──┘    ║      ',
                '       ║        └──┴───┴───┴┘ └┴───┴┘ └┴┘└┘└┴┘└─┘        ║      ',
               f'       ║                                     {version}   ║      ',
                '       ╚═════════════════════════════════════════════════╝      ',
                '                                                                ']
        for line in logo:
            print(line)
        sys.exit(0)

    args = parser.parse_args()
         
    if args.alloc:
        try:
            _allocation = int(args.alloc, 16)
        except ValueError:
            parser.error('The allocation was invalid\n')
    else:
        _allocation = None

    if args.codehook:
        if 0x80000000 > int(args.codehook, 16) >= 0x81800000:
            parser.error('The codehandler hook address was beyond bounds\n')
        else:
            try:
                _codehook = int(args.codehook, 16)
            except ValueError:
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

    #dolFile, gctFile = sort_file_args(args.fileA, args.fileB)

    try:
        if not os.path.isdir('BUILD'):
            os.mkdir('BUILD')
            
        if not os.path.isfile(args.dolFile):
            parser.error('File "' + dolFile + '" does not exist')
            
        if not os.path.exists(args.codelist):
            parser.error('File/folder "' + gctFile + '" does not exist')

        tmpdir = ''.join(random.choice('1234567890-_abcdefghijklomnpqrstuvwxyz') for i in range(6)) + '-GeckoLoader'

        if not os.path.isdir(tmpdir):
            os.mkdir(tmpdir)

        with open(resource_path(os.path.join('bin', os.path.normpath(codehandlerFile))), 'rb') as handler:
            codehandler = CodeHandler(handler)
            codehandler.allocation = _allocation
            codehandler.hookAddress = _codehook
            codehandler.includeAll = args.txtcodes

        with open(resource_path(os.path.join('bin', 'geckoloader.bin')), 'rb') as kernelfile:
            geckoKernel = KernelLoader(kernelfile)

            if (args.init is not None):
                geckoKernel.initAddress = args.init.lstrip("0x").upper()

            geckoKernel.codeLocation = args.movecodes
            geckoKernel.verbosity = args.verbose
            geckoKernel.quiet = args.quiet

        with open(os.path.normpath(args.dolFile), 'rb') as dol:
            dolFile = DolFile(dol)

        codehandler.optimizeList = args.optimize
        geckoKernel.protect = args.protect

        if args.dest:
            if os.path.splitext(args.dest)[1] == "":
                dest = os.path.normpath(os.path.join(os.getcwd(), args.dest.lstrip('\\').lstrip('/'), os.path.basename(args.dolFile)))
            else:
                dest = os.path.normpath(os.path.join(os.getcwd(), args.dest.lstrip('\\').lstrip('/')))
        else:
            dest = os.path.normpath(os.path.join(os.getcwd(), "BUILD", os.path.basename(args.dolFile)))

        if not os.path.exists(dest) and os.path.dirname(dest) not in ('', '/'):
            os.makedirs(os.path.dirname(dest), exist_ok=True)

        geckoKernel.build(args.codelist, dolFile, codehandler, tmpdir, dest)
        
        shutil.rmtree(tmpdir)
        sys.exit(0)

    except FileNotFoundError as err:
        parser.error(err)
        sys.exit(1)
