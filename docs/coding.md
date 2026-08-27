# Coding standards

## Safety

- Instrument sources must be treated as read-only.
- Copy operations must never use `--delete`, `--remove-source-files`, `--move`,
  mirroring, or purge behavior.
- Cleanup is restricted to the configured local staging root.
- Destructive commands must default to report-only and require an explicit flag.
- Passwords, CIFS credential contents, private keys, and tokens must never be
  committed or printed.

## Python

- Support Python 3.11 or newer and prefer the standard library.
- Keep command execution argument-based; do not enable `shell=True`.
- Return a nonzero status if any enabled instrument fails.
- Log operation names, instruments, and paths without logging secrets.
- Put machine-specific values in TOML rather than conditional branches.
- Write unit tests for configuration validation, time selection, and retention.

## Shell and systemd

- Shell scripts are limited to installation and read-only health checks.
- Use `set -euo pipefail` for installation and `set -u -o pipefail` when a
  health check must continue after individual failures.
- Scheduled work uses oneshot systemd services and persistent timers.
- Timers must never be enabled automatically by the installer.
