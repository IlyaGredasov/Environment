$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: add_context.ps1 [-t PATTERN]... [-c PATTERN]...

  -t, --tree  Add matching files to the tree section.
  -c, --cat   Print matching files with their contents.

Patterns can be literal paths, PowerShell wildcards, simple brace globs like
src/*.{cpp,hpp}, or regular expressions matched against repo paths.
"@
}

$treePatterns = New-Object System.Collections.Generic.List[string]
$catPatterns = New-Object System.Collections.Generic.List[string]

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        { $_ -in @("-t", "--tree") } {
            if ($i + 1 -ge $args.Count) {
                Write-Error "add_context.ps1: missing value for $($args[$i])"
                exit 2
            }
            $treePatterns.Add([string]$args[$i + 1])
            $i++
            continue
        }
        { $_ -in @("-c", "--cat") } {
            if ($i + 1 -ge $args.Count) {
                Write-Error "add_context.ps1: missing value for $($args[$i])"
                exit 2
            }
            $catPatterns.Add([string]$args[$i + 1])
            $i++
            continue
        }
        { $_ -in @("-h", "--help") } {
            Show-Usage
            exit 0
        }
        default {
            Write-Error "add_context.ps1: unknown argument: $($args[$i])"
            Show-Usage | Write-Error
            exit 2
        }
    }
}

function Expand-Braces {
    param([Parameter(Mandatory = $true)][string]$Pattern)

    $start = $Pattern.IndexOf("{")
    if ($start -lt 0) {
        return @($Pattern)
    }

    $end = $Pattern.IndexOf("}", $start + 1)
    if ($end -lt 0) {
        return @($Pattern)
    }

    $prefix = $Pattern.Substring(0, $start)
    $inner = $Pattern.Substring($start + 1, $end - $start - 1)
    $suffix = $Pattern.Substring($end + 1)
    $result = New-Object System.Collections.Generic.List[string]

    foreach ($part in $inner.Split(",")) {
        foreach ($expanded in Expand-Braces "$prefix$part$suffix") {
            $result.Add($expanded)
        }
    }

    return $result.ToArray()
}

function ConvertTo-DefaultDisplayPath {
    param([Parameter(Mandatory = $true)]$Item)

    $root = (Get-Location).ProviderPath.TrimEnd("\", "/")
    $fullName = $Item.FullName.TrimEnd("\", "/")

    if ($fullName.Equals($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = "."
    } elseif ($fullName.StartsWith("$root\", [System.StringComparison]::OrdinalIgnoreCase) -or
        $fullName.StartsWith("$root/", [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $fullName.Substring($root.Length).TrimStart("\", "/")
    } else {
        $relative = $fullName
    }

    return $relative.Replace("\", "/")
}

function ConvertTo-InputDisplayPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Item
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Item.FullName.TrimEnd("\", "/").Replace("\", "/")
    }

    $displayPath = $Path.TrimEnd("\", "/").Replace("\", "/")
    if ($displayPath -eq "") {
        return "."
    }
    return $displayPath
}

function Test-GitPath {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Path)

    return $Path -eq ".git" -or
        $Path.EndsWith("/.git") -or
        $Path.StartsWith(".git/") -or
        $Path.Contains("/.git/")
}

function Test-WildcardPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return $Path -match "[*?\[]"
}

function Get-ChildDisplayPath {
    param(
        [Parameter(Mandatory = $true)][string]$DisplayRoot,
        [Parameter(Mandatory = $true)][string]$RootFullName,
        [Parameter(Mandatory = $true)][string]$ChildFullName
    )

    $root = $RootFullName.TrimEnd("\", "/")
    $child = $ChildFullName.TrimEnd("\", "/")

    if ($child.Equals($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = ""
    } elseif ($child.StartsWith("$root\", [System.StringComparison]::OrdinalIgnoreCase) -or
        $child.StartsWith("$root/", [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $child.Substring($root.Length).TrimStart("\", "/")
    } else {
        $relative = $child
    }

    $relative = $relative.Replace("\", "/")
    if ($DisplayRoot -eq "." -or $DisplayRoot -eq "") {
        return $relative
    }
    if ($relative -eq "") {
        return $DisplayRoot.Replace("\", "/")
    }
    return "$($DisplayRoot.Replace('\', '/'))/$relative"
}

function Get-PatternMatches {
    param([Parameter(Mandatory = $true)][string]$Pattern)

    $items = New-Object System.Collections.Generic.List[object]
    $found = $false

    foreach ($expanded in Expand-Braces $Pattern) {
        $literalExists = Test-Path -LiteralPath $expanded

        if ($literalExists) {
            $item = Get-Item -LiteralPath $expanded -Force
            $items.Add([PSCustomObject]@{
                Item = $item
                DisplayPath = ConvertTo-InputDisplayPath $expanded $item
            })
            $found = $true
        }

        if ((-not $literalExists) -or (Test-WildcardPath $expanded)) {
            foreach ($item in Get-ChildItem -Path $expanded -Force -ErrorAction SilentlyContinue) {
                $items.Add([PSCustomObject]@{
                    Item = $item
                    DisplayPath = ConvertTo-DefaultDisplayPath $item
                })
                $found = $true
            }
        }
    }

    if (-not $found) {
        try {
            foreach ($item in Get-ChildItem -LiteralPath . -Recurse -Force -ErrorAction SilentlyContinue) {
                $relative = ConvertTo-DefaultDisplayPath $item
                if ((-not (Test-GitPath $relative)) -and $relative -match $Pattern) {
                    $items.Add([PSCustomObject]@{
                        Item = $item
                        DisplayPath = $relative
                    })
                }
            }
        } catch {
            return @()
        }
    }

    return $items.ToArray()
}

function Get-MatchingFiles {
    param([Parameter(Mandatory = $true)][string]$Pattern)

    $files = New-Object System.Collections.Generic.List[object]

    foreach ($match in Get-PatternMatches $Pattern) {
        $item = $match.Item
        $displayPath = $match.DisplayPath

        if (Test-GitPath $displayPath) {
            continue
        }

        if ($item.PSIsContainer) {
            foreach ($file in Get-ChildItem -LiteralPath $item.FullName -Recurse -Force -File -ErrorAction SilentlyContinue) {
                $fileDisplayPath = Get-ChildDisplayPath $displayPath $item.FullName $file.FullName
                if (-not (Test-GitPath $fileDisplayPath)) {
                    $files.Add([PSCustomObject]@{
                        Item = $file
                        DisplayPath = $fileDisplayPath
                    })
                }
            }
        } elseif ($item -is [System.IO.FileInfo]) {
            $files.Add([PSCustomObject]@{
                Item = $item
                DisplayPath = $displayPath
            })
        }
    }

    return $files.ToArray()
}

function Write-Tree {
    param([Parameter(Mandatory = $true)][string[]]$Paths)

    $seenDirs = New-Object System.Collections.Generic.HashSet[string]

    foreach ($path in $Paths) {
        $parts = $path -split "/"
        for ($i = 0; $i -lt $parts.Count - 1; $i++) {
            $dir = ($parts[0..$i] -join "/")
            if ($seenDirs.Add($dir)) {
                if ($i -eq 0) {
                    Write-Output $parts[$i]
                } else {
                    Write-Output "$(('|   ' * ($i - 1)))|-- $($parts[$i])"
                }
            }
        }

        if ($parts.Count -eq 1) {
            Write-Output $parts[0]
        } else {
            Write-Output "$(('|   ' * ($parts.Count - 2)))|-- $($parts[$parts.Count - 1])"
        }
    }
}

$treeFiles = New-Object System.Collections.Generic.List[object]
$catFiles = New-Object System.Collections.Generic.List[object]
$seenTree = New-Object System.Collections.Generic.HashSet[string]
$seenCat = New-Object System.Collections.Generic.HashSet[string]

foreach ($pattern in $treePatterns) {
    foreach ($entry in Get-MatchingFiles $pattern) {
        $key = $entry.Item.FullName.ToLowerInvariant()
        if ($seenTree.Add($key)) {
            $treeFiles.Add($entry)
        }
    }
}

foreach ($pattern in $catPatterns) {
    foreach ($entry in Get-MatchingFiles $pattern) {
        $key = $entry.Item.FullName.ToLowerInvariant()
        if ($seenCat.Add($key)) {
            $catFiles.Add($entry)
        }
    }
}

if ($treeFiles.Count -gt 0) {
    $treePaths = $treeFiles | ForEach-Object { $_.DisplayPath } | Sort-Object -Unique
    Write-Tree $treePaths
}

if ($treeFiles.Count -gt 0 -and $catFiles.Count -gt 0) {
    Write-Output ""
}

foreach ($entry in $catFiles) {
    Write-Output "# $($entry.DisplayPath)"
    Get-Content -LiteralPath $entry.Item.FullName -Raw -ErrorAction SilentlyContinue
    Write-Output ""
}
