# Convert a .docx to PDF with Microsoft Word (COM) and print the page count.
#   powershell -File scripts/docx_to_pdf.ps1 -In docs\report\btqc_report.docx
param([Parameter(Mandatory = $true)][string]$In, [string]$Out = "")
$in = (Resolve-Path $In).Path
if (-not $Out) { $Out = [System.IO.Path]::ChangeExtension($in, ".pdf") }
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($in, $false, $true)
    $pages = $doc.ComputeStatistics(2)   # wdStatisticPages
    $doc.SaveAs([ref]$Out, [ref]17)      # wdFormatPDF
    $doc.Close([ref]0)
    "pages=$pages pdf=$Out"
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
