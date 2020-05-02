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

#define callFunction(addr) ((void (*)())addr)()

#define FALSE 0
#define TRUE 1
#define NULL 0

typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
typedef int s32;
typedef short s16;
typedef char s8;
typedef u32 BOOL;
typedef u32 unk32;

__attribute__((noreturn)) int main();

enum {
    MEM1_START = 0x80000000,
    MEM1_END = 0x81800000,
    CODEHANDLER_ENTRY = 0x800018A8,
    GAME_ENTRY = 0xDEADBEEF,
    GCT_MAGIC = 0x00D0C0DE
};

struct Info {
    const u32 allocsize;
    const u32 _loaderSize;
    const u32 _loaderFullSize;
    struct CodeList* _codelistPointer;
    const u32 _wiiVIHook[4];
    const u32 _gcnVIHook[8];
    const u32 otherModPointer[4];
};

struct CodeList {
    u16 mBaseASM;
    u16 mUpperBase;
    u16 mOffsetASM;
    u16 mLowerOffset;
};

struct DiscInfo {
    const u8 mDiscID;
    const u16 mGameCode;
    const u8 mRegionCode;
    const u16 mMakerCode;
    const u8 mDiscNumber;
    const u8 mDiscVersion;
    const u8 mAudioStreaming;
    const u8 mStreamBufferSize;
    const u8 mUnknown[12];
    const u32 mWiiMagic;
    const u32 mGCNMagic;
    const u32 mUnknown2[2];
    u32 mRAMSize;
    const u32 mUnknown3[2];
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

//struct Info* infoPointer = &gInfo;

static inline void flushAddr(void* addr)
{
    dcbf(addr);
    icbi(addr);
}

static inline void directWrite(u32* addr, u32 value)
{
    *addr = value;
    flushAddr(addr);
}

/*This constructs a branch instruction. &TO = ((TO - FROM) & MAX_OFFSET) | BRANCH_TYPE | !!isLink*/
static inline void directBranchEx(void* addr, void* ptr, BOOL lk)
{
    directWrite((u32*)(addr), ((((u32)(ptr) - (u32)(addr)) & 0x3ffffff) | 0x48000000 | !!lk));
}

static inline u32* findArrayInstance(u32* start, const u32 end, const u32 arrayLength, const u32* hookData)
{
    u32 index = 0;

    /*Loop through the games RAM, make sure we don't find our own hook data by accident*/
    for (u32 i = 0; (u32)&start[i] < end; ++i) {
        /*If the data matches, increase the index counter and continue search,
		else set index to 0 and continue searching*/
        if (start[i] == hookData[index])
            ++index;
        else
            index = 0;

        /*If the data has matched the whole array, return the address of the match*/
        if (index > (arrayLength) && ((u32)&start[i] < (u32)&gInfo || (u32)&start[i] > (u32)&gInfo + sizeof(gInfo))) {
            return &start[i];
        }
    }
    return NULL;
}

static inline u32* findU32Instance(u32* start, u32 end, u32 hookData)
{
    for (u32 i = 0; (u32)&start[i] < end; ++i) {
        if (start[i] == hookData) {
            return &start[i];
        }
    }
    return NULL;
}

/*Find VI hook for Game*/
static inline u32* findVIHook(struct DiscInfo* discResources, struct Info* infoPointer, u32* start, const u32 end)
{
    const u32* hookData;
    u32 arrayLength;

    /*If the game is built for the Wii, set the hookdata to be the Wii variant*/
    if (discResources->mWiiMagic) {
        hookData = (const u32*)infoPointer->_wiiVIHook;
        arrayLength = sizeof(infoPointer->_wiiVIHook) / sizeof(u32);
    } else /*The game is built for the GCN, set the hookdata to be the GCN variant*/
    {
        hookData = (const u32*)infoPointer->_gcnVIHook;
        arrayLength = sizeof(infoPointer->_gcnVIHook) / sizeof(u32);
    }
    return findArrayInstance(start, end, (const u32)arrayLength, hookData);
}

/*Call this after findFunction, finds the address of the first instance
of value hookInstruction, and hooks it to the pointer hookTo*/
static inline void hookFunction(volatile u32* start, u32 hookInstruction, u32 hookTo, BOOL isLink)
{
    int i = 0;
    while (start[i] != hookInstruction) {
        ++i;
    }
    directBranchEx((u32*)(&start[i]), (void*)(hookTo), isLink);
}

/*Reallocate the games internal memory heap based on the console
the game is for, to make space for our codes*/
static inline void setHeap(struct DiscInfo* discResources, u32 alloc)
{
    if (discResources->mWiiMagic) {
        discResources->mHeapPointer = (u32*)((u32)discResources->mWiiHeap - alloc);
        discResources->mWiiHeap = (u32)discResources->mHeapPointer;
    } else {
        discResources->mHeapPointer = (u32*)((u32)discResources->mHeapPointer - alloc);
    }
}

static inline void memCopy(u32* to, u32* from, s32 size)
{
    for (s32 i = 0; i < size; ++i) {
        to[i] = from[i];
    }
}

static inline BOOL initMods(struct DiscInfo* discResources)
{
    setHeap(discResources, gInfo.allocsize); /*Reallocate the internal heap*/
    s32 sizeDiff = (gInfo._loaderFullSize - gInfo._loaderSize) / 4; /*Calculate size of codelist*/

    /*Copy codelist to the new allocation*/
    memCopy(discResources->mHeapPointer, findU32Instance((u32*)&gInfo, MEM1_END, GCT_MAGIC), sizeDiff);

    /*Change codelist pointer to the new address in the allocation*/
    gInfo._codelistPointer->mUpperBase = ((u32)discResources->mHeapPointer >> 16) & 0xFFFF;
    gInfo._codelistPointer->mLowerOffset = (u32)(discResources->mHeapPointer) & 0xFFFF;

    /*Update the cache, so that the instructions fully update*/
    flushAddr(&gInfo._codelistPointer->mBaseASM);

    volatile u32* functionAddr = findVIHook(discResources, &gInfo, (u32*)MEM1_START, MEM1_END);
    if (functionAddr == NULL) return FALSE;
    hookFunction(functionAddr, 0x4E800020, CODEHANDLER_ENTRY, FALSE);
    return TRUE;
}

int main()
{
    struct DiscInfo* discResources = (struct DiscInfo*)MEM1_START;
    if (discResources->mWiiMagic || discResources->mGCNMagic) {
        if (initMods(discResources) == TRUE) {
            callFunction(CODEHANDLER_ENTRY); /*Call the codehandler if successful*/
        }
    }
    callFunction(GAME_ENTRY); /*Call the game start*/
}
