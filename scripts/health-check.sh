#!/usr/bin/env bash
set -u
set -o pipefail

status=0

check() {
    local description=$1
    shift
    if "$@"; then
        printf 'OK: %s\n' "$description"
    else
        printf 'FAILED: %s\n' "$description"
        status=1
    fi
}

check "system clock synchronized" bash -c \
    '[[ $(timedatectl show --property=NTPSynchronized --value) == yes ]]'
check "at least 2 GiB staging space" bash -c \
    '[[ $(df --output=avail /srv/instrument-data | tail -n 1) -ge 2097152 ]]'
check "Oak SSH key exists" test -r /home/think-lab/.ssh/id_ed25519_oak
check "Oak TCP 22 reachable over IPv4" timeout 5 bash -c \
    '</dev/tcp/dtn.oak.stanford.edu/22'

python3 /opt/think-lab/src/think_lab.py status || status=1
systemctl list-timers \
    think-lab-pull.timer think-lab-upload.timer think-lab-cleanup.timer \
    --all --no-pager

exit "$status"
