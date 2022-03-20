#pragma once

#include "types.h"

extern OSGlobals gGlobals;

class OSGlobals {

public:
  enum class TVMODE { NTSC, PAL, DEBUG, DEBUGPAL, MPAL, PAL60 };

  struct MetaData {

    const u8 mDiscID;                 // 0x0000
    const u16 mGameCode;              // 0x0001
    const u8 mRegionCode;             // 0x0003
    const u16 mMakerCode;             // 0x0004
    const u8 mDiscNumber;             // 0x0006
    const u8 mDiscVersion;            // 0x0007
    const u8 mAudioStreaming;         // 0x0008
    const u8 mStreamBufferSize;       // 0x0009
    const u8 _00[12];                 // 0x000A
    const u32 mWiiMagic;              // 0x0018
    const u32 mGCNMagic;              // 0x001C
    const u32 mNinBootCode;           // 0x0020
    const u32 mAppVersion;            // 0x0024
    const u32 mPhysicalRAMSize;       // 0x0028
    const u32 mBoardModel;            // 0x002C
    u8 *mOSArenaLo;                   // 0x0030
    u8 *mOSArenaHi;                   // 0x0034
    u32 *mFstStart;                   // 0x0038
    u32 mFstSize;                     // 0x003C
    u32 mDebuggerPresent;             // 0x0040
    const u32 mDebuggerExceptionMask; // 0x0044
    void *mExceptionHookDest;         // 0x0048
    const u32 mExceptionReturn;       // 0x004C
    u32 _01[0x10 / 4];                // 0x0050
    u32 mDebuggerHook[0x24 / 4];      // 0x0060
    u32 _02[0x3C / 4];                // 0x0084
    u32 mCurrentOSContext;            // 0x00C0
    u32 mPreviousOSMask;              // 0x00C4
    u32 mCurrentOSMask;               // 0x00C8
    OSGlobals::TVMODE mTVMode;       // 0x00CC
    u32 mARAMSize;                    // 0x00D0
    void *mCurOSContextLogical;       // 0x00D4
    void *mDefaultOSThreadLogical;    // 0x00D8
    u32 *mThreadQueueHead;            // 0x00DC
    u32 *mThreadQueueTail;            // 0x00E0
    u32 *mCurrentOSThread;            // 0x00E4
    u32 mDebuggerSize;                // 0x00E8
    u32 *mDebuggerMonitorLoc;         // 0x00EC
    u32 mSimulatedMemSize;            // 0x00F0
    u8 *mBi2HeaderLoc;                // 0x00F4
    u32 mBusClockSpeed;               // 0x00F8
    u32 mCPUClockSpeed;               // 0x00FC
    u32 _04[0x3010 / 4];              // 0x0100
    u8 *mWiiHeap;                     // 0x3110
  };

  static MetaData sMetaData;

  enum class CONSOLETYPE { Gamecube, Wii, Unknown };

  inline u32 getGameID() {
    return ((u32)sMetaData.mDiscID << 24) | ((u32)sMetaData.mGameCode << 8) |
           ((u32)sMetaData.mRegionCode);
  }
  inline u16 getMakerID() { return sMetaData.mMakerCode; }
  inline u8 getDiscNumber() { return sMetaData.mDiscNumber; }
  inline u8 getDiscVersion() { return sMetaData.mDiscVersion; }

  CONSOLETYPE detectHomeConsole() {
    if (sMetaData.mGCNMagic) {
      return CONSOLETYPE::Gamecube;
    } else if (sMetaData.mWiiMagic) {
      return CONSOLETYPE::Wii;
    }

    return CONSOLETYPE::Unknown;
  }

  void allocHeap(u32 alloc) {
    if (sMetaData.mBi2HeaderLoc < sMetaData.mOSArenaHi) {
      sMetaData.mOSArenaHi = sMetaData.mBi2HeaderLoc - alloc;
      if (detectHomeConsole() == OSGlobals::CONSOLETYPE::Wii) {
        sMetaData.mWiiHeap = sMetaData.mBi2HeaderLoc - alloc;
      }
    } else {
      if (detectHomeConsole() == OSGlobals::CONSOLETYPE::Wii) {
        sMetaData.mOSArenaHi = sMetaData.mWiiHeap - alloc;
        sMetaData.mWiiHeap -= alloc;
      } else {
        sMetaData.mOSArenaHi -= alloc;
      }
    }
  }
};