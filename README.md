# GeckoLoader
**GeckoLoader is a command line tool, providing an easy way to have near unlimited code space, allowing thousands of lines of gecko code for every Wii/GCN game.**

**Windows**

![Imgur](https://i.imgur.com/3NiQ4T4.png)

**Linux**

![Imgur](https://i.imgur.com/6cDiMW7.png)

**Codes**

`GeckoLoader` supports 2 methods:

   1. GCT files (Raw codelist)
   2. Textual Codelist (Ocarina Manager or Dolphin Format txt files)

`GeckoLoader` also supports the ability to use a folder filled with GCT files and/or Textual codelists as input for multi codelist patching

**DOL File**

`GeckoLoader` needs a valid `dol` file to patch with your codes. Simply supply the path to your `dol` file in either the GUI or the CLI

`GeckoLoader` also supports patching the same `dol` file multiple times until the file becomes filled with section data.

**Steps to compile GeckoLoader**

Run the installer and choose to install `GeckoLoader`

Then you can do either:
   1. In command prompt, input `GeckoLoader -h` for help on syntax and options
   2. Run the command `GeckoLoader <dol> <codelist> <options>` filling in the variables as needed

Or:
   1. Fill out the relevant data in the GUI
   2. Click the RUN button

Your new patched `dol` file will be in the folder `./geckoloader-build` by default
