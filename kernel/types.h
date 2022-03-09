#pragma once

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned long u32;
typedef unsigned long long u64;
typedef char s8;
typedef short s16;
typedef long s32;
typedef long long s64;
typedef float f32;
typedef double f64;
typedef volatile s8 vs8;
typedef volatile s16 vs16;
typedef volatile s32 vs32;
typedef volatile s64 vs64;
typedef volatile u8 vu8;
typedef volatile u16 vu16;
typedef volatile u32 vu32;
typedef volatile u64 vu64;
typedef volatile f32 vf32;
typedef volatile f64 vf64;

typedef unsigned long size_t;

#ifdef __cplusplus
#define NULL nullptr
#else
#define NULL ((void*)0)
#define bool int
#define true 1
#define false 0
#endif