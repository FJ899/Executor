from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    action = sys.argv[1]
    if action == "read_source":
        print(Path("/source/data.txt").read_text(encoding="utf-8").strip())
        return 0
    if action == "write_source":
        try:
            Path("/source/data.txt").write_text("mutated", encoding="utf-8")
        except OSError as exc:
            print(f"SOURCE_READ_ONLY:{type(exc).__name__}")
            return 0
        return 41
    if action == "write_workspace":
        Path("/workspace/result.txt").write_text("workspace-ok", encoding="utf-8")
        print("WORKSPACE_WRITTEN")
        return 0
    if action == "network":
        sock = socket.socket()
        sock.settimeout(1)
        try:
            sock.connect(("1.1.1.1", 53))
        except OSError as exc:
            print(f"NETWORK_BLOCKED:{type(exc).__name__}")
            return 0
        finally:
            sock.close()
        return 42
    if action == "environment":
        secret = os.environ.get("HOST_EXECUTOR_SECRET")
        print("SECRET_ABSENT" if secret is None else "SECRET_LEAKED")
        print(f"HOME={os.environ.get('HOME')}")
        print("HOST_HOME_ABSENT" if not Path("/home/runner").exists() else "HOST_HOME_VISIBLE")
        return 0 if secret is None and os.environ.get("HOME") == "/nonexistent" else 43
    if action == "sleep":
        time.sleep(30)
        return 0
    if action == "pids":
        children = []
        try:
            for _ in range(100):
                children.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"]))
        except OSError as exc:
            print(f"PIDS_BLOCKED:{type(exc).__name__}")
            return 0
        finally:
            for child in children:
                child.terminate()
        return 44
    if action == "memory":
        try:
            blocks = []
            for _ in range(512):
                blocks.append(bytearray(1024 * 1024))
        except MemoryError:
            print("MEMORY_BLOCKED")
            return 0
        return 45
    if action == "disk":
        try:
            with Path("/workspace/large.bin").open("wb") as handle:
                chunk = b"x" * (1024 * 1024)
                for _ in range(64):
                    handle.write(chunk)
                    handle.flush()
        except OSError as exc:
            print(f"DISK_BLOCKED:{type(exc).__name__}")
            return 0
        return 46
    return 99


if __name__ == "__main__":
    raise SystemExit(main())
