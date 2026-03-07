# Ralph-Beads Project Initialization (Windows PowerShell)
#
# Bootstraps a new Ralph-Beads project from the GitHub template.
# Idempotent - safe to re-run; skips completed steps.
#
# Usage:
#   .\init.ps1              # Interactive setup
#   .\init.ps1 -Check       # Check prerequisites only, no prompts
#   .\init.ps1 -SkipGitHub  # Skip all GitHub integration steps
#
# Steps:
#   1. Check prerequisites (git, python3, gh, bd)
#   2. Initialize beads database if needed
#   3. Detect/create GitHub remote
#   4. Detect/setup GitHub Project
#   5. Bootstrap GitHub labels
#   6. Save configuration to .ralph-beads.yml
#   7. Print summary and next steps

[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$SkipGitHub,
    [switch]$Help
)

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir = Join-Path $ScriptDir "scripts"
$ConfigFile = Join-Path $ScriptDir ".ralph-beads.yml"

if ($Help) {
    Write-Host "Usage: .\init.ps1 [-Check] [-SkipGitHub]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Check         Check prerequisites only, no prompts"
    Write-Host "  -SkipGitHub    Skip GitHub remote, projects, and label setup"
    Write-Host "  -Help          Show this help message"
    exit 0
}

# --- Helpers ---

function Write-Header {
    Write-Host ""
    Write-Host "========================================="
    Write-Host "  Ralph-Beads Project Initialization"
    Write-Host "========================================="
    Write-Host ""
}

function Write-Step {
    param([int]$Step, [string]$Description)
    Write-Host "--- Step ${Step}: $Description ---"
}

function Get-JsonField {
    param([string]$Json, [string]$PythonExpr)
    try {
        $result = $Json | python3 -c $PythonExpr 2>$null
        return $result
    } catch {
        return ""
    }
}

function Write-Summary {
    Write-Host ""
    Write-Host "========================================="
    Write-Host "  Setup Summary"
    Write-Host "========================================="
    Write-Host ""

    $beadsDir = Join-Path $ScriptDir ".beads"
    if (Test-Path $beadsDir) {
        Write-Host "  Beads database: initialized"
    } else {
        Write-Host "  Beads database: not initialized"
    }

    if (Test-Path $ConfigFile) {
        Write-Host "  Config file: $ConfigFile"
        $owner = & python3 (Join-Path $ScriptsDir "config.py") get github.owner 2>$null
        $repo = & python3 (Join-Path $ScriptsDir "config.py") get github.repo 2>$null
        $projectNum = & python3 (Join-Path $ScriptsDir "config.py") get github.project_number 2>$null
        if ($owner -and $repo) {
            Write-Host "  GitHub repo: $owner/$repo"
        } else {
            Write-Host "  GitHub repo: not configured"
        }
        if ($projectNum) {
            Write-Host "  GitHub Project: #$projectNum"
        } else {
            Write-Host "  GitHub Project: not configured"
        }
    } else {
        Write-Host "  Config file: not created"
    }

    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Write specs in specs/ describing what to build"
    Write-Host "  2. Run '.\loop.sh plan' (or use VS Code Copilot /plan) to generate the task graph"
    Write-Host "  3. Run '.\loop.sh' (or use VS Code Copilot /build) to start building"
    Write-Host ""
}

# --- Step 1: Prerequisites ---

Write-Header
Write-Step 1 "Checking prerequisites"

$prereqScript = Join-Path $ScriptsDir "prereqs.py"
$prereqJson = & python3 $prereqScript --json 2>&1 | Out-String
$prereqOk = Get-JsonField $prereqJson "import sys,json; print(json.load(sys.stdin).get('all_ok', False))"

# Show human-readable report
& python3 $prereqScript 2>&1
Write-Host ""

if ($prereqOk -ne "True") {
    Write-Host "Some prerequisites are missing. Install them and re-run .\init.ps1"
    $hasCore = Get-JsonField $prereqJson "import sys,json; tools={t['name']:t['found'] for t in json.load(sys.stdin)['tools']}; print(tools.get('git',False) and tools.get('python3',False))"
    if ($hasCore -ne "True") {
        Write-Host "ERROR: git and python3 are required. Cannot continue." -ForegroundColor Red
        exit 1
    }
    Write-Host "WARNING: Continuing with available tools (some features may be limited)." -ForegroundColor Yellow
    Write-Host ""
}

if ($Check) {
    Write-Host "Check complete."
    exit 0
}

# --- Step 2: Beads Database ---

Write-Step 2 "Beads database"

$beadsDir = Join-Path $ScriptDir ".beads"
if (Test-Path $beadsDir) {
    Write-Host "  .beads/ directory exists - skipping initialization."
    try {
        $issueCount = & bd list --json 2>$null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>$null
        Write-Host "  Current issues: $issueCount"
    } catch {
        Write-Host "  Current issues: unknown"
    }
} else {
    Write-Host "  Initializing beads database..."
    $bdPath = Get-Command bd -ErrorAction SilentlyContinue
    if ($bdPath) {
        try {
            & bd init 2>&1
            Write-Host "  Beads database initialized."
        } catch {
            Write-Host "  WARNING: bd init failed. You may need to initialize manually." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  WARNING: bd CLI not found - skipping beads initialization." -ForegroundColor Yellow
        Write-Host "  Install bd and re-run .\init.ps1 to initialize."
    }
}
Write-Host ""

# --- Step 3: GitHub Remote ---

Write-Step 3 "GitHub remote"

$githubOwner = ""
$githubRepo = ""

if ($SkipGitHub) {
    Write-Host "  Skipped (-SkipGitHub)."
} else {
    $remoteScript = Join-Path $ScriptsDir "gh_remote.py"
    $remoteResult = & python3 $remoteScript --check --json 2>&1 | Out-String
    $remoteStatus = Get-JsonField $remoteResult "import sys,json; print(json.load(sys.stdin).get('status','error'))"

    if ($remoteStatus -eq "found") {
        $githubOwner = Get-JsonField $remoteResult "import sys,json; r=json.load(sys.stdin).get('remote',{}); print(r.get('owner',''))"
        $githubRepo = Get-JsonField $remoteResult "import sys,json; r=json.load(sys.stdin).get('remote',{}); print(r.get('repo',''))"
        Write-Host "  GitHub remote: $githubOwner/$githubRepo"
    } elseif ($remoteStatus -eq "skipped" -and -not $Check) {
        # No remote found - run interactively to allow creation
        & python3 $remoteScript 2>&1
        # Re-check after interactive flow
        $remoteResult = & python3 $remoteScript --check --json 2>&1 | Out-String
        $remoteStatus = Get-JsonField $remoteResult "import sys,json; print(json.load(sys.stdin).get('status','error'))"
        if ($remoteStatus -eq "found") {
            $githubOwner = Get-JsonField $remoteResult "import sys,json; r=json.load(sys.stdin).get('remote',{}); print(r.get('owner',''))"
            $githubRepo = Get-JsonField $remoteResult "import sys,json; r=json.load(sys.stdin).get('remote',{}); print(r.get('repo',''))"
            Write-Host "  GitHub remote: $githubOwner/$githubRepo"
        } else {
            Write-Host "  GitHub remote: not configured (local-only mode)"
        }
    } else {
        Write-Host "  GitHub remote: $remoteStatus"
    }
}
Write-Host ""

# --- Step 4: GitHub Project ---

Write-Step 4 "GitHub Project"

$githubProject = ""

if ($SkipGitHub -or -not $githubOwner -or -not $githubRepo) {
    if ($SkipGitHub) {
        Write-Host "  Skipped (-SkipGitHub)."
    } else {
        Write-Host "  Skipped (no GitHub remote configured)."
    }
} else {
    $projectScript = Join-Path $ScriptsDir "gh_project_setup.py"
    $projectResult = & python3 $projectScript --check --json 2>&1 | Out-String
    $projectStatus = Get-JsonField $projectResult "import sys,json; print(json.load(sys.stdin).get('status','error'))"

    if ($projectStatus -eq "found") {
        $githubProject = Get-JsonField $projectResult "import sys,json; p=json.load(sys.stdin).get('project',{}); print(p.get('number',''))"
        $projectTitle = Get-JsonField $projectResult "import sys,json; p=json.load(sys.stdin).get('project',{}); print(p.get('title',''))"
        Write-Host "  Found GitHub Project: $projectTitle (#$githubProject)"
    } elseif ($projectStatus -eq "skipped" -and -not $Check) {
        Write-Host "  No GitHub Projects found."
        $createProject = Read-Host "  Create a new project with default columns? [Y/n]"
        if (-not $createProject) { $createProject = "Y" }
        if ($createProject -match "^[Yy]") {
            $createPython = @"
import sys, json
sys.path.insert(0, sys.argv[1])
import gh_project_setup
result = gh_project_setup.create_project(sys.argv[2], sys.argv[3])
if result:
    print(json.dumps(result))
else:
    print("{}")
"@
            $createResult = $createPython | python3 - $ScriptsDir $githubOwner $githubRepo 2>&1 | Out-String
            $githubProject = Get-JsonField $createResult "import sys,json; print(json.load(sys.stdin).get('number',''))"
            if ($githubProject) {
                Write-Host "  Created GitHub Project #$githubProject"
            } else {
                Write-Host "  WARNING: Failed to create project." -ForegroundColor Yellow
            }
        } else {
            Write-Host "  Skipped project creation."
        }
    } else {
        Write-Host "  GitHub Project: $projectStatus"
    }
}
Write-Host ""

# --- Step 5: Label Bootstrap ---

Write-Step 5 "GitHub labels"

if ($SkipGitHub -or -not $githubOwner -or -not $githubRepo) {
    if ($SkipGitHub) {
        Write-Host "  Skipped (-SkipGitHub)."
    } else {
        Write-Host "  Skipped (no GitHub remote configured)."
    }
} else {
    $labelsDone = & python3 (Join-Path $ScriptsDir "config.py") get labels.bootstrap 2>$null
    if ($labelsDone -eq "true") {
        Write-Host "  Labels already bootstrapped - skipping."
    } else {
        Write-Host "  Bootstrapping GitHub labels..."
        $labelsScript = Join-Path $ScriptsDir "gh-labels.sh"
        if (Test-Path $labelsScript) {
            # Try bash first (Git Bash / WSL), fall back to gh commands directly
            $bashPath = Get-Command bash -ErrorAction SilentlyContinue
            if ($bashPath) {
                & bash $labelsScript 2>&1
            } else {
                Write-Host "  WARNING: bash not available. Run 'bash scripts/gh-labels.sh' from Git Bash or WSL." -ForegroundColor Yellow
            }
        } else {
            Write-Host "  WARNING: gh-labels.sh not found - skipping." -ForegroundColor Yellow
        }
    }
}
Write-Host ""

# --- Step 6: Save Configuration ---

Write-Step 6 "Configuration"

$skipGithubFlag = if ($SkipGitHub) { "1" } else { "0" }
$savePython = @"
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
import config

owner = sys.argv[3]
repo = sys.argv[4]
project = sys.argv[5]
skip_github = sys.argv[6] == "1"

cfg = config.load_config(repo_root)

if owner:
    cfg["github"]["owner"] = owner
if repo:
    cfg["github"]["repo"] = repo
if project:
    cfg["github"]["project_number"] = project
if owner and repo and not skip_github:
    cfg["labels"]["bootstrap"] = "true"

config.save_config(cfg, repo_root)
print("  Configuration saved to .ralph-beads.yml")
"@

try {
    $savePython | python3 - $ScriptDir $ScriptsDir $githubOwner $githubRepo $githubProject $skipGithubFlag 2>&1
} catch {
    Write-Host "  WARNING: Failed to save configuration." -ForegroundColor Yellow
}

Write-Host ""

# --- Step 7: Summary ---

Write-Summary
