#!/usr/bin/env python3
"""The fault matrix: every tool, every way the outside world can fail.

    pytest tests/test_fault_injection.py -q

Twelve rows of FINDINGS.md are the same bug - a failure rendered as a
result - and every one of them was found by a person noticing, not by a
check. This file is the check. See tests/faultkit.py for the property and
why the harness runs the real tools rather than simulating them.

Read a failure here as: "<tool> under <fault> exited 0". That is the whole
bug, and it is always worth fixing.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faultkit                                                 # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent
TOOLS = TEMPLATE / "tools"
TESTS = Path(__file__).resolve().parent

# Which tools reach outside, how, and with what arguments. A tool listed
# here is claiming "I depend on this"; the matrix holds it to the claim.
HTTP_TOOLS = {
    "ingest_arxiv":  ["ingest_arxiv.py", "--config", "agents/queries.yaml",
                      "--out", "vault/10-literature"],
    "ingest_repos":  ["ingest_repos.py", "--config", "agents/queries.yaml",
                      "--out", "vault/20-notes"],
    "drift_check":   ["drift_check.py", "check", "--repo", "."],
    "attribution":   ["attribution.py", "--repo", "."],
    # join resolves a handle to its noreply address through the GitHub API
    # before it writes anything. A fault here must stop it BEFORE the
    # manifest is touched: a member row invented from a failed lookup is a
    # wrong identity written into the file identity is read from.
    "join":          ["join.py", "--handle", "newmember", "--name", "New Member",
                      "--repo", "."],
}


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    """One provisioned syndicate, reused across the matrix (nothing mutates
    it that matters, and generating it per-case would dominate the runtime)."""
    d = tmp_path_factory.mktemp("faultrepo") / "syndicate"
    shutil.copytree(TEMPLATE, d, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", "*.pyc"))
    m = d / "syndicate.yaml"
    t = m.read_text(encoding="utf-8")
    t = t.replace('"github-handle"', '"realmember"')
    t = t.replace('email: "ID+handle@users.noreply.github.com"',
                  'email: "1+realmember@users.noreply.github.com"')
    t = t.replace('commit: "RECORD-AT-ACTIVATION"', 'commit: "%s"' % ("a" * 40))
    m.write_text(t, encoding="utf-8")
    for cmd in (["init", "-q", "-b", "main"],
                ["config", "user.name", "Real Member"],
                ["config", "user.email", "1+realmember@users.noreply.github.com"],
                ["add", "-A"], ["commit", "-q", "-m", "genesis"]):
        subprocess.run(["git"] + cmd, cwd=d, check=True, capture_output=True)
    # An origin with a real origin/main, because join checks out against it
    # before it ever resolves a handle. Without one, join dies at the
    # checkout and every fault test for it passes without reaching the code
    # under test - which is exactly how the first version of
    # test_join_writes_no_member_row survived a mutation that made join
    # fabricate an address out of a failed lookup.
    origin = d.parent / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True)
    for cmd in (["remote", "add", "origin", str(origin)],
                ["push", "-q", "-u", "origin", "main"]):
        subprocess.run(["git"] + cmd, cwd=d, check=True, capture_output=True)
    return d


def run_http_fault(repo, tool_key, fault, tmp_path):
    argv = list(HTTP_TOOLS[tool_key])
    tool_path = TOOLS / argv[0]
    runner = tmp_path / ("runner_%s_%s.py" % (tool_key, fault))
    runner.write_text(
        faultkit.http_runner_source(TOOLS, TESTS, tool_path, argv, fault),
        encoding="utf-8")
    r = subprocess.run([sys.executable, str(runner)], cwd=str(repo),
                       text=True, capture_output=True, timeout=180)
    return r.returncode, (r.stdout + r.stderr)


@pytest.mark.parametrize("tool_key", sorted(HTTP_TOOLS))
@pytest.mark.parametrize("fault", sorted(faultkit.HTTP_FAULTS))
def test_no_tool_exits_zero_when_its_source_failed(repo, tool_key, fault, tmp_path):
    """THE property. A tool whose data source was unavailable must not exit 0.

    Not "should warn" - a warning is not an exit code, and a workflow reads
    the exit code (row 62's second door: `ots` missing printed "stamps
    deferred" and exited 0). Not "should mention the error" - a message can
    be true while the exit code lies. The exit code is the machine-readable
    claim and it is the one that has to be honest.

    Exit 2 is a perfectly good answer here, and usually the right one:
    transient, try later, no human needed.
    """
    code, out = run_http_fault(repo, tool_key, fault, tmp_path)
    assert code != 0, (
        "%s under %s exited 0.\n\nThat is a green run meaning 'I could not "
        "look' - FINDINGS rows 34, 51 and 62, again. Whatever it printed "
        "below, a workflow reading the exit code was told everything is "
        "fine:\n\n%s" % (tool_key, fault, out[-2000:]))


@pytest.mark.parametrize("fault", sorted(faultkit.HTTP_FAULTS))
def test_doctor_is_unmoved_by_a_broken_network(repo, fault, tmp_path):
    """The negative control, and it is not optional.

    A matrix that made every tool fail under every fault would pass its own
    property while proving nothing - the harness could simply be breaking
    Python. doctor is offline BY DESIGN: it never calls the network, so its
    verdict must be identical with the network destroyed. If this test ever
    fails, either doctor grew a network call it should not have, or the
    harness is breaking more than it claims to.
    """
    baseline = subprocess.run(
        [sys.executable, str(TOOLS / "doctor.py"), "--repo", str(repo), "--json"],
        text=True, capture_output=True, timeout=120)
    runner = tmp_path / ("runner_doctor_%s.py" % fault)
    runner.write_text(faultkit.http_runner_source(
        TOOLS, TESTS, TOOLS / "doctor.py",
        ["doctor.py", "--repo", str(repo), "--json"], fault), encoding="utf-8")
    faulted = subprocess.run([sys.executable, str(runner)], cwd=str(repo),
                             text=True, capture_output=True, timeout=120)
    # The WHOLE verdict, not just the exit code. Comparing return codes alone
    # let a harness that broke builtins.open() slip through: doctor crashed,
    # the crash happened to exit with the same code as the healthy run, and
    # the control called that agreement. That is row 63's shape - a check
    # that appears to compare an outcome and actually compares one integer.
    assert faulted.returncode == baseline.returncode, (
        "doctor's verdict moved when the network broke (%d -> %d under %s). "
        "doctor is offline by design; either it gained a network call, or "
        "this harness is breaking more than the network.\n%s"
        % (baseline.returncode, faulted.returncode, fault,
           (faulted.stdout + faulted.stderr)[-1200:]))
    assert json.loads(faulted.stdout) == json.loads(baseline.stdout), (
        "doctor returned the same exit code under %s but a different report. "
        "Either it reached the network, or the harness broke something it "
        "does not claim to break." % fault)


# ── tools that shell out rather than speak HTTP ─────────────────────────────

def shim(tmp_path, name, body):
    d = tmp_path / ("shim_" + name)
    d.mkdir(parents=True, exist_ok=True)
    if body is not None:
        p = d / name
        p.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        p.chmod(0o755)
    return d


@pytest.mark.parametrize("fault", sorted(faultkit.CLI_FAULTS))
def test_anchor_upgrade_never_claims_bitcoin_it_did_not_check(repo, fault, tmp_path):
    """Row 62, generalised to every way `ots` can let you down.

    The original was one specific failure - four calendars refusing with
    403. A fix for one string is not a fix for the class, so the class is
    what gets tested: missing binary, non-zero exit, silence, empty output,
    and output that parses to nothing useful. None of them may produce a
    statement about Bitcoin.
    """
    body = faultkit.CLI_FAULTS[fault]
    if fault == "cli_silent_fail":
        body = "exit 1"
    d = shim(tmp_path, "ots", body)
    # an empty dir for cli_missing: ots simply is not there
    env = dict(os.environ, PATH=str(d) + os.pathsep + "/usr/bin:/bin")
    r = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "upgrade",
                        "--repo", str(repo)], text=True, capture_output=True,
                       env=env, timeout=180)
    out = r.stdout + r.stderr
    assert r.returncode != 0 or "0 anchor" in out or not (repo / "ledger" /
        "anchors" / "log.jsonl").exists() or _no_unconfirmed(repo), (
        "anchor upgrade under %s exited 0 with anchors it never checked "
        "(row 62):\n%s" % (fault, out[-1500:]))
    assert "not yet in a Bitcoin block" not in out, (
        "under %s it still made a claim about Bitcoin - nobody answered:\n%s"
        % (fault, out[-1500:]))


@pytest.mark.parametrize("fault", sorted(faultkit.HTTP_FAULTS))
def test_join_writes_no_member_row_when_the_lookup_failed(repo, fault, tmp_path):
    """The exit code is half of it; the manifest is the other half.

    join's whole job is turning a handle into the noreply address that IS
    that member's identity (operator rule #9). If the lookup fails and it
    writes a row anyway, the wrong identity is now in the file every other
    tool reads identity from - and attribution will score commits against
    it, or fail to, silently. So this asserts the side effect too: refusing
    loudly while leaving a half-written row behind would pass a
    code-only check.
    """
    before = (repo / "syndicate.yaml").read_text(encoding="utf-8")
    code, out = run_http_fault(repo, "join", fault, tmp_path)
    after = (repo / "syndicate.yaml").read_text(encoding="utf-8")
    assert code != 0, (
        "join under %s exited 0 having never resolved the handle:\n%s"
        % (fault, out[-1200:]))
    assert after == before, (
        "join under %s modified syndicate.yaml despite a failed identity "
        "lookup - that is a fabricated member row in the file identity is "
        "read from:\n%s" % (fault, out[-1200:]))
    assert "newmember@users.noreply.github.com" not in after


def _no_unconfirmed(repo) -> bool:
    import json as _j
    p = repo / "ledger" / "anchors" / "log.jsonl"
    if not p.exists():
        return True
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip() and _j.loads(line).get("status") != "confirmed":
            return False
    return True
