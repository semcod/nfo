"""Opt-in POSIX JSONL bounds with a stable lock and lossless raw segments."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import time
from uuid import uuid4


@contextmanager
def _directory(path, create=False):
    path = Path(path)
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _file(parent, name, flags):
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("bounded JSONL requires single-link regular files")
        yield fd
    finally:
        os.close(fd)


def _write_all(fd, data):
    remaining = memoryview(data)
    while remaining:
        count = os.write(fd, remaining)
        if count <= 0:
            raise OSError("JSONL write made no progress")
        remaining = remaining[count:]
    os.fsync(fd)


class BoundedJSONLWriter:
    """All writers to a path must use this protocol; lock files stay in place.

    Segments are not pruned or compressed on the append path. A segment directory
    can survive a failed operation; its bytes must never be blindly removed.
    """

    def __init__(self, file_path, max_bytes):
        if os.name != "posix":
            raise NotImplementedError("bounded JSONL currently requires POSIX file locking")
        import fcntl
        self._fcntl = fcntl
        self.path = Path(os.path.abspath(file_path))
        self.max_bytes = max_bytes

    @contextmanager
    def _segment(self):
        archive = self.path.parent / "archive"
        with _directory(archive, create=True) as parent:
            name = f"{self.path.name}.nfo-{time.time_ns()}-{uuid4().hex}"
            os.mkdir(name, mode=0o700, dir_fd=parent)
            folder = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                yield folder
                os.fsync(folder)
                os.fsync(parent)
            finally:
                os.close(folder)

    def _roll(self, parent, active):
        # No content copying, truncation or history rewriting. The exclusively
        # created private directory makes the destination unique and empty.
        before = os.fstat(active)
        current = os.stat(self.path.name, dir_fd=parent, follow_symlinks=False)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns):
            raise OSError("JSONL path changed outside the cooperative lock")
        os.fsync(active)
        with self._segment() as folder:
            os.rename(self.path.name, "events.jsonl", src_dir_fd=parent, dst_dir_fd=folder)
        os.fsync(parent)

    def write(self, payload):
        with _directory(self.path.parent) as parent:
            lock_name = "." + self.path.name + ".nfo.lock"
            with _file(parent, lock_name, os.O_CREAT | os.O_RDWR) as lock:
                self._fcntl.flock(lock, self._fcntl.LOCK_EX)
                info = os.fstat(lock)
                named = os.stat(lock_name, dir_fd=parent, follow_symlinks=False)
                if (info.st_dev, info.st_ino) != (named.st_dev, named.st_ino):
                    raise OSError("JSONL lock path changed")
                self._append(parent, payload)

    def _append(self, parent, payload):
        flags = os.O_CREAT | os.O_RDWR | os.O_APPEND
        with _file(parent, self.path.name, flags) as active:
            size = os.fstat(active).st_size
            partial = size > 0 and os.pread(active, 1, size - 1) != b"\n"
            rollover = size > 0 and (partial or size + len(payload) > self.max_bytes)
            if rollover:
                self._roll(parent, active)
            elif len(payload) <= self.max_bytes:
                _write_all(active, payload)
                os.fsync(parent)
                return
        # The old descriptor is closed before opening the fresh active inode.
        with _file(parent, self.path.name, flags) as active:
            if os.fstat(active).st_size:
                raise OSError("fresh JSONL file changed outside the cooperative lock")
            if len(payload) > self.max_bytes:
                with self._segment() as folder:
                    with _file(folder, ".events.incomplete", os.O_CREAT | os.O_EXCL | os.O_WRONLY) as out:
                        _write_all(out, payload)
                    os.rename(".events.incomplete", "events.jsonl",
                              src_dir_fd=folder, dst_dir_fd=folder)
                os.fsync(active)
            else:
                _write_all(active, payload)
            os.fsync(parent)
