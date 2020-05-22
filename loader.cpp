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

#define call(addr) ((void (*)(...))addr)
#define MEM1_START 0x80000000
#define MEM1_END 0x81800000
#define CODEHANDLER 0x800018A8
#define GCT_MAGIC 0x00D0C0DE

typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
typedef int s32;
typedef short s16;
typedef char s8;

__attribute__((noreturn)) int main();

struct Info {
    const u32 allocsize;
    const u32 loaderSize;
    const u32 loaderFullSize;
    struct CodeList* codelistPointer;
    const u32 wiiVIHook[4];
    const u32 gcnVIHook[8];
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
    const u8 _00[12];
    const u32 mWiiMagic;
    const u32 mGCNMagic;
    const u32 _01[2];
    u32 mRAMSize;
    const u32 _02[2];
    u32* mHeapPointer;
    u32 mHeapMirror;
    u32 mFstSize;
    u32 mData[0x30D0 / 4];
    u32 mWiiHeap;
};

Info gpModInfo = {
    0, /*This is the code allocation*/
    0, /*This is the size of the GeckoLoader*/
    0, /*This is the size of the GeckoLoader + the codelist*/
    (CodeList*)0x800018F8, /*This points to where the codelist address is set in the codehandler*/
    { 0x7CE33B78, 0x38870034, 0x38A70038, 0x38C7004C },
    { 0x7C030034, 0x38830020, 0x5485083C, 0x7C7F2A14, 0xA0030000, 0x7C7D2A14, 0x20A4003F, 0xB0030000 },
};

DiscInfo* gpDiscResources = (DiscInfo*)MEM1_START;

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
static inline void directBranchEx(void* addr, void* ptr, bool lk)
{
    directWrite((u32*)(addr), ((((u32)(ptr) - (u32)(addr)) & 0x3ffffff) | 0x48000000 | !!lk));
}

static inline u32* findArrayInstance(u32* start, const u32 end, u32 arrayLength, const u32* hookData)
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
        if (index >= (arrayLength) && ((u32)&start[i] < (u32)&gpModInfo || (u32)&start[i] > (u32)&gpModInfo + sizeof(Info)))
            return (u32*)&start[i];
    }
    return nullptr;
}

static inline u32* findU32Instance(u32* start, u32 end, u32 hookData)
{
    for (u32 i = 0; (u32)&start[i] < end; ++i) {
        if (start[i] == hookData) {
            return (u32*)&start[i];
        }
    }
    return nullptr;
}

/*Find VI hook for Game*/
static inline u32* findVIHook(u32* start, const u32 end)
{
    const u32* hookData;
    u32 arrayLength;

    /*If the game is built for the Wii, set the hookdata to be the Wii variant*/
    if (gpDiscResources->mWiiMagic) {
        hookData = (const u32*)gpModInfo.wiiVIHook;
        arrayLength = sizeof(gpModInfo.wiiVIHook) / sizeof(u32);
    } else /*The game is built for the GCN, set the hookdata to be the GCN variant*/
    {
        hookData = (const u32*)gpModInfo.gcnVIHook;
        arrayLength = sizeof(gpModInfo.gcnVIHook) / sizeof(u32);
    }
    return findArrayInstance(start, end, arrayLength, hookData);
}

/*Call this after findFunction, finds the address of the first instance
of value hookInstruction, and hooks it to the pointer hookTo*/
static inline void hookFunction(u32* start, u32 hookInstruction, u32 hookTo, bool isLink)
{
    int i = 0;
    while (start[i] != hookInstruction) {
        ++i;
    }
    directBranchEx((u32*)(&start[i]), (void*)(hookTo), isLink);
}

/*Reallocate the games internal memory heap based on the console
the game is for, to make space for our codes*/
static inline void setHeap(u32 alloc)
{
    if (gpDiscResources->mWiiMagic) {
        gpDiscResources->mHeapPointer = (u32*)((u32)gpDiscResources->mWiiHeap - alloc);
        gpDiscResources->mWiiHeap = (u32)gpDiscResources->mHeapPointer;
    } else {
        gpDiscResources->mHeapPointer = (u32*)((u32)gpDiscResources->mHeapPointer - alloc);
    }
}

static inline void memCopy(u32* to, u32* from, s32 size)
{
    for (s32 i = 0; i < size; ++i) {
        *to++ = *from++;
    }
}

static inline bool initMods(DiscInfo* gpDiscResources)
{
    setHeap(gpModInfo.allocsize); /*Reallocate the internal heap*/

    /*Copy codelist to the new allocation*/
    memCopy(gpDiscResources->mHeapPointer, findU32Instance((u32*)&gpModInfo, MEM1_END, GCT_MAGIC), (gpModInfo.loaderFullSize - gpModInfo.loaderSize) / 4);

    /*Change codelist pointer to the new address in the allocation*/
    gpModInfo.codelistPointer->mUpperBase = ((u32)gpDiscResources->mHeapPointer >> 16) & 0xFFFF;
    gpModInfo.codelistPointer->mLowerOffset = (u32)(gpDiscResources->mHeapPointer) & 0xFFFF;

    /*Update the cache, so that the instructions fully update*/
    flushAddr(&gpModInfo.codelistPointer->mBaseASM);

    u32* functionAddr = findVIHook((u32*)MEM1_START, MEM1_END);

    if (functionAddr == nullptr)
        return false;

    hookFunction(functionAddr, 0x4E800020, CODEHANDLER, false);
    return true;
}

int main()
{
    if ((gpDiscResources->mWiiMagic || gpDiscResources->mGCNMagic) && initMods(gpDiscResources) == true)
        call(CODEHANDLER)(); /*Call the codehandler if successful*/

    call(0xDEADBEEF)(); /*Call the game start*/
}
