"""Load .env and upload dist/* with twine using TWINE_* credentials."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
DIST = ROOT / "dist"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value

    # Back-compat for older .env keys
    if "TWINE_USERNAME" not in os.environ and "USERNAME" in os.environ:
        os.environ["TWINE_USERNAME"] = os.environ["USERNAME"]
    if "TWINE_PASSWORD" not in os.environ and "TOKEN" in os.environ:
        os.environ["TWINE_PASSWORD"] = os.environ["TOKEN"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload built distributions with twine.")
    parser.add_argument(
        "--repository",
        default="pypi",
        help="Twine repository name (pypi or testpypi).",
    )
    args = parser.parse_args()

    load_dotenv(ENV_PATH)

    username = os.environ.get("TWINE_USERNAME", "")
    password = os.environ.get("TWINE_PASSWORD", "")
    if username != "__token__" or not password.startswith("pypi-"):
        print(
            "Missing or invalid PyPI credentials.\n"
            "Put this in .env:\n"
            "  TWINE_USERNAME=__token__\n"
            "  TWINE_PASSWORD=pypi-<your-api-token>\n"
            "Create a token at https://pypi.org/manage/account/token/",
            file=sys.stderr,
        )
        return 1

    artifacts = sorted(DIST.glob("*"))
    artifacts = [p for p in artifacts if p.suffix in {".whl", ".gz"}]
    if not artifacts:
        print(f"No distributions found in {DIST}", file=sys.stderr)
        return 1

    cmd = ["twine", "upload", "--non-interactive"]
    if args.repository != "pypi":
        cmd.extend(["--repository", args.repository])
    cmd.extend(str(p) for p in artifacts)

    print("Uploading:", ", ".join(p.name for p in artifacts))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
