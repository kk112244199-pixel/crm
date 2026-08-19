$ErrorActionPreference = "Stop"
# 登录时启动 HF sidecar。优先用户 Startup 快捷方式（无需管理员）；计划任务需要权限时会跳过。
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\run_hf_sidecar.ps1"
$startup = [Environment]::GetFolderPath("Startup")
$lnkPath = Join-Path $startup "MontoCRM-HF-Sidecar.lnk"
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut($lnkPath)
$lnk.TargetPath = "powershell.exe"
$lnk.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$lnk.WorkingDirectory = $root
$lnk.WindowStyle = 7
$lnk.Save()
Write-Host "startup shortcut: $lnkPath"

$taskName = "MontoCRM-HF-Sidecar"
$arg = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
try {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "MontoCRM BGE sidecar on 18090" | Out-Null
    Write-Host "registered scheduled task $taskName"
} catch {
    Write-Host "scheduled task skipped (need admin): $($_.Exception.Message)"
}

$listening = Get-NetTCPConnection -LocalPort 18090 -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Start-Process powershell.exe -ArgumentList $arg -WindowStyle Hidden
    Write-Host "started sidecar now"
} else {
    Write-Host "port 18090 already listening"
}
