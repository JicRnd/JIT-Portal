"""
JIT Cylinder Quote - Milestone 1 Windows Builder / Launcher

What this script does:
1. Finds Cylinder_Quote_Web_Milestone_1.zip.
2. Extracts the project if it is not already installed.
3. Creates a private Python virtual environment (.venv).
4. Installs the project's requirements (Flask).
5. Creates RUN_CYLINDER_QUOTE.bat for future launches.
6. Starts the Flask calculator on port 5055.
7. Opens http://127.0.0.1:5055 in the default browser.

Recommended use:
- Put this .py file and Cylinder_Quote_Web_Milestone_1.zip in the same folder.
- Double-click this file, or run: python BUILD_AND_RUN_CYLINDER_QUOTE.py
- Press Ctrl+C in the console to stop the server.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import webbrowser
import zipfile
from pathlib import Path

PROJECT_FOLDER = "Cylinder_Quote_Web_Milestone_1"
ZIP_NAME = f"{PROJECT_FOLDER}.zip"
PORT = 5055
LOCAL_URL = f"http://127.0.0.1:{PORT}"
HEALTH_URL = f"{LOCAL_URL}/api/health"


def banner(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72)


def pause_on_error(message: str) -> None:
    print(f"\nERROR: {message}")
    print("\nPress Enter to close this window.")
    try:
        input()
    except EOFError:
        pass
    raise SystemExit(1)


def check_python() -> None:
    if sys.version_info < (3, 9):
        pause_on_error(
            f"Python 3.9 or newer is required. You are running {sys.version.split()[0]}."
        )
    print(f"Python: {sys.executable}")
    print(f"Version: {sys.version.split()[0]}")


def candidate_zip_paths(script_dir: Path) -> list[Path]:
    candidates = [script_dir / ZIP_NAME]

    home = Path.home()
    candidates.extend(
        [
            home / "Downloads" / ZIP_NAME,
            home / "Desktop" / ZIP_NAME,
            Path.cwd() / ZIP_NAME,
        ]
    )

    # Keep order but remove duplicates.
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_zip(script_dir: Path) -> Path | None:
    for path in candidate_zip_paths(script_dir):
        if path.is_file():
            return path
    return None


def validate_project(project_dir: Path) -> bool:
    required = [
        project_dir / "run.py",
        project_dir / "requirements.txt",
        project_dir / "app" / "web.py",
        project_dir / "cylinder_quote_engine" / "engine.py",
        project_dir / "data" / "series_pricing.csv",
    ]
    return all(path.exists() for path in required)


def extract_project(zip_path: Path, install_root: Path) -> Path:
    project_dir = install_root / PROJECT_FOLDER

    if validate_project(project_dir):
        print(f"Existing installation found: {project_dir}")
        return project_dir

    if project_dir.exists():
        print("An incomplete project folder already exists.")
        backup = install_root / f"{PROJECT_FOLDER}_incomplete_backup"
        if backup.exists():
            shutil.rmtree(backup)
        project_dir.rename(backup)
        print(f"Moved it to: {backup}")

    print(f"Extracting: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(install_root)

    if not validate_project(project_dir):
        pause_on_error(
            "The ZIP extracted, but the expected project files were not found. "
            "Make sure you are using Cylinder_Quote_Web_Milestone_1.zip."
        )

    print(f"Installed project: {project_dir}")
    return project_dir


def venv_python_path(project_dir: Path) -> Path:
    if os.name == "nt":
        return project_dir / ".venv" / "Scripts" / "python.exe"
    return project_dir / ".venv" / "bin" / "python"


def create_venv(project_dir: Path) -> Path:
    env_dir = project_dir / ".venv"
    env_python = venv_python_path(project_dir)

    if env_python.exists():
        print(f"Virtual environment already exists: {env_dir}")
        return env_python

    print(f"Creating virtual environment: {env_dir}")
    try:
        venv.EnvBuilder(with_pip=True, clear=False).create(env_dir)
    except Exception as exc:
        pause_on_error(f"Could not create the Python virtual environment: {exc}")

    if not env_python.exists():
        pause_on_error("Virtual environment was created, but its Python executable is missing.")

    return env_python


def run_checked(command: list[str], cwd: Path, description: str) -> None:
    print(f"\n{description}...")
    print(" ".join(command))
    try:
        result = subprocess.run(command, cwd=str(cwd), check=False)
    except OSError as exc:
        pause_on_error(f"Could not run {description}: {exc}")

    if result.returncode != 0:
        pause_on_error(f"{description} failed with exit code {result.returncode}.")


def install_requirements(env_python: Path, project_dir: Path) -> None:
    requirements = project_dir / "requirements.txt"

    # First check whether Flask is already importable in this project's venv.
    check = subprocess.run(
        [str(env_python), "-c", "import flask; print(flask.__version__ if hasattr(flask, '__version__') else 'installed')"],
        cwd=str(project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )

    if check.returncode == 0:
        print(f"Flask is already installed in the project environment ({check.stdout.strip()}).")
        return

    run_checked(
        [str(env_python), "-m", "pip", "install", "-r", str(requirements)],
        project_dir,
        "Installing Flask and project requirements",
    )


def verify_application(env_python: Path, project_dir: Path) -> None:
    verify_code = (
        "from app import create_app; "
        "app=create_app(); "
        "client=app.test_client(); "
        "r=client.get('/api/health'); "
        "assert r.status_code == 200, r.status_code; "
        "print(r.get_json())"
    )
    run_checked(
        [str(env_python), "-c", verify_code],
        project_dir,
        "Verifying the calculator application",
    )


def create_future_launcher(project_dir: Path) -> Path:
    launcher = project_dir / "RUN_CYLINDER_QUOTE.bat"
    contents = r'''@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment is missing.
    echo Run BUILD_AND_RUN_CYLINDER_QUOTE.py again to repair the installation.
    pause
    exit /b 1
)
start "" http://127.0.0.1:5055
.venv\Scripts\python.exe run.py
pause
'''
    launcher.write_text(contents, encoding="utf-8", newline="\r\n")
    print(f"Future launcher created: {launcher}")
    return launcher


def wait_for_server(timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.4)
    return False


def local_network_ip() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def start_server(env_python: Path, project_dir: Path) -> None:
    banner("STARTING JIT CYLINDER QUOTE CALCULATOR")
    print(f"Local address: {LOCAL_URL}")
    ip = local_network_ip()
    if ip:
        print(f"LAN address:   http://{ip}:{PORT}")
        print("Other PCs on the same network may use the LAN address if Windows Firewall allows it.")

    print("\nStarting the Flask server...")
    try:
        process = subprocess.Popen(
            [str(env_python), "run.py"],
            cwd=str(project_dir),
        )
    except OSError as exc:
        pause_on_error(f"Could not start the server: {exc}")

    if wait_for_server():
        print("\nServer health check: PASS")
        print(f"Opening browser: {LOCAL_URL}")
        webbrowser.open(LOCAL_URL)
    else:
        print("\nWARNING: The server did not answer its health check within 20 seconds.")
        print("Check the messages above for a Flask startup error.")

    print("\nThe calculator server is running.")
    print("Leave this window open while using the calculator.")
    print("Press Ctrl+C here when you want to stop it.\n")

    try:
        return_code = process.wait()
        if return_code != 0:
            print(f"Server stopped with exit code {return_code}.")
    except KeyboardInterrupt:
        print("\nStopping calculator...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print("Calculator stopped.")


def main() -> None:
    banner("JIT CYLINDER QUOTE - BUILD AND RUN")
    check_python()

    script_dir = Path(__file__).resolve().parent
    install_root = script_dir
    project_dir = install_root / PROJECT_FOLDER

    if validate_project(project_dir):
        print(f"Using existing project installation: {project_dir}")
    else:
        zip_path = find_zip(script_dir)
        if zip_path is None:
            searched = "\n".join(f"  - {p}" for p in candidate_zip_paths(script_dir))
            pause_on_error(
                f"Could not find {ZIP_NAME}.\n\n"
                "Put the Milestone 1 ZIP in the same folder as this Python file and run it again.\n\n"
                f"Locations checked:\n{searched}"
            )
        project_dir = extract_project(zip_path, install_root)

    env_python = create_venv(project_dir)
    install_requirements(env_python, project_dir)
    verify_application(env_python, project_dir)
    create_future_launcher(project_dir)

    banner("BUILD COMPLETE")
    print(f"Project folder: {project_dir}")
    print("Next time you can run RUN_CYLINDER_QUOTE.bat inside that folder.")

    start_server(env_python, project_dir)


if __name__ == "__main__":
    main()
