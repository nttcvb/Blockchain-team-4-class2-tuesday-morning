$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$docx = (Resolve-Path -LiteralPath (Join-Path $taskRoot 'docs\Huong_dan_mo_hinh_Luna_UST.docx')).Path
$renderDir = Join-Path $taskRoot '.guide_work\render'
New-Item -ItemType Directory -Path $renderDir -Force | Out-Null
$pdf = Join-Path $renderDir 'guide.pdf'
$wordApp = $null
$guideDocument = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $guideDocument = $wordApp.Documents.Open($docx,$false,$true)
    $guideDocument.Fields.Update() | Out-Null
    $guideDocument.Repaginate()
    $pageCount = $guideDocument.ComputeStatistics(2)
    $guideDocument.ExportAsFixedFormat($pdf,17)
    [pscustomobject]@{Renderer='Microsoft Word fixed-format export';Pages=$pageCount;PDF=$pdf} | ConvertTo-Json
} finally {
    if ($null -ne $guideDocument) { $guideDocument.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($guideDocument) }
    if ($null -ne $wordApp) {
        if ($wordApp.Documents.Count -eq 0) { $wordApp.Quit(0) }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp)
    }
}
