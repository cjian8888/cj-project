Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = appDir
shell.Run Chr(34) & appDir & "\start_fpas.cmd" & Chr(34), 0, False
