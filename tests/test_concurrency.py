import threading
import time
from app.db import get_connection


def test_wal_mode_and_busy_timeout(temp_db: str) -> None:
    conn = get_connection(temp_db)
    mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"
    assert timeout == 5000


def test_concurrent_connection_waits_for_lock(temp_db: str) -> None:
    conn1 = get_connection(temp_db)
    conn2 = get_connection(temp_db)

    conn1.execute("BEGIN IMMEDIATE;")

    thread2_started = False
    thread2_finished = False
    thread2_error = None

    def worker() -> None:
        nonlocal thread2_started, thread2_finished, thread2_error
        thread2_started = True
        try:
            conn2.execute("BEGIN IMMEDIATE;")
            conn2.execute("COMMIT;")
            thread2_finished = True
        except Exception as err:
            thread2_error = err

    thread = threading.Thread(target=worker)
    thread.start()

    time.sleep(0.3)
    assert thread2_started is True
    assert thread2_finished is False

    conn1.execute("COMMIT;")
    thread.join(timeout=4.0)

    conn1.close()
    conn2.close()

    assert thread2_error is None
    assert thread2_finished is True
