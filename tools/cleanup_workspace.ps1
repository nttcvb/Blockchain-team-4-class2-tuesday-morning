$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$workspaceRoot = (Resolve-Path -LiteralPath (Join-Path $taskRoot '..')).Path
$auditDir = Join-Path $taskRoot 'outputs\cleanup'
New-Item -ItemType Directory -Path $auditDir -Force | Out-Null
$targets = [System.Collections.Generic.List[string]]::new()
$keepDirs = @('governance_1164_evidence','v4_fit_audit','v3_terminal_audit')
$keepFiles = @('dashboard_check.py','dashboard_check.json','dashboard_check_initial.json','dashboard_check_same_session.json','dashboard_presentation_audit.json','dashboard-presentation-proof.jpg','dashboard-presentation-server.json','dashboard-presentation-server.log','dashboard-presentation-server-error.log')
foreach ($item in Get-ChildItem -LiteralPath (Join-Path $taskRoot 'outputs\improvement') -Force) {
    if ($item.PSIsContainer -and $item.Name -notin $keepDirs) { $targets.Add($item.FullName) }
    elseif (-not $item.PSIsContainer -and $item.Extension -ne '.md' -and $item.Name -notin $keepFiles) { $targets.Add($item.FullName) }
}
$currentRuns = @('20261011T071942383237Z_train','20261011T071942831158Z_all')
foreach ($run in Get-ChildItem -LiteralPath (Join-Path $taskRoot 'outputs\calibration\runs') -Directory) {
    if ($run.Name -notin $currentRuns) { $targets.Add($run.FullName) }
}
foreach ($relative in @('.pytest_cache','tmp','luna_sim\__pycache__','tests\__pycache__','outputs\runs','outputs\experiments','outputs\calibration\candidate_all.json')) {
    $path = Join-Path $taskRoot $relative
    if (Test-Path -LiteralPath $path) { $targets.Add((Resolve-Path -LiteralPath $path).Path) }
}
foreach ($relative in @('outputs\COMPLETION_AUDIT.md','outputs\dashboard-final-tests.xml','outputs\dashboard-proof.jpg','outputs\historical_comparison.html','outputs\REPORT_VI.md','outputs\REPRODUCIBILITY.json','outputs\test-results.xml','outputs\v3-core-tests.xml','outputs\v3-tests.xml')) {
    $path = Join-Path $taskRoot $relative
    if (Test-Path -LiteralPath $path) { $targets.Add((Resolve-Path -LiteralPath $path).Path) }
}
$archive = Join-Path $workspaceRoot 'terra-luna-run-replication (1).zip'
$zipCheck = Join-Path $auditDir 'duplicate_archive_check.json'
if ((Test-Path -LiteralPath $archive) -and (Test-Path -LiteralPath $zipCheck)) {
    $proof = Get-Content -LiteralPath $zipCheck -Raw | ConvertFrom-Json
    if ($proof.all_extracted_files_match -ne $true) { throw 'Archive duplicate check did not pass' }
    $currentZipSHA = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($currentZipSHA -ne $proof.zip_sha256) { throw 'Archive changed since duplicate verification' }
    $targets.Add((Resolve-Path -LiteralPath $archive).Path)
}
$protected = @('data','luna_sim','tests','baselines','outputs\reconstruction')
$before = @{}
foreach ($relative in $protected) {
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $taskRoot $relative) -File -Recurse) {
        if ($file.FullName -notmatch '\\__pycache__\\') { $before[$file.FullName] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash }
    }
}
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $taskRoot 'outputs\calibration') -File) {
    if ($file.Name -ne 'candidate_all.json') { $before[$file.FullName]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash }
}
$rows = [System.Collections.Generic.List[object]]::new()
foreach ($target in $targets) {
    $resolved = (Resolve-Path -LiteralPath $target).Path
    $inProject = $resolved.StartsWith($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase)
    if (-not $inProject -and $resolved -ne $archive) { throw "Target outside authorized cleanup scope: $resolved" }
    if ($resolved -eq $taskRoot -or $resolved -eq $workspaceRoot) { throw 'Refusing workspace-root deletion' }
    $item = Get-Item -LiteralPath $resolved -Force
    $files = if ($item.PSIsContainer) { @(Get-ChildItem -LiteralPath $resolved -File -Recurse -Force) } else { @($item) }
    foreach ($file in $files) {
        if ($before.ContainsKey($file.FullName)) { throw "Protected dependency was included: $($file.FullName)" }
        $rows.Add([pscustomobject]@{Path=$file.FullName;Bytes=$file.Length;SHA256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()})
    }
}
$rows | Export-Csv -LiteralPath (Join-Path $auditDir 'deleted_files.csv') -NoTypeInformation -Encoding utf8
foreach ($target in $targets) { Remove-Item -LiteralPath $target -Recurse -Force }
foreach ($entry in $before.GetEnumerator()) {
    if (-not (Test-Path -LiteralPath $entry.Key)) { throw "Required file removed: $($entry.Key)" }
    if ((Get-FileHash -LiteralPath $entry.Key -Algorithm SHA256).Hash -ne $entry.Value) { throw "Required file changed: $($entry.Key)" }
}
$summary = [pscustomobject]@{Status='complete';FinishedUTC=(Get-Date).ToUniversalTime().ToString('o');DeletedFiles=$rows.Count;DeletedBytes=($rows|Measure-Object Bytes -Sum).Sum;DeletedTargets=@($targets);ProtectedFilesVerified=$before.Count;ProtectedFilesUnchanged=$true;Kept='Raw dataset, Python environment, core, tests and referenced baselines, current calibration runs, reconstruction and seed/cadence validation, current audits and source evidence'}
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $auditDir 'cleanup_summary.json') -Encoding utf8
$summary | Select-Object Status,DeletedFiles,DeletedBytes,ProtectedFilesVerified | ConvertTo-Json
