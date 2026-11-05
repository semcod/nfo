"""Lossless byte bounds must be shared by processes, not individual sinks."""
import json
import multiprocessing
import os
from pathlib import Path

import pytest

from nfo.json_sink import JSONSink
from nfo.models import LogEntry

pytestmark = pytest.mark.skipif(os.name != "posix", reason="bounded mode requires POSIX")


def entry(marker):
    return LogEntry(timestamp=LogEntry.now(), level="INFO", function_name=marker,
                    module="rotation-test", args=(), kwargs={}, arg_types=[],
                    kwarg_types={}, return_value=None, return_type="None", duration_ms=0)


def payloads(path):
    archived = list((path.parent / "archive").glob(path.name + ".nfo-*/events.jsonl"))
    return [p.read_bytes() for p in archived] + ([path.read_bytes()] if path.exists() else [])


def writer(path, start, count):
    sink = JSONSink(path, max_bytes=1300)
    for number in range(start, start + count):
        sink.write(entry(str(number)))
        try:
            active_size = Path(path).stat().st_size
        except FileNotFoundError:
            # Another cooperating writer can be between rename and recreation.
            active_size = 0
        assert active_size <= 1300


def crash_after_rollover(path):
    import nfo.json_rotation as rotation
    rename = rotation.os.rename
    def interrupted(*args, **kwargs):
        rename(*args, **kwargs)
        os._exit(17)
    rotation.os.rename = interrupted
    JSONSink(path, max_bytes=1000).write(entry("not acknowledged"))


def test_multiple_processes_preserve_every_record_and_active_bound(tmp_path):
    path = tmp_path / "events.jsonl"
    ctx = multiprocessing.get_context("spawn")
    workers = [ctx.Process(target=writer, args=(str(path), n*20, 20)) for n in range(4)]
    for process in workers:
        process.start()
    for process in workers:
        process.join(30)
        assert process.exitcode == 0
    rows = [json.loads(line) for part in payloads(path) for line in part.splitlines()]
    assert sorted(int(row["function_name"]) for row in rows) == list(range(80))
    assert path.stat().st_size <= 1300


def test_oversized_utf8_record_is_archived_intact_and_delegated(tmp_path):
    path = tmp_path / "events.jsonl"
    seen = []
    class Delegate:
        def write(self, value):
            seen.append(value)
    value = entry("ł" * 2000)
    sink = JSONSink(path, max_bytes=1000, delegate=Delegate())
    sink.write(value)
    assert path.stat().st_size <= 1000
    assert len(seen) == 1 and seen[0] is value
    rows = [json.loads(line) for part in payloads(path) for line in part.splitlines()]
    assert len(rows) == 1 and rows[0]["function_name"] == "ł" * 2000


def test_existing_partial_or_oversized_bytes_are_not_rewritten(tmp_path):
    path = tmp_path / "events.jsonl"
    before = b'opaque-\xff-partial'
    path.write_bytes(before)
    JSONSink(path, max_bytes=1000).write(entry("next"))
    parts = payloads(path)
    assert before in parts
    assert json.loads(path.read_bytes())["function_name"] == "next"


def test_environment_opt_in_and_explicit_zero_override(tmp_path, monkeypatch):
    monkeypatch.setenv("NFO_JSONL_MAX_BYTES", "1")
    bounded = tmp_path / "bounded.jsonl"
    JSONSink(bounded).write(entry("bounded"))
    assert bounded.stat().st_size <= 1
    legacy = tmp_path / "legacy.jsonl"
    JSONSink(legacy, max_bytes=0).write(entry("legacy"))
    assert legacy.stat().st_size > 1
    assert not (tmp_path / ("." + legacy.name + ".nfo.lock")).exists()


@pytest.mark.parametrize("budget", [-1, True, 1.5, "10"])
def test_invalid_explicit_budgets_refuse_without_files(tmp_path, budget):
    with pytest.raises(ValueError):
        JSONSink(tmp_path / "events.jsonl", max_bytes=budget)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("budget", ["bad", "-1", "1.5", ""])
def test_invalid_environment_budgets_refuse(tmp_path, monkeypatch, budget):
    monkeypatch.setenv("NFO_JSONL_MAX_BYTES", budget)
    with pytest.raises(ValueError):
        JSONSink(tmp_path / "events.jsonl")


def test_symlink_and_fifo_sources_are_refused(tmp_path):
    target = tmp_path / "target"
    target.write_bytes(b"keep\n")
    path = tmp_path / "events.jsonl"
    path.symlink_to(target)
    with pytest.raises((ValueError, OSError)):
        JSONSink(path, max_bytes=1000).write(entry("blocked"))
    assert target.read_bytes() == b"keep\n"
    path.unlink()
    os.mkfifo(path)
    with pytest.raises((ValueError, OSError)):
        JSONSink(path, max_bytes=1000).write(entry("blocked"))


def test_atomic_rollover_failure_preserves_original(tmp_path, monkeypatch):
    import nfo.json_rotation as rotation
    path = tmp_path / "events.jsonl"
    original = b"old bytes\n" * 200
    path.write_bytes(original)
    def refuse(*args, **kwargs):
        raise OSError("fixture rollover refusal")
    monkeypatch.setattr(rotation.os, "rename", refuse)
    with pytest.raises(OSError):
        JSONSink(path, max_bytes=1000).write(entry("never committed"))
    assert path.read_bytes() == original


def test_process_exit_releases_lock_and_next_writer_recovers(tmp_path):
    path = tmp_path / "events.jsonl"
    ctx = multiprocessing.get_context("spawn")
    first = ctx.Process(target=writer, args=(str(path), 0, 2))
    first.start(); first.join(20)
    assert first.exitcode == 0
    writer(str(path), 2, 2)
    rows = [json.loads(line) for part in payloads(path) for line in part.splitlines()]
    assert sorted(int(row["function_name"]) for row in rows) == [0, 1, 2, 3]


def test_process_death_after_move_keeps_bytes_and_releases_lock(tmp_path):
    path = tmp_path / "events.jsonl"
    before = b"pre-existing bytes\n" * 200
    path.write_bytes(before)
    ctx = multiprocessing.get_context("spawn")
    process = ctx.Process(target=crash_after_rollover, args=(str(path),))
    process.start(); process.join(20)
    assert process.exitcode == 17
    JSONSink(path, max_bytes=1000).write(entry("recovered"))
    assert before in payloads(path)
    assert json.loads(path.read_bytes())["function_name"] == "recovered"


def test_hardlinked_source_is_refused_without_altering_alias(tmp_path):
    original = tmp_path / "original"
    original.write_bytes(b"private bytes\n")
    path = tmp_path / "events.jsonl"
    os.link(original, path)
    with pytest.raises(ValueError):
        JSONSink(path, max_bytes=1000).write(entry("refused"))
    assert original.read_bytes() == b"private bytes\n"


def test_symlinked_parent_is_refused(tmp_path):
    real = tmp_path / "real"; real.mkdir()
    alias = tmp_path / "alias"; alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        JSONSink(alias / "events.jsonl", max_bytes=1000).write(entry("refused"))
    assert not list(real.iterdir())


def test_incomplete_oversized_write_is_not_a_completed_segment(tmp_path, monkeypatch):
    import nfo.json_rotation as rotation
    path = tmp_path / "events.jsonl"
    write = rotation.os.write
    def partial(fd, data):
        write(fd, data[:10])
        raise OSError("fixture partial archive write")
    monkeypatch.setattr(rotation.os, "write", partial)
    with pytest.raises(OSError):
        JSONSink(path, max_bytes=1).write(entry("failed"))
    assert not list((tmp_path / "archive").glob("*/events.jsonl"))
    assert list((tmp_path / "archive").glob("*/.events.incomplete"))
    assert path.read_bytes() == b""


def test_short_writes_are_completed(tmp_path, monkeypatch):
    import nfo.json_rotation as rotation
    path = tmp_path / "events.jsonl"
    write = rotation.os.write
    monkeypatch.setattr(rotation.os, "write", lambda fd, data: write(fd, data[:7]))
    JSONSink(path, max_bytes=1000).write(entry("complete"))
    assert json.loads(path.read_bytes())["function_name"] == "complete"


def test_utf8_budget_counts_bytes_instead_of_characters(tmp_path):
    path = tmp_path / "events.jsonl"
    value = entry("ą" * 20)
    text = json.dumps(value.as_dict(), ensure_ascii=False, default=str) + "\n"
    budget = (len(text) + len(text.encode("utf-8"))) // 2
    assert len(text) < budget < len(text.encode("utf-8"))
    JSONSink(path, max_bytes=budget).write(value)
    assert path.read_bytes() == b""
    assert text.encode("utf-8") in payloads(path)


def test_lock_inode_persists_and_segments_are_private(tmp_path):
    path = tmp_path / "events.jsonl"
    previous = os.umask(0)
    try:
        sink = JSONSink(path, max_bytes=1000)
        sink.write(entry("first"))
        lock = tmp_path / ("." + path.name + ".nfo.lock")
        inode = lock.stat().st_ino
        for number in range(10):
            JSONSink(path, max_bytes=1000).write(entry(str(number)))
        assert lock.stat().st_ino == inode and lock.stat().st_mode & 0o777 == 0o600
        folders = list((tmp_path / "archive").glob("*.nfo-*"))
        assert folders and all(p.stat().st_mode & 0o777 == 0o700 for p in folders)
    finally:
        os.umask(previous)


def test_symlinked_archive_directory_refuses_without_moving_source(tmp_path):
    path = tmp_path / "events.jsonl"
    before = b"original\n" * 200
    path.write_bytes(before)
    outside = tmp_path / "outside"; outside.mkdir()
    (tmp_path / "archive").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        JSONSink(path, max_bytes=1000).write(entry("refused"))
    assert path.read_bytes() == before and not list(outside.iterdir())


@pytest.mark.parametrize("failure", [1, 2, 3])
def test_fsync_failure_never_loses_preexisting_bytes_or_delegates(tmp_path, monkeypatch, failure):
    import nfo.json_rotation as rotation
    path = tmp_path / "events.jsonl"
    before = b"old durable bytes\n" * 100
    path.write_bytes(before)
    original, calls, seen = rotation.os.fsync, [], []
    def fail(fd):
        calls.append(fd)
        if len(calls) == failure:
            raise OSError("fixture durability failure")
        return original(fd)
    class Delegate:
        def write(self, value):
            seen.append(value)
    monkeypatch.setattr(rotation.os, "fsync", fail)
    with pytest.raises(OSError):
        JSONSink(path, max_bytes=1000, delegate=Delegate()).write(entry("not acknowledged"))
    assert before in payloads(path) and not seen
