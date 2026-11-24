#!/usr/bin/env python3
"""One-line excuse writer for the make.fun one-liner bounty.

The program takes no input and talks to no network. It checks a single
hard-coded excuse against the competition rules, then publishes it as
``entry.txt`` inside the output directory named by MAKEFUN_OUTPUT_DIR
(default ``/output``). Only the Python 3 standard library is used.
"""

import os
import stat
import sys
import tempfile

ENTRY_TEXT = (
    "I got stuck in a loop apologizing to myself for missing your "
    "deadline instead of meeting it."
)

CHAR_LIMIT = 200
ENTRY_FILENAME = "entry.txt"
DEFAULT_OUTPUT_DIR = "/output"
ENTRY_MODE = 0o644
TERMINATORS = ".!?…"


def die(reason):
    """Report a fatal problem on stderr and stop with exit code 1."""
    sys.stderr.write("error: %s\n" % reason)
    raise SystemExit(1)


def _reject_if_not_text(value):
    if not isinstance(value, str):
        die("sentence is not text")


def _reject_if_blank_or_padded(value):
    if value != value.strip() or value.strip() == "":
        die("sentence is empty or whitespace-only")


def _reject_if_wrong_length(value):
    size = len(value)
    if size < 1 or size > CHAR_LIMIT:
        die("sentence must be 1-200 characters, got %d" % size)


def _reject_if_trailing_newline(value):
    if value.endswith("\n"):
        die("sentence must not end with a newline")


def _reject_if_control_char(value):
    for char in value:
        point = ord(char)
        if point < 0x20 or 0x7F <= point < 0xA0:
            die("sentence contains a control character U+%04X" % point)


def _reject_if_not_one_sentence(value):
    total = 0
    for mark in TERMINATORS:
        total += value.count(mark)
    if total != 1 or not value.endswith("."):
        die("sentence must be exactly one sentence ending in a period")


def _reject_if_double_space(value):
    if "  " in value:
        die("sentence contains a double space")


def _reject_if_not_one_line(value):
    # splitlines() also treats U+2028, U+2029 and U+0085 as line breaks,
    # which the control-character scan above does not reject, so a
    # sentence smuggling a Unicode separator in as a second line is
    # caught here and nowhere else.
    if len(value.splitlines()) != 1:
        die("sentence must be exactly one line")


def check_entry(text):
    """Run every competition gate over the excuse, in order."""
    _reject_if_not_text(text)
    _reject_if_blank_or_padded(text)
    _reject_if_wrong_length(text)
    _reject_if_trailing_newline(text)
    _reject_if_control_char(text)
    _reject_if_not_one_sentence(text)
    _reject_if_double_space(text)
    _reject_if_not_one_line(text)


def _write_fully(fd, data):
    """Drain ``data`` into ``fd``; a single os.write call may write short."""
    offset = 0
    while offset < len(data):
        count = os.write(fd, data[offset:])
        if count == 0:
            die("short write while writing entry.txt")
        offset += count


def _output_dir():
    """Resolve the output directory from the environment, or fail."""
    chosen = os.environ.get("MAKEFUN_OUTPUT_DIR") or DEFAULT_OUTPUT_DIR
    if not os.path.isdir(chosen):
        die("output directory does not exist: %s" % chosen)
    return chosen


def _clear_top_level(directory):
    """Remove plain files and symlinks at the top of ``directory``.

    The directory itself is never removed: the grader mounts it.
    Subdirectories are left untouched.
    """
    for entry in os.listdir(directory):
        candidate = os.path.join(directory, entry)
        try:
            if os.path.islink(candidate) or os.path.isfile(candidate):
                os.unlink(candidate)
        except OSError as err:
            die("cannot clean %s: %s" % (candidate, err))


def _fsync_dir(directory):
    handle = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def _publish(directory, data):
    """Write ``data`` to entry.txt atomically via temp file plus rename.

    mkstemp picks a unique name (O_EXCL internally), so a stale temp
    file left by an interrupted earlier run can never block this run,
    and the finally clause removes our temp file on any failure before
    the atomic publish.
    """
    destination = os.path.join(directory, ENTRY_FILENAME)
    scratch = None
    try:
        fd, scratch = tempfile.mkstemp(
            prefix=".entry.txt.", suffix=".tmp", dir=directory
        )
        try:
            _write_fully(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(scratch, ENTRY_MODE)
        os.replace(scratch, destination)
        scratch = None  # published; no longer ours to clean up
        _fsync_dir(directory)
    except OSError as err:
        die("cannot publish %s: %s" % (destination, err))
    finally:
        if scratch is not None:
            try:
                os.unlink(scratch)
            except OSError:
                pass
    return destination


def _verify_written(path, expected):
    """Read-back check: the file must match the constant byte for byte."""
    with open(path, "rb") as handle:
        actual = handle.read()
    if actual != expected:
        die("read-back mismatch: entry.txt does not match the sentence")
    found = stat.S_IMODE(os.stat(path).st_mode)
    if found != ENTRY_MODE:
        die("entry.txt mode is %o, expected 0644" % found)


def main():
    check_entry(ENTRY_TEXT)
    encoded = ENTRY_TEXT.encode("utf-8")
    directory = _output_dir()
    _clear_top_level(directory)
    target = _publish(directory, encoded)
    _verify_written(target, encoded)
    print(
        "wrote %s (%d characters, %d bytes)"
        % (target, len(ENTRY_TEXT), len(encoded))
    )


if __name__ == "__main__":
    main()
