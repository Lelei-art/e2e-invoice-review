$root = $PSScriptRoot
$jobs = @(
    Start-Job { Set-Location $using:root; uv run --project backend --locked --no-sync uvicorn backend.app.main:app --reload }
    Start-Job { Set-Location "$using:root\frontend"; corepack pnpm dev }
)

try {
    while (($jobs | Where-Object State -eq Running).Count -gt 0) {
        Receive-Job $jobs
        Start-Sleep -Seconds 1
    }
}
finally {
    $jobs | Stop-Job
    $jobs | Remove-Job
}
