from io import BytesIO
from access import *

class DolFile:

    def __init__(self, f):
        self._rawData = BytesIO(f.read())
        self.fileOffsetLoc = 0
        self.fileAddressLoc = 0x48
        self.fileSizeLoc = 0x90 
        self.fileEntryLoc = 0xE0
        
        self.textSections = []
        self.dataSections = []
        self.maxTextSections = 7
        self.maxDataSections = 11
        
        self._currentEnd = None 
        
        # Read text and data section addresses and sizes 
        for i in range(18):
            f.seek(self.fileOffsetLoc + (i << 2))
            offset = read_uint32(f)
            f.seek(self.fileAddressLoc + (i << 2))
            address = read_uint32(f)
            f.seek(self.fileSizeLoc + (i << 2))
            size = read_uint32(f)
            
            if offset != 0:
                if i < self.maxTextSections:
                    self.textSections.append((offset, address, size))
                else:
                    self.dataSections.append((offset, address, size))
        
        f.seek(0xD8)
        self.bssOffset = read_uint32(f)
        self.bssSize = read_uint32(f)
        self.entryPoint = read_uint32(f)
        
        self._bssData = BytesIO(self._rawData.getbuffer()[self.bssOffset:self.bssOffset + self.bssSize])
        
        self._currAddr = self.textSections[0][1]
        self.seek(self._currAddr)
        f.seek(0)
        
    # Internal function for 
    def resolve_address(self, gcAddr):
        for offset, address, size in self.textSections:
            if address <= gcAddr < address+size:
                return offset, address, size 
        for offset, address, size in self.dataSections:
            if address <= gcAddr < address+size:
                return offset, address, size 
        
        raise RuntimeError(f"Unmapped address: 0x{gcAddr:X}")

    def seek_safe_address(self, gcAddr, buffer=0):
        for offset, address, size in self.textSections:
            if address > (gcAddr + buffer) or address+size < gcAddr:
                continue
            gcAddr = address + size
        for offset, address, size in self.dataSections:
            if address > (gcAddr + buffer) or address+size < gcAddr:
                continue
            gcAddr = address + size
        return gcAddr
    
    # Unsupported: Reading an entire dol file 
    # Assumption: A read should not go beyond the current section 
    def read(self, size):
        if self._currAddr + size > self._currentEnd:
            raise RuntimeError("Read goes over current section")
            
        self._currAddr += size  
        return self._rawData.read(size)
        
    # Assumption: A write should not go beyond the current section 
    def write(self, data):
        if self._currAddr + len(data) > self._currentEnd:
            raise RuntimeError("Write goes over current section")
            
        self._rawData.write(data)
        self._currAddr += len(data)
    
    def seek(self, where, whence=0):
        if whence == 0:
            offset, gc_start, gc_size = self.resolve_address(where)
            self._rawData.seek(offset + (where-gc_start))
            
            self._currAddr = where
            self._currentEnd = gc_start + gc_size
        elif whence == 1:
            offset, gc_start, gc_size = self.resolve_address(self._currAddr + where)
            self._rawData.seek(offset + ((self._currAddr + where)-gc_start))
            
            self._currAddr += where
            self._currentEnd = gc_start + gc_size
        else:
            raise RuntimeError("Unsupported whence type '{}'".format(whence))
        
    def tell(self):
        return self._currAddr
    
    def save(self, f):
        f.seek(0)
        f.write(self._rawData.getbuffer())

    def get_size(self):
        oldpos = self._rawData.tell()
        self._rawData.seek(0, 2)
        size = self._rawData.tell()
        self._rawData.seek(oldpos)
        return size

    def get_alignment(self, alignment):
        size = self.get_size()

        if size % alignment != 0:
            return alignment - (size % alignment)
        else:
            return 0

    def align(self, alignment):
        oldpos = self._rawData.tell()
        self._rawData.seek(0, 2)
        self._rawData.write(bytes.fromhex("00" * self.get_alignment(alignment)))
        self._rawData.seek(oldpos)
    
    def append_text_sections(self, sections_list: list):
        offset = len(self.textSections) << 2

        if len(sections_list) + len(self.textSections) > self.maxTextSections:
            return False

        '''Write offset to each section in DOL file header'''
        self._rawData.seek(offset)
        for section_offset in sections_list:
            self._rawData.write(section_offset[1].to_bytes(4, byteorder='big', signed=False)) #offset in file
        
        self._rawData.seek(0x48 + offset)

        '''Write in game memory addresses for each section in DOL file header'''
        for section_addr in sections_list:
            self._rawData.write(section_addr[0].to_bytes(4, byteorder='big', signed=False)) #absolute address in game

        '''Get size of GeckoLoader + gecko codes, and the codehandler'''
        size_list = []
        for i, section_offset in enumerate(sections_list, start=1):
            if i > len(sections_list) - 1:
                size_list.append(self.get_size() - section_offset[1])
            else:
                size_list.append(sections_list[i][1] - section_offset[1])

        '''Write size of each section into DOL file header'''
        self._rawData.seek(0x90 + offset)
        for size in size_list:
            self._rawData.write(size.to_bytes(4, byteorder='big', signed=False))

        return True

    def append_data_sections(self, sections_list: list):
        offset = len(self.dataSections) << 2

        if len(sections_list) + len(self.dataSections) > self.maxDataSections:
            return False

        '''Write offset to each section in DOL file header'''
        self._rawData.seek(offset)
        for section_offset in sections_list:
            write_uint32(self._rawData, section_offset[1]) #offset in file
        
        self._rawData.seek(0x64 + offset)

        '''Write in game memory addresses for each section in DOL file header'''
        for section_addr in sections_list:
            write_uint32(self._rawData, section_addr[0]) #absolute address in game

        '''Get size of GeckoLoader + gecko codes, and the codehandler'''
        size_list = []
        for i, section_offset in enumerate(sections_list, start=1):
            if i > len(sections_list) - 1:
                size_list.append(self.get_size() - section_offset[1])
            else:
                size_list.append(sections_list[i][1] - section_offset[1])

        '''Write size of each section into DOL file header'''
        self._rawData.seek(0xAC + offset)
        for size in size_list:
            write_uint32(self._rawData, size)

        return True

    def set_entry_point(self, address):
        oldpos = self._rawData.tell()
        self._rawData.seek(self.fileEntryLoc)
        write_uint32(self._rawData, address)
        self._rawData.seek(oldpos)

    def insert_branch(self, to, _from, lk=0):
        self.write(((to - _from) & 0x3FFFFFF | 0x48000000 | lk).to_bytes(4, byteorder='big', signed=False))

        

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
        stringoffset = read_uint32(dol) 
        identifier = read_ubyte(dol) 
        dol.seek(stringoffset, 0)
        name = read_string(dol)
         
        entries.append((identifier,i, name, hex(stringoffset)))
        
    entries.sort(key=lambda x: x[0])
    for val in entries:
        print(hex(val[0]), val)