#Written by JoshuaMK 2020

import argparse
import os
import random
import shutil
import sys
from distutils.version import LooseVersion

from dolreader import DolFile
from kernel import CodeHandler, KernelLoader
from tools import CommandLineParser, color_text
from versioncheck import Updater

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

__version__ = 'v6.0.0'

def resource_path(relative_path: str):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = os.path.dirname(os.path.realpath(sys.argv[0]))
    return os.path.join(base_path, relative_path)
    
def sort_file_args(fileA, fileB):
    if os.path.splitext(fileA)[1].lower() == '.dol':
        dolFile = fileA
        gctFile = fileB
    elif os.path.splitext(fileB)[1].lower() == '.dol':
        dolFile = fileB
        gctFile = fileA
    else:
        parser.error(color_text('No dol file was passed\n', defaultColor=TREDLIT))
    return dolFile, gctFile

if __name__ == "__main__":
    parser = CommandLineParser(prog='GeckoLoader ' + __version__,
                               description='Process files and allocations for GeckoLoader',
                               allow_abbrev=False)

    parser.add_argument('dolfile', help='DOL file')
    parser.add_argument('codelist', help='Folder or Gecko GCT|TXT file')
    parser.add_argument('-a', '--alloc',
                        help='Define the size of the code allocation in hex, only applies when using the ARENA space',
                        metavar ='SIZE')
    parser.add_argument('-i', '--init',
                        help='Define where GeckoLoader is initialized in hex',
                        metavar='ADDRESS')
    parser.add_argument('-m', '--movecodes',
                        help='''["AUTO", "LEGACY", "ARENA"] Choose if GeckoLoader moves the codes to OSArenaHi,
                        or the legacy space. Default is "AUTO",
                        which auto decides where to insert the codes''',
                        default='AUTO',
                        choices=['AUTO', 'LEGACY', 'ARENA'],
                        metavar='TYPE')
    parser.add_argument('-tc', '--txtcodes',
                        help='''["ACTIVE", "ALL"] What codes get parsed when a txt file is used.
                        "ALL" makes all codes get parsed,
                        "ACTIVE" makes only activated codes get parsed.
                        "ACTIVE" is the default''',
                        default='ACTIVE',
                        metavar='TYPE')
    parser.add_argument('--handler',
                        help='''["MINI", "FULL"] Which codehandler gets used. "MINI" uses a smaller codehandler
                        which only supports (0x, 2x, Cx, and E0 types) and supports up to
                        600 lines of gecko codes when using the legacy codespace.
                        "FULL" is the standard codehandler, supporting up to 350 lines of code
                        in the legacy codespace. "FULL" is the default''',
                        default='FULL',
                        choices=['MINI', 'FULL'],
                        metavar='TYPE')
    parser.add_argument('--hooktype',
                        help='''["VI", "GX", "PAD"] The type of hook used for the RAM search. "VI" or "GX" are recommended,
                        although "PAD" can work just as well. "VI" is the default''',
                        default='VI',
                        choices=['VI', 'GX', 'PAD'],
                        metavar='HOOK')
    parser.add_argument('--hookaddress',
                        help='Choose where the codehandler hooks to in hex, overrides auto hooks',
                        metavar='ADDRESS')
    parser.add_argument('-o', '--optimize',
                        help='''Optimizes the codelist by directly patching qualifying
                        ram writes into the dol file, and removing them from the codelist''',
                        action='store_true')
    parser.add_argument('-p', '--protect',
                        help='''Targets and nullifies the standard codehandler provided by loaders and Dolphin Emulator,
                        only applies when the ARENA is used''',
                        action='store_true')
    parser.add_argument('--dest',
                        help='Target path to put the modified DOL, can be a folder or file',
                        metavar='PATH')
    parser.add_argument('--check-update',
                        help='''Checks to see if a new update exists on the GitHub Repository releases page,
                        this option overrides all other commands.''',
                        action='store_true')
    parser.add_argument('--encrypt',
                        help='Encrypts the codelist on compile time, helping to slow the snoopers',
                        action='store_true')
    parser.add_argument('-q', '--quiet',
                        help='Print nothing to the console',
                        action='store_true')
    parser.add_argument('-v', '--verbose',
                        help='Print extra info to the console',
                        default=0,
                        action='count')

    if len(sys.argv) == 1:
        version = __version__.rjust(9, ' ')
        helpMessage = 'Try option -h for more info on this program'.center(64, ' ')

        logo = ['                                                                ',
                ' ╔═══════════════════════════════════════════════════════════╗  ',
                ' ║                                                           ║  ',
                ' ║  ┌───┐┌───┐┌───┐┌┐┌─┐┌───┐┌┐   ┌───┐┌───┐┌───┐┌───┐┌───┐  ║  ',
                ' ║  │┌─┐││┌──┘│┌─┐││││┌┘│┌─┐│││   │┌─┐││┌─┐│└┐┌┐││┌──┘│┌─┐│  ║  ',
                ' ║  ││ └┘│└──┐││ └┘│└┘┘ ││ ││││   ││ ││││ ││ │││││└──┐│└─┘│  ║  ',
                ' ║  ││┌─┐│┌──┘││ ┌┐│┌┐│ ││ ││││ ┌┐││ │││└─┘│ │││││┌──┘│┌┐┌┘  ║  ',
                ' ║  │└┴─││└──┐│└─┘││││└┐│└─┘││└─┘││└─┘││┌─┐│┌┘└┘││└──┐│││└┐  ║  ',
                ' ║  └───┘└───┘└───┘└┘└─┘└───┘└───┘└───┘└┘ └┘└───┘└───┘└┘└─┘  ║  ',
                ' ║                                                           ║  ',
                ' ║           ┌┐┌───┐┌───┐┌┐ ┌┐┌┐ ┌┐┌───┐┌─┐┌─┐┌┐┌─┐          ║  ',
                ' ║           │││┌─┐││┌─┐│││ ││││ │││┌─┐││ └┘ ││││┌┘          ║  ',
                ' ║           ││││ │││└──┐│└─┘│││ ││││ │││┌┐┌┐││└┘┘           ║  ',
                ' ║     ┌──┐┌┐││││ ││└──┐││┌─┐│││ │││└─┘││││││││┌┐│ ┌──┐      ║  ',
                ' ║     └──┘│└┘││└─┘││└─┘│││ │││└─┘││┌─┐││││││││││└┐└──┘      ║  ',
                ' ║         └──┘└───┘└───┘└┘ └┘└───┘└┘ └┘└┘└┘└┘└┘└─┘          ║  ',
               f' ║                                                {version}  ║  ',
                ' ╚═══════════════════════════════════════════════════════════╝  ',
                '                                                                ',
                '        GeckoLoader is a cli tool for allowing extended         ',
                '           gecko code space in all Wii and GC games.            ',
                '                                                                ',
               f'{helpMessage}',
                '                                                                ']
        for line in logo:
            print(color_text(line, [('║', TREDLIT), ('╔╚╝╗═', TRED)], TGREENLIT))
        sys.exit(0)
    elif '--check-update' in sys.argv:
        repoChecker = Updater('JoshuaMKW', 'GeckoLoader')

        tag, status = repoChecker.get_newest_version()

        print('')
        
        if status is False:
            parser.error(color_text(tag + '\n', defaultColor=TREDLIT), print_usage=False)

        if LooseVersion(tag) > LooseVersion(__version__):
            print(color_text(f'  :: A new update is live at {repoChecker.gitReleases.format(repoChecker.owner, repoChecker.repo)}', defaultColor=TYELLOWLIT))
            print(color_text(f'  :: Current version is "{__version__}", Most recent version is "{tag}"', defaultColor=TYELLOWLIT))
        elif LooseVersion(tag) < LooseVersion(__version__):
            print(color_text('  :: No update available', defaultColor=TGREENLIT))
            print(color_text(f'  :: Current version is "{__version__}(dev)", Most recent version is "{tag}(release)"', defaultColor=TGREENLIT))
        else:
            print(color_text('  :: No update available', defaultColor=TGREENLIT))
            print(color_text(f'  :: Current version is "{__version__}(release)", Most recent version is "{tag}(release)"', defaultColor=TGREENLIT))
        
        print('')
        sys.exit(0)

    args = parser.parse_args()
         
    if args.alloc:
        try:
            _allocation = int(args.alloc, 16)
        except ValueError:
            parser.error(color_text('The allocation was invalid\n', defaultColor=TREDLIT))
    else:
        _allocation = None

    if args.hookaddress:
        if 0x80000000 > int(args.hookaddress, 16) >= 0x81800000:
            parser.error(color_text('The codehandler hook address was beyond bounds\n', defaultColor=TREDLIT))
        else:
            try:
                _codehook = int(args.hookaddress, 16)
            except ValueError:
                parser.error(color_text('The codehandler hook address was invalid\n', defaultColor=TREDLIT))
    else:
        _codehook = None

    if args.handler:
        if args.handler == 'MINI':
            codeHandlerFile = 'codehandler-mini.bin'
        else:
            codeHandlerFile = 'codehandler.bin'
    else:
        codeHandlerFile = 'codehandler.bin'

    try:
        if not os.path.isfile(args.dolfile):
            parser.error(color_text(f'File "{args.dolfile}" does not exist\n', defaultColor=TREDLIT))
            
        if not os.path.exists(args.codelist):
            parser.error(color_text(f'File/folder "{args.codelist}" does not exist\n', defaultColor=TREDLIT))

        tmpdir = ''.join(random.choice('1234567890-_abcdefghijklomnpqrstuvwxyz') for i in range(6)) + '-GeckoLoader'

        with open(resource_path(os.path.join('bin', os.path.normpath(codeHandlerFile))), 'rb') as handler:
            codeHandler = CodeHandler(handler)
            codeHandler.allocation = _allocation
            codeHandler.hookAddress = _codehook
            codeHandler.hookType = args.hooktype
            codeHandler.includeAll = (args.txtcodes.lower() == 'all')

        with open(resource_path(os.path.join('bin', 'geckoloader.bin')), 'rb') as kernelfile:
            geckoKernel = KernelLoader(kernelfile)

            if args.init is not None:
                geckoKernel.initAddress = int(args.init, 16)

            geckoKernel.codeLocation = args.movecodes
            geckoKernel.verbosity = args.verbose
            geckoKernel.quiet = args.quiet
            geckoKernel.encrypt = args.encrypt

        with open(os.path.normpath(args.dolfile), 'rb') as dol:
            dolFile = DolFile(dol)

        codeHandler.optimizeList = args.optimize
        geckoKernel.protect = args.protect

        if args.dest:
            if os.path.splitext(args.dest)[1] == "":
                dest = os.path.normpath(os.path.join(os.getcwd(), args.dest.lstrip('\\').lstrip('/'), os.path.basename(args.dolfile)))
            else:
                dest = os.path.normpath(os.path.join(os.getcwd(), args.dest.lstrip('\\').lstrip('/')))
        else:
            dest = os.path.normpath(os.path.join(os.getcwd(), "BUILD", os.path.basename(args.dolfile)))

        if not os.path.exists(dest) and os.path.dirname(dest) not in ('', '/'):
            os.makedirs(os.path.dirname(dest), exist_ok=True)

        if not os.path.exists(os.path.abspath(tmpdir)):
            os.mkdir(tmpdir)

        geckoKernel.build(parser, args.codelist, dolFile, codeHandler, tmpdir, dest)

        shutil.rmtree(tmpdir)
        sys.exit(0)

    except FileNotFoundError as e:
        parser.error(color_text(e + '\n', defaultColor=TREDLIT))
