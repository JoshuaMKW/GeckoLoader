from io import FileIO
from tools import get_alignment
import struct

def read_sbyte(f):
    return struct.unpack("b", f.read(1))[0]

def write_sbyte(f, val):
    f.write(struct.pack("b", val))

def read_sint16(f):
    return struct.unpack(">h", f.read(2))[0]

def write_sint16(f, val):
    f.write(struct.pack(">h", val))

def read_sint32(f):
    return struct.unpack(">i", f.read(4))[0]

def write_sint32(f, val):
    f.write(struct.pack(">i", val))

def read_ubyte(f):
    return struct.unpack("B", f.read(1))[0]

def write_ubyte(f, val):
    f.write(struct.pack("B", val))

def read_uint16(f):
    return struct.unpack(">H", f.read(2))[0]

def write_uint16(f, val):
    f.write(struct.pack(">H", val))

def read_uint32(f):
    return struct.unpack(">I", f.read(4))[0]

def write_uint32(f, val):
    f.write(struct.pack(">I", val))

def read_float(f):
    return struct.unpack(">f", f.read(4))[0]

def write_float(f, val):
    f.write(struct.pack(">f", val))

def read_double(f):
    return struct.unpack(">d", f.read(4))[0]

def write_double(f, val):
    f.write(struct.pack(">d", val))

def read_bool(f, vSize=1):
    return struct.unpack("B", f.read(vSize))[0] > 0

def write_bool(f, val, vSize=1):
    if val is True: f.write(b'\x00'*(vSize-1) + b'\x01')
    else: f.write(b'\x00' * vSize)

class GC_File(FileIO):

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        
    def __enter__(self):
        self._filestream = open(*self._args, **self._kwargs)
        return self._filestream

    def __exit__(self, *args):
        self._filestream.close()
    
    def size(self, ofs: int = 0):
        _pos = self.tell()
        self.seek(0, 2)
        _size = self.tell()
        self.seek(_pos, 1)
        return _size + ofs

    def size_alignment(self, alignment: int):
        """ Return file alignment, 0 = aligned, non zero = misaligned """
        return get_alignment(self.size(), alignment)

    def align_file_size(self, alignment: int, fillchar='00'):
        """ Align a file to be the specified size """
        self.write(bytes.fromhex(fillchar * self.size_alignment(alignment)))


    