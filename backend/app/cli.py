import argparse
import sys
import uuid

from app.api_keys import create_api_key, list_api_keys, revoke_api_key
from app.db import SessionLocal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Manage Tokenward API keys"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-key", help="Create a new API key")
    create.add_argument("--name", required=True, help="Who or what the key is for")

    commands.add_parser("list-keys", help="List all API keys")

    revoke = commands.add_parser("revoke-key", help="Revoke a key by its id")
    revoke.add_argument("key_id", type=uuid.UUID)

    args = parser.parse_args(argv)

    with SessionLocal() as session:
        if args.command == "create-key":
            try:
                api_key, plaintext = create_api_key(session, args.name)
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            print(f"Created key '{api_key.name}' (id {api_key.id})")
            print(f"API key: {plaintext}")
            print("Save this key now. It cannot be shown again.")

        elif args.command == "list-keys":
            keys = list_api_keys(session)
            if not keys:
                print("No API keys yet.")
            for key in keys:
                state = "revoked" if key.revoked_at else "active"
                print(f"{key.id}  {key.key_prefix}...  {state:<7}  {key.name}")

        elif args.command == "revoke-key":
            if not revoke_api_key(session, args.key_id):
                print("No active key with that id.", file=sys.stderr)
                return 1
            print(f"Revoked key {args.key_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())