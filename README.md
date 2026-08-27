# Think-Lab instrument data collector

Think-Lab is a Raspberry Pi service that collects recent instrument files from
read-only SMB mounts on Stanford's SRLN, stages them locally, uploads them to
Oak, and removes staging copies after 30 days.

The deployed workflow is deliberately non-destructive:

- Instrument shares are mounted read-only.
- Pulls copy files into `/srv/instrument-data`; they never remove source data.
- Uploads use `rsync` without `--delete`.
- Cleanup only removes expired files from the local staging directory.
- SMB passwords and the Oak SSH private key are never stored in this repository.

## Repository layout

```text
config/instruments.toml       Machine and workflow configuration
src/think_lab.py              Pull, upload, cleanup, and status commands
systemd/                      One-shot services and schedules
scripts/install.sh            Install or update files on Think-Lab
scripts/health-check.sh       Read-only operational checks
tests/                        Unit tests for configuration and retention logic
docs/                         Architecture, standards, and operator guidance
```

## Commands

```bash
python3 src/think_lab.py --config config/instruments.toml pull --preview
python3 src/think_lab.py --config config/instruments.toml upload
python3 src/think_lab.py --config config/instruments.toml cleanup
python3 src/think_lab.py --config config/instruments.toml status
```

Perform an operation only after its preview succeeds:

```bash
python3 src/think_lab.py --config config/instruments.toml pull
python3 src/think_lab.py --config config/instruments.toml upload --execute
python3 src/think_lab.py --config config/instruments.toml cleanup --delete
```

## Adding an instrument

1. Register the instrument and SRLN Ethernet MAC with the network owner.
2. Expose a dedicated SMB share with a narrow TCP 445 firewall rule that allows
   only Think-Lab.
3. Create a root-readable CIFS credential file on Think-Lab. Never commit it.
4. Test a temporary read-only mount and then add the validated mount to
   `/etc/fstab` using `_netdev,nofail,x-systemd.automount`.
5. Add one `[[instruments]]` block to `config/instruments.toml` with
   `enabled = false`.
6. Run `status`, a preview pull, a real pull, and a preview upload.
7. Set `enabled = true`, install the updated configuration, and verify the next
   scheduled cycle.

See [operations.md](docs/operations.md) for deployment and validation commands.
