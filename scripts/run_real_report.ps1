param(
    [string]$Category = "pet feeder",
    [string]$Market = "BR",
    [string]$Output = "reports/real-latest.json"
)

$ErrorActionPreference = "Stop"
$envFile = Join-Path (Get-Location) ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing .env. Copy .env.example and configure QWEN_API_KEY first."
}

Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split("=", 2)
        Set-Item -Path ("Env:" + $parts[0].Trim()) -Value $parts[1].Trim().Trim('"').Trim("'")
    }
}

$env:PYTHONPATH = "backend"
python -m foresight $Category --market $Market --mode real --output $Output
