"""Install a per-user systemd unit for the Linux Meshnet Compose stack."""

from pathlib import Path
import shlex


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    service = Path.home() / ".config/systemd/user/mage-agents-lab.service"
    service.parent.mkdir(parents=True, exist_ok=True)
    script = root / "scripts/start_meshnet_services.py"
    content = f"""[Unit]
Description=Mage Agents Lab on Nord Meshnet
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/python3 {shlex.quote(str(script))}
Restart=on-failure
RestartSec=15
TimeoutStartSec=240

[Install]
WantedBy=default.target
"""
    service.write_text(content, encoding="utf-8")
    print(f"Wrote {service}")
    print("Run: systemctl --user daemon-reload")
    print("Run: systemctl --user enable --now mage-agents-lab.service")
    print('Run: sudo loginctl enable-linger "$USER"')


if __name__ == "__main__":
    main()
