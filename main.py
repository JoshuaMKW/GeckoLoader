#Written by JoshuaMK 2020

import sys, os, time

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def build(gct, dol, size):
    with open(resource_path('sme-code.bin'), 'rb') as code, open(dol, 'rb+') as dol, open(gct, 'rb') as gecko, open(resource_path('codehandler.bin'), 'rb') as handler, open('tmp.bin', 'wb+') as tmp, open(os.path.join('BUILD', os.path.split(r'{}'.format(dol))[1][:-2]), 'wb+') as final:
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
        _init = final.read(4)

        '''Patch the values for the addresses and such'''
        
        hooked = False
        heaped = False
        sized = False
        fsized = False

        initUpperAddr = bytes.fromhex(upperAddr)
        geckoUpperAddr = bytes.fromhex(upperAddr)
        gUpperAddr = bytes.fromhex(upperAddr)
        
        while hooked == False or heaped == False or sized == False or fsized == False:
            try:
                sample = tmp.read(4)
                if sample == HOOK: #Found keyword "HOOK". Goes with the entry to the game
                    if not hooked:
                        tmp.seek(-4, 1)

                        initInfo = tmp.tell()
                        if int(lowerAddr, 16) + initInfo > int('7FFF', 16): #Absolute addressing
                            initUpperAddr = bytes.fromhex('{:04X}'.format(int(upperAddr, 16) + 1))
                        if int(lowerAddr, 16) + (initInfo + 4) > int('7FFF', 16): #Absolute addressing
                            geckoUpperAddr = bytes.fromhex('{:04X}'.format(int(upperAddr, 16) + 1))
                        
                        tmp.write(_init)
                        hooked = True
                elif sample == HEAP: #Found keyword "HEAP". Goes with the resize of the heap
                    if not heaped:
                        tmp.seek(-4, 1)
                        
                        gInfo = tmp.tell()
                        if int(lowerAddr, 16) + gInfo > int('7FFF', 16): #Absolute addressing
                            gUpperAddr = bytes.fromhex('{:04X}'.format(int(upperAddr, 16) + 1))
                            
                        if size == '0' or size == '':
                            tmp.write(get_size(gecko))
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
                print('Fatal error (' + err + '), build failed to complete')
                time.sleep(3)
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
            elif sample == CH:
                tmp.seek(-2, 1)
                tmp.write(geckoUpperAddr)
            elif sample == CL:
                tmp.seek(-2, 1)
                tmp.write(bytes.fromhex('{:04X}'.format(int(lowerAddr, 16) + (initInfo + 4))))
            elif sample == IH:
                tmp.seek(-2, 1)
                tmp.write(initUpperAddr)
            elif sample == IL:
                tmp.seek(-2, 1)
                tmp.write(bytes.fromhex('{:04X}'.format(int(lowerAddr, 16) + initInfo)))
            elif sample == JH:
                tmp.seek(-2, 1)
                tmp.write(geckoUpperAddr)
            elif sample == JL:
                tmp.seek(-2, 1)
                tmp.write(bytes.fromhex('{:04X}'.format(int(lowerAddr, 16) + (initInfo + 8))))
            sample = tmp.read(2)
                
        tmp.seek(0)
        gecko.seek(0)
        dol_handler_offset = get_size(final)
        final.write(handler.read())
        time.sleep(0.01)
        dol_sme_offset = get_size(final)
        final.write(tmp.read())
        time.sleep(0.01)
        final.write(gecko.read())
        final.seek(0, 0)
        status = False
        i = 0
        while i < 6:
            size = int(final.read(4).hex(), 16)
            if size == 0:
                status = True
                offset = i * 4
                final.seek(-4, 1)
                final.write(dol_handler_offset)
                final.write(dol_sme_offset)
                
                final.seek(int('48', 16) + offset)
                final.write(bytes.fromhex('80001800'))
                final.write(cLoader)
                final.seek(int('E0', 16))
                final.write(_START)
                handler_size = get_size(handler)
                tmp.seek(0, 2)
                gecko.seek(0, 2)
                sme_code_size = get_size(tmp, gecko.tell())
                final.seek(int('90', 16) + offset)
                final.write(handler_size)
                final.write(sme_code_size)
                break
            else:
                i += 1
        if status == False:
            print('Not enough sections to patch the DOL file! Potentially due to previous mods?')

def get_size(file, offset=0):
    """ Return a file's size in bytes """
    file.seek(0, 2)
    return(bytes.fromhex('{:08X}'.format(file.tell() + offset)))
    

if __name__ == "__main__":
    if len(sys.argv) == 1:
        while True:
            gct = input('Name of the input GCT file? ')
            if os.path.splitext(gct)[1] == '':
                gct = gct + '.gct'
            if os.path.splitext(gct)[1] != '.gct' and os.path.splitext(gct)[1] != '.GCT':
                print('Invalid input!')
                continue
            if os.path.exists(gct):
                gct = os.path.abspath(gct)
                break
            else:
                print('File not found! Please try again.')
        while True:
            dol = input('Name of the input dol file? ')
            if os.path.splitext(dol)[1] == '':
                dol = dol + '.dol'
            if os.path.splitext(dol)[1] != '.dol':
                print('Invalid input!')
                continue
            if os.path.exists(dol):
                dol = os.path.abspath(dol)
                break
            else:
                print('File not found! Please try again.')
    elif len(sys.argv) == 2:
        if sys.argv[1].endswith('.gct') or sys.argv[1].endswith('.GCT'):
            gct = sys.argv[1]
            while True:
                dol = input('Name of the input dol file? ')
                if os.path.splitext(dol)[1] == '':
                    dol = dol + '.dol'
                if os.path.splitext(dol)[1] != '.dol':
                    print('Invalid input!')
                    continue
                if os.path.exists(dol):
                    dol = os.path.abspath(dol)
                    break
                else:
                    print('File not found! Please try again.')
        elif sys.argv[1].endswith('.dol'):
            dol = sys.argv[1]
            while True:
                gct = input('Name of the input GCT file? ')
                if os.path.splitext(gct)[1] == '':
                    gct = gct + '.gct'
                if os.path.splitext(gct)[1] != '.gct' and os.path.splitext(gct)[1] != '.GCT':
                    print('Invalid input!')
                    continue
                if os.path.exists(gct):
                    gct = os.path.abspath(gct)
                    break
                else:
                    print('File not found! Please try again.')
        else:
            print('The given file is invalid! Please provide a valid dol file, a valid GCT file, or both.')
            time.sleep(1)
            sys.exit(1)
    else:
        if sys.argv[1].endswith('.gct') or sys.argv[1].endswith('.GCT'):
            gct = sys.argv[1]
            if sys.argv[2].endswith('.dol'):
                dol = sys.argv[2]
            else:
                while True:
                    dol = input('Name of the input DOL file? ')
                    if os.path.splitext(dol)[1] == '':
                        dol = dol + '.dol'
                    if os.path.splitext(dol)[1] != '.dol':
                        print('Invalid input!')
                        continue
                    if os.path.exists(dol):
                        dol = os.path.abspath(dol)
                        break
                    else:
                        print('File not found! Please try again.')
        elif sys.argv[1].endswith('.dol'):
            dol = sys.argv[1]
            if sys.argv[2].endswith('.gct') or sys.argv[2].endswith('.GCT'):
                gct = sys.argv[2]
            else:
                while True:
                    gct = input('Name of the input GCT file? ')
                    if os.path.splitext(gct)[1] == '':
                        gct = gct + '.gct'
                    if os.path.splitext(gct)[1] != '.gct' and os.path.splitext(gct)[1] != '.GCT':
                        print('Invalid input!')
                        continue
                    if os.path.exists(gct):
                        gct = os.path.abspath(gct)
                        break
                    else:
                        print('File not found! Please try again.')
        else:
            print('The given files are invalid! Please provide a valid DOL file, a valid GCT file, or both.')
            sys.exit(1)

        
    while True:
        size = input('Define code allocation in hex. (Type 0 or press Enter on empty input for auto size): ')
        try:
            int(size, 16)
            break
        except Exception:
            if size == '':
                break
            else:
                print('Invalid input! {} is not hexadecimal!'.format(size))
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
        build(gct, dol, size)
        os.remove('tmp.bin')
        print('Compiled in {:0.4f} seconds!'.format(time.time() - time1))
        time.sleep(4)

    except Exception as err:
        print(err)
        time.sleep(4)
        sys.exit(1)
