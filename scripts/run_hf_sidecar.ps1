$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $env:HF_HOME) { $env:HF_HOME = "D:\huggingface_cache" }
$env:HUGGINGFACE_HUB_CACHE = $env:HF_HOME
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
if (-not $env:EMBEDDING_MODEL) { $env:EMBEDDING_MODEL = "BAAI/bge-m3" }
if (-not $env:RERANK_MODEL) { $env:RERANK_MODEL = "BAAI/bge-reranker-v2-m3" }
Set-Location (Join-Path $root "apps\hf-sidecar")
Write-Host "HF_HOME=$env:HF_HOME  port=18090"
python -m uvicorn main:app --host 127.0.0.1 --port 18090
