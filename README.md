# GeckoLoader
**GeckoLoader is a command line tool, providing an easy way to have near unlimited code space, allowing thousands of lines of gecko code for every Wii/GCN game.**

**Steps to prepare a codelist**

   1. Download `Ocarina Manager`
   2. Open `Ocarina Manager` and supply it with the codes you desire, checking the boxes of the codes that you want to be used in `GeckoLoader`
   3. Save it as a txt file in your `current working directory`

**Steps to prepare a .dol file**

   1. Copy a clean `dol` file from your choice game into your `current working directory`

**Steps to compile GeckoLoader**

   1. Run the installer and choose to install `GeckoLoader`
   2. In command prompt, input `GeckoLoader -h` for help on syntax and options
   3. Run the command `GeckoLoader <dol> <codelist> <options>` filling in the variables as needed

Your new patched `dol` file will be in the folder `./geckoloader-build` by default

*NOTE: <codelist> can be an Ocarina formatted txt file, a gct, or a folder containing the previous mentioned files.
