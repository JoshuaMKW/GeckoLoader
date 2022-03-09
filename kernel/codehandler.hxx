#pragma once

#include "types.h"

struct CodeHandler {
    u8 mDiscID;
    u16 mGameCode;
    u8 mRegionCode;
    u16 mMakerCode;
    u32 mRegArea[38];
    u32 mHandler[];
};

struct CodeHandlerBinary {
    s32 mExitInstrOfs;
    s32 mGeckoCodeOfs;
    s32 mRegListOfs;
    s32 _padding1;
    CodeHandler mCodeHandler;
};