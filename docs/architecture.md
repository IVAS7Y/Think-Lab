# Architecture

## Purpose

Think-Lab is an SRLN-connected staging host between vendor instrument computers
and Stanford Oak. It reduces changes on instrument computers and centralizes
scheduled transfer, reporting, and retention.

## Data flow

```text
Instrument SMB shares (read-only)
  -> CIFS automounts under /mnt
  -> Python pull into /srv/instrument-data
  -> Python rsync upload over SSH/IPv4
  -> /oak/stanford/orgs/nano/<Instrument>
```

Local staging copies are removed 30 days after their filesystem creation time.
Oak files are not removed by this workflow. Oak is the long-term destination,
but Oak is not backed up by default and must not be described as a backup.

## Repository and deployed paths

```text
Repository                    Deployed location
src/think_lab.py              /opt/think-lab/src/think_lab.py
config/instruments.toml       /etc/think-lab/instruments.toml
systemd/think-lab-*           /etc/systemd/system/think-lab-*
scripts/health-check.sh       /opt/think-lab/scripts/health-check.sh
```

Secrets remain outside both locations:

- SMB credential files: `/root/.smb-*`
- Oak private key: `/home/think-lab/.ssh/id_ed25519_oak`

## Scheduling

- Pull: 08:00 and 20:00 local time
- Oak upload: 08:30 and 20:30 local time
- Staging cleanup: 02:00 local time

Pull and upload have separate process locks. A failed instrument is reported
without preventing later instruments from being attempted.

## Network boundaries

- SMB TCP 445 is allowed only from Think-Lab to explicitly registered hosts.
- Oak upload uses SSH TCP 22 and forces IPv4.
- Remote administration is limited by the SRLN firewall to the approved
  Stanford VPN source range.
