# Operations guide

## Important deployment rule

The existing `/usr/local/sbin` scripts and `instrument-*.timer` units remain the
production workflow until this replacement passes preview and live validation.
Do not disable the old timers merely because this repository was installed.

## Install files without enabling schedules

From a clone of this repository on Think-Lab:

```bash
sudo ./scripts/install.sh
sudo systemd-analyze verify /etc/systemd/system/think-lab-*.service \
  /etc/systemd/system/think-lab-*.timer
```

Review `/etc/think-lab/instruments.toml`, particularly enabled instruments and
paths. The installer preserves an existing configuration rather than replacing
it.

## Validate the replacement

```bash
sudo -u think-lab /opt/think-lab/scripts/health-check.sh
sudo -u think-lab python3 /opt/think-lab/src/think_lab.py pull --preview
sudo -u think-lab python3 /opt/think-lab/src/think_lab.py upload
sudo -u think-lab python3 /opt/think-lab/src/think_lab.py cleanup
```

The upload and cleanup commands above are previews. They should not upload or
delete files.

After reviewing the preview, test one real pull and upload:

```bash
sudo -u think-lab python3 /opt/think-lab/src/think_lab.py pull
sudo -u think-lab python3 /opt/think-lab/src/think_lab.py upload --execute
```

Verify Oak independently and inspect logs before changing timers.

## Cut over from the old workflow

Only after successful validation:

```bash
sudo systemctl enable --now \
  think-lab-pull.timer think-lab-upload.timer think-lab-cleanup.timer
systemctl list-timers \
  think-lab-pull.timer think-lab-upload.timer think-lab-cleanup.timer --all
```

After at least one successful scheduled cycle, disable the old timers to prevent
duplicate runs:

```bash
sudo systemctl disable --now \
  instrument-pull.timer instrument-upload.timer instrument-cleanup.timer
```

Do not delete the old scripts until the replacement has completed several
scheduled cycles successfully.

## Logs

```bash
journalctl -u think-lab-pull.service -n 100 --no-pager
journalctl -u think-lab-upload.service -n 100 --no-pager
journalctl -u think-lab-cleanup.service -n 100 --no-pager
```

## Add a machine

Keep a new instrument disabled while validating it:

```toml
[[instruments]]
id = "fiji3"
display_name = "Fiji 3"
enabled = false
mount = "/mnt/fiji3"
oak_directory = "Fiji3"
```

Confirm TCP 445, authenticated share access, a temporary read-only mount,
capacity, a preview pull, a real pull, and a preview Oak upload. Then set
`enabled = true`, reinstall or copy the configuration, and monitor the next
scheduled cycle.
