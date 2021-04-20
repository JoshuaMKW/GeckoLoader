from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, IO, List, Tuple, Union

from dolreader import DolFile
from fileutils import (write_ubyte, write_uint16, write_uint32)


class InvalidGeckoCodeError(Exception):
    pass


class GeckoCode(object):
    class Type(Enum):
        WRITE_8 = 0x00
        WRITE_16 = 0x02
        WRITE_32 = 0x04
        WRITE_STR = 0x06
        WRITE_SERIAL = 0x08
        IF_EQ_32 = 0x20
        IF_NEQ_32 = 0x22
        IF_GT_32 = 0x24
        IF_LT_32 = 0x26
        IF_EQ_16 = 0x28
        IF_NEQ_16 = 0x2A
        IF_GT_16 = 0x2C
        IF_LT_16 = 0x2E
        BASE_ADDR_LOAD = 0x40
        BASE_ADDR_SET = 0x42
        BASE_ADDR_STORE = 0x44
        PTR_ADDR_LOAD = 0x48
        PTR_ADDR_SET = 0x4A
        PTR_ADDR_STORE = 0x4C
        PTR_GET_NEXT = 0x4E
        REPEAT_SET = 0x60
        REPEAT_EXEC = 0x62
        RETURN = 0x64
        GOTO = 0x66
        GOSUB = 0x68
        GECKO_REG_SET = 0x80
        GECKO_REG_LOAD = 0x82
        GECKO_REG_STORE = 0x84
        GECKO_REG_OPERATE_I = 0x86
        GECKO_REG_OPERATE_I = 0x88
        MEMCPY_1 = 0x8A
        MEMCPY_2 = 0x8C
        GECKO_IF_EQ_16 = 0xA0
        GECKO_IF_NEQ_16 = 0xA2
        GECKO_IF_GT_16 = 0xA4
        GECKO_IF_LT_16 = 0xA6
        COUNTER_IF_EQ_16 = 0xA8
        COUNTER_IF_NEQ_16 = 0xAA
        COUNTER_IF_GT_16 = 0xAC
        COUNTER_IF_LT_16 = 0xAE
        ASM_EXECUTE = 0xC0
        ASM_INSERT = 0xC2
        ASM_INSERT_L = 0xC4
        WRITE_BRANCH = 0xC6
        SWITCH = 0xCC
        ADDR_RANGE_CHECK = 0xCE
        TERMINATE = 0xE0
        ENDIF = 0xE2
        EXIT = 0xF0
        ASM_INSERT_XOR = 0xF2
        BRAINSLUG_SEARCH = 0xF6

    @staticmethod
    def int_to_type(id: int) -> Type:
        return GeckoCode.Type(id & 0xEE)

    @staticmethod
    def is_ifblock(_type: Type) -> bool:
        return _type in {
            GeckoCode.Type.IF_EQ_32,
            GeckoCode.Type.IF_NEQ_32,
            GeckoCode.Type.IF_GT_32,
            GeckoCode.Type.IF_LT_32,
            GeckoCode.Type.IF_EQ_16,
            GeckoCode.Type.IF_NEQ_16,
            GeckoCode.Type.IF_GT_16,
            GeckoCode.Type.IF_LT_16,
            GeckoCode.Type.GECKO_IF_EQ_16,
            GeckoCode.Type.GECKO_IF_NEQ_16,
            GeckoCode.Type.GECKO_IF_GT_16,
            GeckoCode.Type.GECKO_IF_LT_16,
            GeckoCode.Type.COUNTER_IF_EQ_16,
            GeckoCode.Type.COUNTER_IF_NEQ_16,
            GeckoCode.Type.COUNTER_IF_GT_16,
            GeckoCode.Type.COUNTER_IF_LT_16,
            GeckoCode.Type.BRAINSLUG_SEARCH
        }

    @staticmethod
    def is_multiline(_type) -> bool:
        return _type in {
            GeckoCode.Type.WRITE_STR,
            GeckoCode.Type.WRITE_SERIAL,
            GeckoCode.Type.ASM_EXECUTE,
            GeckoCode.Type.ASM_INSERT,
            GeckoCode.Type.ASM_INSERT_L,
            GeckoCode.Type.ASM_INSERT_XOR,
            GeckoCode.Type.BRAINSLUG_SEARCH
        }

    @staticmethod
    def is_preprocess_allowed(_type) -> bool:
        return _type in {
            GeckoCode.Type.WRITE_8,
            GeckoCode.Type.WRITE_16,
            GeckoCode.Type.WRITE_32,
            GeckoCode.Type.WRITE_STR,
            GeckoCode.Type.WRITE_SERIAL,
            GeckoCode.Type.WRITE_BRANCH
        }

    def __init__(self):
        raise InvalidGeckoCodeError(
            f"Cannot instantiate abstract type {self.__class__.__name__}")

    def __len__(self):
        return 0

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> Any:
        raise IndexError

    def __setitem__(self, index: int, value: Any):
        raise IndexError

    @property
    def children(self) -> List["GeckoCode"]:
        return []

    @property
    def codetype(self) -> Type:
        return None

    @property
    def value(self) -> Union[int, bytes]:
        return None

    @value.setter
    def value(self, value: Union[int, bytes]):
        pass

    def add_child(self, child: "GeckoCode"):
        pass

    def remove_child(self, child: "GeckoCode"):
        pass

    def virtual_length(self) -> int:
        return 0

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        return False


class Write8(GeckoCode):
    def __init__(self, value: Union[int, bytes], repeat: int = 0, address: int = 0x80000000, isPointer: bool = False):
        self.value = value
        self.address = address
        self.repeat = repeat
        self.isPointer = isPointer

    def __len__(self):
        return 8

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> int:
        if index != 0:
            raise IndexError(
                f"Index [{index}] is beyond the virtual code size")
        return self.value

    def __setitem__(self, index: int, value: Union[int, bytes]):
        if index != 0:
            raise IndexError(
                f"Index [{index}] is beyond the virtual code size")
        elif isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} to the data of {self.__class__.__name__}")

        self.value = value

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.WRITE_8

    @property
    def value(self) -> int:
        return self._value & 0xFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self._value = value & 0xFF

    def virtual_length(self) -> int:
        return 1

    def apply(self, dol: DolFile):
        if dol.is_mapped(self.address):
            dol.seek(self.address)
            counter = self.repeat
            while counter + 1 > 0:
                dol.write(self.value.to_bytes(1, "big", signed=False))
                counter -= 1
            return True
        return False

class Write16(GeckoCode):
    def __init__(self, value: Union[int, bytes], repeat: int = 0, address: int = 0x80000000, isPointer: bool = False):
        self.value = value
        self.address = address
        self.repeat = repeat
        self.isPointer = isPointer

    def __len__(self):
        return 8

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> int:
        if index != 0:
            raise IndexError(
                f"Index [{index}] is beyond the virtual code size")
        return self.value

    def __setitem__(self, index: int, value: Union[int, bytes]):
        if index != 0:
            raise IndexError(
                f"Index [{index}] is beyond the virtual code size")
        elif isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} to the data of {self.__class__.__name__}")

        self.value = value

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.WRITE_16

    @property
    def value(self) -> int:
        return self._value & 0xFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self._value = value & 0xFFFF

    def virtual_length(self) -> int:
        return 1

    def apply(self, dol: DolFile):
        if dol.is_mapped(self.address):
            dol.seek(self.address)
            counter = self.repeat
            while counter + 1 > 0:
                dol.write(self.value.to_bytes(2, "big", signed=False))
                counter -= 1
            return True
        return False

class Write32(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0x80000000, isPointer: bool = False):
        self.value = value
        self.address = address
        self.isPointer = isPointer

    def __len__(self):
        return 8

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> int:
        if index != 0:
            raise IndexError(
                f"Index [{index}] is beyond the virtual code size")
        return self.value

    def __setitem__(self, index: int, value: Union[int, bytes]):
        if index != 0:
            raise IndexError(
                f"Index [{index}] is beyond the virtual code size")
        elif isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} to the data of {self.__class__.__name__}")

        self.value = value

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.WRITE_32

    @property
    def value(self) -> int:
        return self._value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self._value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1

    def apply(self, dol: DolFile):
        if dol.is_mapped(self.address):
            dol.seek(self.address)
            dol.write(self.value.to_bytes(4, "big", signed=False))
            return True
        return False

class WriteString(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0x80000000, isPointer: bool = False):
        self.value = value
        self.address = address
        self.isPointer = isPointer

    def __len__(self):
        return 8 + len(self.value)

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> bytes:
        return self.value[index]

    def __setitem__(self, index: int, value: Union[int, bytes]):
        if isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} to the data of {self.__class__.__name__}")
        self.value[index] = value

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.WRITE_STR

    @property
    def value(self) -> bytes:
        return self._value

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, int):
            value = (value & 0xFFFFFFFF).to_bytes(4, "big", signed=False)
        self._value = value

    def virtual_length(self) -> int:
        return ((len(self) + 7) & -0x8) >> 3

    def apply(self, dol: DolFile) -> bool:
        if dol.is_mapped(self.address):
            dol.seek(self.address)
            dol.write(self.value)
            return True
        return False
    
class WriteSerial(GeckoCode):
    def __init__(self, value: Union[int, bytes], repeat: int = 0, address: int = 0x80000000, isPointer: bool = False,
                 valueSize: int = 2, addrInc: int = 4, valueInc: int = 0):
        self.value = value
        self.valueInc = valueInc
        self.valueSize = valueSize
        self.address = address
        self.addressInc = addrInc
        self.repeat = repeat
        self.isPointer = isPointer

    def __len__(self):
        return 16

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> Tuple[int, int]:
        if index >= self.repeat:
            raise IndexError(
                f"Index [{index}] is beyond the virtual code size")
        elif index < 0:
            index += self.repeat + 1

        return (self.address + self.addressInc*index,
                self.value + self.valueInc*index)

    def __setitem__(self, index: int, value: Any):
        if index != 0:
            raise IndexError(
                f"Index [{index}] is beyond the virtual code size")
        elif isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} to the data of {self.__class__.__name__}")

        self.value = value

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.WRITE_SERIAL

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, int):
            value = (value & 0xFFFFFFFF).to_bytes(4, "big", signed=False)
        self._value = value

    def virtual_length(self) -> int:
        return 2

    def apply(self, dol: DolFile) -> bool:
        if dol.is_mapped(self.address):
            for addr, value in self:
                dol.seek(addr)
                dol.write(value)
            return True
        return False

    """
    try:
        if codetype.hex().startswith("2") or codetype.hex().startswith("3"):
            skipcodes += 1

        elif codetype.startswith(b"\xE0"):
            skipcodes -= 1

        elif codetype.startswith(b"\xF0"):
            codelist += b"\xF0\x00\x00\x00\x00\x00\x00\x00"
            break

        self._rawData.seek(-8, 1)
        codelist += self._rawData.read(
            GCT.determine_codelength(codetype, info))

    except (RuntimeError, UnmappedAddressError):
        self._rawData.seek(-8, 1)
        codelist += self._rawData.read(
            GCT.determine_codelength(codetype, info))
    """

    """ --------------- """

    """
    def add_child(self, child: "GeckoCode"):
        if self.is_ifblock():
            raise InvalidGeckoCodeError(
                "Non IF type code can't contain children")
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        if self.is_ifblock():
            raise InvalidGeckoCodeError(
                "Non IF type code can't contain children")
        self._children.remove(child)

    def virtual_length(self) -> int:
        if self.is_multiline():
            return (len(self) >> 3) + 1
        elif self.is_ifblock():
            return len(self.children) + 1
        else:
            return 1

    def populate_from_bytes(self, f: IO):
        while metadata := f.read(4):
            info = self._rawData.read(4)
            address = 0x80000000 | (int.from_bytes(
                metadata, byteorder="big", signed=False) & 0x1FFFFFF)
            codetype = (int.from_bytes(
                metadata, "big", signed=False) >> 24) & 0xFF
            isPointerType = (codetype & 0x10 != 0)

            if (codetype & 0xEF) <= 0x0F:
                self.add_child(GeckoCode(GeckoCode.Type.WRITE,
                                         info, address, isPointerType))
            elif (codetype & 0xEF) <= 0x2F:
                ifBlock = GeckoCode(GeckoCode.Type.IF, info,
                                    address, isPointerType)
                ifBlock.populate_from_bytes(f)
                self.add_child(GeckoCode(GeckoCode.Type.IF,
                                         info, address, isPointerType))
            elif (codetype & 0xEF) <= 0xC5:
                self.add_child(GeckoCode(GeckoCode.Type.ASM,
                                         info, address, isPointerType))
            elif (codetype & 0xEF) <= 0xC7:
                self.add_child(GeckoCode(GeckoCode.Type.BRANCH,
                                         info, address, isPointerType))
            elif (codetype & 0xEF) in {0xE0, 0xE2}:
                break

    def apply(self, dol: DolFile, preprocess: bool = True):
        if not self.is_preprocess_allowed():
            return

        if dol.is_mapped(self.address):
            dol.seek(self.address)
            if self._type in {GeckoCode.Type.WRITE_8, GeckoCode.Type.WRITE_16}:
                counter = int.from_bytes(
                    self.info, byteorder="big", signed=False)
                while counter + 1 > 0:
                    dol.write(self.data)
                    counter -= 1
            elif self._type in {GeckoCode.Type.WRITE_32, GeckoCode.Type.WRITE_STR}:
                dol.write(self.data)
            elif self._type == GeckoCode.Type.WRITE_SERIAL:
                value = int.from_bytes(
                    self.info[:4], byteorder="big", signed=False)
                _data = int.from_bytes(
                    self.info[4:6], byteorder="big", signed=False)
                size = (_data & 0x3000) >> 12
                counter = _data & 0xFFF
                addressIncrement = int.from_bytes(
                    self.info[6:8], byteorder="big", signed=False)
                valueIncrement = int.from_bytes(
                    self.info[8:12], byteorder="big", signed=False)
                while counter + 1 > 0:
                    if size == 0:
                        write_ubyte(dol, value & 0xFF)
                        dol.seek(-1, 1)
                    elif size == 1:
                        write_uint16(dol, value & 0xFFFF)
                        dol.seek(-2, 1)
                    elif size == 2:
                        write_uint32(dol, value)
                        dol.seek(-4, 1)
                    else:
                        raise ValueError(
                            "Size type {} does not match 08 codetype specs".format(size))

                    dol.seek(addressIncrement, 1)
                    value += valueIncrement
                    counter -= 1
                    if value > 0xFFFFFFFF:
                        value -= 0x100000000
            elif self._type == GeckoCode.Type.WRITE_BRANCH:
                dol.insert_branch(int.from_bytes(
                    self.info, byteorder="big", signed=False), self.address, lk=(self.address & 1) == 1)
    """
