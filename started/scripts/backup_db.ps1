# IQCG - PostgreSQL backup script (Windows / Task Scheduler)
# Usage:
#   powershell -ExecutionPolicy Bypass -File backup_db.ps1 -Frequency daily
#   powershell -ExecutionPolicy Bypass -File backup_db.ps1 -Frequency hourly
param(
    [Parameter(Mandatory = $true)][ValidateSet("daily", "hourly")]
    [string]$Frequency,
    [string]$ProjectDir = "E:\VsCode\django",
    [string]$BackupRoot = "E:\Backups\iqcg",
    [string]$PgDump = "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
    [int]$KeepDaily = 30,
    [int]$KeepHourly = 48
)

$ErrorActionPreference = "Stop"

# --- read .env ---
$envFile = Join-Path $ProjectDir ".env"
$cfg = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*)\s*$') { $cfg[$Matches[1]] = $Matches[2] }
}
$DbName = $cfg["DB_NAME"]; $DbUser = $cfg["DB_USER"]; $DbPassword = $cfg["DB_PASSWORD"]
$DbHost = $cfg["DB_HOST"]; $DbPort = $cfg["DB_PORT"]

$stamp = if ($Frequency -eq "daily") { Get-Date -Format "yyyy-MM-dd_HHmm" } else { Get-Date -Format "yyyy-MM-dd_HH00" }
$dir = Join-Path $BackupRoot $Frequency
New-Item -ItemType Directory -Force $dir | Out-Null
$out = Join-Path $dir "$($DbName)_$stamp.dump"

$env:PGPASSWORD = $DbPassword
& $PgDump -h $DbHost -p $DbPort -U $DbUser -Fc -Z 6 -f $out $DbName
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }
$env:PGPASSWORD = $null

$size = "{0:N1} KB" -f ((Get-Item $out).Length / 1KB)
Write-Output "[$(Get-Date -Format o)] OK: $out ($size)"

# --- retention ---
$keep = if ($Frequency -eq "daily") { $KeepDaily } else { $KeepHourly }
Get-ChildItem $dir -Filter *.dump | Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $keep | ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Output "Retention: removed $($_.Name)"
    }
