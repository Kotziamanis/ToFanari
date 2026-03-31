@echo off
title ToFanari - Create Desktop Shortcut
set "FOLDER=%~dp0"
set "EXE=%FOLDER%ToFanari.exe"
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $desk = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut($desk + '\ToFanari.lnk'); $s.TargetPath = '%EXE%'; $s.WorkingDirectory = '%FOLDER:~0,-1%'; $s.Save(); Write-Host 'Shortcut created: Desktop\ToFanari.lnk'"
echo.
echo Done. You can now launch ToFanari from your Desktop.
pause
