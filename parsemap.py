import os
import sys
import time
import re
import argparse

def getMemoryMap(map):
    regex = re.compile(r'(?:(\.init|\.text|\.bss)\s\s)([0-9a-fA-F]{8})(?:\s)([0-9a-fA-F]{8})')
    data = re.findall(regex, map.read())
    map.seek(0)
    return data[0], data[1], data[2]

def parseMap(map, regex):
    definelist = []
    init, text, bss = getMemoryMap(map)
    with open(os.path.join('build', 'definefuncs.hxx'), 'w+') as funclist:
        for function in re.findall(regex, map.read()):
            if len(function) == 1:
                continue
            if function[3] != '':
                template = '_' + function[3]
            else:
                template = function[3]
            if int(function[0], 16) > int(init[1], 16) + int(init[2], 16) and int(function[0], 16) < int(bss[1], 16):
                continue
            if int(function[0], 16) >= int(bss[1], 16):
                func = ('#define {} (0x{})\n'.format(function[1], function[0]))
                if func[:15] not in definelist:
                    definelist.append(func[:15])
                    funclist.write(func)

            else:
                func = ('#define {}{} ((u32 (*)(...))0x{})\n'.format(function[1], template, function[0].upper()))
                if func[:30] not in definelist:
                    definelist.append(func[:30])
                    funclist.write(func)

            
if __name__ == '__main__':

    if not os.path.isdir('build'):
        os.mkdir('build')

    parser = argparse.ArgumentParser(prog='parsemap',
                                     description='Process .map files to extract functions in the c++ #define format',
                                     allow_abbrev=False)

    parser.add_argument('file', help='mapfile')

    args = parser.parse_args()

    regex = re.compile(r'(?<=\s[0-9a-fA-F]{8}\s[0-9a-fA-F]{6}\s)([0-9a-fA-F]{8})(?:\s\s4\s)([\w]+)((?:<)(\w)|)')
    with open(args.file, 'r') as map:
        parseMap(map, regex)

    print('Program finished!')
    time.sleep(2)