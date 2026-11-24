import argparse
import sys
from datetime import datetime, timezone
from app.db import get_connection, init_db
from app.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    init_db()
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT id FROM users WHERE username = ?", (args.username,))
        if cursor.fetchone():
            sys.stderr.write("User already exists\n")
            sys.exit(1)
        hashed_password = hash_password(args.password)
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (username, password_hash, role, active, created_at) VALUES (?, ?, 'owner', 1, ?)",
            (args.username, hashed_password, created_at),
        )
        sys.stdout.write(f"Owner {args.username} created successfully\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
