#!/usr/bin/env python3
"""Think-Lab instrument collection, Oak upload, and staging retention CLI."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tomllib
from typing import Iterator, Sequence


class WorkflowError(RuntimeError):
    """Raised when an operation cannot safely continue."""


def log(message: str) -> None:
    """Write a timestamped message suitable for journald."""
    timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}", flush=True)


def load_config(path: Path) -> dict:
    """Load and validate the dependency-free TOML configuration."""
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    settings = config.get("settings")
    instruments = config.get("instruments")
    if not isinstance(settings, dict) or not isinstance(instruments, list):
        raise WorkflowError("Configuration requires [settings] and [[instruments]].")

    staging_root = PurePosixPath(settings.get("staging_root", ""))
    if staging_root != PurePosixPath("/srv/instrument-data"):
        raise WorkflowError("staging_root must be /srv/instrument-data.")

    seen: set[str] = set()
    required = {"id", "display_name", "mount", "oak_directory"}
    for instrument in instruments:
        missing = required.difference(instrument)
        if missing:
            raise WorkflowError(
                f"Instrument is missing fields: {', '.join(sorted(missing))}"
            )
        instrument_id = instrument["id"]
        if not isinstance(instrument_id, str) or not instrument_id.replace("-", "").isalnum():
            raise WorkflowError(f"Invalid instrument id: {instrument_id!r}")
        oak_directory = instrument["oak_directory"]
        if not isinstance(oak_directory, str) or not oak_directory.replace("-", "").isalnum():
            raise WorkflowError(f"Invalid Oak directory: {oak_directory!r}")
        if not PurePosixPath(instrument["mount"]).is_absolute():
            raise WorkflowError(f"Mount must be absolute: {instrument['mount']!r}")
        if instrument_id in seen:
            raise WorkflowError(f"Duplicate instrument id: {instrument_id}")
        seen.add(instrument_id)
    return config


def enabled_instruments(config: dict) -> list[dict]:
    """Return instruments enabled for scheduled processing."""
    return [item for item in config["instruments"] if item.get("enabled", True)]


def staging_path(config: dict, instrument: dict) -> Path:
    """Return an instrument's local staging directory."""
    return Path(config["settings"]["staging_root"]) / instrument["id"]


def validate_clock(settings: dict, now: dt.datetime | None = None) -> None:
    """Refuse timestamp-based work when the Pi clock is implausibly old."""
    current = now or dt.datetime.now().astimezone()
    configured_minimum = settings["minimum_valid_time"]
    minimum = (
        configured_minimum
        if isinstance(configured_minimum, dt.datetime)
        else dt.datetime.fromisoformat(configured_minimum)
    )
    if current < minimum:
        raise WorkflowError(f"System clock is invalid: {current.isoformat()}")


def require_free_space(path: Path, minimum_free_gib: int) -> None:
    """Stop pulls before the staging filesystem reaches critical capacity."""
    available = shutil.disk_usage(path).free
    required = minimum_free_gib * 1024**3
    if available < required:
        raise WorkflowError(f"Less than {minimum_free_gib} GiB remains on {path}.")


def recent_relative_files(source: Path, cutoff: dt.datetime) -> Iterator[str]:
    """Yield rsync-relative paths for regular files modified after cutoff."""
    cutoff_timestamp = cutoff.timestamp()
    for root, _directories, filenames in os.walk(source):
        root_path = Path(root)
        for filename in filenames:
            candidate = root_path / filename
            try:
                if candidate.is_file() and candidate.stat().st_mtime > cutoff_timestamp:
                    yield candidate.relative_to(source).as_posix()
            except OSError as error:
                log(f"WARNING: Could not inspect {candidate}: {error}")


def run(command: Sequence[str], *, input_bytes: bytes | None = None) -> None:
    """Run an external command without invoking a shell."""
    subprocess.run(command, input=input_bytes, check=True)


def mount_is_readable(path: Path) -> bool:
    """Trigger an automount and bound an SMB directory-read attempt to 30 seconds."""
    result = subprocess.run(
        ["timeout", "30", "ls", "--", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0 and path.is_mount()


@contextlib.contextmanager
def process_lock(path: Path):
    """Prevent two instances of the same workflow from running concurrently."""
    import fcntl  # Linux-only; lazy import permits unit tests on Windows.

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise WorkflowError(f"Another workflow holds {path}.") from error
        yield


def lock_path(operation: str) -> Path:
    """Keep runtime locks in the service account's private state directory."""
    return Path.home() / ".local" / "state" / "think-lab" / f"{operation}.lock"


def pull(config: dict, preview: bool) -> int:
    """Copy recently modified files from read-only mounts into staging."""
    settings = config["settings"]
    root = Path(settings["staging_root"])
    if not root.is_dir():
        raise WorkflowError(f"Staging directory is unavailable: {root}")
    validate_clock(settings)
    root.mkdir(parents=True, exist_ok=True)
    require_free_space(root, int(settings["minimum_free_gib"]))
    cutoff = dt.datetime.now().astimezone() - dt.timedelta(days=int(settings["recent_days"]))
    status = 0

    with process_lock(lock_path("pull")):
        for instrument in enabled_instruments(config):
            source = Path(instrument["mount"])
            destination = staging_path(config, instrument)
            log(f"Pulling {instrument['display_name']} from {source}")
            if not mount_is_readable(source):
                log(f"ERROR: Mount is unavailable or unreadable: {source}")
                status = 1
                continue

            files = list(recent_relative_files(source, cutoff))
            log(f"Selected {len(files)} recent files for {instrument['id']}")
            if preview or not files:
                continue
            destination.mkdir(parents=True, exist_ok=True)
            file_list = b"\0".join(path.encode("utf-8") for path in files) + b"\0"
            try:
                run(
                    [
                        "rsync", "--from0", "--files-from=-", "-rt", "--partial",
                        f"{source}/", f"{destination}/",
                    ],
                    input_bytes=file_list,
                )
            except subprocess.CalledProcessError:
                log(f"ERROR: Transfer failed for {instrument['id']}")
                status = 1
    return status


def upload(config: dict, execute: bool) -> int:
    """Preview or upload staging data to Oak without deleting remote files."""
    settings = config["settings"]
    identity = Path(settings["oak_identity_file"])
    if not identity.is_file():
        raise WorkflowError(f"Oak identity file is unavailable: {identity}")
    status = 0
    ssh_command = f"ssh -4 -i {identity} -o BatchMode=yes -o ConnectTimeout=15"

    with process_lock(lock_path("upload")):
        for instrument in enabled_instruments(config):
            source = staging_path(config, instrument)
            remote_path = f"{settings['oak_root']}/{instrument['oak_directory']}/"
            destination = f"{settings['oak_user']}@{settings['oak_host']}:{remote_path}"
            log(f"Uploading {instrument['display_name']} to {remote_path}")
            if not source.is_dir():
                log(f"ERROR: Staging directory is missing: {source}")
                status = 1
                continue
            command = [
                "rsync", "-rt", "--partial", "--human-readable", "--stats",
                "-e", ssh_command,
            ]
            if not execute:
                command.append("--dry-run")
            command.extend([f"{source}/", destination])
            try:
                run(command)
            except subprocess.CalledProcessError:
                log(f"ERROR: Oak transfer failed for {instrument['id']}")
                status = 1
    return status


def birth_epoch(path: Path) -> int:
    """Read the Linux filesystem birth time used for staging retention."""
    result = subprocess.run(
        ["stat", "-c", "%W", "--", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip())


def cleanup(config: dict, delete: bool) -> int:
    """Report or remove files that have lived in staging past retention."""
    settings = config["settings"]
    root = Path(settings["staging_root"])
    if not root.is_dir():
        raise WorkflowError(f"Staging directory is unavailable: {root}")
    validate_clock(settings)
    cutoff = int(
        (dt.datetime.now().astimezone() - dt.timedelta(days=int(settings["retention_days"]))).timestamp()
    )
    eligible_files = deleted_files = eligible_bytes = deleted_bytes = 0
    status = 0

    with process_lock(lock_path("cleanup")):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                created = birth_epoch(path)
                if created == 0:
                    log(f"WARNING: Creation time unavailable: {path}")
                    status = 1
                    continue
                if created > cutoff:
                    continue
                size = path.stat().st_size
                eligible_files += 1
                eligible_bytes += size
                print(f"{'DELETE' if delete else 'WOULD DELETE'}: {path}")
                if delete:
                    path.unlink()
                    deleted_files += 1
                    deleted_bytes += size
            except (OSError, subprocess.CalledProcessError, ValueError) as error:
                log(f"WARNING: Could not process {path}: {error}")
                status = 1

        if delete:
            for directory in sorted(
                (path for path in root.rglob("*") if path.is_dir()),
                key=lambda path: len(path.parts),
                reverse=True,
            ):
                with contextlib.suppress(OSError):
                    directory.rmdir()

    print(f"Eligible files: {eligible_files}")
    print(f"Eligible size: {eligible_bytes / 1024**3:.2f} GiB")
    print(f"Deleted files: {deleted_files}")
    print(f"Deleted size: {deleted_bytes / 1024**3:.2f} GiB")
    print(f"Mode: {'delete' if delete else 'report'}")
    return status


def status(config: dict) -> int:
    """Print read-only mount, staging, capacity, and Oak-key checks."""
    settings = config["settings"]
    root = Path(settings["staging_root"])
    result = 0
    for instrument in config["instruments"]:
        mount = Path(instrument["mount"])
        state = "mounted" if mount_is_readable(mount) else "unavailable"
        enabled = "enabled" if instrument.get("enabled", True) else "disabled"
        print(f"{instrument['id']}: {enabled}, {state}, source={mount}")
        if instrument.get("enabled", True) and state != "mounted":
            result = 1
    if root.exists():
        usage = shutil.disk_usage(root)
        print(f"staging: {root}, free={usage.free / 1024**3:.2f} GiB")
    else:
        print(f"staging: missing ({root})")
        result = 1
    identity = Path(settings["oak_identity_file"])
    print(f"oak key: {'present' if identity.is_file() else 'missing'} ({identity})")
    return result


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/think-lab/instruments.toml"),
        help="TOML configuration path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    pull_parser = subparsers.add_parser("pull", help="copy recent instrument files")
    pull_parser.add_argument("--preview", action="store_true")
    upload_parser = subparsers.add_parser("upload", help="copy staging data to Oak")
    upload_parser.add_argument("--execute", action="store_true")
    cleanup_parser = subparsers.add_parser("cleanup", help="expire local staging files")
    cleanup_parser.add_argument("--delete", action="store_true")
    subparsers.add_parser("status", help="show read-only workflow health")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected workflow command with consistent error handling."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "pull":
            return pull(config, args.preview)
        if args.command == "upload":
            return upload(config, args.execute)
        if args.command == "cleanup":
            return cleanup(config, args.delete)
        return status(config)
    except (OSError, KeyError, tomllib.TOMLDecodeError, WorkflowError) as error:
        log(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
