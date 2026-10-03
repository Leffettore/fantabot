# The unattended matchday run: bring the bundled Postgres up, then field every lega with an
# open matchday.
#
# Scheduled by Windows Task Scheduler (see `scripts/register_matchday_task.ps1`). Idempotent:
# a run with no open matchday, or past the first kickoff, changes nothing, so it is safe to
# run several times a day. It submits only when BOTH locks are set: FANTABOT_AUTO_ACT=true in
# .env (the operator's choice, never this script's) and the --arm below.
#
# No Docker: the database is `fantabot-app`'s bundled Postgres (~/.fantabot/pgdata), started
# with `fantabot-app db start` — safe to call every run, since it leaves the server running
# and a second call against an already-running one is a no-op. Requires `fantabot-app` on
# PATH (`uv tool install ./app` from the repo root).
#
# --refresh brings voti/lega/news up to date per lega, once per matchday (the "due" marker
# caps it) — it is what actually runs FANTABOT_LINEUP_NEWS's roster-scoped news fetch when
# that setting is on. Without it, this command never refreshed anything at all.
#
# Output goes to logs\matchday-<date>.log, appended per run. Exit code is submit-all's.

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("matchday-{0:yyyy-MM-dd}.log" -f (Get-Date))

function Write-Log([string]$line) {
    ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $line) | Out-File -FilePath $log -Append -Encoding utf8
}

$conda = Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"

Write-Log "---- matchday run"

# Native output goes through cmd's redirection: PowerShell 5.1's `>>` would re-encode it as
# UTF-16 into a file that Write-Log keeps in UTF-8.
cmd /c "fantabot-app db start >> `"$log`" 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Log "fantabot-app db start failed"; exit 1 }

# Rich writes box-drawing characters; without UTF-8 the log fills with mojibake.
$env:PYTHONIOENCODING = "utf-8"
$env:COLUMNS = "160"

cmd /c "`"$conda`" run -n fanta --no-capture-output fantabot lineup submit-all --arm --refresh >> `"$log`" 2>&1"
$code = $LASTEXITCODE
Write-Log "submit-all exited $code"
exit $code
