$historyPath = (Get-PSReadLineOption).HistorySavePath

$lines = Get-Content $historyPath
[array]::Reverse($lines)

$unique = $lines | Select-Object -Unique

[array]::Reverse($unique)

Set-Content -Path $historyPath -Value $unique
