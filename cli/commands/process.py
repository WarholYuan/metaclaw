"""CLI process management commands."""

import os
import sys
import subprocess
import time
import tempfile
import shutil
import zipfile
import urllib.request
from typing import Optional

import click

from cli.utils import get_project_root, get_pid_file, get_service_log_file
from common.brand import APP_NAME, CLI_NAME

_IS_WIN = sys.platform == "win32"


def _get_pid_file():
    return get_pid_file()


def _get_log_file():
    return get_service_log_file()


def _release_zip_url(version: str) -> str:
    """Build the release archive URL for non-git installations."""
    target = version[1:] if version.startswith("v") else version
    base = os.environ.get("METACLAW_RELEASE_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/{target}.zip"
    return f"https://github.com/WarholYuan/metaclaw/archive/refs/tags/{target}.zip"


def _find_extracted_project_dir(extract_dir: str) -> str:
    """Return the extracted directory that contains app.py."""
    direct = os.path.join(extract_dir, "app.py")
    if os.path.exists(direct):
        return extract_dir
    for name in os.listdir(extract_dir):
        candidate = os.path.join(extract_dir, name)
        if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "app.py")):
            return candidate
    raise RuntimeError("downloaded archive does not contain app.py")


def _replace_app_from_dir(source_dir: str, target_dir: str):
    """Replace application files while preserving local config/runtime data."""
    preserve = {
        "config.json",
        ".env",
        "nohup.out",
        "run.log",
        DEFAULT_LOCAL_PID_FILE,
        "__pycache__",
        ".pytest_cache",
        "tmp",
        "logs",
        "user_datas.pkl",
    }
    backup_base = os.path.join(
        os.path.dirname(target_dir),
        f"{os.path.basename(target_dir)}_backup_{time.strftime('%Y%m%d%H%M%S')}",
    )
    backup_dir = backup_base
    suffix = 1
    while os.path.exists(backup_dir):
        suffix += 1
        backup_dir = f"{backup_base}_{suffix}"
    shutil.copytree(target_dir, backup_dir, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))

    for name in os.listdir(target_dir):
        if name in preserve or name == ".git":
            continue
        path = os.path.join(target_dir, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    for name in os.listdir(source_dir):
        if name in preserve or name == ".git":
            continue
        src = os.path.join(source_dir, name)
        dst = os.path.join(target_dir, name)
        if os.path.isdir(src) and not os.path.islink(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    return backup_dir


DEFAULT_LOCAL_PID_FILE = f".{CLI_NAME}.pid"


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process is still running (cross-platform)."""
    if _IS_WIN:
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                stderr=subprocess.DEVNULL,
            )
            return str(pid) in out.decode(errors="ignore")
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def _kill_pid(pid: int, force: bool = False):
    """Terminate a process by PID (cross-platform)."""
    if _IS_WIN:
        flag = "/F" if force else ""
        cmd = ["taskkill"]
        if force:
            cmd.append("/F")
        cmd.extend(["/PID", str(pid)])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        import signal
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)


def _read_pid() -> Optional[int]:
    pid_file = _get_pid_file()
    if not os.path.exists(pid_file):
        return None
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        if _is_pid_alive(pid):
            return pid
        os.remove(pid_file)
        return None
    except (ValueError, OSError):
        try:
            os.remove(pid_file)
        except OSError:
            pass
        return None


def _write_pid(pid: int):
    with open(_get_pid_file(), "w") as f:
        f.write(str(pid))


def _remove_pid():
    pid_file = _get_pid_file()
    if os.path.exists(pid_file):
        os.remove(pid_file)


@click.command()
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground (don't daemonize)")
@click.option("--no-logs", is_flag=True, help="Don't tail logs after starting")
def start(foreground, no_logs):
    """Start agent service."""
    pid = _read_pid()
    if pid:
        click.echo(f"{APP_NAME} is already running (PID: {pid}).")
        return

    root = get_project_root()
    app_py = os.path.join(root, "app.py")
    if not os.path.exists(app_py):
        click.echo("Error: app.py not found in project root.", err=True)
        sys.exit(1)

    python = sys.executable

    if foreground:
        click.echo(f"Starting {APP_NAME} in foreground...")
        if _IS_WIN:
            sys.exit(subprocess.call([python, app_py], cwd=root))
        else:
            os.execv(python, [python, app_py])
    else:
        log_file = _get_log_file()
        click.echo(f"Starting {APP_NAME}...")
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        popen_kwargs = dict(cwd=root)
        if _IS_WIN:
            CREATE_NO_WINDOW = 0x08000000
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            )
        else:
            popen_kwargs["start_new_session"] = True

        with open(log_file, "a") as log:
            proc = subprocess.Popen(
                [python, app_py],
                stdout=log,
                stderr=log,
                **popen_kwargs,
            )
        _write_pid(proc.pid)
        click.echo(click.style(f"✓ {APP_NAME} started (PID: {proc.pid})", fg="green"))
        click.echo(f"  Logs: {log_file}")

        if not no_logs:
            click.echo("  Press Ctrl+C to stop tailing logs.\n")
            _tail_log(log_file)


@click.command()
def stop():
    """Stop agent service."""
    pid = _read_pid()
    if not pid:
        click.echo(f"{APP_NAME} is not running.")
        return

    click.echo(f"Stopping {APP_NAME} (PID: {pid})...")
    try:
        _kill_pid(pid)
        for _ in range(30):
            time.sleep(0.1)
            if not _is_pid_alive(pid):
                break
        else:
            _kill_pid(pid, force=True)
    except (ProcessLookupError, OSError):
        pass

    _remove_pid()
    click.echo(click.style(f"✓ {APP_NAME} stopped.", fg="green"))


@click.command()
@click.option("--no-logs", is_flag=True, help="Don't tail logs after restarting")
@click.pass_context
def restart(ctx, no_logs):
    """Restart agent service."""
    ctx.invoke(stop)
    time.sleep(1)
    ctx.invoke(start, no_logs=no_logs)


@click.command()
@click.argument("version", required=False)
@click.option("--force", is_flag=True, help="Allow update with local source changes")
@click.pass_context
def update(ctx, version, force):
    """Update and restart agent service.

    VERSION is optional. If provided, update to that Git tag, for example:
    metaclaw update 2.0.10
    """
    root = get_project_root()

    # 1. Stop service first so git pull won't conflict with running code
    ctx.invoke(stop)

    # 2. Git update
    if os.path.isdir(os.path.join(root, ".git")):
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            text=True,
        ).strip()
        if dirty and not force:
            click.echo("Error: local source files have changes. Update aborted.", err=True)
            click.echo("Run 'git status' in the app directory, or use --force if you know what you are doing.", err=True)
            sys.exit(1)

        if version:
            target = version[1:] if version.startswith("v") else version
            click.echo(f"Fetching tags and updating to {target}...")
            ret = subprocess.call(["git", "fetch", "--tags", "--force"], cwd=root)
            if ret != 0:
                click.echo("Error: git fetch failed.", err=True)
                sys.exit(1)
            ret = subprocess.call(["git", "rev-parse", "--verify", f"refs/tags/{target}"], cwd=root)
            if ret != 0:
                click.echo(f"Error: version tag not found: {target}", err=True)
                sys.exit(1)
            ret = subprocess.call(["git", "checkout", "--detach", target], cwd=root)
            if ret != 0:
                click.echo(f"Error: checkout failed for version {target}.", err=True)
                sys.exit(1)
        else:
            click.echo("Pulling latest code...")
            ret = subprocess.call(["git", "pull"], cwd=root)
            if ret != 0:
                click.echo("Error: git pull failed.", err=True)
                sys.exit(1)
    else:
        if not version:
            click.echo("Not a git repository. Provide a version to update from a release archive.", err=True)
            sys.exit(1)
        url = _release_zip_url(version)
        click.echo(f"Downloading release archive: {url}")
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = os.path.join(tmpdir, "metaclaw.zip")
            try:
                urllib.request.urlretrieve(url, archive_path)
                with zipfile.ZipFile(archive_path) as zf:
                    zf.extractall(tmpdir)
                source_dir = _find_extracted_project_dir(tmpdir)
                backup_dir = _replace_app_from_dir(source_dir, root)
                click.echo(f"Backed up previous app files to: {backup_dir}")
            except Exception as e:
                click.echo(f"Error: release archive update failed: {e}", err=True)
                sys.exit(1)

    python = sys.executable
    req_file = os.path.join(root, "requirements.txt")

    if _IS_WIN:
        # On Windows, the CLI exe (this process) locks itself, so
        # `pip install -e .` fails with WinError 5.  Write a small .bat
        # helper waits for the CLI process to exit, then installs & starts.
        bat = os.path.join(root, f"_{CLI_NAME}_update.bat")
        lines = [
            "@echo off",
            "chcp 65001 >nul",
            f"echo Waiting for {CLI_NAME}.exe to exit...",
            "timeout /t 3 /nobreak >nul",
        ]
        if os.path.exists(req_file):
            lines.append(f'echo Installing dependencies...')
            lines.append(f'"{python}" -m pip install -r requirements.txt -q')
        lines += [
            f"echo Reinstalling {CLI_NAME} CLI...",
            f'"{python}" -m pip install -e . -q',
            f"echo Starting {APP_NAME}...",
            f'"{python}" -m cli.cli start --no-logs',
            "echo.",
            "echo Update complete. You can close this window.",
            "pause >nul",
            "del \"%~f0\"",
        ]
        with open(bat, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        subprocess.Popen(
            ["cmd.exe", "/c", "start", f"{APP_NAME} Update", "/wait", bat],
            cwd=root,
        )
        click.echo(click.style(
            "✓ Update script launched. Please follow the new window for progress.",
            fg="green"))
    else:
        # 3. Install dependencies
        if os.path.exists(req_file):
            click.echo("Installing dependencies...")
            subprocess.call(
                [python, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                cwd=root,
            )
        click.echo(f"Reinstalling {CLI_NAME} CLI...")
        subprocess.call(
            [python, "-m", "pip", "install", "-e", ".", "-q"],
            cwd=root,
        )

        # 4. Start service
        click.echo("")
        time.sleep(1)
        ctx.invoke(start, no_logs=False)


@click.command()
def status():
    """Show running status."""
    from cli import __version__
    from cli.utils import load_config_json

    pid = _read_pid()
    if pid:
        click.echo(click.style(f"● {APP_NAME} is running (PID: {pid})", fg="green"))
    else:
        click.echo(click.style(f"● {APP_NAME} is not running", fg="red"))

    click.echo(f"  版本: v{__version__}")

    cfg = load_config_json()
    if cfg:
        channel = cfg.get("channel_type", "unknown")
        if isinstance(channel, list):
            channel = ", ".join(channel)
        click.echo(f"  通道: {channel}")
        click.echo(f"  模型: {cfg.get('model', 'unknown')}")
        mode = "Agent" if cfg.get("agent") else "Chat"
        click.echo(f"  模式: {mode}")


@click.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", default=50, help="Number of lines to show")
def logs(follow, lines):
    """View service logs."""
    log_file = _get_log_file()
    if not os.path.exists(log_file):
        click.echo("No log file found.")
        return

    if follow:
        _tail_log(log_file, lines)
    else:
        _print_last_lines(log_file, lines)


def _print_last_lines(file_path: str, n: int = 50):
    """Print the last N lines of a file (cross-platform)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        for line in all_lines[-n:]:
            click.echo(line, nl=False)
    except Exception as e:
        click.echo(f"Error reading log file: {e}", err=True)


def _tail_log(log_file: str, lines: int = 50):
    """Follow log file output. Blocks until Ctrl+C (cross-platform)."""
    _print_last_lines(log_file, lines)

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    click.echo(line, nl=False)
                else:
                    time.sleep(0.3)
    except KeyboardInterrupt:
        pass
