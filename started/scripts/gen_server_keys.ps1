# IQCG - Generate server RSA keypair (openssl from XAMPP)
# Usage: powershell -ExecutionPolicy Bypass -File gen_server_keys.ps1
param([string]$ProjectDir = "E:\VsCode\django", [string]$OpenSsl = "C:\xampp\apache\bin\openssl.exe")

$ErrorActionPreference = "Stop"
$certs = Join-Path $ProjectDir "certs"
New-Item -ItemType Directory -Force $certs | Out-Null

$priv = Join-Path $certs "private_key.pem"
$pub = Join-Path $certs "public_key.pem"

if ((Test-Path $priv) -or (Test-Path $pub)) {
    Write-Warning "Keys already exist in $certs. Use rotate_rsa_key.ps1 to replace them safely."
    exit 1
}

& $OpenSsl genrsa -out $priv 4096
& $OpenSsl rsa -pubout -in $priv -out $pub

Write-Output "Created:"
Write-Output "  $priv (keep SECRET - never commit)"
Write-Output "  $pub  (safe to distribute)"
