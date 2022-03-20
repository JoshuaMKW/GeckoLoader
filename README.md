![GeckoLoaderLogo](https://user-images.githubusercontent.com/60854312/159154005-b666fa45-67a6-4c6b-8a61-b986676e6083.png)

---

### GeckoLoader is a command line tool, providing an easy way to have near unlimited code space, allowing thousands of lines of gecko code for every Wii/GCN game.

## Windows

![Imgur](https://i.imgur.com/3NiQ4T4.png)

## Linux

![Imgur](https://i.imgur.com/6cDiMW7.png)

---

## Installation

Run the installer and choose to install `GeckoLoader`

## Usage

### Codes

`GeckoLoader` supports 2 methods:

   1. GCT files (Raw codelist)
   2. Textual Codelist (Ocarina Manager or Dolphin Format txt files)

`GeckoLoader` also supports the ability to use a folder filled with GCT files and/or Textual codelists as input for multi codelist patching.

### DOL

`GeckoLoader` needs a valid `dol` file to patch with your codes. Simply supply the path to your `dol` file in either the GUI or the CLI.

`GeckoLoader` also supports patching the same `dol` file multiple times until the file becomes filled with section data.

### Compilation

Then you can do either:

   1. In command prompt, input `GeckoLoader -h` for help on syntax and options
   2. Run the command `GeckoLoader <dol> <codelist> <options>` filling in the variables as needed

Or:

   1. Fill out the relevant data in the GUI
   2. Click the "RUN" button

Your new patched `dol` file will be in the folder `./geckoloader-build` by default.

## Common Issues

### The allocation was invalid

This means the manual allocation amount you've passed into GeckoLoader is not a hexidecimal number.

### The codehandler hook address was beyond bounds

This means the manual hook address you've passed into GeckoLoader is beyond valid range. Values from 0x80000000 to 0x817FFFFF (inclusive) are allowed.

### The codehandler hook address was invalid

This means the manual hook address you've passed into GeckoLoader is not a hexidecimal number.

### There are no unused sections left for GeckoLoader to use

This means you've used up all of the remaining text/data sections, and GeckoLoader can't make space for itself. Try using a fresh DOL if this has been patched many times. Otherwise you're out of luck.

### Init address specified for GeckoLoader (x) clobbers existing dol sections

This means the address you specified manually for GeckoLoader to initialize at is about to mutilate your game and thus, try a safer address instead.

### Failed to find a hook address

This means it couldn't find a known location to hook to. This can be resolved by trying different hooktypes, or manually specifying a hook address.

### Allocated codespace was smaller than the given codelist

This means you manually specified an allocation size that happens to be smaller than the codelist's minimum space requirements. Give it some more room to work with or let it automatically decide the allocation amount.

### Credits

- Wiimm - Original idea and implementation this is based from
- Riidefi - Taught me C/C++, which this uses

**Make sure to give proper credit to myself (JoshuaMK) and this project when you utilize it in a mod! It's much appreciated**
