#pragma once

#include "types.h"

#define dcbst(_val) asm volatile("dcbst 0, %0" : : "r"(_val))
#define dcbf(_val) asm volatile("dcbf 0, %0" : : "r"(_val))
#define icbi(_val) asm volatile("icbi 0, %0" : : "r"(_val))

namespace Memory {

static void memcpy(void *dst, void *src, size_t size) {
  u8 *castDst = static_cast<u8 *>(dst);
  u8 *castSrc = static_cast<u8 *>(src);
  for (s32 i = 0; i < size; ++i) {
    *castDst++ = *castSrc++;
  }
}

namespace Cache {

inline void flushAddr(void *addr) {
  dcbf(addr);
  icbi(addr);
}

inline void flushRange(u8 *addr, s32 size) {
  size += 31 + (((u32)addr & 31) > 0);

  for (u32 i = 0; i < (size >> 5); ++i) {
    flushAddr((void *)(addr + (i << 5)));
  }
}

inline void storeAddr(void *addr) {
  dcbst(addr);
  icbi(addr);
}

inline void storeRange(u8 *addr, s32 size) {
  size += 31 + (((u32)addr & 31) > 0);

  for (u32 i = 0; i < (size >> 5); ++i) {
    storeAddr((void *)(addr + (i << 5)));
  }
}

} // namespace Cache

namespace Direct {

template <typename T> inline void write(T *addr, T value) {
  *addr = value;
  Cache::flushAddr(addr);
}

/*This constructs a branch instruction. &TO = ((TO - FROM) & MAX_OFFSET) |
 * BRANCH_TYPE | !!isLink*/
inline void writeBranch(void *addr, void *to, bool lk) {
  Direct::write<u32>((u32 *)(addr), ((((u32)(to) - (u32)(addr)) & 0x3ffffff) |
                                     0x48000000 | lk));
}

/*Get the target address of the branch at bAddr*/
inline u32 getBranch(u32 *bAddr) {
  s32 offset;
  if (*bAddr & 0x2000000)
    offset = (*bAddr & 0x3FFFFFD) - 0x4000000;
  else
    offset = *bAddr & 0x3FFFFFD;
  return (u32)bAddr + offset;
}

} // namespace Direct

namespace Search {

template <typename T>
T *array(T *start, T *end, size_t matchLen, const T *matchData) {
  u32 index = 0;

  /*Loop through the games RAM, make sure we don't find our own hook data by
   * accident*/
  for (u32 i = 0; &start[i] < end; ++i) {
    /*If the data matches, increase the index counter and continue search,
    else set index to 0 and continue searching*/
    if (start[i] == matchData[index])
      ++index;
    else
      index = 0;

    /*If the data has matched the whole array, return the address of the match*/
    if (index >= matchLen)
      return &start[i];
  }
  return nullptr;
}

template <typename T> T *single(T *start, T *end, T match) {
  for (u32 i = 0; &start[i] < end; ++i) {
    if (start[i] == match) {
      return &start[i];
    }
  }
  return nullptr;
}

/*Call this after viHook, finds the address of the first instance
of targetVal, and hooks it to the pointer hookTo*/
static inline void hookFunction(u32 *start, u32 targetVal, void *hookTo,
                                bool lk) {
  Direct::branch(Search::single<u32>(start, start + 0x500, targetVal), hookTo,
                 lk);
}

} // namespace Search

class Crypt {

private:
  u32 key;

  u32 getKey() {
    u32 b1 = (this->key >> 24) & 0xFF;
    u32 b2 = (this->key >> 16) & 0xFF;
    u32 b3 = (this->key >> 8) & 0xFF;
    u32 b4 = this->key & 0xFF;
    b1 ^= b2;
    b2 ^= b3;
    b3 ^= b4;
    return (b4 << 24) | (b3 << 16) | (b2 << 8) | b1;
  }

  void setKey(u32 key) {
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
  Crypt(u32 key) { this->key = key; }

  inline void xorCrypt(u32 *dest, u32 *buffer, u32 size) {
    auto key = this->getKey();

    for (u32 i = 0; i < size; ++i) {
      dest[i] = buffer[i] ^ key;
      key += i << 3;
    }
  }
};

constexpr u32 mem_start = 0x80000000;
constexpr u32 mem_end = 0x81800000;
constexpr size_t mem_size = mem_end - mem_start;

} // namespace Memory