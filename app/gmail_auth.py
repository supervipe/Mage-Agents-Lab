import argparse
from pathlib import Path

from app.gmail import connect_account


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect one Gmail account")
    parser.add_argument("--client-secrets", required=True, type=Path)
    parser.add_argument("--account", required=True)
    args = parser.parse_args()
    print(f"Connected {connect_account(args.client_secrets, args.account)}")


if __name__ == "__main__":
    main()
