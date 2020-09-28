from io import BytesIO

import tools
from fileutils import *

class UnmappedAddressError(Exception): pass
class SectionCountFullError(Exception): pass
class AddressOutOfRangeError(Exception): pass

class DolFile(object):

    def __init__(self, f=None):
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
        
        self._currLogicAddr = self.get_first_section()[1]
        self.seek(self._currLogicAddr)
        f.seek(0)

    def __str__(self):
        return "Nintendo DOL format executable for the Wii and Gamecube"
        
    # Internal function for 
    def resolve_address(self, gcAddr, raiseError=True) -> tuple:
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
            raise UnmappedAddressError(f"Unmapped address: 0x{gcAddr:X}")

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

    @property
    def sections(self) -> tuple:
        """ Generator that yields each section's data """
        for i in self.textSections:
            yield i
        for i in self.dataSections:
            yield i
        
        return

    def get_final_section(self) -> tuple:
        largestOffset = 0
        indexToTarget = 0
        targetType = "Text"

        for i, sectionData in enumerate(self.textSections):
            if sectionData[0] > largestOffset:
                largestOffset = sectionData[0]
                indexToTarget = i
                targetType = "Text"
        for i, sectionData in enumerate(self.dataSections):
            if sectionData[0] > largestOffset:
                largestOffset = sectionData[0]
                indexToTarget = i
                targetType = "Data"
        
        if targetType == "Text":
            return self.textSections[indexToTarget]
        else:
            return self.dataSections[indexToTarget]

    def get_first_section(self) -> tuple:
        smallestOffset = 0xFFFFFFFF
        indexToTarget = 0
        targetType = "Text"

        for i, sectionData in enumerate(self.textSections):
            if sectionData[0] < smallestOffset:
                smallestOffset = sectionData[0]
                indexToTarget = i
                targetType = "Text"
        for i, sectionData in enumerate(self.dataSections):
            if sectionData[0] < smallestOffset:
                smallestOffset = sectionData[0]
                indexToTarget = i
                targetType = "Data"
        
        if targetType == "Text":
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
            raise RuntimeError(f"Unsupported whence type '{whence}'")
        
    def tell(self) -> int:
        return self._currLogicAddr
    
    def save(self, f):
        f.seek(0)
        f.write(b"\x00" * self.get_full_size())

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
            write_uint32(f, offset) #offset in file
            f.seek(self.fileAddressLoc + (i * 4))
            write_uint32(f, address) #game address
            f.seek(self.fileSizeLoc + (i * 4))
            write_uint32(f, size) #size in file

            f.seek(offset)
            f.write(data.getbuffer())

        f.seek(self.fileBssInfoLoc)
        write_uint32(f, self.bssAddress)
        write_uint32(f, self.bssSize)

        f.seek(self.fileEntryLoc)
        write_uint32(f, self.entryPoint)
        align_byte_size(f, 256)

    def get_full_size(self) -> int:
        offset, _, size, _ = self.get_final_section()
        return (0x100 + offset + size + 255) & -256

    def get_section_size(self, sectionsList: list, index: int) -> int:
        return sectionsList[index][2]
    
    def append_text_sections(self, sectionsList: list) -> bool:
        """ Follows the list format: [tuple(<Bytes>Data, <Int>GameAddress or None), tuple(<Bytes>Data... """

        '''Write offset/address/size to each section in DOL file header'''
        for i, dataSet in enumerate(sectionsList):
            if len(self.textSections) >= self.maxTextSections:
                raise SectionCountFullError(f"Exceeded max text section limit of {self.maxTextSections}")

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
                raise AddressOutOfRangeError(f"Address '{address:08X}' of text section {i} is beyond scope (0x80000000 <-> 0x81200000)")

            self.textSections.append((offset, address, size, data))

    def append_data_sections(self, sectionsList: list) -> bool:
        """ Follows the list format: [tuple(<Bytes>Data, <Int>GameAddress or None), tuple(<Bytes>Data... """

        '''Write offset/address/size to each section in DOL file header'''
        for i, dataSet in enumerate(sectionsList):
            if len(self.dataSections) >= self.maxDataSections:
                raise SectionCountFullError(f"Exceeded max data section limit of {self.maxDataSections}")

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
                raise AddressOutOfRangeError(f"Address '{address:08X}' of data section {i} is beyond scope (0x80000000 <-> 0x81200000)")

            self.dataSections.append((offset, address, size, data))

    def insert_branch(self, to: int, _from: int, lk=0):
        self.seek(_from)
        write_uint32(self, (to - _from) & 0x3FFFFFD | 0x48000000 | lk)

    def extract_branch_addr(self, bAddr: int) -> tuple:
        """ Returns the branch offset of the given instruction,
            and if the branch is conditional """

        self.seek(bAddr)

        ppc = read_uint32(self)
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

    def print_info(self):
        print("|---DOL INFO---|".center(20, " "))
        for i, (offset, addr, size, _) in enumerate(self.textSections):
            header = f"|  Text section {i}  |"
            print("-"*len(header) + "\n" + header + "\n" + "-"*len(header) + f"\n File offset:\t0x{offset:X}\n Virtual addr:\t0x{addr:X}\n Size:\t\t0x{size:X}\n")
        
        for i, (offset, addr, size, _) in enumerate(self.dataSections):
            header = f"|  Data section {i}  |"
            print("-"*len(header) + "\n" + header + "\n" + "-"*len(header) + f"\n File offset:\t0x{offset:X}\n Virtual addr:\t0x{addr:X}\n Size:\t\t0x{size:X}\n")

        header = "|  BSS section  |"  
        print("-"*len(header) + "\n" + header + "\n" + "-"*len(header) + f"\n Virtual addr:\t0x{self.bssAddress:X}\n Size:\t\t0x{self.bssSize:X}\n End:\t\t0x{self.bssAddress+self.bssSize:X}\n")
        
        header = "|  Miscellaneous Info  |"
        print("-"*len(header) + "\n" + header + "\n" + "-"*len(header) + f"\n Text sections:\t{len(self.textSections)}\n Data sections:\t{len(self.dataSections)}\n File length:\t0x{self.get_full_size():X} bytes\n")

if __name__ == "__main__":
    # Example usage (Reading global string "mario" from Super Mario Sunshine (NTSC-U))

    with open("Start.dol", "rb") as f:
        dol = DolFile(f)
        
    name = dol.read_string(addr=0x804165A0)
    print(name)
