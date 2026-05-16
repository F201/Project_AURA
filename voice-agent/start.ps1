# Wrapper invoked by PM2 for the voice-agent process.
# Reads TTS_TYPE from ../.env and activates the right Python env.
# conda run is used for qwen (GPU) so PM2 doesn't need to manage env activation.

$envFile = Join-Path $PSScriptRoot "../.env"
$ttsType = "cartesia"

if (Test-Path $envFile) {
    $line = Get-Content $envFile | Where-Object { $_ -match "^TTS_TYPE\s*=" } | Select-Object -First 1
    if ($line) { $ttsType = ($line -split "=", 2)[1].Trim() }
}

if ($ttsType -eq "qwen") {
    Write-Host "[voice-agent] TTS_TYPE=qwen — launching via conda env 'aura'"
    conda run -n aura --no-capture-output python agent.py dev
} else {
    Write-Host "[voice-agent] TTS_TYPE=$ttsType — launching via venv"
    & "$PSScriptRoot/venv/Scripts/python.exe" agent.py dev
}
