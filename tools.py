import struct
import sys
import os
from argparse import ArgumentParser

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

def read_sbyte(f): return struct.unpack("b", f.read(1))[0]
def write_sbyte(f, val): f.write(struct.pack("b", val))
def read_sint16(f): return struct.unpack(">h", f.read(2))[0]
def write_sint16(f, val): f.write(struct.pack(">h", val))
def read_sint32(f): return struct.unpack(">i", f.read(4))[0]
def write_sint32(f, val): f.write(struct.pack(">i", val))
def read_ubyte(f): return struct.unpack("B", f.read(1))[0]
def write_ubyte(f, val): f.write(struct.pack("B", val))
def read_uint16(f): return struct.unpack(">H", f.read(2))[0]
def write_uint16(f, val): f.write(struct.pack(">H", val))
def read_uint32(f): return struct.unpack(">I", f.read(4))[0]
def write_uint32(f, val): f.write(struct.pack(">I", val))
def read_float(f): return struct.unpack(">f", f.read(4))[0]
def write_float(f, val): f.write(struct.pack(">f", val))
def read_double(f): return struct.unpack(">d", f.read(4))[0]
def write_double(f, val): f.write(struct.pack(">d", val))
def read_bool(f, vSize=1): return struct.unpack("B", f.read(vSize))[0] > 0
def write_bool(f, val, vSize=1):
    if val is True: f.write(b'\x00'*(vSize-1) + b'\x01')
    else: f.write(b'\x00' * vSize)

def get_alignment(number, align: int):
    if number % align != 0:
        return align - (number % align)
    else:
        return 0

def get_size(f, offset=0):
    """ Return a stream's size in bytes """
    f.seek(0, 2)
    return f.tell() + offset

def get_file_alignment(f, alignment: int):
    """ Return file alignment, 0 = aligned, non zero = misaligned """
    return get_alignment(get_size(f), alignment)

def align_file(f, alignment: int, fillchar='00'):
    """ Align a file to be the specified size """
    f.write(bytes.fromhex(fillchar * get_file_alignment(f, alignment)))

def color_text(text: str, textToColor: list=[('', None)], defaultColor: str=None):
    currentColor = None
    formattedText = ''

    format = False
    for itemPair in textToColor:
        if itemPair[0] != '' and itemPair[1] is not None:
            format = True
            break

    if not format:
        return defaultColor + text + TRESET

    for char in text:
        handled = False
        for itemPair in textToColor:
            if (char in itemPair[0] or '\*' in itemPair[0]) and itemPair[1] is not None:
                if currentColor != itemPair[1]:
                    formattedText += TRESET
                    formattedText += itemPair[1]
                    currentColor = itemPair[1]
                handled = True

            elif defaultColor is not None:
                formattedText += TRESET
                formattedText += defaultColor
                currentColor = defaultColor

            elif currentColor is not None:
                formattedText += TRESET
                currentColor = None

            if handled:
                break

        formattedText += char

    return formattedText + TRESET

class CommandLineParser(ArgumentParser):
    
    def error(self, message: str, prefix: str=None, print_usage=True, exit=True):
        if print_usage:
            self.print_usage(sys.stderr)

        if prefix is None:
            if exit:
                self.exit(2, f'{self.prog}: error: {message}\n')
            else:
                self._print_message(f'{self.prog}: error: {message}\n')
        else:
            if exit:
                self.exit(2, f'{prefix} {message}\n')
            else:
                self._print_message(f'{prefix} {message}\n')