' Launches JARVIS in voice mode, minimized, with no extra popup window.
' A shortcut to this file lives in the Windows Startup folder so JARVIS runs at login
' and listens for "Hey Jarvis" all the time.
Set sh = CreateObject("WScript.Shell")
proj = "C:\Users\HP-5CD4371SQ6\Desktop\opensource\jarvish"
sh.CurrentDirectory = proj
' Window style 7 = minimized (and not focused), so it stays out of your way.
sh.Run "cmd /c """ & proj & "\run-voice.bat""", 7, False
