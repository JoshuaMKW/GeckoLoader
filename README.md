# GeckoLoader
**An easy way to have near unlimited code space, allowing thousands of lines of gecko code for every Wii/GCN game.**

**Steps to compile using source files:**

   1. Extract main.dol/Start.dol (varies by extraction method) from the desired game into the same directory as "main.py"
   2. Move your GCT into the same directory as "main.py"
   3. Run main.py and input the names of the main.dol/Start.dol, and the GCT.
   4. Define your code allocation (Is in hex: 30000 = 0x30000)

   Your new patched main.dol/Start.dol will be in the folder ./BUILD/

**Steps to compile using Release Build:**

   1. Extract main.dol/Start.dol (varies by extraction method) from the desired game into the same directory as "main.py"
   2. Move your GCT into the same directory as "main.exe"
   3. Either run main.exe and input the names of the main.dol/Start.dol, and the GCT, OR drag the main.dol/Start.dol and the GCT onto main.exe and drop them
   4. Define your code allocation (Is in hex: 30000 = 0x30000)

  Your new patched main.dol/Start.dol will be in the folder ./BUILD/
