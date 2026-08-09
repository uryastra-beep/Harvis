Option Explicit

Dim shell, fileSystem, scriptDirectory, pythonExecutable, logDirectory, logFile, command

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonExecutable = fileSystem.BuildPath(scriptDirectory, ".venv\Scripts\python.exe")

If Not fileSystem.FileExists(pythonExecutable) Then
    MsgBox "Harvis is not set up yet. Run run_harvis.ps1 once to create the Python environment and install dependencies.", vbExclamation, "Harvis"
    WScript.Quit 1
End If

logDirectory = shell.ExpandEnvironmentStrings("%APPDATA%\Harvis")
If Not fileSystem.FolderExists(logDirectory) Then
    fileSystem.CreateFolder(logDirectory)
End If

logFile = fileSystem.BuildPath(logDirectory, "harvis.log")
shell.CurrentDirectory = scriptDirectory

command = "cmd.exe /d /c """"" & pythonExecutable & """ -m harvis >> """ & logFile & """ 2>&1"""
shell.Run command, 0, False
