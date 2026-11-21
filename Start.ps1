$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$workspacePython = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $projectPython) {
    $taskPython = $projectPython
} elseif (Test-Path -LiteralPath $workspacePython) {
    $taskPython = $workspacePython
} else {
    python -m venv .venv
    $taskPython = $projectPython
    & $taskPython -m pip install -e '.[test]'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
}
& $taskPython -m streamlit run app.py
