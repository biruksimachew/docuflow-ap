$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "===== API LIVENESS ====="

$liveness = Invoke-RestMethod `
    -Uri "http://localhost:8000/health" `
    -Method Get

$liveness |
    ConvertTo-Json -Depth 5

Write-Host ""
Write-Host "===== DEPENDENCY READINESS ====="

$readiness = Invoke-RestMethod `
    -Uri "http://localhost:8000/health/ready" `
    -Method Get

$readiness |
    ConvertTo-Json -Depth 5

Write-Host ""
Write-Host "===== TESSERACT INSTALLATION ====="

docker compose exec -T api `
    tesseract --version

if ($LASTEXITCODE -ne 0) {
    throw "Tesseract is unavailable."
}

Write-Host ""
Write-Host "===== AUTOMATED TESTS ====="

docker compose exec -T api `
    pytest -q tests -p no:cacheprovider

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
Write-Host "===== SECURE INVOICE INTAKE ====="

docker compose exec -T api `
    python scripts/test_intake.py

if ($LASTEXITCODE -ne 0) {
    throw "Invoice intake test failed."
}

Write-Host ""
Write-Host "===== LOCAL OCR PROVIDER ====="

docker compose exec -T api `
    python -m scripts.check_ocr_provider

if ($LASTEXITCODE -ne 0) {
    throw "OCR provider test failed."
}

Write-Host ""
Write-Host "===== DOCUMENT OCR PIPELINE ====="

docker compose exec -T api `
    python -m scripts.check_document_pipeline

if ($LASTEXITCODE -ne 0) {
    throw "Document OCR pipeline test failed."
}

Write-Host ""
Write-Host "===== CANONICAL HEADER EXTRACTION ====="

docker compose exec -T api `
    python -m scripts.check_header_extraction

if ($LASTEXITCODE -ne 0) {
    throw "Header extraction test failed."
}

Write-Host ""
Write-Host "===== CANONICAL LINE-ITEM EXTRACTION ====="

docker compose exec -T api `
    python -m scripts.check_line_item_extraction

if ($LASTEXITCODE -ne 0) {
    throw "Line-item extraction test failed."
}

Write-Host ""
Write-Host "===== DETERMINISTIC VALIDATION ====="

docker compose exec -T api `
    python -m scripts.check_deterministic_validation

if ($LASTEXITCODE -ne 0) {
    throw "Deterministic validation test failed."
}

Write-Host ""
Write-Host "===== BUSINESS DUPLICATE DETECTION ====="

docker compose exec -T api `
    python -m scripts.check_business_duplicate

if ($LASTEXITCODE -ne 0) {
    throw "Business duplicate detection test failed."
}

Write-Host ""
Write-Host "===== VENDOR AND PURCHASE-ORDER MATCHING ====="

docker compose exec -T api `
    python -m scripts.check_vendor_po_matching

if ($LASTEXITCODE -ne 0) {
    throw "Vendor and PO matching test failed."
}

Write-Host ""
Write-Host "===== AUTHORITATIVE DECISION ENGINE ====="

docker compose exec -T api `
    python -m scripts.check_decision_engine

if ($LASTEXITCODE -ne 0) {
    throw "Authoritative decision engine test failed."
}

Write-Host ""
Write-Host "All DocuFlow AP decision-engine checks passed."