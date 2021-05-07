from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Generator, IO, List, Tuple, Union

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
        BASE_GET_NEXT = 0x46
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
        GECKO_REG_OPERATE = 0x88
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

    class ArithmeticType(Enum):
        ADD = 0
        MUL = 1
        OR = 2
        AND = 3
        XOR = 4
        SLW = 5
        SRW = 6
        ROL = 7
        ASR = 8
        FADDS = 9
        FMULS = 10

    @staticmethod
    def int_to_type(id: int) -> Type:
        return GeckoCode.Type(id & 0xEE)

    @staticmethod
    def type_to_int(ty: Type) -> int:
        return ty.value

    @staticmethod
    def is_ifblock(_type: Union[Type, "GeckoCode"]) -> bool:
        if isinstance(_type, GeckoCode):
            _type = _type.codetype

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
    def is_multiline(_type: Union[Type, "GeckoCode"]) -> bool:
        if isinstance(_type, GeckoCode):
            _type = _type.codetype

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
    def is_preprocess_allowed(_type: Union[Type, "GeckoCode"]) -> bool:
        if isinstance(_type, GeckoCode):
            _type = _type.codetype

        return _type in {
            GeckoCode.Type.WRITE_8,
            GeckoCode.Type.WRITE_16,
            GeckoCode.Type.WRITE_32,
            GeckoCode.Type.WRITE_STR,
            GeckoCode.Type.WRITE_SERIAL,
            GeckoCode.Type.WRITE_BRANCH
        }

    @staticmethod
    def typeof(code: "GeckoCode") -> Type:
        return code.codetype

    @staticmethod
    def bytes_to_geckocode(f: IO) -> Generator["GeckoCode"]:
        metadata = f.read(4)
        address = 0x80000000 | (int.from_bytes(
            metadata, byteorder="big", signed=False) & 0x1FFFFFF)
        codetype = GeckoCode.int_to_type((int.from_bytes(
            metadata, "big", signed=False) >> 24) & 0xFF)
        isPointerType = (codetype & 0x10 != 0)

        if codetype == GeckoCode.Type.WRITE_8:
            info = f.read(4)
            value = int.from_bytes(info[3:], "big", signed=False)
            repeat = int.from_bytes(info[:2], "big", signed=False)
            return Write8(value, repeat, address, isPointerType)
        elif codetype == GeckoCode.Type.WRITE_16:
            info = f.read(4)
            value = int.from_bytes(info[2:], "big", signed=False)
            repeat = int.from_bytes(info[:2], "big", signed=False)
            return Write16(value, repeat, address, isPointerType)
        elif codetype == GeckoCode.Type.WRITE_32:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return Write32(value, address, isPointerType)
        elif codetype == GeckoCode.Type.WRITE_STR:
            size = int.from_bytes(f.read(4), "big", signed=False)
            return WriteString(f.read(size), address, isPointerType)
        elif codetype == GeckoCode.Type.WRITE_SERIAL:
            info = f.read(12)
            value = int.from_bytes(info[:4], "big", signed=False)
            valueSize = int.from_bytes(info[4:5], "big", signed=False) >> 4
            repeat = int.from_bytes(info[4:5], "big", signed=False) & 0xF
            addressInc = int.from_bytes(info[6:8], "big", signed=False)
            valueInc = int.from_bytes(info[8:], "big", signed=False)
            return WriteSerial(value, repeat, address, isPointerType, valueSize, addressInc, valueInc)
        elif codetype == GeckoCode.Type.IF_EQ_32:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return IfEqual32(value, address, endif=(address & 1) == 1)
        elif codetype == GeckoCode.Type.IF_NEQ_32:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return IfNotEqual32(value, address, endif=(address & 1) == 1)
        elif codetype == GeckoCode.Type.IF_GT_32:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return IfGreaterThan32(value, address, endif=(address & 1) == 1)
        elif codetype == GeckoCode.Type.IF_LT_32:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return IfLesserThan32(value, address, endif=(address & 1) == 1)
        elif codetype == GeckoCode.Type.IF_EQ_16:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return IfEqual16(value, address, endif=(address & 1) == 1)
        elif codetype == GeckoCode.Type.IF_NEQ_16:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return IfNotEqual16(value, address, endif=(address & 1) == 1)
        elif codetype == GeckoCode.Type.IF_GT_16:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return IfGreaterThan16(value, address, endif=(address & 1) == 1)
        elif codetype == GeckoCode.Type.IF_LT_16:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            return IfLesserThan16(value, address, endif=(address & 1) == 1)
        elif codetype == GeckoCode.Type.BASE_ADDR_LOAD:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            flags = int.from_bytes(metadata, "big", signed=False)
            return BaseAddressLoad(value, flags & 0x01110000, flags & 0xF, isPointerType)
        elif codetype == GeckoCode.Type.BASE_ADDR_SET:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            flags = int.from_bytes(metadata, "big", signed=False)
            return BaseAddressSet(value, flags & 0x01110000, flags & 0xF, isPointerType)
        elif codetype == GeckoCode.Type.BASE_ADDR_STORE:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            flags = int.from_bytes(metadata, "big", signed=False)
            return BaseAddressStore(value, flags & 0x00110000, flags & 0xF, isPointerType)
        elif codetype == GeckoCode.Type.BASE_GET_NEXT:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            flags = int.from_bytes(metadata, "big", signed=False)
            return BaseAddressGetNext(value)
        elif codetype == GeckoCode.Type.PTR_ADDR_LOAD:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            flags = int.from_bytes(metadata, "big", signed=False)
            return PointerAddressLoad(value, flags & 0x01110000, flags & 0xF, isPointerType)
        elif codetype == GeckoCode.Type.PTR_ADDR_SET:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            flags = int.from_bytes(metadata, "big", signed=False)
            return PointerAddressSet(value, flags & 0x01110000, flags & 0xF, isPointerType)
        elif codetype == GeckoCode.Type.PTR_ADDR_STORE:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            flags = int.from_bytes(metadata, "big", signed=False)
            return PointerAddressStore(value, flags & 0x00110000, flags & 0xF, isPointerType)
        elif codetype == GeckoCode.Type.PTR_GET_NEXT:
            info = f.read(4)
            value = int.from_bytes(info, "big", signed=False)
            flags = int.from_bytes(metadata, "big", signed=False)
            return PointerAddressGetNext(value)

    def __init__(self):
        raise InvalidGeckoCodeError(
            f"Cannot instantiate abstract type {self.__class__.__name__}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__dict__})"

    def __str__(self) -> str:
        return self.__class__.__name__

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
    def __init__(self, value: Union[int, bytes], repeat: int = 0, address: int = 0, isPointer: bool = False):
        self.value = value
        self.address = address
        self.repeat = repeat
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        if self.repeat > 0:
            return f"({intType:X}) Write byte 0x{self.value:2X} to (0x{self.address:8X} + the {addrstr}) {self.repeat + 1} times consecutively"
        else:
            return f"({intType:X}) Write byte 0x{self.value:2X} to 0x{self.address:8X} + the {addrstr}"

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
    def __init__(self, value: Union[int, bytes], repeat: int = 0, address: int = 0, isPointer: bool = False):
        self.value = value
        self.address = address
        self.repeat = repeat
        self.isPointer = isPointer

    def __len__(self):
        return 8

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        if self.repeat > 0:
            return f"({intType:X}) Write short 0x{self.value:4X} to (0x{self.address:8X} + the {addrstr}) {self.repeat + 1} times consecutively"
        else:
            return f"({intType:X}) Write short 0x{self.value:4X} to 0x{self.address:8X} + the {addrstr}"

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
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False):
        self.value = value
        self.address = address
        self.isPointer = isPointer

    def __len__(self):
        return 8

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) Write word 0x{self.value:8X} to 0x{self.address:8X} + the {addrstr}"

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
    def __init__(self, value: bytes, address: int = 0, isPointer: bool = False):
        self.value = value
        self.address = address
        self.isPointer = isPointer

    def __len__(self):
        return 8 + len(self.value)

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) Write {len(self) - 8} bytes to 0x{self.address:8X} + the {addrstr}"

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

    def __setitem__(self, index: int, value: bytes):
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
    def value(self, value: bytes):
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
    def __init__(self, value: Union[int, bytes], repeat: int = 0, address: int = 0, isPointer: bool = False,
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

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        valueType = ("byte", "short", "word")[self.valueSize]
        if self.repeat > 0:
            mapping = f"incrementing the value by {self.valueInc} and the address by {self.addressInc} each iteration"
            return f"({intType:X}) Write {valueType} 0x{self.value:8X} to (0x{self.address:8X} + the {addrstr}) {self.repeat + 1} times consecutively, {mapping}"
        else:
            return f"({intType:X}) Write {valueType} 0x{self.value:8X} to 0x{self.address:8X} + the {addrstr})"

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


class IfEqual32(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False,
                 endif: bool = False):
        self.value = value
        self.address = address
        self.endif = endif
        self.isPointer = isPointer
        self._children = []

    def __len__(self):
        return sum([len(c) for c in self])

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) If the word at address (0x{self.address:8X} + the {addrstr}) is equal to 0x{self.value:08X}, run the encapsulated codes"

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> GeckoCode:
        return self._children[index]

    def __setitem__(self, index: int, value: GeckoCode):
        if not isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} as a child of {self.__class__.__name__}")

        self._children[index] = value

    @property
    def children(self) -> List["GeckoCode"]:
        return self._children

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.IF_EQ_32

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def add_child(self, child: "GeckoCode"):
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        self._children.remove(child)

    def virtual_length(self) -> int:
        return len(self.children) + 1

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        for code in self:
            code.apply(dol)
        return True


class IfNotEqual32(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False,
                 endif: bool = False):
        self.value = value
        self.address = address
        self.endif = endif
        self.isPointer = isPointer
        self._children = []

    def __len__(self):
        return sum([len(c) for c in self])

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) If the word at address (0x{self.address:8X} + the {addrstr}) is not equal to 0x{self.value:08X}, run the encapsulated codes"

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> GeckoCode:
        return self._children[index]

    def __setitem__(self, index: int, value: GeckoCode):
        if not isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} as a child of {self.__class__.__name__}")

        self._children[index] = value

    @property
    def children(self) -> List["GeckoCode"]:
        return self._children

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.IF_NEQ_32

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def add_child(self, child: "GeckoCode"):
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        self._children.remove(child)

    def virtual_length(self) -> int:
        return len(self.children) + 1

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        for code in self:
            code.apply(dol)
        return True


class IfGreaterThan32(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False,
                 endif: bool = False):
        self.value = value
        self.address = address
        self.endif = endif
        self.isPointer = isPointer
        self._children = []

    def __len__(self):
        return sum([len(c) for c in self])

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) If the word at address (0x{self.address:8X} + the {addrstr}) is greater than 0x{self.value:08X}, run the encapsulated codes"

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> GeckoCode:
        return self._children[index]

    def __setitem__(self, index: int, value: GeckoCode):
        if not isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} as a child of {self.__class__.__name__}")

        self._children[index] = value

    @property
    def children(self) -> List["GeckoCode"]:
        return self._children

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.IF_GT_32

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def add_child(self, child: "GeckoCode"):
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        self._children.remove(child)

    def virtual_length(self) -> int:
        return len(self.children) + 1

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        for code in self:
            code.apply(dol)
        return True


class IfLesserThan32(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False,
                 endif: bool = False):
        self.value = value
        self.address = address
        self.endif = endif
        self.isPointer = isPointer
        self._children = []

    def __len__(self):
        return sum([len(c) for c in self])

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) If the word at address (0x{self.address:8X} + the {addrstr}) is lesser than 0x{self.value:08X}, run the encapsulated codes"

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> GeckoCode:
        return self._children[index]

    def __setitem__(self, index: int, value: GeckoCode):
        if not isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} as a child of {self.__class__.__name__}")

        self._children[index] = value

    @property
    def children(self) -> List["GeckoCode"]:
        return self._children

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.IF_LT_32

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def add_child(self, child: "GeckoCode"):
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        self._children.remove(child)

    def virtual_length(self) -> int:
        return len(self.children) + 1

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        for code in self:
            code.apply(dol)
        return True


class IfEqual16(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False,
                 endif: bool = False, mask: int = 0xFFFF):
        self.value = value
        self.address = address
        self.endif = endif
        self.mask = mask
        self.isPointer = isPointer
        self._children = []

    def __len__(self):
        return sum([len(c) for c in self])

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) If the short at address (0x{self.address:8X} + the {addrstr}) is equal to (0x{self.value:04X} & 0x{self.mask:04X}), run the encapsulated codes"

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> GeckoCode:
        return self._children[index]

    def __setitem__(self, index: int, value: GeckoCode):
        if not isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} as a child of {self.__class__.__name__}")

        self._children[index] = value

    @property
    def children(self) -> List["GeckoCode"]:
        return self._children

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.IF_EQ_16

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def add_child(self, child: "GeckoCode"):
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        self._children.remove(child)

    def virtual_length(self) -> int:
        return len(self.children) + 1

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        for code in self:
            code.apply(dol)
        return True


class IfNotEqual16(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False,
                 endif: bool = False, mask: int = 0xFFFF):
        self.value = value
        self.address = address
        self.endif = endif
        self.mask = mask
        self.isPointer = isPointer
        self._children = []

    def __len__(self):
        return sum([len(c) for c in self])

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) If the short at address (0x{self.address:8X} + the {addrstr}) is not equal to (0x{self.value:04X} & 0x{self.mask:04X}), run the encapsulated codes"

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> GeckoCode:
        return self._children[index]

    def __setitem__(self, index: int, value: GeckoCode):
        if not isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} as a child of {self.__class__.__name__}")

        self._children[index] = value

    @property
    def children(self) -> List["GeckoCode"]:
        return self._children

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.IF_NEQ_16

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def add_child(self, child: "GeckoCode"):
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        self._children.remove(child)

    def virtual_length(self) -> int:
        return len(self.children) + 1

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        for code in self:
            code.apply(dol)
        return True


class IfGreaterThan16(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False,
                 endif: bool = False, mask: int = 0xFFFF):
        self.value = value
        self.address = address
        self.endif = endif
        self.mask = mask
        self.isPointer = isPointer
        self._children = []

    def __len__(self):
        return sum([len(c) for c in self])

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) If the short at address (0x{self.address:8X} + the {addrstr}) is greater than (0x{self.value:04X} & 0x{self.mask:04X}), run the encapsulated codes"

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> GeckoCode:
        return self._children[index]

    def __setitem__(self, index: int, value: GeckoCode):
        if not isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} as a child of {self.__class__.__name__}")

        self._children[index] = value

    @property
    def children(self) -> List["GeckoCode"]:
        return self._children

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.IF_GT_16

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def add_child(self, child: "GeckoCode"):
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        self._children.remove(child)

    def virtual_length(self) -> int:
        return len(self.children) + 1

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        for code in self:
            code.apply(dol)
        return True


class IfLesserThan16(GeckoCode):
    def __init__(self, value: Union[int, bytes], address: int = 0, isPointer: bool = False,
                 endif: bool = False, mask: int = 0xFFFF):
        self.value = value
        self.address = address
        self.endif = endif
        self.mask = mask
        self.isPointer = isPointer
        self._children = []

    def __len__(self):
        return sum([len(c) for c in self])

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        return f"({intType:X}) If the short at address (0x{self.address:8X} + the {addrstr}) is lesser than (0x{self.value:04X} & 0x{self.mask:04X}), run the encapsulated codes"

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        try:
            return self[self._iterpos]
        except IndexError:
            raise StopIteration

    def __getitem__(self, index: int) -> GeckoCode:
        return self._children[index]

    def __setitem__(self, index: int, value: GeckoCode):
        if not isinstance(value, GeckoCode):
            raise InvalidGeckoCodeError(
                f"Cannot assign {value.__class__.__name__} as a child of {self.__class__.__name__}")

        self._children[index] = value

    @property
    def children(self) -> List["GeckoCode"]:
        return self._children

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.IF_LT_16

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def add_child(self, child: "GeckoCode"):
        self._children.append(child)

    def remove_child(self, child: "GeckoCode"):
        self._children.remove(child)

    def virtual_length(self) -> int:
        return len(self.children) + 1

    def populate_from_bytes(self, f: IO):
        pass

    def apply(self, dol: DolFile) -> bool:
        for code in self:
            code.apply(dol)
        return True


class BaseAddressLoad(GeckoCode):
    def __init__(self, value: int, flags: int = 0, register: int = 0, isPointer: bool = False):
        self.value = value
        self.flags = flags
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        flags = self.flags
        if flags == 0x000:
            return f"({intType:X}) Set the base address to the value at address [0x{self.value}]"
        elif flags == 0x001:
            return f"({intType:X}) Set the base address to the value at address [gr{self.register} + 0x{self.value}]"
        elif flags == 0x010:
            return f"({intType:X}) Set the base address to the value at address [{addrstr} + 0x{self.value}]"
        elif flags == 0x011:
            return f"({intType:X}) Set the base address to the value at address [{addrstr} + gr{self.register} + 0x{self.value}]"
        elif flags == 0x100:
            return f"({intType:X}) Add the value at address [0x{self.value}] to the base address"
        elif flags == 0x101:
            return f"({intType:X}) Add the value at address [gr{self.register} + 0x{self.value}] to the base address"
        elif flags == 0x110:
            return f"({intType:X}) Add the value at address [{addrstr} + 0x{self.value}] to the base address"
        elif flags == 0x111:
            return f"({intType:X}) Add the value at address [{addrstr} + gr{self.register} + 0x{self.value}] to the base address"

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
        return GeckoCode.Type.BASE_ADDR_LOAD

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class BaseAddressSet(GeckoCode):
    def __init__(self, value: int, flags: int = 0, register: int = 0, isPointer: bool = False):
        self.value = value
        self.flags = flags
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        flags = self.flags
        if flags == 0x000:
            return f"({intType:X}) Set the base address to the value 0x{self.value}"
        elif flags == 0x001:
            return f"({intType:X}) Set the base address to the value (gr{self.register} + 0x{self.value})"
        elif flags == 0x010:
            return f"({intType:X}) Set the base address to the value ({addrstr} + 0x{self.value})"
        elif flags == 0x011:
            return f"({intType:X}) Set the base address to the value ({addrstr} + gr{self.register} + 0x{self.value})"
        elif flags == 0x100:
            return f"({intType:X}) Add the value 0x{self.value} to the base address"
        elif flags == 0x101:
            return f"({intType:X}) Add the value (gr{self.register} + 0x{self.value}) to the base address"
        elif flags == 0x110:
            return f"({intType:X}) Add the value ({addrstr} + 0x{self.value}) to the base address"
        elif flags == 0x111:
            return f"({intType:X}) Add the value ({addrstr} + gr{self.register}) + 0x{self.value} to the base address"
        return f"({intType:X}) Invalid flag {flags}"

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
        return GeckoCode.Type.BASE_ADDR_SET

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class BaseAddressStore(GeckoCode):
    def __init__(self, value: int, flags: int = 0, register: int = 0, isPointer: bool = False):
        self.value = value
        self.flags = flags
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        flags = self.flags
        if flags == 0x000:
            return f"({intType:X}) Store the base address at address [0x{self.value}]"
        elif flags == 0x001:
            return f"({intType:X}) Store the base address at address [gr{self.register} + 0x{self.value}]"
        elif flags == 0x010:
            return f"({intType:X}) Store the base address at address [{addrstr} + 0x{self.value}]"
        elif flags == 0x011:
            return f"({intType:X}) Store the base address at address [{addrstr} + gr{self.register} + 0x{self.value}]"
        return f"({intType:X}) Invalid flag {flags}"

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
        return GeckoCode.Type.BASE_ADDR_STORE

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class BaseAddressGetNext(GeckoCode):
    def __init__(self, value: int):
        self.value = value

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype)
        return f"({intType:X}) Set the base address to be the next Gecko Code's address + {self.value}"

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
        return GeckoCode.Type.BASE_GET_NEXT

    @property
    def value(self) -> int:
        return self.value & 0xFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFF

    def virtual_length(self) -> int:
        return 1


class PointerAddressLoad(GeckoCode):
    def __init__(self, value: int, flags: int = 0, register: int = 0, isPointer: bool = False):
        self.value = value
        self.flags = flags
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        flags = self.flags
        if flags == 0x000:
            return f"({intType:X}) Set the pointer address to the value at address [0x{self.value}]"
        elif flags == 0x001:
            return f"({intType:X}) Set the pointer address to the value at address [gr{self.register} + 0x{self.value}]"
        elif flags == 0x010:
            return f"({intType:X}) Set the pointer address to the value at address [{addrstr} + 0x{self.value}]"
        elif flags == 0x011:
            return f"({intType:X}) Set the pointer address to the value at address [{addrstr} + gr{self.register} + 0x{self.value}]"
        elif flags == 0x100:
            return f"({intType:X}) Add the value at address [0x{self.value}] to the pointer address"
        elif flags == 0x101:
            return f"({intType:X}) Add the value at address [gr{self.register} + 0x{self.value}] to the pointer address"
        elif flags == 0x110:
            return f"({intType:X}) Add the value at address [{addrstr} + 0x{self.value}] to the pointer address"
        elif flags == 0x111:
            return f"({intType:X}) Add the value at address [{addrstr} + gr{self.register} + 0x{self.value}] to the pointer address"

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
        return GeckoCode.Type.PTR_ADDR_LOAD

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class PointerAddressSet(GeckoCode):
    def __init__(self, value: int, flags: int = 0, register: int = 0, isPointer: bool = False):
        self.value = value
        self.flags = flags
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        flags = self.flags
        if flags == 0x000:
            return f"({intType:X}) Set the pointer address to the value 0x{self.value}"
        elif flags == 0x001:
            return f"({intType:X}) Set the pointer address to the value (gr{self.register} + 0x{self.value})"
        elif flags == 0x010:
            return f"({intType:X}) Set the pointer address to the value ({addrstr} + 0x{self.value})"
        elif flags == 0x011:
            return f"({intType:X}) Set the pointer address to the value ({addrstr} + gr{self.register} + 0x{self.value})"
        elif flags == 0x100:
            return f"({intType:X}) Add the value 0x{self.value} to the pointer address"
        elif flags == 0x101:
            return f"({intType:X}) Add the value (gr{self.register} + 0x{self.value}) to the pointer address"
        elif flags == 0x110:
            return f"({intType:X}) Add the value ({addrstr} + 0x{self.value}) to the pointer address"
        elif flags == 0x111:
            return f"({intType:X}) Add the value ({addrstr} + gr{self.register}) + 0x{self.value} to the pointer address"
        return f"({intType:X}) Invalid flag {flags}"

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
        return GeckoCode.Type.PTR_ADDR_SET

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class PointerAddressStore(GeckoCode):
    def __init__(self, value: int, flags: int = 0, register: int = 0, isPointer: bool = False):
        self.value = value
        self.flags = flags
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        flags = self.flags
        if flags == 0x000:
            return f"({intType:X}) Store the pointer address at address [0x{self.value}]"
        elif flags == 0x001:
            return f"({intType:X}) Store the pointer address at address [gr{self.register} + 0x{self.value}]"
        elif flags == 0x010:
            return f"({intType:X}) Store the pointer address at address [{addrstr} + 0x{self.value}]"
        elif flags == 0x011:
            return f"({intType:X}) Store the pointer address at address [{addrstr} + gr{self.register} + 0x{self.value}]"
        return f"({intType:X}) Invalid flag {flags}"

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
        return GeckoCode.Type.PTR_ADDR_STORE

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class PointerAddressGetNext(GeckoCode):
    def __init__(self, value: int):
        self.value = value

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype)
        return f"({intType:X}) Set the base address to be the next Gecko Code's address + {self.value}"

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
        return GeckoCode.Type.PTR_GET_NEXT

    @property
    def value(self) -> int:
        return self.value & 0xFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFF

    def virtual_length(self) -> int:
        return 1


class SetRepeat(GeckoCode):
    def __init__(self, repeat: int = 0, b: int = 0):
        self.repeat = repeat
        self.b = b

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype)
        return f"({intType:X}) Store next code address and number of times to repeat in b{self.b}"

    def __len__(self):
        return 8

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.REPEAT_SET

    def virtual_length(self) -> int:
        return 1


class ExecuteRepeat(GeckoCode):
    def __init__(self, b: int = 0):
        self.b = b

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype)
        return f"({intType:X}) If NNNN stored in b{self.b} is > 0, it is decreased by 1 and the code handler jumps to the next code address stored in b{self.b}"

    def __len__(self):
        return 8

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.REPEAT_EXEC

    def virtual_length(self) -> int:
        return 1


class Return(GeckoCode):
    def __init__(self, flags: int = 0, b: int = 0):
        self.b = b
        self.flags = flags

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype)
        if self.flags == 0:
            return f"({intType:X}) If the code execution status is true, jump to the next code address stored in b{self.b} (NNNN in bP is not touched)"
        elif self.flags == 1:
            return f"({intType:X}) If the code execution status is false, jump to the next code address stored in b{self.b} (NNNN in bP is not touched)"
        elif self.flags == 2:
            return f"({intType:X}) Jump to the next code address stored in b{self.b} (NNNN in bP is not touched)"

    def __len__(self):
        return 8

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.RETURN

    def virtual_length(self) -> int:
        return 1


class Goto(GeckoCode):
    def __init__(self, flags: int = 0, lineOffset: int = 0):
        self.flags = flags
        self.offset = lineOffset

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype)
        if self.flags == 0:
            return f"({intType:X}) If the code execution status is true, jump to (next line of code + {self.offset} lines)"
        elif self.flags == 1:
            return f"({intType:X}) If the code execution status is false, jump to (next line of code + {self.offset} lines)"
        elif self.flags == 2:
            return f"({intType:X}) Jump to (next line of code + {self.offset} lines)"

    def __len__(self):
        return 8

    @property
    def codetype(self) -> GeckoCode.Type:
        return GeckoCode.Type.GOTO

    def virtual_length(self) -> int:
        return 1


class GeckoRegisterSet(GeckoCode):
    def __init__(self, value: int, flags: int = 0, register: int = 0, isPointer: bool = False):
        self.value = value
        self.flags = flags
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        flags = self.flags
        if flags == 0x00:
            return f"({intType:X}) Set Gecko Register {self.register} to the value 0x{self.value}"
        elif flags == 0x01:
            return f"({intType:X}) Set Gecko Register {self.register} to the value (0x{self.value} + the {addrstr})"
        elif flags == 0x10:
            return f"({intType:X}) Add the value 0x{self.value} to Gecko Register {self.register}"
        elif flags == 0x11:
            return f"({intType:X}) Add the value (0x{self.value} + the {addrstr}) to Gecko Register {self.register}"
        return f"({intType:X}) Invalid flag {flags}"

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
        return GeckoCode.Type.GECKO_REG_SET

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class GeckoRegisterLoad(GeckoCode):
    def __init__(self, value: int, flags: int = 0, register: int = 0, isPointer: bool = False):
        self.value = value
        self.flags = flags
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        flags = self.flags
        if flags == 0x00:
            return f"({intType:X}) Set Gecko Register {self.register} to the byte at address 0x{self.value}"
        elif flags == 0x10:
            return f"({intType:X}) Set Gecko Register {self.register} to the short at address 0x{self.value}"
        elif flags == 0x20:
            return f"({intType:X}) Set Gecko Register {self.register} to the word at address 0x{self.value}"
        elif flags == 0x01:
            return f"({intType:X}) Set Gecko Register {self.register} to the byte at address (0x{self.value} + the {addrstr})"
        elif flags == 0x11:
            return f"({intType:X}) Set Gecko Register {self.register} to the short at address (0x{self.value} + the {addrstr})"
        elif flags == 0x21:
            return f"({intType:X}) Set Gecko Register {self.register} to the word at address (0x{self.value} + the {addrstr})"
        return f"({intType:X}) Invalid flag {flags}"

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
        return GeckoCode.Type.GECKO_REG_LOAD

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class GeckoRegisterStore(GeckoCode):
    def __init__(self, value: int, repeat: int = 0, flags: int = 0,
                 register: int = 0, valueSize: int = 0, isPointer: bool = False):
        self.value = value
        self.valueSize = valueSize
        self.flags = flags
        self.repeat = repeat
        self.register = register
        self.isPointer = isPointer

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype) | (
            0x10 if self.isPointer else 0)
        addrstr = "pointer address" if self.isPointer else "base address"
        valueType = ("byte", "short", "word")[self.valueSize]

        flags = self.flags
        if flags > 0x21:
            return f"({intType:X}) Invalid flag {flags}"

        if self.repeat > 0:
            if flags & 0x01:
                return f"({intType:X}) Store Gecko Register {self.register}'s {valueType} to [0x{self.value} + the {addrstr}] {self.repeat + 1} times consecutively"
            else:
                return f"({intType:X}) Store Gecko Register {self.register}'s {valueType} to [0x{self.value}] {self.repeat + 1} times consecutively"
        else:
            if flags & 0x01:
                return f"({intType:X}) Store Gecko Register {self.register}'s {valueType} to [0x{self.value} + the {addrstr}]"
            else:
                return f"({intType:X}) Store Gecko Register {self.register}'s {valueType} to [0x{self.value}]"

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
        return GeckoCode.Type.GECKO_REG_STORE

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class GeckoRegisterOperateI(GeckoCode):
    def __init__(self, value: int, opType: GeckoCode.ArithmeticType, flags: int = 0, register: int = 0):
        self.value = value
        self.opType = opType
        self.register = register
        self.flags = flags

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype)
        grAccessType = f"[Gecko Register {self.register}]" if (
            self.flags & 1) != 0 else f"Gecko Register {self.register}"
        valueAccessType = f"[{self.value}]" if (
            self.flags & 0x2) != 0 else f"{self.value}"
        opType = self.opType
        if opType == GeckoCode.ArithmeticType.ADD:
            return f"({intType:X}) Add {valueAccessType} to {grAccessType}"
        elif opType == GeckoCode.ArithmeticType.MUL:
            return f"({intType:X}) Multiply {grAccessType} by {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.OR:
            return f"({intType:X}) OR {grAccessType} with {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.XOR:
            return f"({intType:X}) XOR {grAccessType} with {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.SLW:
            return f"({intType:X}) Shift {grAccessType} left by {valueAccessType} bits"
        elif opType == GeckoCode.ArithmeticType.SRW:
            return f"({intType:X}) Shift {grAccessType} right by {valueAccessType} bits"
        elif opType == GeckoCode.ArithmeticType.ROL:
            return f"({intType:X}) Rotate {grAccessType} left by {valueAccessType} bits"
        elif opType == GeckoCode.ArithmeticType.ASR:
            return f"({intType:X}) Arithmetic shift {grAccessType} right by {valueAccessType} bits"
        elif opType == GeckoCode.ArithmeticType.FADDS:
            return f"({intType:X}) Add {valueAccessType} to {grAccessType} as a float"
        elif opType == GeckoCode.ArithmeticType.FMULS:
            return f"({intType:X}) Multiply {grAccessType} by {valueAccessType} as a float"
        return f"({intType:X}) Invalid operation flag {opType}"

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
        return GeckoCode.Type.GECKO_REG_OPERATE_I

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


class GeckoRegisterOperate(GeckoCode):
    def __init__(self, otherRegister: int, opType: GeckoCode.ArithmeticType, flags: int = 0, register: int = 0):
        self.opType = opType
        self.register = register
        self.other = otherRegister
        self.flags = flags

    def __str__(self) -> str:
        intType = GeckoCode.type_to_int(self.codetype)
        grAccessType = f"[Gecko Register {self.register}]" if (
            self.flags & 1) != 0 else f"Gecko Register {self.register}"
        valueAccessType = f"[Gecko Register {self.other}]" if (
            self.flags & 0x2) != 0 else f"Gecko Register {self.other}"
        opType = self.opType
        if opType == GeckoCode.ArithmeticType.ADD:
            return f"({intType:X}) Add {valueAccessType} to {grAccessType}"
        elif opType == GeckoCode.ArithmeticType.MUL:
            return f"({intType:X}) Multiply {grAccessType} by {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.OR:
            return f"({intType:X}) OR {grAccessType} with {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.XOR:
            return f"({intType:X}) XOR {grAccessType} with {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.SLW:
            return f"({intType:X}) Shift {grAccessType} left by {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.SRW:
            return f"({intType:X}) Shift {grAccessType} right by {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.ROL:
            return f"({intType:X}) Rotate {grAccessType} left by {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.ASR:
            return f"({intType:X}) Arithmetic shift {grAccessType} right by {valueAccessType}"
        elif opType == GeckoCode.ArithmeticType.FADDS:
            return f"({intType:X}) Add {valueAccessType} to {grAccessType} as a float"
        elif opType == GeckoCode.ArithmeticType.FMULS:
            return f"({intType:X}) Multiply {grAccessType} by {valueAccessType} as a float"
        return f"({intType:X}) Invalid operation flag {opType}"

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
        return GeckoCode.Type.GECKO_REG_OPERATE

    @property
    def value(self) -> int:
        return self.value & 0xFFFFFFFF

    @value.setter
    def value(self, value: Union[int, bytes]):
        if isinstance(value, bytes):
            value = int.from_bytes(value, "big", signed=False)
        self.value = value & 0xFFFFFFFF

    def virtual_length(self) -> int:
        return 1


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
