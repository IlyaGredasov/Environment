Import-Module PSReadLine

Set-PSReadLineOption `
    -MaximumHistoryCount 400000 `
    -HistorySaveStyle SaveIncrementally `
    -HistoryNoDuplicates `
    -HistorySearchCursorMovesToEnd `
    -PredictionSource HistoryAndPlugin `
    -PredictionViewStyle InlineView `
    -ShowToolTips

Set-PSReadLineKeyHandler -Chord Ctrl+Spacebar -Function MenuComplete

Set-Alias -Name np -Value notepad++.exe
Set-Alias -Name mcr -Value micro.exe
function ps-history { & notepad++.exe (get-PSReadlineOption).HistorySavePath }
function rm-rf {
    param([Parameter(Mandatory=$true)][string]$Path)
    Remove-Item -Path $Path -Recurse -Force
}
function grep-hist {
    param($pattern)
    Get-Content (Get-PSReadlineOption).HistorySavePath | Select-String -Pattern $pattern
}
