$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Test-Port18090 {
    return [bool](Get-NetTCPConnection -LocalPort 18090 -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-Port18090)) {
    Write-Host "starting HF sidecar on 18090..."
    $sidecar = Join-Path $root "scripts\run_hf_sidecar.ps1"
    Start-Process powershell.exe -ArgumentList "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$sidecar`"" -WindowStyle Hidden
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:18090/health" -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $ok = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (-not $ok) { Write-Warning "sidecar health not ready yet; API will fail-open to hash until it is" }
} else {
    Write-Host "HF sidecar already on 18090"
}

docker compose up -d
Write-Host "stack up. UI: https://127.0.0.1:18443/  (self-signed; Apache holds 443)"
Write-Host "Public Let's Encrypt: set CERT_DIR to certbot live dir, then bash scripts/load-le-certs.sh (Linux). No public domain configured on this machine."
