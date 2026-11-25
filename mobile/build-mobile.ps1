param(
    [string] $Abis = 'arm64-v8a,x86_64',
    [string] $ArmArch = 'armv8-a',
    [switch] $DeviceTests
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$project = Split-Path $PSScriptRoot
$build = Join-Path $PSScriptRoot 'build'
$qwen = Join-Path $build 'qwen3-tts.cpp'
$revision = '16bb5afcd06311031c72a8488f8d59660dc2fb46'
New-Item -ItemType Directory -Force -Path $build | Out-Null

if (-not (Test-Path -LiteralPath "$qwen/.git")) {
    git clone --filter=blob:none --no-checkout https://github.com/Danmoreng/qwen3-tts.cpp.git $qwen
}
if ((git -C $qwen rev-parse HEAD) -ne $revision) {
    git -C $qwen checkout --detach $revision
}
git -C $qwen submodule update --init --recursive --depth 1
$qwenCmake = Join-Path $qwen 'CMakeLists.txt'
$flags = [IO.File]::ReadAllText($qwenCmake)
if ($flags.Contains(' -O3 -march=native')) {
    [IO.File]::WriteAllText($qwenCmake, $flags.Replace(' -O3 -march=native', ' -O3'))
}
$workerPatch = Join-Path $project 'desktop-agent/android-tts/reuse-ggml-workers.patch'
$PSNativeCommandUseErrorActionPreference = $false
git -C "$qwen/ggml" apply --unidiff-zero --reverse --check $workerPatch 2>$null
$alreadyPatched = $LASTEXITCODE -eq 0
$PSNativeCommandUseErrorActionPreference = $true
if (-not $alreadyPatched) {
    git -C "$qwen/ggml" apply --unidiff-zero $workerPatch
}

Push-Location (Join-Path $project 'desktop')
try {
    if (-not (Test-Path -LiteralPath 'node_modules/vite')) {
        npm install --legacy-peer-deps --no-package-lock
    }
    node node_modules/vite/bin/vite.js build --config vite.mobile-avatar.config.ts
} finally {
    Pop-Location
}

python "$PSScriptRoot/prepare-assets.py"
python "$project/desktop-agent/android-tts/export_voice.py" `
    "$project/voice-agent/resources/voice/aura_voice_xvec.pt" "$build/assets/aura-speaker.json"

$task = if ($DeviceTests) { 'connectedDebugAndroidTest' } else { 'assembleDebug' }
& "$PSScriptRoot/gradlew.bat" -p $PSScriptRoot $task "-PauraAbis=$Abis" "-PauraArmArch=$ArmArch"
