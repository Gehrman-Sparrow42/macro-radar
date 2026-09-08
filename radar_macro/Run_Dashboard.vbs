Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & ScriptDir & "\Run_Dashboard.bat" & chr(34), 0
Set WshShell = Nothing
Set FSO = Nothing
