---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "jsonl-rotation",
  "kind": "information",
  "version": 1,
  "title": "Bounded JSONL writes and cooperative rotation",
  "status": "proposed",
  "owner": "semcod/nfo",
  "scope": "repository",
  "created": "2026-11-05",
  "updated": "2026-11-05",
  "review_after": "2026-12-05",
  "source_revision": "2d74ad212ef279aef19b7a3aa9a6a507b2ead5af",
  "affected_repositories": [
    "semcod/nfo"
  ],
  "evidence": [
    "https://github.com/semcod/nfo/issues/10",
    "repo://semcod/nfo/nfo/json_rotation.py",
    "repo://semcod/nfo/tests/test_json_sink_rotation.py"
  ]
}
---

# Bounded JSONL writes and cooperative rotation

<!-- docs:section purpose -->
## Purpose

Keep an explicitly configured active JSONL file within a byte budget while
preserving historical bytes and oversized events in separate raw segments.
This addresses the producer dependency of maskservice/c2004#738 (PLF-22243).

<!-- docs:section scope -->
## Scope

`JSONSink` keeps its existing unbounded default. Bounded mode is opt-in and
currently requires POSIX `flock`, directory descriptors and atomic same-device
rename. Unsupported operating systems refuse bounded mode explicitly; the
legacy sink remains available. This source change does not activate any service,
change a runtime package or grant publication or maintenance authority.

<!-- docs:section evidence -->
## Evidence

Tests exercise multiple spawned processes, unchanged legacy behavior,
oversized UTF-8 events, partial existing tails, short writes, process death
immediately after rollover, nonregular and linked paths, and refused I/O.
The required protected matrix remains Python 3.11, 3.12 and 3.13. Passing local
tests does not establish independently approved merge or deployment.

<!-- docs:section content -->
## Configuration and protocol

Use `JSONSink(path, max_bytes=50000000)`, or set `NFO_JSONL_MAX_BYTES=50000000`
in the intended service environment. The constructor argument overrides the
environment. Zero disables bounding explicitly; unset environment also disables
it. Negative, boolean or noninteger constructor values and invalid environment
values are refused before writing. The budget counts encoded UTF-8 bytes,
including the final newline, rather than characters.

Every writer to a path must use bounded mode. Before enabling it, stop legacy
writers and activate the cooperating implementation together. Do not combine
it with an offline rotator or an external tool that ignores the lock. Do not
remove, rename, replace or hardlink the persistent `.<filename>.nfo.lock`.

An instance thread lock protects serialization inside its process. A stable
per-path `flock` then serializes processes before they open the active inode.
The active file is opened anew for each event, so a waiting writer follows the
new inode after rollover. Symlinked path components, symlinked files, special
files and multiply linked active/lock files are refused. Create the log's parent
directory before use. New active files and lock files use mode 0600.

Readers outside the lock may briefly observe a missing active pathname between
rollover and recreation; treat that as an empty current file and retry, while
historical bytes remain in the segment. Writers following this protocol never
open or append the active file outside the shared lock.

Before a complete event would exceed the budget, the current nonempty file is
fsynced and moved atomically into an exclusively created private directory under
`archive/<filename>.nfo-<time>-<uuid>/events.jsonl`. Historical bytes are not
parsed, truncated, rewritten or deleted. An incomplete existing tail also causes
rollover before a new event, preserving the opaque tail without joining the new
JSON record to it. Each private segment directory uses mode 0700.

An event larger than the entire budget is preserved intact in its own segment;
it is not dropped or split and the active file remains empty. A partially failed
oversized write remains `.events.incomplete` for inspection and is not named as
a completed segment. Short writes are retried. The downstream delegate runs only
after the local write/segment has completed successfully.

Active and segment file data are fsynced, as are the changed directories.
Segments remain raw rather than being compressed on the append path. This keeps
rollover short; later backup/compression/retention is a separate operation.
There is no archive count limit, automatic pruning or disk-space quota. Segment
names are identifiers, not a trusted global ordering index across clock changes;
bytes and record order within each segment remain intact.

<!-- docs:section limitations -->
## Failure and compatibility boundaries

All writers must cooperate and use a consistent budget. A thread lock alone,
a legacy writer or another program ignoring the sidecar can invalidate the
bound. A successful write by cooperating processes leaves the active file at
or below the configured budget. Archives can exceed that budget and continue
to consume disk space; the budget is for the active file only.

A process dying after atomic rollover leaves its old bytes in a segment and
releases its OS lock; a subsequent cooperating writer can create the new active
file. An I/O or fsync error is a failed operation. The active path, a raw segment
or an incomplete artifact may remain; inspect before retrying. No exactly-once
promise is made after uncertain durability or partial I/O. Never delete recovery
artifacts automatically, and do not treat fixture tests as a power-loss test.

<!-- docs:section next_actions -->
## Publication and activation

Publish through the repository's existing protected Python matrix and independent
Validator. Activate an immutable approved package in the intended service only,
with all previous writers stopped and recoverable state available. Check the
actual loaded package, scoped environment, active-file size and service health
after restart. Existing archives must remain preserved. Other services keep
the legacy default unless explicitly configured.
