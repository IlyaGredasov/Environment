$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: install_dot_clang.ps1 [-u USER] [--environ PATH]

Link:
  <ENVIRON drive>:\Programming\C++\.clang-format -> ENVIRON\common\configs\.clang-format
  <ENVIRON drive>:\Programming\C++\.clang-tidy   -> ENVIRON\common\configs\.clang-tidy

Defaults:
  USER    current user; accepted for parity with Linux scripts
  ENVIRON D:\Programming\Environment
"@
}

$targetUser = $env:USERNAME
$environ = "D:\Programming\Environment"

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        { $_ -in @("-u", "--user") } {
            if ($i + 1 -ge $args.Count) {
                Write-Error "install_dot_clang.ps1: missing value for $($args[$i])"
                exit 2
            }
            $targetUser = [string]$args[$i + 1]
            $i++
            continue
        }
        "--environ" {
            if ($i + 1 -ge $args.Count) {
                Write-Error "install_dot_clang.ps1: missing value for --environ"
                exit 2
            }
            $environ = [string]$args[$i + 1]
            $i++
            continue
        }
        { $_ -in @("-h", "--help") } {
            Show-Usage
            exit 0
        }
        default {
            Write-Error "install_dot_clang.ps1: unknown argument: $($args[$i])"
            Show-Usage | Write-Error
            exit 2
        }
    }
}

function Resolve-EnvironmentPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ($Path -eq "~") {
        return $HOME
    }
    if ($Path.StartsWith("~\")) {
        return Join-Path $HOME $Path.Substring(2)
    }
    return [System.IO.Path]::GetFullPath($Path)
}

function Resolve-ClangSource {
    param(
        [Parameter(Mandatory = $true)][string]$EnvironmentPath,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $candidate = Join-Path $EnvironmentPath "common\configs\$Name"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }

    $candidate = Join-Path $EnvironmentPath "common\$Name"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }

    throw "install_dot_clang.ps1: missing source for $Name"
}

function New-FileSymlink {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Target
    )

    if ((Test-Path -LiteralPath $Target) -and -not ((Get-Item -LiteralPath $Target -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "install_dot_clang.ps1: refusing to replace non-symlink: $Target"
    }

    Remove-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
    New-Item -ItemType SymbolicLink -Path $Target -Target $Source -Force | Out-Null
}

$environ = Resolve-EnvironmentPath $environ
$environmentRoot = [System.IO.DirectoryInfo]::new($environ)
if (-not $environmentRoot.Root -or -not $environmentRoot.Root.Name) {
    throw "install_dot_clang.ps1: cannot determine drive for ENVIRON: $environ"
}

$driveRoot = $environmentRoot.Root.FullName
$targetDir = Join-Path $driveRoot "Programming\C++"

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

$clangFormat = Resolve-ClangSource $environ ".clang-format"
$clangTidy = Resolve-ClangSource $environ ".clang-tidy"

New-FileSymlink $clangFormat (Join-Path $targetDir ".clang-format")
New-FileSymlink $clangTidy (Join-Path $targetDir ".clang-tidy")

Write-Host "Installed clang config links for $targetUser"
