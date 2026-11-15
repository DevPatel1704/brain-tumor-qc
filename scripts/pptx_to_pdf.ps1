# Convert a .pptx to PDF with Microsoft PowerPoint (COM).
#   powershell -File scripts/pptx_to_pdf.ps1 -In docs\slides\btqc_presentation.pptx
param([Parameter(Mandatory = $true)][string]$In, [string]$Out = "")
$in = (Resolve-Path $In).Path
if (-not $Out) { $Out = [System.IO.Path]::ChangeExtension($in, ".pdf") }
$pp = New-Object -ComObject PowerPoint.Application
try {
    $pres = $pp.Presentations.Open($in, $true, $false, $false)   # read-only, untitled, no window
    $pres.SaveAs($Out, 32)                                        # ppSaveAsPDF
    "slides=$($pres.Slides.Count) pdf=$Out"
    $pres.Close()
} finally {
    $pp.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pp) | Out-Null
}
