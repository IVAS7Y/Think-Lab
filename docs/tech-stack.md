# Technology stack

- Raspberry Pi 4B running Ubuntu
- Python 3.11 or newer, standard library only
- TOML configuration parsed with Python `tomllib`
- `rsync` for local staging and Oak transfers
- OpenSSH with an unshared Think-Lab key for Oak DTN authentication
- `cifs-utils` and systemd automounts for read-only SMB access
- systemd oneshot services, persistent timers, and journald logs
- Python `unittest` for dependency-free automated tests

The runtime intentionally avoids PyYAML and other downloadable Python packages
so that maintenance does not depend on internet package availability.
