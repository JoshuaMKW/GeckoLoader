/*Credits to riidefi for hook code, cache asm, and teaching me C*/

#define dcbst(_val)  asm volatile("dcbst 0, %0" : : "r" (_val))
#define dcbf(_val)  asm volatile("dcbf 0, %0" : : "r" (_val))
#define icbi(_val)  asm volatile("icbi 0, %0" : : "r" (_val))

typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
typedef int BOOL;
typedef u32 unk32;
enum { FALSE, TRUE };
enum { NULL };

struct Info {
    u32 allocsize;
    u32 _loaderSize;
    u32 _loaderFullSize;
    struct CodeList* _codelistPointer;
    u32 _wiiVIHook[4];
    u32 _gcnVIHook[8];
};

struct CodeList {
    u16 mBaseASM;
    u16 mUpperBase;
    u16 mOffsetASM;
    u16 mLowerOffset;
};

struct DiscInfo {
    u8 mDiscID;
    u16 mGameCode;
    u8 mRegionCode;
    u16 mMakerCode;
    u8 mDiscNumber;
    u8 mDiscVersion;
    u8 mAudioStreaming;
    u8 mStreamBufferSize;
    u8 mUnknown[12];
    u32 mWiiMagic;
    u32 mGCNMagic;
    u32 mUnknown2[2];
    u32 mRAMSize;
    u32 mUnknown3[2];
    u32* mHeapPointer;
    u32 mHeapMirror;
    u32 mFstSize;
    u32 mData[(0x3110 - 0x40) / 4];
    u32 mWiiHeap;
};

struct Info gInfo = {
    .allocsize = 0, //Set to ASCII HEAP in bin file after compiling if using main.py
    ._loaderSize = 0, //Set to ASCII LSIZ in bin file after compiling if using main.py
    ._loaderFullSize = 0, //Set to ASCII FSIZ in bin file after compiling if using main.py
    ._codelistPointer = (struct CodeList*)0x800018F8,
    ._wiiVIHook = {0x7CE33B78, 0x38870034,
		   0x38A70038, 0x38C7004C},
    ._gcnVIHook = {0x7C030034, 0x38830020,
		   0x5485083C, 0x7C7F2A14,
		   0xA0030000, 0x7C7D2A14,
		   0x20A4003F, 0xB0030000},
};

static inline void flushAddr(void* addr)
{
   	dcbf(addr);
    	icbi(addr);
}

static inline void directWrite(u32* addr, u32 ptr) {
    	addr[0] = ptr;
    	flushAddr(addr);
}

static inline void directBranchEx(void* addr, void* ptr, BOOL lk) {
    	directWrite((u32*)(addr),
    	((((u32)(ptr) - (u32)(addr)) & 0x3ffffff) | 0x48000000 | !!lk));
}

void (*_init_registers)(void) = &gInfo; //Set to game entry address. ASCII HEAP in bin file after compiling if using main.py
void (*_codeHandler)(void) = &gInfo; //Set to codehandler entry address. Set to 800018A8 in bin file after compiling

static inline u32* findFunction(u32* hookData, u32* start, u32 end, u32 arrayLength) {
	u32 index = 0;
	for (u32 i = 0; (u32)&start[i] < end; ++i) {
	    if (start[i] == hookData[index]) index = index + 1;
	    else index = 0;
	    if (index >= (arrayLength - 1)) {
            	if ((u32)&start[i] < &gInfo || (u32)&start[i] > (u32)&gInfo + 0x100){
                    return &start[i];
                }
	    }
	}
	return NULL;
}

void hookFunction(u32* start, u32 hookInstruction, u32 hookTo) {
	int i = 0;
	while (start[i] != hookInstruction) {
		++i;
	}
	directBranchEx((u32*)(&start[i]), (void*)(hookTo), FALSE);
}

static inline void overwriteValue(u32* addr, u32 newValue) {
    addr[0] = newValue;
    flushAddr(&addr[0]);
}

void initMods(struct DiscInfo* baseAddress) {

	struct Info* infoPointer = &gInfo;
	const u32* geckoPointerInit = (u32*)(u32)baseAddress + 0x18F8;
	u32 sizeDiff = infoPointer->_loaderFullSize - infoPointer->_loaderSize;
	const u32* sourcePointer = (u32*)(infoPointer);

	if (infoPointer->_codelistPointer) {
		if (baseAddress->mWiiMagic) {
			baseAddress->mHeapPointer = (u32)baseAddress->mWiiHeap - infoPointer->allocsize;
			baseAddress->mWiiHeap = (u32)baseAddress->mHeapPointer;
		}
		else if(baseAddress->mGCNMagic) {
			baseAddress->mHeapPointer = (u32)baseAddress->mHeapPointer - infoPointer->allocsize;
		}

		if (infoPointer->_loaderFullSize > 0 && infoPointer->_loaderSize > 0) {
			while (sizeDiff > 0) {
				sizeDiff = sizeDiff - 4;
				baseAddress->mHeapPointer[sizeDiff / 4] = sourcePointer[sizeDiff / 4];
			}
			infoPointer->_codelistPointer->mUpperBase = ((u32)baseAddress->mHeapPointer >> 16) & 0xFFFF;
			infoPointer->_codelistPointer->mLowerOffset = (u32)(baseAddress->mHeapPointer) & 0xFFFF;
			flushAddr(&infoPointer->_codelistPointer->mUpperBase);
			flushAddr(&infoPointer->_codelistPointer->mLowerOffset);

		        u32* functionAddr;
		        if (baseAddress->mWiiMagic) {
			    functionAddr = findFunction((u32*)infoPointer->_wiiVIHook, (u32*)baseAddress, 0x817FFF00, 0x4);
		        }
		        else {
			    functionAddr = findFunction((u32*)infoPointer->_gcnVIHook, (u32*)baseAddress, 0x817FFF00, 0x8);
		        }
			if (functionAddr) {
				hookFunction(functionAddr, 0x4E800020, 0x800018A8);
			}
		}
	}
}

int main() {
    struct DiscInfo* baseAddress = (struct DiscInfo*)0x80000000;
    if (baseAddress->mWiiMagic || baseAddress->mGCNMagic) {
	initMods(baseAddress);
    	(*_codeHandler)(); //Call codehandler
    }
    (*_init_registers)(); //Call game entry "_init_registers"
}
