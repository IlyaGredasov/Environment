$directories = @(
	"F:\Programming\Projects\HelmDet\api\",
	"F:\Programming\Projects\Riddoc\api\",
	"F:\Programming\Projects\Riddoc\scripts"
)

$directories | ForEach-Object -Parallel {
    if (Test-Path $_) {
        $colors = "Cyan", "Green", "Yellow", "Magenta", "White"
        $randomColor = $colors | Get-Random

        Set-Location $_
        
        Write-Host "Start: $_" -ForegroundColor $randomColor
        uv lock --upgrade && uv sync --upgrade
        Write-Host "Sync: $_" -ForegroundColor $randomColor
    } else {
        Write-Warning "Not found: $_"
    }
}
