#!/usr/bin/env python3
"""Hostile conditions, and the machinery to put a real tool inside one.

WHY THIS EXISTS
  Twelve rows of FINDINGS.md are one bug wearing different clothes: something
  external failed, and the tool reported a RESULT instead of the failure.
  Row 34 (API died, review credit zeroed, exit 0). Row 51 (egress blocked,
  "fix your queries"). Row 62 (calendars unreachable, "not yet in a Bitcoin
  block", exit 0). Each was caught by a human noticing something odd, never
  by machinery, and row 62 only because the sandbox happened to block the
  OpenTimestamps calendars that day.

  Finding the same bug five times by luck is not a process. This is the
  process: every tool that depends on something outside itself gets run with
  that thing broken, in every way it can break, and the exit code is checked.

THE PROPERTY, STATED ONCE
  A tool whose data source was unavailable MUST NOT exit 0.

  Not "should print a warning" - a warning is not an exit code, and a
  workflow reads the exit code (row 62's second door). Not "should mention
  the error" - a message can be true while the exit code lies. The exit code
  is the machine-readable claim, and it is the one that must be honest.

ONE BORROWED CONSTRAINT
  The harness drives each tool through its REAL entry point, in a
  subprocess, with the fault installed underneath it. It never reimplements
  a tool's logic to "simulate" what it would do.

  That rule is borrowed from an unrelated monitoring runtime (UMA-AGENTIC),
  whose ledger-replay check once compared two different compiled programs
  and therefore measured cross-compilation drift rather than ledger
  integrity - a check that looked like it verified one thing and actually
  verified another. Row 63 is the same mistake in this repository: a guard
  that appeared to read three exit codes and in fact read two. A harness
  that simulated a tool instead of running it would be that mistake a third
  time, so it does not get the chance.
"""
import io
import json
import socket
import urllib.error
import urllib.request


# ── the faults ──────────────────────────────────────────────────────────────
# Each entry is what the outside world does instead of answering. The names
# are the ones a person would use in an incident, so a failure reads as a
# sentence: "ingest_arxiv under http_406 exited 0".

def _http_error(code, body=b"", headers=None):
    def raise_it(*a, **k):
        raise urllib.error.HTTPError(
            "https://example.invalid", code, "injected %d" % code,
            headers or {}, io.BytesIO(body))
    return raise_it


def _url_error(reason):
    def raise_it(*a, **k):
        raise urllib.error.URLError(reason)
    return raise_it


def _timeout(*a, **k):
    raise socket.timeout("injected timeout")


def _body(payload: bytes):
    """Reachable, answers, and the answer is useless. The nastiest class:
    nothing raises, so a tool only notices if it actually checks."""
    def respond(*a, **k):
        return io.BytesIO(payload)
    return respond


HTTP_FAULTS = {
    # refusals the record has actually met
    "http_403_forbidden":   _http_error(403),
    "http_406_not_accept":  _http_error(406),            # row 51, live
    "http_429_rate_limit":  _http_error(429, headers={"Retry-After": "1"}),
    "http_500_server":      _http_error(500),
    "http_502_gateway":     _http_error(502),
    # the network, absent in its three usual ways
    "dns_failure":          _url_error(socket.gaierror("Name or service not known")),
    "connection_refused":   _url_error(ConnectionRefusedError("Connection refused")),
    "timeout":              _timeout,
    # answered, but with nothing usable - no exception to notice
    "empty_body":           _body(b""),
    "truncated_xml":        _body(b"<?xml version='1.0'?><feed><entry><tit"),
    "garbage_body":         _body(b"\x00\x01\x02 not a response at all"),
    "html_error_page":      _body(b"<html><body>502 Bad Gateway</body></html>"),
    "empty_json_object":    _body(json.dumps({}).encode()),
    "json_wrong_shape":     _body(json.dumps({"unexpected": "shape"}).encode()),
}

# Faults for tools that shell out instead of speaking HTTP.
CLI_FAULTS = {
    "cli_missing":      None,                      # binary absent from PATH
    "cli_exit_1":       "exit 1",
    "cli_silent_fail":  "exit 1",                  # non-zero, says nothing at all
    "cli_empty_output": "exit 0",                  # zero, produces nothing
    "cli_garbage":      "echo 'not the expected output'; exit 0",
}


# ── the runner ──────────────────────────────────────────────────────────────

RUNNER = r'''
import io, json, socket, sys, time, urllib.error, urllib.request
sys.path.insert(0, %(tools)r)
fault = %(fault)r

# The retry LOGIC is under test; the wall clock is not. Tools back off
# exponentially by design - correct behaviour, and ruinous here. Measured,
# not estimated: the same 75 cases on the same machine took 1944s (32m24s)
# with real sleeps and 6.8s without. 286x. A half-hour guard gets run once,
# then moved to a nightly, then disabled - and a disabled guard is no guard,
# which is the failure this whole file exists to prevent, arriving by the
# side door. Every retry still happens and every decision is still made;
# only the waiting is gone.
time.sleep = lambda *a, **k: None

import faultkit
urllib.request.urlopen = faultkit.HTTP_FAULTS[fault]

sys.argv = %(argv)r
src = open(%(tool)r, encoding="utf-8").read()
try:
    exec(compile(src, %(tool)r, "exec"), {"__name__": "__main__", "__file__": %(tool)r})
except SystemExit as e:
    code = e.code
    sys.exit(code if isinstance(code, int) else (0 if code is None else 1))
'''


def http_runner_source(tools_dir, tests_dir, tool_path, argv, fault):
    return ("import sys; sys.path.insert(0, %r)\n" % str(tests_dir)) + (
        RUNNER % dict(tools=str(tools_dir), fault=fault,
                      argv=list(argv), tool=str(tool_path)))
