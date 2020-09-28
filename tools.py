import struct
import sys
import os
from io import IOBase
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
    TRESET = ""
    TGREEN = ""
    TGREENLIT = ""
    TYELLOW = ""
    TYELLOWLIT = ""
    TRED = ""
    TREDLIT = ""

def get_alignment(number: int, align: int) -> int:
    if number % align != 0:
        return align - (number % align)
    else:
        return 0

def stream_size(obj, ofs: int = 0) -> int:
    if hasattr(obj, "getbuffer"):
        return len(obj.getbuffer()) + ofs
    elif hasattr(obj, "tell") and hasattr(obj, "seek"):
        _pos = obj.tell()
        obj.seek(0, 2)
        _size = obj.tell()
        obj.seek(_pos, 1)
        return _size + ofs
    else:
        raise NotImplementedError(f"Getting the stream size of class {type(obj)} is unsupported")

def align_byte_size(obj, alignment: int, fillchar="00"):
    if isinstance(obj, bytes):
        obj += bytes.fromhex(fillchar * get_alignment(len(obj), alignment))
    elif isinstance(obj, bytearray):
        obj.append(bytearray.fromhex(fillchar * get_alignment(len(obj), alignment)))
    elif issubclass(type(obj), IOBase):
        _size = stream_size(obj)
        obj.write(bytes.fromhex(fillchar * get_alignment(_size, alignment)))
    else:
        raise NotImplementedError(f"Aligning the size of class {type(obj)} is unsupported")

def color_text(text: str, textToColor: list=[("", None)], defaultColor: str=None) -> str:
    currentColor = None
    formattedText = ""

    format = False
    for itemPair in textToColor:
        if itemPair[0] != "" and itemPair[1] is not None:
            format = True
            break

    if not format:
        return defaultColor + text + TRESET

    for char in text:
        handled = False
        for itemPair in textToColor:
            if (char in itemPair[0] or r"\*" in itemPair[0]) and itemPair[1] is not None:
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
                self.exit(2, f"{self.prog}: error: {message}\n")
            else:
                self._print_message(f"{self.prog}: error: {message}\n")
        else:
            if exit:
                self.exit(2, f"{prefix} {message}\n")
            else:
                self._print_message(f"{prefix} {message}\n")