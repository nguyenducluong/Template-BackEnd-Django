# IQCG - Rotate server RSA keypair safely
# Flow: generate new keys into certs/next -> deploy -> clients handshake again
#       -> run this script with -Promote to swap them in.
# Usage:
#   powershell -File rotate_rsa_key.ps1          # step 1: generate into certs/next
#   powershell -File rotate_rsa_key.ps1 -Promote # step 2: swap next -> current
param(
    [string]$ProjectDir = "E:\VsCode\django",
    [string]$OpenSsl = "C:\xampp\apache\bin\openssl.exe",
    [switch]$Promote
)

$ErrorActionPreference = "Stop"
$certs = Join-Path $ProjectDir "certs"
$next = Join-Path $certs "next"

if (-not $Promote) {
    New-Item -ItemType Directory -Force $next | Out-Null
    & $OpenSsl genrsa -out (Join-Path $next "private_key.pem") 4096
    & $OpenSsl rsa -pubout -in (Join-Path $next "private_key.pem") -out (Join-Path $next "public_key.pem")
    Write-Output "New keypair generated in $next."
    Write-Output "1) Deploy this folder to the server."
    Write-Output "2) Let clients handshake (they get keys wrapped with the NEW public key)."
    Write-Output "3) Wait at most CRYPTO_SESSION_TTL seconds, then run with -Promote."
    exit 0
}

# Promote: backup current, move next -> current
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = Join-Path $certs "backup_$stamp"
New-Item -ItemType Directory -Force $bak | Out-Null
foreach ($f in @("private_key.pem", "public_key.pem")) {
    Move-Item (Join-Path $certs $f) (Join-Path $bak $f) -Force
    Move-Item (Join-Path $next $f) (Join-Path $certs $f) -Force
}
Write-Output "Rotation done. Old keys archived in $bak"
Write-Output "Restart the Django process so the new keys are loaded (key cache cleared on restart)."
