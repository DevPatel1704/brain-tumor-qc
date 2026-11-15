# Group B GPU chain for the final report (2026-11-15). Runs detached; each step logs to results/train_logs/.
# Steps continue even if one fails. Order: quick checks first, the long jobs last.
$ErrorActionPreference = 'Continue'
$repo = 'D:\Foundation Project\brain-tumor-qc'
$py = "$repo\.venv\Scripts\python.exe"
$logs = "$repo\results\train_logs"
$env:MLFLOW_DISABLE_AGENT_HINT = '1'
$env:PYTHONUNBUFFERED = '1'
Set-Location $repo

function Step($name, [string[]]$argv) {
    "$(Get-Date -Format 'HH:mm:ss') START $name" | Add-Content "$logs\group_b_chain.log"
    $p = Start-Process -FilePath $py -ArgumentList $argv -WorkingDirectory $repo -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput "$logs\$name.log" -RedirectStandardError "$logs\$name.err"
    "$(Get-Date -Format 'HH:mm:ss') END   $name exit=$($p.ExitCode)" | Add-Content "$logs\group_b_chain.log"
}

Step 'r7_r8' @('scripts/r7_r8_check.py', '--fold', 'mid', '--cases', '3')
Step 'embedding_shift' @('scripts/embedding_shift.py', '--fold', 'mid', '--per-group', '30')
Step 'infer_notta' @('scripts/infer.py', '--methods', 'baseline', '--groups', 'mid', '--per-split', '15',
                     '--flips', '1', '--pred-root', "$repo\results\predictions_notta")
Step 'infer_tta_entropy' @('scripts/infer.py', '--methods', 'tta_entropy', '--groups', 'mid', '--per-split', '15',
                           '--flips', '8')
Step 'infer_rolling' @('scripts/infer.py', '--methods', 'baseline', '--groups', 'mid', '--per-split', '15',
                       '--rolling', '--stop-at', '19:00', '--flips', '8')
"$(Get-Date -Format 'HH:mm:ss') CHAIN DONE" | Add-Content "$logs\group_b_chain.log"
