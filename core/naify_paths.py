import os
import sys
from pathlib import Path
from typing import Final
from core.naify_utility import print_log

def get_data_dir() -> Path:

    data_dir: Path

    if os.name == "nt": # Windows 환경
        data_dir = Path(os.environ["LOCALAPPDATA"]) / "Naify"
    else:
        data_dir = Path.home() / ".local" / "share" / "naify"

    return data_dir


def get_resource_dir() -> Path:

    resource_dir: Path

    if getattr(sys, "frozen", False): # PyInstaller 실행 환경
        resource_dir = Path(getattr(sys, "_MEIPASS"))
    else: # 일반 Python 실행 환경
        resource_dir = Path(__file__).resolve().parent.parent

    return resource_dir


def ensure_data_dirs() -> None:
    try:
        DATA_DIR.mkdir(parents=True)
        CACHE_DIR.mkdir(parents=True)
    except Exception as e:
        print_log(content=f"{e}")
    finally:
        print_log(content=f"Data Directory = {DATA_DIR}")
        print_log(content=f"Dir Exist? = {DATA_DIR.exists()}")
        print_log(content=f"Is file: {DATA_DIR.is_file()}")

        print("Contents:", list(DATA_DIR.iterdir()))
        print("Python:", sys.executable)
        print("Computer:", os.environ.get("COMPUTERNAME"))
        print("LocalAppData:", os.environ.get("LOCALAPPDATA"))
        

DATA_DIR: Final[Path] = get_data_dir()

CONFIG_PATH: Final[Path] = DATA_DIR / "config.json"

SECRETS_PATH: Final[Path] = DATA_DIR / "secrets.json"

CACHE_DIR: Final[Path] = DATA_DIR / "cache"

RESOURCE_DIR: Final[Path] = get_resource_dir()

WEB_DIR: Final[Path] = RESOURCE_DIR / "web"