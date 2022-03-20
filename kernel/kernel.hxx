#pragma once

#include "types.h"
#include "ticket.hxx"

class GeckoLoaderKernel {
    void execHandler(void (*codehandler)());
public:
    void runTicket(Ticket &ticket);
};