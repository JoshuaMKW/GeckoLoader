using System;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;

public class Program
{
    static void Main(string[] args)
    {
	Installer installer = new Installer();
	installer.GetUserInput();
    }
}

public class Installer
{
    public string programfolder;
    public bool copyfiles;
    public bool overwrite;

    public Installer()
    {
	programfolder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "GeckoLoader");
	copyfiles = true;
	overwrite = true;
    }

    private static void ClearConsoleLine(int index, bool moveto)
    {
	int currentLineCursor = Console.CursorTop;
	Console.SetCursorPosition(0, index);
    	Console.Write(new string(' ', Console.WindowWidth));
	if (moveto) Console.SetCursorPosition(0, index);
	else Console.SetCursorPosition(0, currentLineCursor);
    }

    private static string HandleConsoleQuestion(string msg, string[] options)
    {
	bool handled = false;
	string input = String.Empty;

	while (handled == false)
        {
	    Console.Write("{0} ({1}): ", msg, String.Join("|", options));

	    input = Console.ReadLine();
	    if (options.Any(s => s.Contains(input.ToLower())))
	    {
	    	handled = true;
            }
	    else
            {
	    	ClearConsoleLine(Console.CursorTop - 1, true);
            }
        }
	return input;
    }

    private void SetProgramFolderToPath(string folderName)
    {
	this.programfolder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), folderName);

	if (!Directory.Exists(this.programfolder)) Directory.CreateDirectory(this.programfolder);
		
	var scope = EnvironmentVariableTarget.User;
	var curPATH = Environment.GetEnvironmentVariable("PATH", scope);

	if (!curPATH.Contains(this.programfolder))
        {
	    var newValue = curPATH + ";" + this.programfolder;
	    Environment.SetEnvironmentVariable("PATH", newValue, scope);
        }
    }

    private bool MoveFilesToprogramfolder(string wildcard, bool copy = true, bool overwrite = false)
    {
	DirectoryInfo cwd = new DirectoryInfo(Path.Combine(Directory.GetCurrentDirectory()));
	DirectoryInfo programspace = new DirectoryInfo(this.programfolder);

	bool validinstall = false;
		
	try
        {
	    foreach (FileInfo file in programspace.EnumerateFiles())
	    {
	    	file.Delete();
	    }
	    foreach (DirectoryInfo dir in programspace.EnumerateDirectories())
	    {
	        dir.Delete(true);
	    }

	    foreach (FileInfo file in cwd.EnumerateFiles(wildcard, SearchOption.TopDirectoryOnly))
	    {
	        string ext = ".exe.py.bin";

	        if (ext.Contains(file.Extension.ToLower()))
	        {
		    if (file.Extension.ToLower() == ".exe" && file.Name != "GeckoLoader.exe") continue;
		    if (file.Name.ToLower() == "geckoloader.py" || file.Name.ToLower() == "geckoloader.exe") validinstall = true;
		    file.CopyTo(Path.Combine(programspace.FullName, file.Name), true);
            	}
	    }
	    foreach (DirectoryInfo dir in cwd.EnumerateDirectories())
	    {
	    	if (!Directory.Exists(Path.Combine(programspace.FullName, dir.Name)))
            	{
		    Directory.CreateDirectory(Path.Combine(programspace.FullName, dir.Name));
            	}
	    	foreach (FileInfo subfile in dir.EnumerateFiles(wildcard, SearchOption.TopDirectoryOnly))
            	{
		    subfile.CopyTo(Path.Combine(programspace.FullName, dir.Name, subfile.Name), true);
	    	}
	    }
        }
	catch (UnauthorizedAccessException e)
        {
	    Console.WriteLine(String.Format("Insufficient privledges provided! {0}\nTry running with administrator privledges", e));
	    return false;
        }

	return validinstall;
    }

    public void GetUserInput()
    {
	string status;
	string[] options = { "y", "n" };

	Console.SetWindowSize(84, 30);
	Console.Title = "GeckoLoader Installer";
	Console.WriteLine("This installer modifies the Windows User PATH variable\n");

	status = HandleConsoleQuestion("Are you sure you want to continue?", options);

	if (status.ToLower() == "y")
        {
	    this.SetProgramFolderToPath("GeckoLoader");
	    if (this.MoveFilesToprogramfolder("*", this.copyfiles, this.overwrite) == false)
	    {
	        Console.WriteLine("Failed to install :( Is Geckoloader and its dependancies in the same directory?");
	    }
            else
            {
	    	Console.WriteLine("Finished installation successfully! You can run GeckoLoader from anywhere\nby simply calling \"GeckoLoader <dol> <gct|txt|folder> [options]\"");
            }
        }
	else
        {
	    Console.WriteLine("That's okay! You can always run this program again when you feel ready.");
        }
	Console.Write("Press any key to exit . . . ");
	Console.ReadKey();
    }
}
