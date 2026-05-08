$ErrorActionPreference = "SilentlyContinue"

Write-Host "Stopping Edge update services..."
sc.exe stop edgeupdate
sc.exe stop edgeupdatem
sc.exe config edgeupdate start= disabled
sc.exe config edgeupdatem start= disabled

Write-Host "Deleting Edge scheduled tasks..."
schtasks /Delete /TN "MicrosoftEdgeUpdateTaskMachineCore" /F
schtasks /Delete /TN "MicrosoftEdgeUpdateTaskMachineUA" /F

Write-Host "Adding registry policies..."
reg add "HKLM\SOFTWARE\Policies\Microsoft\EdgeUpdate" /v UpdateDefault /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\EdgeUpdate" /v InstallDefault /t REG_DWORD /d 0 /f
reg add "HKLM\SOFTWARE\Policies\Microsoft\EdgeUpdate" /v DoNotUpdateToEdgeWithChromium /t REG_DWORD /d 1 /f

Write-Host "Trying to uninstall Edge..."
$edgeInstaller = Get-ChildItem "C:\Program Files (x86)\Microsoft\Edge\Application" -Directory |
    Sort-Object Name -Descending |
    Select-Object -First 1 |
    ForEach-Object { Join-Path $_.FullName "Installer\setup.exe" }

if ($edgeInstaller -and (Test-Path $edgeInstaller)) {
	& $edgeInstaller --uninstall --system-level --verbose-logging --force-uninstall
}

Write-Host "Blocking EdgeUpdate folder..."
$edgeUpdatePath = "C:\Program Files (x86)\Microsoft\EdgeUpdate"

if (Test-Path $edgeUpdatePath) {
    takeown /f $edgeUpdatePath /r /d y
    icacls $edgeUpdatePath /inheritance:r
    icacls $edgeUpdatePath /deny "*S-1-5-18:(OI)(CI)F"
    icacls $edgeUpdatePath /deny "*S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464:(OI)(CI)F"
}

Write-Host "Blocking Edge folder..."
$edgePath = "C:\Program Files (x86)\Microsoft\Edge"

if (Test-Path $edgePath) {
    if ((Get-Item $edgePath).PSIsContainer) {
        takeown /f $edgePath /r /d y
        icacls $edgePath /grant "*S-1-5-32-544:F" /t
        Remove-Item $edgePath -Recurse -Force
    } else {
        Remove-Item $edgePath -Force
    }
}

New-Item -Path $edgePath -ItemType File -Force | Out-Null
attrib +r +s +h $edgePath
takeown /f "C:\Program Files (x86)\Microsoft\EdgeCore" /r /d y
icacls "C:\Program Files (x86)\Microsoft\EdgeCore" /grant "*S-1-5-32-544:F" /t
Remove-Item "C:\Program Files (x86)\Microsoft\EdgeCore" -Recurse -Force
Write-Host "Done. Reboot Windows."
