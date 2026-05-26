Import-Module PSReadLine
Set-Alias -Name np -Value notepad++.exe
Set-Alias -Name mcr -Value micro.exe
function ps-history { & notepad3.exe (get-PSReadlineOption).HistorySavePath }
function rm-rf {
    param([Parameter(Mandatory=$true)][string]$Path)
    Remove-Item -Path $Path -Recurse -Force
}
function grep-hist {
    param($pattern)
    get-content (Get-PSReadlineOption).HistorySavePath | Select-String -Pattern $pattern
}
