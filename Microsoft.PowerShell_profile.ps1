Import-Module PSReadLine
Set-Alias -Name np -Value notepad3.exe
Set-Alias -Name mc -Value micro.exe
function ffmpeg { & ffmpeg.exe -hide_banner $args }
function ffprobe { & ffprobe.exe -hide_banner $args }
function ffplay { & ffplay.exe -hide_banner $args }
function rm-rf {
    param([Parameter(Mandatory=$true)][string]$Path)
    Remove-Item -Path $Path -Recurse -Force
}
function grep-hist {
    param($pattern)
    get-content (Get-PSReadlineOption).HistorySavePath | Select-String -Pattern $pattern
}
