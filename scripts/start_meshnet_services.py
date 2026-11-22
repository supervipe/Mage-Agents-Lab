"""Wait for the host's Meshnet address before starting the Compose services."""

import ipaddress
from pathlib import Path
import socket
import subprocess
import time


ROOT = Path(__file__).resolve().parent.parent


def meshnet_ip() -> str:
    env_file = ROOT / ".env"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("MESHNET_BIND_IP="):
            value = line.partition("=")[2].strip().strip('"\'')
            return str(ipaddress.IPv4Address(value))
    raise RuntimeError("Set MESHNET_BIND_IP in .env before starting Meshnet services")


def address_is_ready(address: str) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((address, 0))
        return True
    except OSError:
        return False


def main() -> None:
    address = meshnet_ip()
    for _ in range(90):
        if address_is_ready(address):
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"Meshnet IP {address} did not appear within three minutes")
    subprocess.run([
        "docker", "compose", "-f", "compose.yaml", "-f", "compose.meshnet.yaml",
        "up", "-d", "api", "worker",
    ], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
