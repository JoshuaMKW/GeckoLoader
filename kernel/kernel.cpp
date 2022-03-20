#include "types.h"
#include "globals.hxx"
#include "kernel.hxx"
#include "memory.hxx"

OSGlobals gGlobals;

void GeckoLoaderKernel::runTicket(Ticket &ticket) {
  ticket.exec();
}


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