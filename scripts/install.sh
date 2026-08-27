#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Run this installer with sudo." >&2
    exit 1
fi

repository_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
install_root=/opt/think-lab
config_root=/etc/think-lab

install -d -o root -g root -m 0755 "$install_root/src" "$install_root/scripts"
install -d -o root -g think-lab -m 0750 "$config_root"
install -o root -g root -m 0755 "$repository_root/src/think_lab.py" "$install_root/src/think_lab.py"
install -o root -g root -m 0755 "$repository_root/scripts/health-check.sh" "$install_root/scripts/health-check.sh"

if [[ ! -e "$config_root/instruments.toml" ]]; then
    install -o root -g think-lab -m 0640 \
        "$repository_root/config/instruments.toml" \
        "$config_root/instruments.toml"
    echo "Installed initial configuration. Review it before enabling timers."
else
    echo "Kept existing $config_root/instruments.toml"
    echo "Review changes in $repository_root/config/instruments.toml manually."
fi

for unit in "$repository_root"/systemd/think-lab-*; do
    install -o root -g root -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"
done

systemctl daemon-reload

echo "Installed files but did not enable timers."
echo "Run the health check and preview commands documented in docs/operations.md."
