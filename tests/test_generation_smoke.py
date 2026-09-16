#!/usr/bin/env python3
"""Generation smoke test: can a syndicate be generated from this template and
can every tool run, in the documented order, against what generation produced?

This exists because finding #38: join.py shipped in v1.2 unable to parse the
manifest in the same commit. Nothing executed the adopter path end-to-end, so
the entry point was a brick for every adopter until an external audit ran it.

The rule this encodes: a tool that reads a template file is only as correct as
the template file it actually reads. Assertions here run against a real
generated tree, never a fixture, because a fixture drifts from the template in
exactly the way that produced #38.

    pytest tests/ -q          (no network: GitHub and arXiv calls are stubbed)
"""
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
import yaml

TEMPLATE = Path(__file__).resolve().parent.parent
TOOLS = TEMPLATE / "tools"


def git(*args, cwd):
    r = subprocess.run(("git",) + args, cwd=cwd, text=True, capture_output=True)
    assert r.returncode == 0, "git " + " ".join(args) + " -> " + r.stderr
    return r.stdout.strip()


@pytest.fixture
def generated(tmp_path):
    """A freshly generated syndicate: the template, git-initialised, committed."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    repo = tmp_path / "syndicate"
    shutil.copytree(TEMPLATE, repo, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", "*.pyc"))
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.name", "Founder", cwd=repo)
    git("config", "user.email", "1+founder@users.noreply.github.com", cwd=repo)
    git("remote", "add", "origin", str(origin), cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "genesis", cwd=repo)
    git("push", "-q", "-u", "origin", "main", cwd=repo)
    return repo


# ─────────────────────────── the adopter path ────────────────────────────

def test_join_can_parse_the_manifest_it_ships_with(generated, monkeypatch):
    """Finding #38. join.py's anchor must match the template's real manifest.

    This is the assertion that was missing. It does not mock the manifest -
    it reads the one generation actually produced.
    """
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(
        json.dumps({"id": 205302507, "login": "newmember"}).encode()))
    monkeypatch.setattr(sys, "argv", [
        "join.py", "--handle", "newmember", "--name", "New Member",
        "--role", "systems", "--repo", str(generated)])
    src = (TOOLS / "join.py").read_text(encoding="utf-8")

    try:
        exec(compile(src, "join.py", "exec"), {"__name__": "__main__"})
    except SystemExit as e:
        assert e.code in (0, None), (
            "join.py failed against its own template: " + str(e.code))

    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))
    emails = [m["email"] for m in cfg["members"]]
    assert "205302507+newmember@users.noreply.github.com" in emails
    assert all(m.get("github") for m in cfg["members"]), "row parsed but malformed"


def test_join_never_persists_a_token(generated, monkeypatch):
    """Finding #39. A PAT must not survive in .git/config after join.py exits."""
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(
        json.dumps({"id": 1, "login": "tokenuser"}).encode()))
    monkeypatch.setattr(sys, "argv", [
        "join.py", "--handle", "tokenuser", "--name", "Token User",
        "--repo", str(generated), "--token", "ghp_SENTINELtoken123"])
    src = (TOOLS / "join.py").read_text(encoding="utf-8")
    try:
        exec(compile(src, "join.py", "exec"), {"__name__": "__main__"})
    except SystemExit:
        pass    # the https push cannot reach a local remote; the config is the assertion

    config = (generated / ".git" / "config").read_text(encoding="utf-8")
    assert "ghp_SENTINEL" not in config, "PAT persisted in .git/config"


# ─────────────────────── the machinery, in documented order ───────────────────

def test_anchor_run_then_verify(generated):
    """anchor.py run -> verify must produce a chain that validates."""
    r = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "run",
                        "--repo", str(generated)], text=True, capture_output=True)
    assert r.returncode == 0, r.stdout + r.stderr
    log = generated / "ledger" / "anchors" / "log.jsonl"
    assert log.exists(), "anchor run wrote no log"
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["seq"] == 1 and entry["prev"] is None
    assert (generated / entry["manifest"]).exists()

    v = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "verify",
                        "--repo", str(generated)], text=True, capture_output=True)
    assert v.returncode == 0, "fresh chain does not verify: " + v.stdout + v.stderr


def test_anchor_is_idempotent_on_the_same_head(generated):
    """Re-anchoring an unchanged HEAD must not fork the chain."""
    for _ in range(2):
        subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "run",
                        "--repo", str(generated)], capture_output=True)
    lines = (generated / "ledger" / "anchors" / "log.jsonl").read_text().splitlines()
    assert len([l for l in lines if l.strip()]) == 1, "duplicate anchor for one HEAD"


def test_bitcoin_height_parses_the_real_ots_format():
    """Finding #30. ots emits BitcoinBlockHeaderAttestation(N), not 'height N'."""
    sys.path.insert(0, str(TOOLS))
    import anchor
    sample = ("File sha256 hash: abc123\n"
              "    verify PendingAttestation('https://a.calendar')\n"
              "    verify BitcoinBlockHeaderAttestation(965554)\n"
              "    verify BitcoinBlockHeaderAttestation(965528)\n")
    info = anchor.parse_info(sample)
    assert info["confirmed"] is True
    assert info["height"] == 965528, "must take the earliest attesting block"
    assert anchor.parse_info("File sha256 hash: abc\n")["confirmed"] is False


def test_bot_exclusion_patterns_match_real_bots(generated):
    """Finding #33. The manifest's exclusion regexes must match bots that run."""
    import re
    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))
    pats = [re.compile(p) for p in cfg["attribution"]["exclude_authors_matching"]]

    def excluded(s):
        return any(p.search(s) for p in pats)

    for bot in ("syndicate-anchor[bot]", "syndicate-ingest[bot]",
                "dependabot[bot]", "github-actions[bot]",
                "anchor-bot@users.noreply.github.com"):
        assert excluded(bot), bot + " is not excluded - attribution firewall inert"
    assert not excluded("1+founder@users.noreply.github.com")


def test_review_gates_cannot_deadlock(generated):
    """A gate above members-1 can never be satisfied. Fail generation, not merge."""
    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))
    if any(m.get("github") == "github-handle" for m in cfg["members"]):
        pytest.skip("unedited template manifest - a mold is not a syndicate "
                    "(operator rule #10). This guard binds at genesis.")
    cap = max(len(cfg["members"]) - 1, 1)
    for path, gate in cfg["governance"]["review_gates"].items():
        assert gate <= cap, (
            path + " gate is " + str(gate) + " but only " + str(cap) +
            " other member(s) can approve - deadlock")


def test_arxiv_queries_carry_no_inline_comments(generated):
    """Finding #13. A # inside the quotes is sent to arXiv as search text."""
    cfg = yaml.safe_load((generated / "agents" / "queries.yaml").read_text(encoding="utf-8"))
    for q in cfg["arxiv_subscriptions"]:
        assert "#" not in q, "query carries comment text into the search: " + q


def test_every_tool_has_a_working_help(generated):
    """A tool that cannot --help is a tool nobody can recover from."""
    for tool in sorted(TOOLS.glob("*.py")):
        r = subprocess.run([sys.executable, str(tool), "--help"],
                           text=True, capture_output=True, cwd=generated)
        assert r.returncode == 0, tool.name + " --help failed: " + r.stderr[:200]


# ──────────────────────── the workflows themselves ────────────────────────

def _strict_load(path):
    """Parse YAML rejecting duplicate keys.

    yaml.safe_load silently keeps the last of a duplicated key, which is how
    a doubled `workflow_dispatch:` survived in two template workflows while
    GitHub's own parser rejected both files outright. Every dispatch of them
    ended in startup_failure, and nothing local caught it - the same shape as
    finding #18 (GitHub's validator catches what safe_load passes).
    """
    class StrictLoader(yaml.SafeLoader):
        pass

    def no_duplicates(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise AssertionError("duplicate key %r at line %d"
                                     % (key, key_node.start_mark.line + 1))
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    StrictLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_duplicates)
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=StrictLoader)


def test_workflows_have_no_duplicate_keys(generated):
    """A workflow GitHub cannot parse is a workflow that has never run."""
    workflows = sorted((generated / ".github" / "workflows").glob("*.yml"))
    assert workflows, "no workflows found"
    for wf in workflows:
        _strict_load(wf)    # raises AssertionError naming the key and line


def test_template_workflows_declare_no_schedule(generated):
    """Operator rule #10: a template is the mold, not a syndicate.

    Skips the test workflow: proving the mold works is not a syndicate pipeline.
    """
    for wf in sorted((generated / ".github" / "workflows").glob("*.yml")):
        if wf.name == "smoke.yml":
            continue
        cfg = _strict_load(wf)
        triggers = cfg.get(True) or cfg.get("on") or {}    # bare `on:` parses as True
        assert "schedule" not in triggers, (
            wf.name + " declares a schedule; templates never run schedules")
