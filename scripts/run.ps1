#Requires -Version 5.1
<#
.SYNOPSIS
    MetaClaw installer & management script for Windows.
.DESCRIPTION
    One-liner install:
      irm https://cdn.link-ai.tech/code/metaclaw/run.ps1 | iex
    Or from a local clone:
      .\scripts\run.ps1              # install / configure
      .\scripts\run.ps1 start        # start service  (delegates to metaclaw CLI)
      .\scripts\run.ps1 stop|restart|status|logs|config|update|help
#>

param(
    [Parameter(Position = 0)]
    [string]$Command = ""
)

$ErrorActionPreference = "Stop"

# ── ensure UTF-8 console encoding on Windows ─────────────────────
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
chcp 65001 | Out-Null

# ── colours ──────────────────────────────────────────────────────
function Write-Cow   { param([string]$M) Write-Host $M -ForegroundColor Green  }
function Write-Warn  { param([string]$M) Write-Host $M -ForegroundColor Yellow }
function Write-Err   { param([string]$M) Write-Host $M -ForegroundColor Red    }
function Write-Info  { param([string]$M) Write-Host $M -ForegroundColor Cyan   }

# ── detect project directory ─────────────────────────────────────
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { $PWD.Path }
$BaseDir   = Split-Path $ScriptDir -Parent

$IsProjectDir = (Test-Path "$BaseDir\app.py") -and (Test-Path "$BaseDir\config-template.json")
if (-not $IsProjectDir) {
    $BaseDir = $PWD.Path
    $IsProjectDir = (Test-Path "$BaseDir\app.py") -and (Test-Path "$BaseDir\config-template.json")
}

# ── Python detection ─────────────────────────────────────────────
function Find-Python {
    foreach ($cmd in @("python3", "python")) {
        $bin = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $bin) { continue }
        try {
            $ver = & $bin.Source -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>$null
            $parts = $ver -split '\.'
            $major = [int]$parts[0]; $minor = [int]$parts[1]
            if ($major -eq 3 -and $minor -ge 9 -and $minor -le 13) {
                return $bin.Source
            }
        } catch {}
    }
    return $null
}

$PythonCmd = Find-Python
function Assert-Python {
    if (-not $PythonCmd) {
        Write-Err "Python 3.9-3.13 not found. Please install from https://www.python.org/downloads/"
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Cow "Found Python: $PythonCmd"
}

# ── clone project ────────────────────────────────────────────────
function Install-Project {
    if (Test-Path "MetaClaw") {
        Write-Warn "Directory 'MetaClaw' already exists."
        $choice = Read-Host "Overwrite(o), backup(b), or quit(q)? [default: b]"
        if (-not $choice) { $choice = "b" }
        switch ($choice.ToLower()) {
            "o" { Remove-Item -Recurse -Force "MetaClaw" }
            "b" {
                $backup = "MetaClaw_backup_$(Get-Date -Format 'yyyyMMddHHmmss')"
                Rename-Item "MetaClaw" $backup
                Write-Cow "Backed up to '$backup'"
            }
            "q" { Write-Err "Installation cancelled."; exit 1 }
            default { Write-Err "Invalid choice."; exit 1 }
        }
    }

    $gitBin = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitBin) {
        Write-Err "Git not found. Please install from https://git-scm.com/download/win"
        Read-Host "Press Enter to exit"
        exit 1
    }

    Write-Cow "Cloning MetaClaw project..."
    $cloneOk = $false

    # Test GitHub connectivity before attempting clone
    try {
        $null = Invoke-WebRequest -Uri "https://github.com" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Cow "GitHub is reachable, cloning from GitHub..."
        $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        git clone --depth 10 --progress "https://github.com/zhayujie/MetaClaw.git" 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -eq 0) { $cloneOk = $true }
        $ErrorActionPreference = $prevEAP
        if (-not $cloneOk) {
            if (Test-Path "MetaClaw") { Remove-Item -Recurse -Force "MetaClaw" }
        }
    } catch {}

    if (-not $cloneOk) {
        Write-Warn "GitHub clone failed or timed out, switching to Gitee mirror..."
        $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        git clone --depth 10 --progress "https://gitee.com/zhayujie/MetaClaw.git" 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -eq 0) { $cloneOk = $true }
        $ErrorActionPreference = $prevEAP
        if (-not $cloneOk) {
            if (Test-Path "MetaClaw") { Remove-Item -Recurse -Force "MetaClaw" }
        }
    }

    if (-not $cloneOk) {
        Write-Err "Clone failed from both GitHub and Gitee. Please check your network connection."
        Write-Err "You can also manually clone: git clone https://gitee.com/zhayujie/MetaClaw.git"
        Read-Host "Press Enter to exit"
        exit 1
    }

    Set-Location "MetaClaw"
    $script:BaseDir = $PWD.Path
    $script:IsProjectDir = $true
    Write-Cow "Project cloned: $BaseDir"
}

# ── install dependencies ─────────────────────────────────────────
function Install-Dependencies {
    Write-Cow "Installing dependencies..."

    $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $PythonCmd -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null

    & $PythonCmd -m pip install -r "$BaseDir\requirements.txt" 2>&1 | ForEach-Object { Write-Host $_ }
    $pipExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP
    if ($pipExit -ne 0) {
        Write-Warn "Some dependencies may have issues, but continuing..."
    }

    Write-Cow "Registering metaclaw CLI..."
    $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $PythonCmd -m pip install -e $BaseDir 2>&1 | Out-Null
    $ErrorActionPreference = $prevEAP

    # Ensure Python Scripts dir is in PATH for this session
    $scriptsDir = & $PythonCmd -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>$null
    if ($scriptsDir -and (Test-Path $scriptsDir)) {
        if ($env:PATH -notlike "*$scriptsDir*") {
            $env:PATH = "$scriptsDir;$env:PATH"
        }
    }

    $cowBin = Get-Command metaclaw -ErrorAction SilentlyContinue
    if ($cowBin) {
        Write-Cow "metaclaw CLI registered: $($cowBin.Source)"
    } else {
        Write-Warn "metaclaw CLI not in PATH. You can use: $PythonCmd -m cli.cli"
        Write-Warn "To fix permanently, add Python Scripts directory to your system PATH."
    }
}

# ── model selection ──────────────────────────────────────────────
$ModelChoices = @{
    "1" = @{ Provider = "MiniMax";                  Default = "MiniMax-M2.7";                           Key = "MINIMAX_KEY" }
    "2" = @{ Provider = "Zhipu AI";                 Default = "glm-5.1";                                Key = "ZHIPU_KEY" }
    "3" = @{ Provider = "Kimi (Moonshot)";          Default = "kimi-k2.6";                              Key = "MOONSHOT_KEY" }
    "4" = @{ Provider = "Doubao (Volcengine Ark)";  Default = "doubao-seed-2-0-code-preview-260215";    Key = "ARK_KEY" }
    "5" = @{ Provider = "Qwen (DashScope)";         Default = "qwen3.6-plus";                           Key = "DASHSCOPE_KEY" }
    "6" = @{ Provider = "Claude";                   Default = "claude-sonnet-4-6";                      Key = "CLAUDE_KEY";  Base = "https://api.anthropic.com/v1" }
    "7" = @{ Provider = "Gemini";                   Default = "gemini-3.1-pro-preview";                 Key = "GEMINI_KEY";  Base = "https://generativelanguage.googleapis.com" }
    "8" = @{ Provider = "OpenAI GPT";               Default = "gpt-5.4";                                Key = "OPENAI_KEY";  Base = "https://api.openai.com/v1" }
    "9" = @{ Provider = "LinkAI";                   Default = "MiniMax-M2.7";                           Key = "LINKAI_KEY" }
}

function Select-Model {
    Write-Info "========================================="
    Write-Info "   Select AI Model"
    Write-Info "========================================="
    Write-Host "1) MiniMax (MiniMax-M2.7, MiniMax-M2.5, etc.)"
    Write-Host "2) Zhipu AI (glm-5.1, glm-5-turbo, glm-5, etc.)"
    Write-Host "3) Kimi (kimi-k2.6, kimi-k2.5, kimi-k2, etc.)"
    Write-Host "4) Doubao (doubao-seed-2-0-code-preview-260215, etc.)"
    Write-Host "5) Qwen (qwen3.6-plus, qwen3.5-plus, qwen3-max, qwq-plus, etc.)"
    Write-Host "6) Claude (claude-sonnet-4-6, claude-opus-4-6, etc.)"
    Write-Host "7) Gemini (gemini-3.1-flash-lite-preview, gemini-3.1-pro-preview, etc.)"
    Write-Host "8) OpenAI GPT (gpt-5.4, gpt-5.2, gpt-4.1, etc.)"
    Write-Host "9) LinkAI (access multiple models via one API)"
    Write-Host ""

    do {
        $choice = Read-Host "Enter your choice [default: 1 - MiniMax]"
        if (-not $choice) { $choice = "1" }
    } while ($choice -notmatch '^[1-9]$')

    $m = $ModelChoices[$choice]
    Write-Cow "Configuring $($m.Provider)..."

    $script:ApiKey    = Read-Host "Enter $($m.Provider) API Key"
    $model            = Read-Host "Enter model name [default: $($m.Default)]"
    if (-not $model) { $model = $m.Default }
    $script:ModelName = $model
    $script:KeyName   = $m.Key
    $script:UseLinkai = ($choice -eq "9")

    if ($m.Base) {
        $base = Read-Host "Enter API Base URL [default: $($m.Base)]"
        if (-not $base) { $base = $m.Base }
        $script:ApiBase = $base
    } else {
        $script:ApiBase = ""
    }
    $script:ModelChoice = $choice
}

# ── channel selection ────────────────────────────────────────────
function Select-Channel {
    Write-Host ""
    Write-Info "========================================="
    Write-Info "   Select Communication Channel"
    Write-Info "========================================="
    Write-Host "1) Weixin"
    Write-Host "2) Feishu"
    Write-Host "3) DingTalk"
    Write-Host "4) WeCom Bot"
    Write-Host "5) QQ"
    Write-Host "6) WeCom App"
    Write-Host "7) Web"
    Write-Host ""

    do {
        $choice = Read-Host "Enter your choice [default: 1 - Weixin]"
        if (-not $choice) { $choice = "1" }
    } while ($choice -notmatch '^[1-7]$')

    $script:ChannelExtra = @{}

    switch ($choice) {
        "1" { $script:ChannelType = "weixin" }
        "2" {
            $script:ChannelType = "feishu"
            $script:ChannelExtra["feishu_app_id"]     = Read-Host "Enter Feishu App ID"
            $script:ChannelExtra["feishu_app_secret"]  = Read-Host "Enter Feishu App Secret"
        }
        "3" {
            $script:ChannelType = "dingtalk"
            $script:ChannelExtra["dingtalk_client_id"]     = Read-Host "Enter DingTalk Client ID"
            $script:ChannelExtra["dingtalk_client_secret"]  = Read-Host "Enter DingTalk Client Secret"
        }
        "4" {
            $script:ChannelType = "wecom_bot"
            $script:ChannelExtra["wecom_bot_id"]     = Read-Host "Enter WeCom Bot ID"
            $script:ChannelExtra["wecom_bot_secret"]  = Read-Host "Enter WeCom Bot Secret"
        }
        "5" {
            $script:ChannelType = "qq"
            $script:ChannelExtra["qq_app_id"]     = Read-Host "Enter QQ App ID"
            $script:ChannelExtra["qq_app_secret"]  = Read-Host "Enter QQ App Secret"
        }
        "6" {
            $script:ChannelType = "wechatcom_app"
            $script:ChannelExtra["wechatcom_corp_id"]       = Read-Host "Enter WeChat Corp ID"
            $script:ChannelExtra["wechatcomapp_token"]      = Read-Host "Enter WeChat Com App Token"
            $script:ChannelExtra["wechatcomapp_secret"]     = Read-Host "Enter WeChat Com App Secret"
            $script:ChannelExtra["wechatcomapp_agent_id"]   = Read-Host "Enter WeChat Com App Agent ID"
            $script:ChannelExtra["wechatcomapp_aes_key"]    = Read-Host "Enter WeChat Com App AES Key"
            $port = Read-Host "Enter port [default: 9898]"
            if (-not $port) { $port = "9898" }
            $script:ChannelExtra["wechatcomapp_port"] = [int]$port
        }
        "7" {
            $script:ChannelType = "web"
            $port = Read-Host "Enter web port [default: 9899]"
            if (-not $port) { $port = "9899" }
            $script:ChannelExtra["web_port"] = [int]$port
        }
    }
}

# ── generate config.json ─────────────────────────────────────────
function New-ConfigFile {
    Write-Cow "Generating config.json..."

    $config = [ordered]@{
        channel_type              = $ChannelType
        model                     = $ModelName
        open_ai_api_key           = ""
        open_ai_api_base          = "https://api.openai.com/v1"
        claude_api_key            = ""
        claude_api_base           = "https://api.anthropic.com/v1"
        gemini_api_key            = ""
        gemini_api_base           = "https://generativelanguage.googleapis.com"
        zhipu_ai_api_key          = ""
        moonshot_api_key          = ""
        ark_api_key               = ""
        dashscope_api_key         = ""
        minimax_api_key           = ""
        voice_to_text             = "openai"
        text_to_voice             = "openai"
        voice_reply_voice         = $false
        speech_recognition        = $true
        group_speech_recognition  = $false
        use_linkai                = $UseLinkai
        linkai_api_key            = ""
        linkai_app_code           = ""
        agent                     = $true
        agent_max_context_tokens  = 40000
        agent_max_context_turns   = 30
        agent_max_steps           = 15
    }

    # Set the correct API key field
    $keyMap = @{
        OPENAI_KEY   = "open_ai_api_key"
        CLAUDE_KEY   = "claude_api_key"
        GEMINI_KEY   = "gemini_api_key"
        ZHIPU_KEY    = "zhipu_ai_api_key"
        MOONSHOT_KEY = "moonshot_api_key"
        ARK_KEY      = "ark_api_key"
        DASHSCOPE_KEY = "dashscope_api_key"
        MINIMAX_KEY  = "minimax_api_key"
        LINKAI_KEY   = "linkai_api_key"
    }
    if ($keyMap.ContainsKey($KeyName)) {
        $config[$keyMap[$KeyName]] = $ApiKey
    }

    # Set API base if provided
    $baseMap = @{
        "6" = "claude_api_base"
        "7" = "gemini_api_base"
        "8" = "open_ai_api_base"
    }
    if ($ApiBase -and $baseMap.ContainsKey($ModelChoice)) {
        $config[$baseMap[$ModelChoice]] = $ApiBase
    }

    # Merge channel-specific fields
    foreach ($k in $ChannelExtra.Keys) {
        $config[$k] = $ChannelExtra[$k]
    }

    $jsonText = $config | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText("$BaseDir\config.json", $jsonText, (New-Object System.Text.UTF8Encoding $false))
    Write-Cow "Configuration file created."
}

# ── start via metaclaw CLI ─────────────────────────────────────────────
function Start-MetaClaw {
    Write-Cow "Starting MetaClaw..."
    $cowBin = Get-Command metaclaw -ErrorAction SilentlyContinue
    if ($cowBin) {
        & metaclaw start
    } else {
        Write-Warn "metaclaw CLI not found, starting directly..."
        & $PythonCmd "$BaseDir\app.py"
    }
}

# ── delegate management commands to metaclaw CLI ──────────────────────
function Invoke-CowCommand {
    param([string]$Cmd)
    $cowBin = Get-Command metaclaw -ErrorAction SilentlyContinue
    if ($cowBin) {
        & metaclaw $Cmd
    } else {
        Write-Err "metaclaw CLI not found. Run this script without arguments first to install."
        exit 1
    }
}

# ── usage ─────────────────────────────────────────────────────────
function Show-Usage {
    Write-Info "========================================="
    Write-Info "   MetaClaw Management Script (Windows)"
    Write-Info "========================================="
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\run.ps1               # Install / Configure"
    Write-Host "  .\run.ps1 <command>     # Management command"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  start      Start the service"
    Write-Host "  stop       Stop the service"
    Write-Host "  restart    Restart the service"
    Write-Host "  status     Check service status"
    Write-Host "  logs       View logs"
    Write-Host "  config     Reconfigure project"
    Write-Host "  update     Update and restart"
    Write-Host "  help       Show this message"
    Write-Host ""
}

# ── install mode ──────────────────────────────────────────────────
function Install-Mode {
    Clear-Host
    Write-Info "========================================="
    Write-Info "   MetaClaw Installation (Windows)"
    Write-Info "========================================="
    Write-Host ""

    if ($IsProjectDir) {
        Write-Cow "Detected existing project directory."
        if (Test-Path "$BaseDir\config.json") {
            Write-Cow "Project already configured."
            Write-Host ""
            Show-Usage
            return
        }
        Write-Warn "No config.json found. Let's configure your project!"
        Write-Host ""
        Assert-Python
    } else {
        Assert-Python
        Install-Project
    }

    Install-Dependencies
    Select-Model
    Select-Channel
    New-ConfigFile

    Write-Host ""
    $startNow = Read-Host "Start MetaClaw now? [Y/n]"
    if ($startNow -ne "n" -and $startNow -ne "N") {
        Start-MetaClaw
    } else {
        Write-Cow "Installation complete!"
        Write-Host ""
        Write-Host "To start manually:"
        Write-Host "  cd $BaseDir"
        Write-Host "  metaclaw start"
    }
}

# ── update ────────────────────────────────────────────────────────
function Update-Project {
    Write-Cow "Updating MetaClaw..."
    Set-Location $BaseDir

    # Stop if running
    $cowBin = Get-Command metaclaw -ErrorAction SilentlyContinue
    if ($cowBin) {
        $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        & metaclaw stop 2>&1 | Out-Null
        $ErrorActionPreference = $prevEAP
    }

    if (Test-Path "$BaseDir\.git") {
        Write-Cow "Pulling latest code..."
        $prevEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        git pull 2>&1 | Out-Null
        $pullExit = $LASTEXITCODE
        $ErrorActionPreference = $prevEAP
        if ($pullExit -ne 0) {
            Write-Warn "GitHub failed, trying Gitee..."
            $ErrorActionPreference = "Continue"
            git remote set-url origin https://gitee.com/zhayujie/MetaClaw.git 2>&1 | Out-Null
            git pull 2>&1 | Out-Null
            $ErrorActionPreference = $prevEAP
        }
    } else {
        Write-Warn "Not a git repository, skipping code update."
    }

    Assert-Python
    Install-Dependencies

    # Start via python -m cli.cli instead of metaclaw.exe, because the exe may
    # still be cached/locked from the previous installation on Windows.
    Write-Cow "Starting MetaClaw..."
    & $PythonCmd -m cli.cli start
}

# ── main ──────────────────────────────────────────────────────────
switch ($Command.ToLower()) {
    ""        { Install-Mode }
    "start"   { Invoke-CowCommand "start" }
    "stop"    { Invoke-CowCommand "stop" }
    "restart" { Invoke-CowCommand "restart" }
    "status"  { Invoke-CowCommand "status" }
    "logs"    { Invoke-CowCommand "logs" }
    "config"  {
        Assert-Python
        Install-Dependencies
        Select-Model
        Select-Channel
        New-ConfigFile
        $r = Read-Host "Restart service now? [Y/n]"
        if ($r -ne "n" -and $r -ne "N") { Invoke-CowCommand "restart" }
    }
    "update"  { Update-Project }
    "help"    { Show-Usage }
    default   {
        Write-Err "Unknown command: $Command"
        Show-Usage
        exit 1
    }
}
