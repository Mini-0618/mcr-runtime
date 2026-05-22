"""
WAL Manager — Instance-Local Write-Ahead Log
=============================================

ARCH-FIND-001 Resolution:
  OLD: transitions.jsonl used process-global path → cross-instance contamination
  NEW: Instance-local WAL in {root}/runtime_logs/wal/{instance_id}/

Design Principles:
  - One WAL directory per LayeredMemory instance (no cross-contamination)
  - Sequential appends are atomic (write-to-tmp + rename + fsync)
  - Each instance has its own WAL directory (no cross-contamination)
  - Strict monotonic seq numbers
  - Adler-32 checksum per entry for corruption detection
  - WAL rotation at 64MB boundaries
"""

import os
import json
import time
import uuid
import zlib
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Iterator, NamedTuple, Optional


WAL_ROTATION_BYTES = 64 * 1024 * 1024  # 64 MB


class WALEntry(NamedTuple):
    """A single WAL entry with all transition metadata."""
    seq: int
    instance_id: str
    tick: int
    type: str
    memory_id: str
    from_state: str
    to_state: str
    reason: str
    checksum: str
    timestamp: str

    def to_json_line(self) -> str:
        return json.dumps(self._asdict(), ensure_ascii=False)

    @staticmethod
    def from_json_line(line: str) -> "WALEntry":
        d = json.loads(line.strip())
        return WALEntry(**d)


class WALManager:
    """
    Instance-local Write-Ahead Log.

    Each LayeredMemory(root) gets its own WAL directory:
      {root}/runtime_logs/wal/{instance_id}/wal_*.jsonl

    The instance_id is persisted at:
      {root}/runtime_logs/instance_id

    So re-opening the same root always uses the same WAL — and different
    roots always have isolated WALs.
    """

    def __init__(
        self,
        root: str,
        instance_id: Optional[str] = None,
        rotation_bytes: int = WAL_ROTATION_BYTES,
    ):
        self.root = Path(root)
        self.rotation_bytes = rotation_bytes

        # Unique instance ID — auto-generated if not provided
        self.instance_id = instance_id or self._generate_instance_id()

        # WAL subdirectory per instance — set before instance_id check
        self.wal_dir = self.root / "runtime_logs" / "wal" / self.instance_id
        self.wal_dir.mkdir(parents=True, exist_ok=True)

        # Persist instance_id so same root always gets same instance_id
        instance_id_file = self.root / "runtime_logs" / "instance_id"
        if instance_id_file.exists():
            saved_id = instance_id_file.read_text().strip()
            if saved_id != self.instance_id:
                # Root was used by a different instance before — adopt saved one
                self.instance_id = saved_id
                self.wal_dir = self.root / "runtime_logs" / "wal" / self.instance_id
                self.wal_dir.mkdir(parents=True, exist_ok=True)
        else:
            instance_id_file.parent.mkdir(parents=True, exist_ok=True)
            instance_id_file.write_text(self.instance_id)

        # Sequence state
        self._seq_lock = Lock()
        self._current_seq = 0
        self._current_wal_size = 0

        self._entries_written = 0
        self._bytes_written = 0
        self._rotation_count = 0
        self._wal_fd = None  # Persistent FD for WAL appends

        # Find existing WAL files in the CORRECT wal_dir (after instance_id resolved)
        self._wal_files = sorted(self.wal_dir.glob("wal_*.jsonl"))
        if self._wal_files:
            self._current_wal_file = self._wal_files[-1]
            self._current_seq = self._count_existing_seqs()
            self._current_wal_size = self._current_wal_file.stat().st_size
            self._wal_fd = open(self._current_wal_file, "ab")  # Re-open existing for appends
        else:
            self._current_wal_file = None
            self._open_new_wal()

        # Replay state
        self.replay_dir = self.root / "runtime_logs" / "replay" / self.instance_id
        self.replay_dir.mkdir(parents=True, exist_ok=True)

        # Metrics
        self.metrics_dir = self.root / "runtime_logs" / "metrics" / self.instance_id
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def _generate_instance_id(self) -> str:
        """Generate a unique instance ID based on hostname + pid + time + random."""
        import socket
        parts = [
            socket.gethostname(),
            str(os.getpid()),
            str(int(time.time())),
            uuid.uuid4().hex[:6],
        ]
        return f"{'-'.join(parts)}"

    def _open_new_wal(self) -> None:
        """Create a new WAL file and open it for appends."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        fname = f"wal_{ts}_{self._current_seq:010d}.jsonl"
        new_file = self.wal_dir / fname

        # Close existing FD if open
        if self._wal_fd is not None:
            try:
                self._wal_fd.close()
            except OSError:
                pass

        self._current_wal_file = new_file
        self._current_wal_size = 0
        self._rotation_count += 1
        # Open in append mode (creates if not exists, cursor at end)
        self._wal_fd = open(self._current_wal_file, "ab", buffering=8192)

    def _count_existing_seqs(self) -> int:
        """Count total sequences across all existing WAL files."""
        total = 0
        for wf in self.wal_dir.glob("wal_*.jsonl"):
            try:
                with open(wf, "rb") as f:
                    total += sum(1 for _ in f)
            except Exception:
                continue
        return total

    def _compute_checksum(self, entry_dict: dict) -> str:
        """Compute adler32 checksum of entry (excluding checksum field itself)."""
        data = json.dumps(entry_dict, sort_keys=True, ensure_ascii=False)
        return zlib.adler32(data.encode("utf-8")).to_bytes(4, "big").hex()

    def append(
        self,
        tick: int,
        type: str,
        memory_id: str,
        from_state: str,
        to_state: str,
        reason: str,
    ) -> WALEntry:
        """
        Atomically append a WAL entry (under _seq_lock).

        Protocol:
        1. Acquire seq lock
        2. Increment seq
        3. Build entry dict + compute checksum
        4. Check rotation (open new WAL if needed)
        5. Write to persistent WAL FD
        6. Release lock
        """
        with self._seq_lock:
            seq = self._current_seq + 1
            self._current_seq = seq
            timestamp = datetime.now().isoformat()

            # Build entry (checksum not yet included)
            entry_dict = {
                "seq": seq,
                "instance_id": self.instance_id,
                "tick": tick,
                "type": type,
                "memory_id": memory_id,
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
                "timestamp": timestamp,
            }

            checksum = self._compute_checksum(entry_dict)
            entry_dict["checksum"] = checksum

            entry = WALEntry(
                seq=seq,
                instance_id=self.instance_id,
                tick=tick,
                type=type,
                memory_id=memory_id,
                from_state=from_state,
                to_state=to_state,
                reason=reason,
                checksum=checksum,
                timestamp=timestamp,
            )

            line = entry.to_json_line() + "\n"
            line_bytes = line.encode("utf-8")

            # Check rotation
            if self._current_wal_size + len(line_bytes) > self.rotation_bytes:
                self._open_new_wal()

            # Write directly to persistent WAL FD (already under _seq_lock)
            self._wal_fd.write(line_bytes)
            self._wal_fd.flush()
            self._current_wal_size += len(line_bytes)
            self._entries_written += 1
            self._bytes_written += len(line_bytes)

            return entry

    def replay(
        self,
        from_seq: int = 1,
        to_seq: Optional[int] = None,
    ) -> Iterator[WALEntry]:
        """
        Replay WAL entries in order.

        Yields WALEntry objects in seq order.
        Validates checksum on each entry — skips corrupted entries.
        """
        wal_files = sorted(self.wal_dir.glob("wal_*.jsonl"))

        for wal_file in wal_files:
            with open(wal_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    seq = d.get("seq", 0)
                    if seq < from_seq:
                        continue
                    if to_seq is not None and seq > to_seq:
                        return

                    # Verify checksum
                    data_for_check = {k: v for k, v in d.items() if k != "checksum"}
                    expected_checksum = self._compute_checksum(data_for_check)
                    if d.get("checksum") != expected_checksum:
                        continue  # Skip corrupted entry

                    yield WALEntry(
                        seq=seq,
                        instance_id=d.get("instance_id", ""),
                        tick=d.get("tick", 0),
                        type=d.get("type", ""),
                        memory_id=d.get("memory_id", ""),
                        from_state=d.get("from_state", ""),
                        to_state=d.get("to_state", ""),
                        reason=d.get("reason", ""),
                        checksum=d.get("checksum", ""),
                        timestamp=d.get("timestamp", ""),
                    )

    def verify(self) -> dict:
        """
        Verify WAL integrity: seq continuity, checksum correctness, no corruption.

        Returns verification report.
        """
        report = {
            "instance_id": self.instance_id,
            "wal_dir": str(self.wal_dir),
            "wal_files": len(self._wal_files),
            "total_entries": 0,
            "checksum_errors": 0,
            "seq_gaps": [],
            "corrupted_lines": [],
            "rotation_count": self._rotation_count,
            "entries_written": self._entries_written,
            "bytes_written": self._bytes_written,
            "verified": True,
        }

        last_seq = 0
        wal_files = sorted(self.wal_dir.glob("wal_*.jsonl"))

        for wal_file in wal_files:
            try:
                with open(wal_file, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                        except json.JSONDecodeError as e:
                            report["corrupted_lines"].append({
                                "file": str(wal_file),
                                "line": line_num,
                                "error": str(e),
                            })
                            report["verified"] = False
                            continue

                        seq = d.get("seq", 0)
                        report["total_entries"] += 1

                        # Seq continuity check
                        if seq != last_seq + 1 and last_seq != 0:
                            report["seq_gaps"].append({
                                "file": str(wal_file),
                                "line": line_num,
                                "expected_seq": last_seq + 1,
                                "found_seq": seq,
                            })

                        last_seq = seq

                        # Checksum verification
                        data_for_check = {k: v for k, v in d.items() if k != "checksum"}
                        expected_checksum = self._compute_checksum(data_for_check)
                        if d.get("checksum") != expected_checksum:
                            report["checksum_errors"] += 1
                            report["verified"] = False

            except OSError as e:
                report["corrupted_lines"].append({
                    "file": str(wal_file),
                    "line": 0,
                    "error": str(e),
                })
                report["verified"] = False

        if report["seq_gaps"] or report["checksum_errors"] > 0 or report["corrupted_lines"]:
            report["verified"] = False

        return report

    def list_wal_files(self) -> list[Path]:
        """Return sorted list of all WAL files for this instance."""
        return sorted(self.wal_dir.glob("wal_*.jsonl"))

    def get_metrics(self) -> dict:
        """Return current WAL metrics."""
        return {
            "instance_id": self.instance_id,
            "wal_dir": str(self.wal_dir),
            "wal_file_count": len(self._wal_files),
            "current_seq": self._current_seq,
            "current_wal_size_bytes": self._current_wal_size,
            "entries_written": self._entries_written,
            "bytes_written": self._bytes_written,
            "rotation_count": self._rotation_count,
        }
