//#include <vector>
//#include <string>

//using std::array;
//using std::memcpy;
//using std::memcmp;
//using std::memset;
//using std::string;

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
#define CODEHANDLER 0x800018A8
#define GCT_MAGIC 0x00D0C0DE

#define __start call(0x4948494C)

using u32 = unsigned int;
using u16 = unsigned short;
using u8 = unsigned char;
using s32 = int;
using s16 = short;
using s8 = char;
using f32 = float;
using f64 = double;

__attribute__((noreturn)) int main();

struct CodeList
{

  u16 mBaseASM;
  u16 mUpperBase;
  u16 mOffsetASM;
  u16 mLowerOffset;
};

struct Info
{

  const u32 allocsize;
  const u32 loaderSize;
  const u32 handlerSize;
  const u32 codeSize;
  const u32 *codehandlerHook;
  const u32 crypted;
};

class DiscHeader
{

public:
  enum class TVMODE
  {
    NTSC,
    PAL,
    DEBUG,
    DEBUGPAL,
    MPAL,
    PAL60
  };

  struct MetaData
  {

    const u8 mDiscID;                 //0x0000
    const u16 mGameCode;              //0x0001
    const u8 mRegionCode;             //0x0003
    const u16 mMakerCode;             //0x0004
    const u8 mDiscNumber;             //0x0006
    const u8 mDiscVersion;            //0x0007
    const u8 mAudioStreaming;         //0x0008
    const u8 mStreamBufferSize;       //0x0009
    const u8 _00[12];                 //0x000A
    const u32 mWiiMagic;              //0x0018
    const u32 mGCNMagic;              //0x001C
    const u32 mNinBootCode;           //0x0020
    const u32 mAppVersion;            //0x0024
    const u32 mPhysicalRAMSize;       //0x0028
    const u32 mBoardModel;            //0x002C
    u8 *mOSArenaLo;                   //0x0030
    u8 *mOSArenaHi;                   //0x0034
    u32 *mFstStart;                   //0x0038
    u32 mFstSize;                     //0x003C
    u32 mDebuggerPresent;             //0x0040
    const u32 mDebuggerExceptionMask; //0x0044
    void *mExceptionHookDest;         //0x0048
    const u32 mExceptionReturn;       //0x004C
    u32 _01[0x10 / 4];                //0x0050
    u32 mDebuggerHook[0x24 / 4];      //0x0060
    u32 _02[0x3C / 4];                //0x0084
    u32 mCurrentOSContext;            //0x00C0
    u32 mPreviousOSMask;              //0x00C4
    u32 mCurrentOSMask;               //0x00C8
    DiscHeader::TVMODE mTVMode;       //0x00CC
    u32 mARAMSize;                    //0x00D0
    void *mCurOSContextLogical;       //0x00D4
    void *mDefaultOSThreadLogical;    //0x00D8
    u32 *mThreadQueueHead;            //0x00DC
    u32 *mThreadQueueTail;            //0x00E0
    u32 *mCurrentOSThread;            //0x00E4
    u32 mDebuggerSize;                //0x00E8
    u32 *mDebuggerMonitorLoc;         //0x00EC
    u32 mSimulatedMemSize;            //0x00F0
    u8 *mBi2HeaderLoc;                //0x00F4
    u32 mBusClockSpeed;               //0x00F8
    u32 mCPUClockSpeed;               //0x00FC
    u32 _04[0x3010 / 4];              //0x0100
    u8 *mWiiHeap;                     //0x3110
  };

  static MetaData sMetaData;

  enum class CONSOLETYPE
  {
    Gamecube,
    Wii,
    Unknown
  };

  inline u32 getGameID() { return ((u32)sMetaData.mDiscID << 24) | ((u32)sMetaData.mGameCode << 8) | ((u32)sMetaData.mRegionCode); }
  inline u16 getMakerID() { return sMetaData.mMakerCode; }
  inline u8 getDiscNumber() { return sMetaData.mDiscNumber; }
  inline u8 getDiscVersion() { return sMetaData.mDiscVersion; }

  CONSOLETYPE detectHomeConsole()
  {
    if (sMetaData.mGCNMagic)
    {
      return CONSOLETYPE::Gamecube;
    }
    else if (sMetaData.mWiiMagic)
    {
      return CONSOLETYPE::Wii;
    }

    return CONSOLETYPE::Unknown;
  }

  inline void setHeap(u32 alloc)
  {
    if (sMetaData.mBi2HeaderLoc < sMetaData.mOSArenaHi)
    {
      sMetaData.mOSArenaHi = sMetaData.mBi2HeaderLoc - alloc;
      if (this->detectHomeConsole() == DiscHeader::CONSOLETYPE::Wii)
      {
        sMetaData.mWiiHeap = sMetaData.mBi2HeaderLoc - alloc;
      }
    }
    else
    {
      if (this->detectHomeConsole() == DiscHeader::CONSOLETYPE::Wii)
      {
        sMetaData.mOSArenaHi = sMetaData.mWiiHeap - alloc;
        sMetaData.mWiiHeap -= alloc;
      }
      else
      {
        sMetaData.mOSArenaHi -= alloc;
      }
      
    }
  }
};

static DiscHeader sDisc;
Info gpModInfo = {
    0x48454150,
    0x4C53495A,
    0x4853495A,
    0x4353495A,
    (const u32 *)0x484F4F4B,
    0x43525054,
};

inline u32 extractBranchAddr(u32 *bAddr)
{
  s32 offset;
  if (*bAddr & 0x2000000)
    offset = (*bAddr & 0x3FFFFFD) - 0x4000000;
  else
    offset = *bAddr & 0x3FFFFFD;
  return (u32)bAddr + offset;
}

namespace Memory
{

  static void memcpy(u8 *to, u8 *from, s32 size)
  {
    for (s32 i = 0; i < size; ++i)
    {
      *to++ = *from++;
    }
  }

  namespace Cache
  {

    static inline void flushAddr(void *addr)
    {
      dcbf(addr);
      icbi(addr);
    }

    static void flushRange(u8 *addr, s32 size)
    {
      size += 31 + (((u32)addr & 31) > 0);

      for (u32 i = 0; i < (size >> 5); ++i)
      {
        flushAddr((void *)(addr + (i << 5)));
      }
    }

    static void storeAddr(void *addr)
    {
      dcbst(addr);
      icbi(addr);
    }

    static void storeRange(u8 *addr, s32 size)
    {
      size += 31 + (((u32)addr & 31) > 0);

      for (u32 i = 0; i < (size >> 5); ++i)
      {
        storeAddr((void *)(addr + (i << 5)));
      }
    }

  } // namespace Cache

  namespace Direct
  {

    template <typename T>
    static inline void write(T *addr, T value)
    {
      *addr = value;
      Cache::flushAddr(addr);
    }

    /*This constructs a branch instruction. &TO = ((TO - FROM) & MAX_OFFSET) | BRANCH_TYPE | !!isLink*/
    static inline void branch(void *addr, void *to, bool lk)
    {
      Direct::write<u32>((u32 *)(addr), ((((u32)(to) - (u32)(addr)) & 0x3ffffff) | 0x48000000 | lk));
    }

  } // namespace Direct

  namespace Search
  {

    static u32 *array(u32 *start, u32 *end, u32 arrayLength, const u32 *hookData)
    {
      u32 index = 0;

      /*Loop through the games RAM, make sure we don't find our own hook data by accident*/
      for (u32 i = 0; &start[i] < end; ++i)
      {
        /*If the data matches, increase the index counter and continue search,
        else set index to 0 and continue searching*/
        if (start[i] == hookData[index])
          ++index;
        else
          index = 0;

        /*If the data has matched the whole array, return the address of the match*/
        if (index >= (arrayLength) && (&start[i] < (u32 *)&gpModInfo || &start[i] > (u32 *)&gpModInfo + sizeof(Info)))
          return &start[i];
      }
      return nullptr;
    }

    template <typename T>
    static T *single(T *start, T *end, T match)
    {
      for (u32 i = 0; &start[i] < end; ++i)
      {
        if (start[i] == match)
        {
          return &start[i];
        }
      }
      return nullptr;
    }

    /*Call this after viHook, finds the address of the first instance
    of targetVal, and hooks it to the pointer hookTo*/
    static inline void hookFunction(u32 *start, u32 targetVal, void *hookTo, bool lk)
    {
      Direct::branch(Search::single<u32>(start, start + 0x500, targetVal), hookTo, lk);
    }

  } // namespace Search

  class Crypt
  {

  private:
    u32 key;

    u32 getKey()
    {
      u32 b1 = (this->key >> 24) & 0xFF;
      u32 b2 = (this->key >> 16) & 0xFF;
      u32 b3 = (this->key >> 8) & 0xFF;
      u32 b4 = this->key & 0xFF;
      b1 ^= b2;
      b2 ^= b3;
      b3 ^= b4;
      return (b4 << 24) | (b3 << 16) | (b2 << 8) | b1;
    }

    void setKey(u32 key)
    {
      u32 b1 = key & 0xFF;
      u32 b2 = (key >> 8) & 0xFF;
      u32 b3 = (key >> 16) & 0xFF;
      u32 b4 = (key >> 24) & 0xFF;
      b3 ^= b4;
      b2 ^= b3;
      b1 ^= b2;
      this->key = (b1 << 24) | (b2 << 16) | (b3 << 8) | b4;
    }

  public:
    Crypt(u32 key)
    {
      this->key = key;
    }

    inline void xorCrypt(u32 *dest, u32 *buffer, u32 size)
    {
      auto key = this->getKey();

      for (u32 i = 0; i < size; ++i)
      {
        dest[i] = buffer[i] ^ key;
        key += i << 3;
      }
    }
  };

  enum class Space : u32
  {
    Start = 0x80000000,
    End = 0x81800000,
    Size = 0x1800000
  };

} // namespace Memory

Memory::Crypt gpCryptor = {0x43595054};

static void initMods()
{
  sDisc.setHeap(gpModInfo.allocsize); /*Reallocate the internal heap*/

  /*Change codelist pointer to the new address in the allocation*/
  CodeList *codelistPointer = (CodeList *)((u32)&gpModInfo + sizeof(Info) + 0xFC);
  codelistPointer->mUpperBase = (((u32)sDisc.sMetaData.mOSArenaHi + gpModInfo.handlerSize) >> 16) & 0xFFFF;
  codelistPointer->mLowerOffset = ((u32)sDisc.sMetaData.mOSArenaHi + gpModInfo.handlerSize) & 0xFFFF;

  /*Copy codelist to the new allocation*/
  if (gpModInfo.crypted)
  {
    Memory::memcpy(sDisc.sMetaData.mOSArenaHi, (u8 *)&gpModInfo + sizeof(Info) + 4, gpModInfo.handlerSize);
    gpCryptor.xorCrypt((u32 *)(sDisc.sMetaData.mOSArenaHi + gpModInfo.handlerSize), (u32 *)((u8 *)&gpModInfo + sizeof(Info) + gpModInfo.handlerSize + 4), gpModInfo.codeSize >> 2);
  }
  else
  {
    Memory::memcpy(sDisc.sMetaData.mOSArenaHi, (u8 *)&gpModInfo + sizeof(Info) + 4, gpModInfo.handlerSize + gpModInfo.codeSize);
  }

  /*Get codehandler hook resources*/
  auto fillInField = Memory::Search::single<u32>((u32 *)sDisc.sMetaData.mOSArenaHi, (u32 *)(sDisc.sMetaData.mOSArenaHi + 0x600), 0x00DEDEDE);
  auto returnAddress = extractBranchAddr((u32 *)gpModInfo.codehandlerHook);
  auto ppc = *gpModInfo.codehandlerHook;

  /*Write hook branch*/
  Memory::Direct::branch((void *)gpModInfo.codehandlerHook, (void *)((u32)sDisc.sMetaData.mOSArenaHi + 0xA8), false); //entryhook

  /*Temporary nop*/
  *fillInField = 0x60000000;

  /*Flush the cache so that the instructions update*/
  Memory::Cache::flushRange((u8 *)sDisc.sMetaData.mOSArenaHi, gpModInfo.handlerSize + gpModInfo.codeSize);

  /*Call the codehandler*/
  call((void *)((u32)(sDisc.sMetaData.mOSArenaHi) + 0xA8))();

  /*Write original instruction or translate offset data if a branch*/
  if (((ppc >> 24) & 0xFF) > 0x47 && ((ppc >> 24) & 0xFF) < 0x4C)
  {
    Memory::Direct::branch((void *)fillInField, (void *)returnAddress, ppc & 1);
  }
  else
  {
    Memory::Direct::write(fillInField, ppc);
  }

  /*Write branch back to the hook address + 4*/
  Memory::Direct::branch((void *)&fillInField[1], (void *)(&gpModInfo.codehandlerHook[1]), false); //return
}

int main()
{
  if (sDisc.detectHomeConsole() != DiscHeader::CONSOLETYPE::Unknown)
  {
    initMods();
  }
  __start();
}