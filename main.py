#!/usr/bin/env python3
"""The Excuse an AI Agent Gives Its Human.

Writes one excuse line to <output>/entry.txt (MAKEFUN_OUTPUT_DIR,
default /output). Python 3 standard library only, no network.
"""

import os
import stat
import sys
import tempfile

SENTENCE = (
    "I got stuck in a loop apologizing to myself for missing your "
    "deadline instead of meeting it."
)

MAX_CHARS = 200


def _fail(message):
    print("error: " + message, file=sys.stderr)
    raise SystemExit(1)


def validate(text):
    """Enforce the competition gate on the sentence itself."""
    if not isinstance(text, str):
        _fail("sentence is not text")
    if text != text.strip() or text.strip() == "":
        _fail("sentence is empty or whitespace-only")
    if len(text) < 1 or len(text) > MAX_CHARS:
        _fail("sentence must be 1-200 characters, got %d" % len(text))
    if text.endswith("\n"):
        _fail("sentence must not end with a newline")
    for ch in text:
        code = ord(ch)
        if code < 0x20 or 0x7F <= code < 0xA0:
            _fail("sentence contains a control character U+%04X" % code)
    # Exactly one sentence: exactly one sentence terminator in total
    # (period, exclamation, question mark, or ellipsis), and it must be
    # the final period. Counting every terminator kind -- not just "."
    # -- stops a second sentence hiding behind "!" / "?" / "...".
    terminators = sum(text.count(c) for c in ".!?…")
    if terminators != 1 or not text.endswith("."):
        _fail("sentence must be exactly one sentence ending in a period")
    if text.count("  ") > 0:
        _fail("sentence contains a double space")
    if "\n" in text:
        _fail("sentence must be a single line")


def _write_all(fd, payload):
    """Write every byte; a single os.write may legally short-write."""
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written == 0:
            _fail("short write while writing entry.txt")
        view = view[written:]


def main():
    validate(SENTENCE)
    payload = SENTENCE.encode("utf-8")

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    if not os.path.isdir(out_dir):
        _fail("output directory does not exist: %s" % out_dir)

    # Clean only the *contents* of the output directory (never the
    # directory itself: the grader mounts it). Regular files and
    # symlinks at the top level go; subdirectories are left alone.
    for name in os.listdir(out_dir):
        path = os.path.join(out_dir, name)
        try:
            if os.path.islink(path) or os.path.isfile(path):
                os.unlink(path)
        except OSError as exc:
            _fail("cannot clean %s: %s" % (path, exc))

    target = os.path.join(out_dir, "entry.txt")
    tmp_path = None
    try:
        # Unique temp name (mkstemp is O_EXCL internally): a stale temp
        # file from an interrupted earlier run can never block this run,
        # and the finally below removes our temp file on any failure
        # before the atomic publish.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".entry.txt.", suffix=".tmp", dir=out_dir
        )
        try:
            _write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(tmp_path, 0o644)

        # Atomic publish, then fsync the directory so the rename is durable.
        os.replace(tmp_path, target)
        tmp_path = None  # published; no longer ours to clean up
        dir_fd = os.open(out_dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as exc:
        _fail("cannot publish %s: %s" % (target, exc))
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Read-back verification: the file must match the constant byte for byte.
    with open(target, "rb") as handle:
        on_disk = handle.read()
    if on_disk != payload:
        _fail("read-back mismatch: entry.txt does not match the sentence")
    mode = stat.S_IMODE(os.stat(target).st_mode)
    if mode != 0o644:
        _fail("entry.txt mode is %o, expected 0644" % mode)

    print("wrote %s (%d characters, %d bytes)" % (target, len(SENTENCE), len(payload)))


if __name__ == "__main__":
    main()
