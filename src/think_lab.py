"""Copy instrument files into a checksum-verified archive."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tomllib
from pathlib import Path
from typing import Any


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_file(source: Path, destination: Path, expected: str) -> bool:
    """Atomically archive a file, returning false when it already exists."""

    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    shutil.copy2(source, temporary)
    if checksum(temporary) != expected:
        temporary.unlink(missing_ok=True)
        raise OSError(f"{source} changed while being copied")
    temporary.replace(destination)
    return True


def collect(config_path: Path) -> tuple[int, int]:
    """Collect configured files and return (archived, skipped)."""

    with config_path.open("rb") as file:
        config: dict[str, Any] = tomllib.load(file)

    archive = Path(config["archive"])
    archived = skipped = 0
    for machine in config.get("machines", []):
        if not machine.get("enabled", True):
            continue
        machine_name = machine["name"]
        for source_config in machine["sources"]:
            source_root = Path(source_config["path"])
            dataset = source_config["dataset"]
            if not source_root.exists():
                print(f"missing: {source_root}")
                continue
            for source in source_root.rglob("*"):
                if not source.is_file():
                    continue
                digest = checksum(source)
                destination = archive / machine_name / dataset / digest / source.name
                if archive_file(source, destination, digest):
                    archived += 1
                else:
                    skipped += 1
    return archived, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="think-lab")
    parser.add_argument("config", nargs="?", type=Path, default="config/machines.toml")
    args = parser.parse_args(argv)
    try:
        archived, skipped = collect(args.config)
    except (KeyError, OSError, tomllib.TOMLDecodeError) as error:
        parser.error(str(error))
    print(f"archived: {archived}, skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
