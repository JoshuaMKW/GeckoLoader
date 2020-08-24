from io import BytesIO

import tools


class DolFile:

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
            offset = tools.read_uint32(f)
            f.seek(self.fileAddressLoc + (i << 2))
            address = tools.read_uint32(f)
            f.seek(self.fileSizeLoc + (i << 2))
            size = tools.read_uint32(f)
            
            if offset >= 0x100:
                f.seek(offset)
                data = BytesIO(f.read(size))
                if i < self.maxTextSections:
                    self.textSections.append((offset, address, size, data))
                else:
                    self.dataSections.append((offset, address, size, data))
        
        f.seek(self.fileBssInfoLoc)
        self.bssAddress = tools.read_uint32(f)
        self.bssSize = tools.read_uint32(f)

        f.seek(self.fileEntryLoc)
        self.entryPoint = tools.read_uint32(f)
        
        self._currLogicAddr = self.textSections[0][1]
        self.seek(self._currLogicAddr)
        f.seek(0)
        
    # Internal function for 
    def resolve_address(self, gcAddr, raiseError=True):
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

    def seek_nearest_unmapped(self, gcAddr, buffer=0):
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

    def get_final_section(self):
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
    def read(self, _size):
        _, address, size, data = self.resolve_address(self._currLogicAddr)
        if self._currLogicAddr + _size > address + size:
            raise RuntimeError("Read goes over current section")
            
        self._currLogicAddr += _size  
        return data.read(_size)
        
    # Assumption: A write should not go beyond the current section 
    def write(self, _data):
        offset, address, size, data = self.resolve_address(self._currLogicAddr)
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
        
    def tell(self):
        return self._currLogicAddr
    
    def save(self, f):
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
            tools.write_uint32(f, offset) #offset in file
            f.seek(self.fileAddressLoc + (i * 4))
            tools.write_uint32(f, address) #game address
            f.seek(self.fileSizeLoc + (i * 4))
            tools.write_uint32(f, size) #size in file

            if offset > tools.get_size(f):
                f.seek(0, 2)
                f.write(b"\x00" * (offset - tools.get_size(f)))

            f.seek(offset)
            f.write(data.getbuffer())
            tools.align_file(f, 32)

        f.seek(self.fileBssInfoLoc)
        tools.write_uint32(f, self.bssAddress)
        tools.write_uint32(f, self.bssSize)

        f.seek(self.fileEntryLoc)
        tools.write_uint32(f, self.entryPoint)
        tools.align_file(f, 256)

    def get_full_size(self):
        fullSize = 0x100
        for section in self.textSections:
            fullSize += section[2]
        for section in self.dataSections:
            fullSize += section[2]
        return fullSize

    def get_section_size(self, sectionsList: list, index: int):
        return sectionsList[index][2]
    
    def append_text_sections(self, sectionsList: list):
        """ Follows the list format: [tuple(<Bytes>Data, <Int>GameAddress or None), tuple(<Bytes>Data... """

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

    def append_data_sections(self, sectionsList: list):
        """ Follows the list format: [tuple(<Bytes>Data, <Int>GameAddress or None), tuple(<Bytes>Data... """

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

    def insert_branch(self, to, _from, lk=0):
        tools.write_uint32(self, (to - _from) & 0x3FFFFFF | 0x48000000 | lk)

if __name__ == "__main__":
    # Example usage (reading some enemy info from the Pikmin 2 demo from US demo disc 17)
    
    def read_string(f):
        start = f.tell()
        length = 0
        while f.read(1) != b"\x00":
            length += 1
            if length > 100:
                break
        
        f.seek(start)
        return f.read(length)
    
    entries = []

    with open("main.dol", "rb") as f:
        dol = DolFile(f)

    start = 0x804ac478 # memory address to start of enemy info table.

    for i in range(100):
        dol.seek(start+0x34*i, 0)
        
        # string offset would normally be pointing to a location in RAM and thus
        # wouldn't be suitable as a file offset but because the seek function of DolFile 
        # takes into account the memory address at which the data sections of the dol file 
        # is loaded, we can use the string offset directly..
        stringoffset = tools.read_uint32(dol) 
        identifier = tools.read_ubyte(dol) 
        dol.seek(stringoffset, 0)
        name = read_string(dol)
         
        entries.append((identifier,i, name, hex(stringoffset)))
        
    entries.sort(key=lambda x: x[0])
    for val in entries:
        print(hex(val[0]), val)
