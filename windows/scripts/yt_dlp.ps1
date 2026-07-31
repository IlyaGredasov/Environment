param(
    [ValidateRange(1, 32)]
    [int]$MaxParallelDownloads = 4
)

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()

$videosFile = Join-Path $PWD 'videos.txt'
$cookiesFile = Join-Path $PWD 'yt_cookies.txt'

if (-not (Test-Path -LiteralPath $videosFile)) {
    throw "Not found: $videosFile"
}

$jobs = [System.Collections.Generic.List[System.Management.Automation.Job]]::new()

function Receive-CompletedJobs {
    param([switch]$WaitForAny)

    if ($jobs.Count -eq 0) {
        return
    }

    if ($WaitForAny) {
        Wait-Job -Any -Job $jobs | Out-Null
    }

    foreach ($job in @($jobs | Where-Object State -in 'Completed', 'Failed', 'Stopped')) {
        Receive-Job -Job $job
        Remove-Job -Job $job
        [void]$jobs.Remove($job)
    }
}

Get-Content -LiteralPath $videosFile |
    Where-Object { $_ -and -not $_.TrimStart().StartsWith('#') } |
    ForEach-Object {
        while ($jobs.Count -ge $MaxParallelDownloads) {
            Receive-CompletedJobs -WaitForAny
        }

        $url = $_
        $jobs.Add((Start-Job -ArgumentList $url, $cookiesFile -ScriptBlock {
		    param($videoUrl, $cookiesPath)

		    yt-dlp `
		        -o '%(playlist|NA)s/%(title)s.%(ext)s' `
		        --yes-playlist `
		        --no-check-certificates `
		        -N 12 `
		        --js-runtime node `
		        --remote-components ejs:github `
		        --extractor-args 'generic:impersonate' `
		        --cookies $cookiesPath `
		        --merge-output-format mkv `
		        --recode-video mkv `
		        --postprocessor-args 'VideoConvertor+ffmpeg_o:-c:v h264_nvenc -preset p5 -cq 23 -c:a copy' `
		        $videoUrl
			}
		))
    }

while ($jobs.Count -gt 0) {
    Receive-CompletedJobs -WaitForAny
}
