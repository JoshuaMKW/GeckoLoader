#pragma once

#include "types.h"

struct SizeInfo {
  size_t mLoaderSize;
  size_t mHandlerSize;
  size_t mCodeSize;

  size_t getPacketSize() const {
    return mLoaderSize + mHandlerSize + mCodeSize;
  }
};

struct Ticket {
  enum class Type {
      MEMORY,
      DISC
  };

  SizeInfo mSizeInfo;
  void *mBinary;

  bool exec();
  void *getLoaderPtr();
  void *getHandlerPtr();
  void *getGeckoPtr();
};