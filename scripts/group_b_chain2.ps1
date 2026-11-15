# Group B GPU chain, second part (2026-11-15): test-time adaptation on in-site test + held-out cases only,
# the 1-flip comparison run, then extra baseline cases until the stop time. Runs detached.
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

Step 'infer_tta_entropy' @('scripts/infer.py', '--methods', 'tta_entropy', '--groups', 'mid', '--per-split', '15',
                           '--splits', 'insite_test', 'heldout', '--flips', '8')
# relative path: no space in the argument (the first chain failed on "Foundation Project")
Step 'infer_notta' @('scripts/infer.py', '--methods', 'baseline', '--groups', 'mid', '--per-split', '15',
                     '--flips', '1', '--pred-root', 'results/predictions_notta')
Step 'infer_rolling' @('scripts/infer.py', '--methods', 'baseline', '--groups', 'mid', '--per-split', '15',
                       '--rolling', '--stop-at', '18:30', '--flips', '8')
"$(Get-Date -Format 'HH:mm:ss') CHAIN2 DONE" | Add-Content "$logs\group_b_chain.log"
