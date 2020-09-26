from io import BytesIO

import tools
from fileutils import *

class DolFile(object):

    def __init__(self, f: GC_File=None):
        self.fileOffsetLoc = 0
        self.fileAddressLoc = 0x48
        self.fileSizeLoc = 0x90 
        self.fileBssInfoLoc = 0xD8
        self.fileEntryLoc = 0xE0
        
        self.textSections = []
        self.dataSections = []
        self.maxTextSections = 7
        self.maxDataSections = 11

        self.bssAddress = 0
        self.bssSize = 0
        self.entryPoint = 0x80003000

        if f is None: return
        
        # Read text and data section addresses and sizes 
        for i in range(self.maxTextSections + self.maxDataSections):
            f.seek(self.fileOffsetLoc + (i << 2))
            offset = read_uint32(f)
            f.seek(self.fileAddressLoc + (i << 2))
            address = read_uint32(f)
            f.seek(self.fileSizeLoc + (i << 2))
            size = read_uint32(f)
            
            if offset >= 0x100:
                f.seek(offset)
                data = BytesIO(f.read(size))
                if i < self.maxTextSections:
                    self.textSections.append((offset, address, size, data))
                else:
                    self.dataSections.append((offset, address, size, data))
        
        f.seek(self.fileBssInfoLoc)
        self.bssAddress = read_uint32(f)
        self.bssSize = read_uint32(f)

        f.seek(self.fileEntryLoc)
        self.entryPoint = read_uint32(f)
        
        self._currLogicAddr = self.textSections[0][1]
        self.seek(self._currLogicAddr)
        f.seek(0)
        
    # Internal function for 
    def resolve_address(self, gcAddr, raiseError=True) -> (None, tuple):
        '''Returns the data of the section that houses the given address
           If raiseError is True, a RuntimeError is raised when the address is unmapped,
           otherwise it returns None'''

        for offset, address, size, data in self.textSections:
            if address <= gcAddr < address+size:
                return offset, address, size, data
        for offset, address, size, data in self.dataSections:
            if address <= gcAddr < address+size:
                return offset, address, size, data
        
        if raiseError:
            raise RuntimeError("Unmapped address: 0x{:X}".format(gcAddr))

        return None

    def seek_nearest_unmapped(self, gcAddr, buffer=0) -> int:
        '''Returns the nearest unmapped address (greater) if the given address is already taken by data'''
        
        for _, address, size, _ in self.textSections:
            if address > (gcAddr + buffer) or address+size < gcAddr:
                continue
            gcAddr = address + size
        for _, address, size, _ in self.dataSections:
            if address > (gcAddr + buffer) or address+size < gcAddr:
                continue
            gcAddr = address + size
        return gcAddr

    def get_final_section(self) -> tuple:
        largestOffset = 0
        indexToTarget = 0
        targetType = 0

        for i, sectionData in enumerate(self.textSections):
            if sectionData[0] > largestOffset:
                largestOffset = sectionData[0]
                indexToTarget = i
                targetType = 0
        for i, sectionData in enumerate(self.dataSections):
            if sectionData[0] > largestOffset:
                largestOffset = sectionData[0]
                indexToTarget = i
                targetType = 1
        
        if targetType == 0:
            return self.textSections[indexToTarget]
        else:
            return self.dataSections[indexToTarget]
    
    # Unsupported: Reading an entire dol file 
    # Assumption: A read should not go beyond the current section 
    def read(self, _size) -> bytes:
        _, address, size, data = self.resolve_address(self._currLogicAddr)
        if self._currLogicAddr + _size > address + size:
            raise RuntimeError("Read goes over current section")
            
        self._currLogicAddr += _size  
        return data.read(_size)
        
    # Assumption: A write should not go beyond the current section 
    def write(self, _data):
        _, address, size, data = self.resolve_address(self._currLogicAddr)
        if self._currLogicAddr + len(_data) > address + size:
            raise RuntimeError("Write goes over current section")
            
        data.write(_data)
        self._currLogicAddr += len(_data)
    
    def seek(self, where, whence=0):
        if whence == 0:
            _, address, _, data = self.resolve_address(where)
            data.seek(where - address)
            
            self._currLogicAddr = where
        elif whence == 1:
            _, address, _, data = self.resolve_address(self._currLogicAddr + where)
            data.seek((self._currLogicAddr + where) - address)
            
            self._currLogicAddr += where
        else:
            raise RuntimeError("Unsupported whence type '{}'".format(whence))
        
    def tell(self) -> int:
        return self._currLogicAddr
    
    def save(self, f: GC_File):
        f.seek(0)
        f.write(b"\x00" * 0x100)

        for i in range(self.maxTextSections + self.maxDataSections):
            if i < self.maxTextSections:
                if i < len(self.textSections):
                    offset, address, size, data = self.textSections[i]
                else:
                    continue
            else:
                if i - self.maxTextSections < len(self.dataSections):
                    offset, address, size, data = self.dataSections[i - self.maxTextSections]
                else:
                    continue

            f.seek(self.fileOffsetLoc + (i * 4))
            f.write_uint32(offset) #offset in file
            f.seek(self.fileAddressLoc + (i * 4))
            f.write_uint32(address) #game address
            f.seek(self.fileSizeLoc + (i * 4))
            f.write_uint32(size) #size in file

            if offset > f.get_size():
                f.seek(0, 2)
                f.write(b"\x00" * (offset - f.get_size()))

            f.seek(offset)
            f.write(data.getbuffer())
            f.align_file(32)

        f.seek(self.fileBssInfoLoc)
        f.write_uint32(self.bssAddress)
        f.write_uint32(self.bssSize)

        f.seek(self.fileEntryLoc)
        f.write_uint32(self.entryPoint)
        f.align_file(256)

    def get_full_size(self) -> int:
        fullSize = 0x100
        for section in self.textSections:
            fullSize += section[2]
        for section in self.dataSections:
            fullSize += section[2]
        return fullSize

    def get_section_size(self, sectionsList: list, index: int) -> int:
        return sectionsList[index][2]
    
    def append_text_sections(self, sectionsList: list) -> bool:
        """ Follows the list format: [tuple(<Bytes>Data, <Int>GameAddress or None), tuple(<Bytes>Data... 
        
            Returns True if the operation can be performed, otherwise it returns False """

        '''Write offset/address/size to each section in DOL file header'''
        for i, dataSet in enumerate(sectionsList):
            if len(self.textSections) >= self.maxTextSections:
                return False

            fOffset, _, fSize, _ = self.get_final_section()
            _, pAddress, pSize, _ = self.textSections[len(self.textSections) - 1]
            data, address = dataSet
            
            if not isinstance(data, BytesIO):
                data = BytesIO(data)

            offset = fOffset + fSize

            if i < len(sectionsList) - 1:
                size = (len(data.getbuffer()) + 31) & -32
            else:
                size = (len(data.getbuffer()) + 255) & -256

            if address is None:
                address = self.seek_nearest_unmapped(pAddress + pSize, size)

            if address < 0x80000000 or address >= 0x81200000:
                raise ValueError("Address '{:08X}' of text section {} is beyond scope (0x80000000 <-> 0x81200000)".format(address, i))

            self.textSections.append((offset, address, size, data))

        return True

    def append_data_sections(self, sectionsList: list) -> bool:
        """ Follows the list format: [tuple(<Bytes>Data, <Int>GameAddress or None), tuple(<Bytes>Data... 
        
            Returns True if the operation can be performed, otherwise it returns False """

        '''Write offset/address/size to each section in DOL file header'''
        for i, dataSet in enumerate(sectionsList):
            if len(self.dataSections) >= self.maxDataSections:
                return False

            fOffset, _, fSize, _ = self.get_final_section()
            _, pAddress, pSize, _ = self.dataSections[len(self.dataSections) - 1]
            data, address = dataSet

            if not isinstance(data, BytesIO):
                data = BytesIO(data)

            offset = fOffset + fSize

            if i < len(sectionsList) - 1:
                size = (len(data.getbuffer()) + 31) & -32
            else:
                size = (len(data.getbuffer()) + 255) & -256

            if address is None:
                address = self.seek_nearest_unmapped(pAddress + pSize, size)

            if address < 0x80000000 or address >= 0x81200000:
                raise ValueError("Address '{:08X}' of data section {} is beyond scope (0x80000000 <-> 0x81200000)".format(address, i))

            self.dataSections.append((offset, address, size, data))

        return True

    def insert_branch(self, to: int, _from: int, lk=0):
        self.seek(_from)
        f.write_uint32(self, (to - _from) & 0x3FFFFFD | 0x48000000 | lk)

    def extract_branch_addr(self, bAddr: int) -> tuple:
        """ Returns the branch offset of the given instruction,
            and if the branch is conditional """

        self.seek(bAddr)

        ppc = f.read_uint32(self)
        conditional = False

        if (ppc >> 24) & 0xFF < 0x48:
            conditional = True

        if conditional is True:
            if (ppc & 0x8000):
                offset = (ppc & 0xFFFD) - 0x10000
            else:
                offset = ppc & 0xFFFD
        else:
            if (ppc & 0x2000000):
                offset = (ppc & 0x3FFFFFD) - 0x4000000
            else:
                offset = ppc & 0x3FFFFFD

        return (bAddr + offset, conditional)

    def read_string(self, addr: int = None, maxlen: int = 0, encoding: str = "utf-8") -> str:
        """ Reads a null terminated string from the specified address """

        if addr != None:
            self.seek(addr)

        length = 0
        string = ""
        while (char := self.read(1)) != b"\x00":
            try:
                string += char.decode(encoding)
            except UnicodeDecodeError:
                print(f"{char} at pos {length}, (address 0x{addr + length:08X}) is not a valid utf-8 character")
                return ""
            if length > maxlen and maxlen != 0:
                break

        return string

if __name__ == "__main__":
    # Example usage (Reading global string "mario" from Super Mario Sunshine (NTSC-U))

    with GC_File("Start.dol", "rb") as f:
        dol = DolFile(f)
        
    name = dol.read_string(addr=0x804165A0)
    print(name)
