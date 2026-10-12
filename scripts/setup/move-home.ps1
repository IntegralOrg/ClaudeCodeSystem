# Windows twin of move-home.sh: copy the downloaded vault to its home, make it a Git repository, open it in Claude.
# Runs in the first session on a clean PC, before Git Bash or Python are usable: Windows PowerShell 5.1 only.
# Same stdout tokens and exit codes as move-home.sh. Every step checks first, so a rerun resumes.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup\move-home.ps1 -Name "Owner" -Email owner@example.com [-Dest DIR] [-NoOpen]
# Exit: 0 ok (HOME_READY + OPEN_URL, or ALREADY_HOME); 2 USAGE; 3 DEST_NOT_EMPTY; 4 SYNCED_PATH; 5 NOT_A_DOWNLOAD;
# 6 GIT_MISSING; 7 COPY_FAILED; 8 GIT_FAILED.
param(
  [string]$Name = '',
  [string]$Email = '',
  [string]$Dest = (Join-Path $env:USERPROFILE 'Brain'),
  [switch]$NoOpen
)
function Stop-With([string]$Token, [string]$Message, [int]$Code) { Write-Output "${Token}: $Message"; exit $Code }

if (-not $Name -or -not $Email) { Write-Output 'USAGE: -Name and -Email are required'; exit 2 }
$Src = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path.TrimEnd('\')
# A quoted ~ or a relative path would otherwise land inside the download (the session's folder) and copy it into itself.
if ($Dest -eq '~') { $Dest = $env:USERPROFILE }
elseif ($Dest.StartsWith('~\') -or $Dest.StartsWith('~/')) { $Dest = Join-Path $env:USERPROFILE $Dest.Substring(2) }
elseif (-not [IO.Path]::IsPathRooted($Dest)) { $Dest = Join-Path $env:USERPROFILE $Dest }
$Dest = [IO.Path]::GetFullPath($Dest).TrimEnd('\')
if ($Dest.StartsWith($Src + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
  Write-Output "USAGE: $Dest is inside the downloaded folder; choose a folder outside it"; exit 2
}

if ((Test-Path -LiteralPath $Dest) -and ((Resolve-Path -LiteralPath $Dest).Path.TrimEnd('\') -eq $Src)) {
  Write-Output "ALREADY_HOME $Dest"; exit 0
}
if (-not (Test-Path -LiteralPath (Join-Path $Src 'SETUP_PENDING'))) { Stop-With 'NOT_A_DOWNLOAD' "$Src has no SETUP_PENDING marker" 5 }

$synced = @($env:OneDrive, $env:OneDriveConsumer, $env:OneDriveCommercial,
            (Join-Path $env:USERPROFILE 'Documents'), (Join-Path $env:USERPROFILE 'Desktop')) | Where-Object { $_ }
foreach ($s in $synced) {
  if (($Dest + '\').StartsWith($s.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    Stop-With 'SYNCED_PATH' "$Dest is inside a folder that syncs to the cloud" 4
  }
}
if ($Dest -match '\\(OneDrive[^\\]*|Dropbox|Google Drive|iCloudDrive)(\\|$)') { Stop-With 'SYNCED_PATH' "$Dest is inside a folder that syncs to the cloud" 4 }

# Git installed earlier in this same session is not on this process's PATH yet: look where the installer puts it.
$gitExe = $null
$cmd = Get-Command git -ErrorAction SilentlyContinue
if ($cmd) { $gitExe = $cmd.Source }
if (-not $gitExe) {
  foreach ($p in @("$env:LOCALAPPDATA\Programs\Git\cmd\git.exe", "$env:ProgramFiles\Git\cmd\git.exe")) {
    if (Test-Path -LiteralPath $p) { $gitExe = $p; break }
  }
}
if (-not $gitExe) { Stop-With 'GIT_MISSING' 'Git for Windows is not installed yet' 6 }

if (-not (Test-Path -LiteralPath (Join-Path $Dest 'SETUP_PENDING'))) {
  if ((Test-Path -LiteralPath $Dest) -and (Get-ChildItem -LiteralPath $Dest -Force | Select-Object -First 1)) {
    Stop-With 'DEST_NOT_EMPTY' "$Dest already has files in it" 3
  }
}
# The first commit happens only after a full copy, so a home with a commit is finished: never copy over it again
# (that would undo what Part B changed). Otherwise copy the marker first, so a crash midway can be resumed.
$homeDone = $false
if (Test-Path -LiteralPath (Join-Path $Dest '.git')) {
  & $gitExe -C $Dest rev-parse -q --verify HEAD 2>$null | Out-Null
  $homeDone = ($LASTEXITCODE -eq 0)
}
if (-not $homeDone) {
  try {
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    Copy-Item -LiteralPath (Join-Path $Src 'SETUP_PENDING') -Destination (Join-Path $Dest 'SETUP_PENDING') -Force -ErrorAction Stop
  } catch { Stop-With 'COPY_FAILED' $_.Exception.Message 7 }
  # robocopy ships with Windows, copies hidden files, and merges into an existing folder, so a rerun resumes.
  # Its exit codes 0 to 7 mean success; 8 and above mean something failed.
  robocopy $Src $Dest /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { Stop-With 'COPY_FAILED' "copying into $Dest failed (robocopy $LASTEXITCODE)" 7 }
}

Set-Location -LiteralPath $Dest
if (-not (Test-Path -LiteralPath (Join-Path $Dest '.git'))) {
  & $gitExe init -q -b main 2>$null
  if ($LASTEXITCODE -ne 0) { Stop-With 'GIT_FAILED' 'git init failed' 8 }
}
& $gitExe config user.name $Name
if ($LASTEXITCODE -ne 0) { Stop-With 'GIT_FAILED' 'git config failed' 8 }
& $gitExe config user.email $Email
if ($LASTEXITCODE -ne 0) { Stop-With 'GIT_FAILED' 'git config failed' 8 }
& $gitExe rev-parse -q --verify HEAD 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  & $gitExe add -A 2>$null
  & $gitExe commit -q -m 'Start my Brain' 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) { Stop-With 'GIT_FAILED' 'first commit failed' 8 }
}
Write-Output "HOME_READY $Dest"
$url = 'claude://code/new?folder=' + [uri]::EscapeDataString($Dest) + '&q=' + [uri]::EscapeDataString('Continue setup')
Write-Output "OPEN_URL $url"
if (-not $NoOpen) { Start-Process $url }
exit 0
