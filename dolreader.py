from io import BytesIO

import tools
from fileutils import *

class UnmappedAddressError(Exception): pass
class SectionCountFullError(Exception): pass
class AddressOutOfRangeError(Exception): pass

class DolFile(object):

    class SectionType():
        Text = 0
        Data = 1

    maxTextSections = 7
    maxDataSections = 11
    offsetInfoLoc = 0
    addressInfoLoc = 0x48
    sizeInfoLoc = 0x90 
    bssInfoLoc = 0xD8
    entryInfoLoc = 0xE0

    def __init__(self, f=None):
        
        self.textSections = []
        self.dataSections = []

        self.bssAddress = 0
        self.bssSize = 0
        self.entryPoint = 0x80003000

        if f is None: return
        
        # Read text and data section addresses and sizes 
        for i in range(DolFile.maxTextSections + DolFile.maxDataSections):
            f.seek(DolFile.offsetInfoLoc + (i << 2))
            offset = read_uint32(f)
            f.seek(DolFile.addressInfoLoc + (i << 2))
            address = read_uint32(f)
            f.seek(DolFile.sizeInfoLoc + (i << 2))
            size = read_uint32(f)
            
            if offset >= 0x100:
                f.seek(offset)
                data = BytesIO(f.read(size))
                if i < DolFile.maxTextSections:
                    self.textSections.append([offset, address, size, data, DolFile.SectionType.Text])
                else:
                    self.dataSections.append([offset, address, size, data, DolFile.SectionType.Data])
        
        f.seek(DolFile.bssInfoLoc)
        self.bssAddress = read_uint32(f)
        self.bssSize = read_uint32(f)

        f.seek(DolFile.entryInfoLoc)
        self.entryPoint = read_uint32(f)
        
        self._currLogicAddr = self.get_first_section()[1]
        self.seek(self._currLogicAddr)
        f.seek(0)

    def __str__(self):
        return "Nintendo DOL format executable for the Wii and Gamecube"
        
    # Internal function for 
    def resolve_address(self, gcAddr) -> tuple:
        """ Returns the data of the section that houses the given address\n
            UnmappedAddressError is raised when the address is unmapped """

        for offset, address, size, data, sectiontype in self.textSections:
            if address <= gcAddr < address+size:
                return offset, address, size, data, sectiontype
        for offset, address, size, data, sectiontype in self.dataSections:
            if address <= gcAddr < address+size:
                return offset, address, size, data, sectiontype
        
        raise UnmappedAddressError(f"Unmapped address: 0x{gcAddr:X}")

    def seek_nearest_unmapped(self, gcAddr, buffer=0) -> int:
        '''Returns the nearest unmapped address (greater) if the given address is already taken by data'''
        
        for _, address, size, _, _ in self.textSections:
            if address > (gcAddr + buffer) or address+size < gcAddr:
                continue
            gcAddr = address + size
        for _, address, size, _, _ in self.dataSections:
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
        """ Returns the last section in the dol file as sorted by internal offset """

        largestOffset = 0
        indexToTarget = 0
        targetType = DolFile.SectionType.Text

        for i, sectionData in enumerate(self.textSections):
            if sectionData[0] > largestOffset:
                largestOffset = sectionData[0]
                indexToTarget = i
                targetType = DolFile.SectionType.Text
        for i, sectionData in enumerate(self.dataSections):
            if sectionData[0] > largestOffset:
                largestOffset = sectionData[0]
                indexToTarget = i
                targetType = DolFile.SectionType.Data
        
        if targetType == DolFile.SectionType.Text:
            return self.textSections[indexToTarget]
        else:
            return self.dataSections[indexToTarget]

    def get_first_section(self) -> tuple:
        """ Returns the first section in the dol file as sorted by internal offset """

        smallestOffset = 0xFFFFFFFF
        indexToTarget = 0
        targetType = DolFile.SectionType.Text

        for i, sectionData in enumerate(self.textSections):
            if sectionData[0] < smallestOffset:
                smallestOffset = sectionData[0]
                indexToTarget = i
                targetType = DolFile.SectionType.Text
        for i, sectionData in enumerate(self.dataSections):
            if sectionData[0] < smallestOffset:
                smallestOffset = sectionData[0]
                indexToTarget = i
                targetType = DolFile.SectionType.Data
        
        if targetType == DolFile.SectionType.Text:
            return self.textSections[indexToTarget]
        else:
            return self.dataSections[indexToTarget]
    
    # Unsupported: Reading an entire dol file 
    # Assumption: A read should not go beyond the current section 
    def read(self, _size) -> bytes:
        _, address, size, data, _ = self.resolve_address(self._currLogicAddr)
        if self._currLogicAddr + _size > address + size:
            raise UnmappedAddressError("Read goes over current section")
            
        self._currLogicAddr += _size  
        return data.read(_size)
        
    # Assumption: A write should not go beyond the current section 
    def write(self, _data):
        _, address, size, data, _ = self.resolve_address(self._currLogicAddr)
        if self._currLogicAddr + len(_data) > address + size:
            raise UnmappedAddressError("Write goes over current section")
            
        data.write(_data)
        self._currLogicAddr += len(_data)
    
    def seek(self, where, whence=0):
        if whence == 0:
            _, address, _, data, _ = self.resolve_address(where)
            data.seek(where - address)
            
            self._currLogicAddr = where
        elif whence == 1:
            _, address, _, data, _ = self.resolve_address(self._currLogicAddr + where)
            data.seek((self._currLogicAddr + where) - address)
            
            self._currLogicAddr += where
        else:
            raise NotImplementedError(f"Unsupported whence type '{whence}'")
        
    def tell(self) -> int:
        return self._currLogicAddr
    
    def save(self, f):
        f.seek(0)
        f.write(b"\x00" * self.get_full_size())

        for i in range(DolFile.maxTextSections + DolFile.maxDataSections):
            if i < DolFile.maxTextSections:
                if i < len(self.textSections):
                    offset, address, size, data, _ = self.textSections[i]
                else:
                    continue
            else:
                if i - DolFile.maxTextSections < len(self.dataSections):
                    offset, address, size, data, _ = self.dataSections[i - DolFile.maxTextSections]
                else:
                    continue

            f.seek(DolFile.offsetInfoLoc + (i << 2))
            write_uint32(f, offset) #offset in file
            f.seek(DolFile.addressInfoLoc + (i << 2))
            write_uint32(f, address) #game address
            f.seek(DolFile.sizeInfoLoc + (i << 2))
            write_uint32(f, size) #size in file

            f.seek(offset)
            f.write(data.getbuffer())

        f.seek(DolFile.bssInfoLoc)
        write_uint32(f, self.bssAddress)
        write_uint32(f, self.bssSize)

        f.seek(DolFile.entryInfoLoc)
        write_uint32(f, self.entryPoint)
        align_byte_size(f, 256)

    def get_full_size(self) -> int:
        try:
            offset, _, size, _, _ = self.get_final_section()
            return (offset + size + 255) & -256
        except IndexError:
            return 0x100

    def get_section_size(self, index: int, section: SectionType) -> int:
        """ Return the current size of the specified section\n
            section: DolFile.SectionType """

        if section == DolFile.SectionType.Text:
            return self.textSections[index][2]
        else:
            return self.dataSections[index][2]

    
    def append_text_sections(self, sectionsList: list) -> bool:
        """ Follows the list format: [tuple(<Bytes>Data, <Int>GameAddress or None), tuple(<Bytes>Data... """

        for i, dataSet in enumerate(sectionsList):
            if len(self.textSections) >= DolFile.maxTextSections:
                raise SectionCountFullError(f"Exceeded max text section limit of {DolFile.maxTextSections}")

            fOffset, _, fSize, _, _ = self.get_final_section()
            _, pAddress, pSize, _, _ = self.textSections[len(self.textSections) - 1]
            data, address = dataSet
            
            if not hasattr(data, "getbuffer"):
                if hasattr(data, "read"):
                    data.seek(0)
                    data = BytesIO(data.read())
                else:
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

            self.textSections.append((offset, address, size, data, DolFile.SectionType.Text))

    def append_data_sections(self, sectionsList: list) -> bool:
        """ Follows the list format: [tuple(<Bytes>Data, <Int>GameAddress or None), tuple(<Bytes>Data... """

        for i, dataSet in enumerate(sectionsList):
            if len(self.dataSections) >= DolFile.maxDataSections:
                raise SectionCountFullError(f"Exceeded max data section limit of {DolFile.maxDataSections}")

            fOffset, _, fSize, _, _ = self.get_final_section()
            _, pAddress, pSize, _, _ = self.dataSections[len(self.dataSections) - 1]
            data, address = dataSet

            if not hasattr(data, "getbuffer"):
                if hasattr(data, "read"):
                    data.seek(0)
                    data = BytesIO(data.read())
                else:
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

            self.dataSections.append((offset, address, size, data, DolFile.SectionType.Data))

    def insert_branch(self, to: int, _from: int, lk=0):
        """ Insert a branch instruction at _from\n
            to:    address to branch to\n
            _from: address to branch from\n
            lk:    0 | 1, is branch linking? """

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
                length += 1
            except UnicodeDecodeError:
                print(f"{char} at pos {length}, (address 0x{addr + length:08X}) is not a valid utf-8 character")
                return ""
            if length > (maxlen-1) and maxlen != 0:
                return string

        return string

    def print_info(self):
        print("")
        print("|-- DOL INFO --|".center(20, " "))
        print("")

        for i, (offset, addr, size, _, _) in enumerate(self.textSections):
            header = f"|  Text section {i}  |"
            print("-"*len(header) + "\n" + header + "\n" + "-"*len(header) + f"\n File offset:\t0x{offset:X}\n Virtual addr:\t0x{addr:X}\n Size:\t\t0x{size:X}\n")
        
        for i, (offset, addr, size, _, _) in enumerate(self.dataSections):
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
