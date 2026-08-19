@echo off
REM GitHub 在本机常阻断 git HTTPS；走 ssh.github.com:443。
C:\Windows\System32\OpenSSH\ssh.exe -p 443 -i "%USERPROFILE%\.ssh\id_ed25519_github" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new %*
