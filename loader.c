/*Credits to riidefi for hook code, cache asm, and teaching me C*/

#define dcbst(_val) asm volatile("dcbst 0, %0" \
                                 :             \
                                 : "r"(_val))
#define dcbf(_val) asm volatile("dcbf 0, %0" \
                                :            \
                                : "r"(_val))
#define icbi(_val) asm volatile("icbi 0, %0" \
                                :            \
                                : "r"(_val))

typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
typedef int s32;
typedef short s16;
typedef char s8;
typedef u32 BOOL;
typedef u32 unk32;
enum {
    FALSE,
    TRUE
};
enum {
    NULL
};

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
    .allocsize = 0, /*This is the code allocation*/
    ._loaderSize = 0, /*This is the size of the GeckoLoader*/
    ._loaderFullSize = 0, /*This is the size of the GeckoLoader + the codelist*/
    ._codelistPointer = (struct CodeList*)0x800018F8, /*This points to where the codelist address is set in the codehandler*/
    ._wiiVIHook = { 0x7CE33B78, 0x38870034, 0x38A70038, 0x38C7004C },
    ._gcnVIHook = { 0x7C030034, 0x38830020, 0x5485083C, 0x7C7F2A14, 0xA0030000, 0x7C7D2A14, 0x20A4003F, 0xB0030000 },
};

const u32* MEM1_START = 0x80000000;
const u32* MEM1_END = 0x817FFF00;
const u32 CODEHANDLER_START = 0x800018A8;

static inline void flushAddr(void* addr)
{
    dcbf(addr);
    icbi(addr);
}

static inline void directWrite(u32* addr, u32 value)
{
    addr[0] = value;
    flushAddr(addr);
}

static inline void directBranchEx(void* addr, void* ptr, BOOL lk)
{
    directWrite((u32*)(addr), ((((u32)(ptr) - (u32)(addr)) & 0x3ffffff) | 0x48000000 | !!lk)); /*This constructs a branch instruction. &TO = ((TO - FROM) & MAX_OFFSET) | BRANCH_TYPE | !!isLink*/
}

void (*_init_registers)(void) = &gInfo; /*Dummy, replace this with the address of the game entry after compile*/
void (*_codeHandler)(void) = &gInfo; /*Dummy, replace this with the address of the codehandler after compile*/

static inline u32* findFunction(u32* gcnHook, u32* wiiHook, u32 range, BOOL isWii)
{
    u32* hookData;
    u32 arrayLength;

    if (isWii) /*If the game is built for the Wii, set the hookdata to be the Wii variant*/
    {
        hookData = wiiHook;
        arrayLength = sizeof(wiiHook) / sizeof(u32);
    } else /*The game is built for the GCN, set the hookdata to be the GCN variant*/
    {
        hookData = gcnHook;
        arrayLength = sizeof(gcnHook) / sizeof(u32);
    }
    u32 index = 0;
    for (u32 i = 0; (u32)&MEM1_START[i] < (u32)MEM1_START + range; ++i) /*Loop through the games RAM, make sure we don't find our own hook data by accident*/
    {
        if (MEM1_START[i] == hookData[index]) /*If the data matches, increase the index counter and continue search, else set index to 0 and continue searching*/
            ++index;
        else
            index = 0;
        if (index >= (arrayLength - 1) && ((u32)&MEM1_START[i] < (u32)&gInfo || (u32)&MEM1_START[i] > (u32)&gInfo + 0x1000)) /*If the data has matched the whole array, return the address of the match*/
        {
            return &MEM1_START[i];
        }
    }
    return NULL;
}

void hookFunction(u32* start, u32 hookInstruction, u32 hookTo, BOOL isLink)
/*Call this after findFunction, finds the address of the first instance of value hookInstruction, and hooks it to the pointer hookTo*/
{
    int i = 0;
    while (start[i] != hookInstruction) {
        ++i;
    }
    directBranchEx((u32*)(&start[i]), (void*)(hookTo), isLink);
}

static inline void setHeap(struct DiscInfo* discResources, struct Info* infoPointer, BOOL isWii)
/*Reallocate the games internal memory heap based on the console the game is for, to make space for our codes*/
{
    if (isWii) {
        discResources->mHeapPointer = (u32*)(u32)discResources->mWiiHeap - infoPointer->allocsize;
        discResources->mWiiHeap = (u32)discResources->mHeapPointer;
    } else {
        discResources->mHeapPointer = (u32*)(u32)discResources->mHeapPointer - infoPointer->allocsize;
    }
}

BOOL initMods(struct DiscInfo* discResources)
{
    struct Info* infoPointer = &gInfo;
    const u32* geckoPointerInit = (u32*)(MEM1_START + 0x18F8);
    s32 sizeDiff = infoPointer->_loaderFullSize - infoPointer->_loaderSize; /*Calculate size of codelist*/
    const u32* sourcePointer = (u32*)(infoPointer);

    if (!infoPointer->_codelistPointer)
        return FALSE; /*Pointer is null*/
    else {
        setHeap(discResources, infoPointer, (discResources->mWiiMagic != 0)); /*Reallocate the internal heap*/
        if (infoPointer->_loaderFullSize == 0 || infoPointer->_loaderSize == 0 || sizeDiff <= 0)
            return FALSE; /*Invalid values*/
        else {
            while (sizeDiff > 0) /*Copy codelist to the new allocation*/
            {
                sizeDiff = sizeDiff - 4;
                discResources->mHeapPointer[sizeDiff / 4] = sourcePointer[sizeDiff / 4];
            }
            infoPointer->_codelistPointer->mUpperBase = ((u32)discResources->mHeapPointer >> 16) & 0xFFFF; /*Change upper codelist pointer to the new address in the allocation*/
            infoPointer->_codelistPointer->mLowerOffset = (u32)(discResources->mHeapPointer) & 0xFFFF; /*Change lower codelist pointer to the new address in the allocation*/
            flushAddr(&infoPointer->_codelistPointer->mUpperBase);
            flushAddr(&infoPointer->_codelistPointer->mLowerOffset);

            u32* functionAddr = findFunction(infoPointer->_gcnVIHook, infoPointer->_wiiVIHook, (MEM1_END - MEM1_START), (discResources->mWiiMagic != 0));
            if (functionAddr) {
                hookFunction(functionAddr, 0x4E800020, CODEHANDLER_START, FALSE);
                return TRUE;
            }
        }
    }
}

int main()
{
    struct DiscInfo* discResources = (struct DiscInfo*)MEM1_START;
    if (discResources->mWiiMagic || discResources->mGCNMagic) {
        if (initMods(discResources) == TRUE)
            (*_codeHandler)(); /*Call the codehandler if successful*/
    }
    (*_init_registers)(); /*Call the game start*/
}
