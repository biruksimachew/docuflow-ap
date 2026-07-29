$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "===== API LIVENESS ====="

$liveness = Invoke-RestMethod `
    -Uri "http://localhost:8000/health" `
    -Method Get

$liveness | ConvertTo-Json -Depth 5

Write-Host ""
Write-Host "===== DEPENDENCY READINESS ====="

$readiness = Invoke-RestMethod `
    -Uri "http://localhost:8000/health/ready" `
    -Method Get

$readiness | ConvertTo-Json -Depth 5

Write-Host ""
Write-Host "===== AUTOMATED TESTS ====="

docker compose exec -T api pytest -q

if ($LASTEXITCODE -ne 0) {
    throw "Automated tests failed."
}

Write-Host ""
Write-Host "===== CELERY TASK ====="

$taskResult = docker compose exec -T api python -c `
    "from app.workers.tasks import ping; print(ping.delay().get(timeout=15))"

if ($LASTEXITCODE -ne 0) {
    throw "Celery task failed."
}

Write-Host $taskResult

Write-Host ""
Write-Host "All DocuFlow AP foundation checks passed."
