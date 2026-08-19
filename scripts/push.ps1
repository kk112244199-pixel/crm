# 本机 Git HTTPS 到 github.com 常被重置时使用（SSH 443）。
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$env:GIT_SSH = Join-Path $PSScriptRoot "git-ssh-github443.cmd"
Set-Location $root
if ($args.Count -eq 0) {
  git push
} else {
  git @args
}
