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


def provision(repo):
    """Replace the template's placeholder member - the step a real syndicate
    takes at genesis, and the one anchor.py now requires before it will stamp."""
    m = repo / "syndicate.yaml"
    m.write_text(m.read_text(encoding="utf-8").replace('"github-handle"', '"realmember"'),
                 encoding="utf-8")
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
    provision(generated)
    r = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "run",
                        "--repo", str(generated)], text=True, capture_output=True)
    assert r.returncode == 0, r.stdout + r.stderr
    log = generated / "ledger" / "anchors" / "log.jsonl"
    assert log.exists(), "anchor run wrote no log"
    entries = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]

    # Assert on the entry THIS run created, found by the repo's own HEAD - never
    # by position. Reading splitlines()[0] passed vacuously the moment the
    # template began carrying its own chain: the first line was the mold's
    # entry, not the one under test.
    head = git("rev-parse", "HEAD", cwd=generated)
    mine = [e for e in entries if e["git_head"] == head]
    assert len(mine) == 1, "expected exactly one anchor for this HEAD, got %d" % len(mine)
    entry = mine[0]
    assert (generated / entry["manifest"]).exists()
    assert entry["seq"] == 1 and entry["prev"] is None, (
        "a generated syndicate must begin its own chain, not inherit one: "
        "got seq=%s prev=%s" % (entry["seq"], entry["prev"]))

    v = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "verify",
                        "--repo", str(generated)], text=True, capture_output=True)
    assert v.returncode == 0, "fresh chain does not verify: " + v.stdout + v.stderr


def test_anchor_is_idempotent_on_the_same_head(generated):
    """Re-anchoring an unchanged HEAD must not fork the chain."""
    provision(generated)
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

    # A gate of 0 is never right, in a mold or a syndicate: it does not relax
    # review, it removes it, and Agreement 10.1 needs at least one approving
    # review to be deliverable. Checked before the mold skip, because skipping
    # here is how gates of 0 reached main unnoticed.
    for path, gate in cfg["governance"]["review_gates"].items():
        assert gate >= 1, (
            path + " gate is 0 - that removes review entirely rather than "
            "capping it; the floor is max(members-1, 1)")

    if any(m.get("github") == "github-handle" for m in cfg["members"]):
        pytest.skip("unedited template manifest - a mold is not a syndicate "
                    "(operator rule #10). The deadlock check binds at genesis.")
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


def test_mold_ships_no_anchor_chain(generated):
    """A generated syndicate must begin its own chain, not inherit the mold's.

    The template briefly carried ledger/anchors/ after its workflow was
    un-bricked and dispatched. Every repo generated from it would have started
    at seq=2, chained to an anchor describing the template's tree rather than
    its own - and test_anchor_run_then_verify passed vacuously throughout,
    because it read the first log line instead of the entry for its own HEAD.

    Anchoring is a syndicate act. The mold does not perform it (operator
    rule #10).
    """
    anchors = generated / "ledger" / "anchors"
    if not anchors.exists():
        return
    stale = sorted(p.name for p in anchors.iterdir() if p.name != ".gitkeep")
    assert not stale, (
        "the template ships an anchor chain; generated syndicates would "
        "inherit it: " + ", ".join(stale))


# ───────────────────────────── the ingester ──────────────────────────────
# ingest_arxiv.py had zero coverage here while it ran red in production for
# four consecutive mornings on nothing but rate limiting. It is also the
# skeleton any future ingestion tool would be cloned from, so its failure
# handling is the part that most needs a guard.

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2609.09999v1</id>
    <title>A Paper About Seams</title>
    <summary>Components do not fail alone.</summary>
    <published>2026-09-16T00:00:00Z</published>
    <author><name>A. Researcher</name></author>
  </entry>
</feed>"""

ERROR_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>http://arxiv.org/api/errors#malformed</id><title>Error</title></entry>
</feed>"""


def _ingest(monkeypatch, responses, tmp_path, config_text=None):
    """Run ingest_arxiv against a scripted sequence of API responses."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ingest_arxiv", TOOLS / "ingest_arxiv.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    seq = list(responses)
    calls = {"n": 0, "slept": []}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        item = seq.pop(0) if seq else seq_last
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(item.encode())

    seq_last = responses[-1] if responses else ATOM
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(mod.time, "sleep", lambda s: calls["slept"].append(s))

    cfg = tmp_path / "queries.yaml"
    cfg.write_text(config_text or 'arxiv_subscriptions:\n  - "cat:quant-ph"\n', encoding="utf-8")
    out = tmp_path / "vault" / "10-literature"
    monkeypatch.setattr(sys, "argv", ["ingest_arxiv.py", "--config", str(cfg), "--out", str(out)])
    return mod.main(), out, calls


def test_ingest_retries_a_429_instead_of_failing_the_day(monkeypatch, tmp_path):
    """A 429 is the API asking us to wait. It ran red four mornings instead."""
    import urllib.error
    throttled = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
    code, out, calls = _ingest(monkeypatch, [throttled, throttled, ATOM], tmp_path)

    assert code == 0, "a 429 that later succeeds must not fail the run"
    assert calls["n"] == 3, "expected two retries then success"
    assert calls["slept"], "retried with no backoff at all"
    assert sorted(calls["slept"]) == calls["slept"], "backoff must not shrink"
    assert len(list(out.glob("*.md"))) == 1


def test_ingest_transient_and_rejected_do_not_share_an_exit_code(monkeypatch, tmp_path):
    """Rate limiting is not a broken subscription; the operator must be able
    to tell them apart without reading the log."""
    import urllib.error
    throttled = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
    code, _, _ = _ingest(monkeypatch, [throttled] * 8, tmp_path)
    assert code == 2, "exhausted retries must exit DEFERRED (2), not a config error"

    code, _, _ = _ingest(monkeypatch, [ERROR_FEED], tmp_path)
    assert code == 1, "a query arXiv rejects must exit 1 - a human has to fix it"


def test_ingest_honours_retry_after(monkeypatch, tmp_path):
    import urllib.error
    throttled = urllib.error.HTTPError(
        "u", 429, "Too Many Requests", {"Retry-After": "7"}, None)
    code, _, calls = _ingest(monkeypatch, [throttled, ATOM], tmp_path)
    assert code == 0
    assert calls["slept"][0] == 7, "Retry-After ignored: got %s" % calls["slept"]


def test_ingest_is_idempotent_across_runs(monkeypatch, tmp_path):
    """The dedup key is load-bearing (MAP.md law 1). Re-running must not duplicate."""
    code, out, _ = _ingest(monkeypatch, [ATOM], tmp_path)
    assert code == 0 and len(list(out.glob("*.md"))) == 1
    note = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert 'arxiv_id: "2609.09999"' in note, "dedup key missing from frontmatter"

    code, out, _ = _ingest(monkeypatch, [ATOM], tmp_path)
    assert code == 0
    assert len(list(out.glob("*.md"))) == 1, "second run duplicated the paper"



def test_anchor_refuses_to_run_in_a_mold(generated):
    """Operator rule #10, enforced by the tool rather than by remembering.

    The template's chain was reverted once and recreated by a single dispatch
    43 minutes later. A guard that only reports the recurrence is not enough
    when the recurrence is one click.
    """
    r = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "run",
                        "--repo", str(generated)], text=True, capture_output=True)
    assert r.returncode != 0, "anchor ran inside an unprovisioned template"
    assert "refusing to anchor" in (r.stdout + r.stderr)
    assert not (generated / "ledger" / "anchors" / "log.jsonl").exists(), \
        "refused but wrote a chain anyway"


def test_anchor_still_runs_once_real_members_exist(generated):
    """The refusal must key on the placeholder row, never on oracle_ref -
    generated syndicates carry `oracle_ref: template` too, and gating on it
    would stop real syndicates from anchoring at all."""
    provision(generated)
    assert 'oracle_ref: "template"' in (generated / "syndicate.yaml").read_text(encoding="utf-8")

    r = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "run",
                        "--repo", str(generated)], text=True, capture_output=True)
    assert r.returncode == 0, "a provisioned syndicate was blocked: " + r.stdout + r.stderr
    assert (generated / "ledger" / "anchors" / "log.jsonl").exists()


def test_ingest_asks_for_atom(monkeypatch, tmp_path):
    """arXiv answered 406 Not Acceptable to a request that never said what it
    would accept. The header is the fix; this is the guard."""
    seen = {}

    def capture(req, timeout=None):
        seen.update({k.lower(): v for k, v in req.header_items()})
        return io.BytesIO(ATOM.encode())

    import importlib.util
    spec = importlib.util.spec_from_file_location("ingest_arxiv", TOOLS / "ingest_arxiv.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.urllib.request, "urlopen", capture)
    cfg = tmp_path / "q.yaml"; cfg.write_text('arxiv_subscriptions:\n  - "cat:quant-ph"\n', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["i", "--config", str(cfg), "--out", str(tmp_path / "v")])
    mod.main()

    assert "accept" in seen, "no Accept header sent - this is what 406'd"
    assert "atom" in seen["accept"], "Accept must name Atom: " + seen["accept"]


def test_ingest_http_refusal_does_not_blame_the_queries(monkeypatch, tmp_path):
    """A 406 is a client/header problem. Telling the operator to fix
    queries.yaml sends them to a file that is already correct - the same
    two-failures-one-bucket mistake as transient-vs-rejected, one level down."""
    import urllib.error
    refused = urllib.error.HTTPError("u", 406, "Not Acceptable", {}, None)
    code, _, calls = _ingest(monkeypatch, [refused], tmp_path)

    assert code == 1, "an HTTP refusal needs a human, so it must not exit 0 or 2"
    assert calls["n"] == 1, "406 will not heal itself; it must not be retried"


# ──────────────────────── the repo ingester ──────────────────────────────
# GitHub answers 403 for BOTH throttling and refusal, where arXiv uses 429 and
# 406. Cloning the arXiv skeleton without accounting for that would classify
# every rate limit as a permanent config error - row 51's mistake, one API over.

REPO_PAYLOAD = json.dumps({"items": [{
    "full_name": "someone/seams", "html_url": "https://github.com/someone/seams",
    "description": "Components do not fail alone.", "stargazers_count": 42,
    "language": "Python", "topics": ["testing"], "pushed_at": "2026-09-01T00:00:00Z",
    "license": {"spdx_id": "MIT"}}]})


def _ingest_repos(monkeypatch, responses, tmp_path, cfg_text=None):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ingest_repos", TOOLS / "ingest_repos.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    seq, calls = list(responses), {"n": 0, "slept": []}

    def fake(req, timeout=None):
        calls["n"] += 1
        item = seq.pop(0) if seq else responses[-1]
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(item.encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    monkeypatch.setattr(mod.time, "sleep", lambda s: calls["slept"].append(s))
    cfg = tmp_path / "q.yaml"
    cfg.write_text(cfg_text or 'github_subscriptions:\n  - "seams stars:5..500"\n', encoding="utf-8")
    out = tmp_path / "vault" / "00-inbox" / "repos"
    monkeypatch.setattr(sys, "argv", ["ingest_repos.py", "--config", str(cfg), "--out", str(out)])
    return mod.main(), out, calls


def _http(code, headers=None, body=b""):
    import urllib.error, email.message
    m = email.message.Message()
    for k, v in (headers or {}).items():
        m[k] = v
    return urllib.error.HTTPError("u", code, "err", m, io.BytesIO(body))


def test_repos_rate_limit_403_is_retried_not_treated_as_refusal(monkeypatch, tmp_path):
    """GitHub throttles with 403, not 429. Reading that as a permanent refusal
    is how a working tool reports a config error it does not have."""
    limited = _http(403, {"X-RateLimit-Remaining": "0"})
    code, out, calls = _ingest_repos(monkeypatch, [limited, REPO_PAYLOAD], tmp_path)
    assert code == 0, "a throttling 403 that later succeeds must not fail the run"
    assert calls["n"] == 2 and calls["slept"], "not retried"
    assert len(list(out.glob("*.md"))) == 1


def test_repos_genuine_403_is_not_retried(monkeypatch, tmp_path):
    """A real authorization failure must fail fast, not hammer a closed door."""
    forbidden = _http(403, {}, b'{"message":"Bad credentials"}')
    code, _, calls = _ingest_repos(monkeypatch, [forbidden] * 6, tmp_path)
    assert code == 1, "a refusal needs a human"
    assert calls["n"] == 1, "retried a permanent 403: %d calls" % calls["n"]


def test_repos_honours_retry_after_on_403(monkeypatch, tmp_path):
    limited = _http(403, {"Retry-After": "9", "X-RateLimit-Remaining": "0"})
    code, _, calls = _ingest_repos(monkeypatch, [limited, REPO_PAYLOAD], tmp_path)
    assert code == 0 and calls["slept"][0] == 9, "Retry-After ignored: %s" % calls["slept"]


def test_repos_malformed_query_is_not_a_transport_problem(monkeypatch, tmp_path):
    """422 means the query is wrong. That one DOES point at queries.yaml."""
    code, _, calls = _ingest_repos(monkeypatch, [_http(422)] * 4, tmp_path)
    assert code == 1 and calls["n"] == 1, "a malformed query must not be retried"


def test_repos_dedup_survives_across_runs(monkeypatch, tmp_path):
    """repo_id is the dedup key, same law as arxiv_id (MAP.md law 1)."""
    code, out, _ = _ingest_repos(monkeypatch, [REPO_PAYLOAD], tmp_path)
    assert code == 0 and len(list(out.glob("*.md"))) == 1
    assert 'repo_id: "someone/seams"' in next(out.glob("*.md")).read_text(encoding="utf-8")
    code, out, _ = _ingest_repos(monkeypatch, [REPO_PAYLOAD], tmp_path)
    assert len(list(out.glob("*.md"))) == 1, "second run duplicated the repo"


def test_attribution_counts_a_members_secondary_email(generated, monkeypatch):
    """Row 29. A member commits from the web UI under the account noreply and
    from a laptop under whatever git config says. Keying on one address scored
    the other at zero, silently, for two weeks. `emails:` lists the rest."""
    import importlib.util, subprocess as sp
    provision(generated)
    m = generated / "syndicate.yaml"
    m.write_text(m.read_text(encoding="utf-8").replace(
        '    email: "ID+handle@users.noreply.github.com"',
        '    email: "ID+handle@users.noreply.github.com"\n'
        '    emails: ["laptop@example.com"]'), encoding="utf-8")

    # a commit under the SECONDARY address only
    (generated / "vault" / "20-notes" / "work.md").write_text("x" * 40, encoding="utf-8")
    git("add", "-A", cwd=generated)
    git("-c", "user.name=Member", "-c", "user.email=laptop@example.com",
        "commit", "-q", "-m", "work under the secondary address", cwd=generated)
    git("remote", "set-url", "origin", "https://github.com/example/syn.git", cwd=generated)

    spec = importlib.util.spec_from_file_location("attribution", TOOLS / "attribution.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "api_get", lambda url: ([], ""))
    monkeypatch.setattr(mod, "api_paged", lambda url: [])
    monkeypatch.setattr(sys, "argv", ["attribution.py", "--repo", str(generated)])
    mod.main()

    # Find the row by the member's handle, never by taking the first CSV: the
    # template ships a placeholder window (github-handle, all zeros) and
    # rglob picked that up instead of what this run wrote. Third time today a
    # test read the wrong row - position is not identity.
    rows = []
    for csv in (generated / "ledger" / "windows").rglob("attribution.csv"):
        rows += [ln for ln in csv.read_text().splitlines()
                 if ln.startswith("realmember,")]
    assert len(rows) == 1, "expected exactly one row for the provisioned member, got %r" % rows
    churn = float(rows[0].split(",")[2])
    assert churn > 0, ("a commit under a listed secondary address scored zero: "
                       + rows[0])


# ───────────────────────── template drift check ──────────────────────────
LINEAGE = "a" * 40
UPSTREAM_HEAD = "b" * 40


def _drift(monkeypatch, repo, responses, command="check"):
    import importlib.util
    spec = importlib.util.spec_from_file_location("drift_check", TOOLS / "drift_check.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    seq, calls = list(responses), {"n": 0, "urls": [], "slept": []}

    def fake(req, timeout=None):
        calls["n"] += 1
        calls["urls"].append(req.full_url)
        item = seq.pop(0) if seq else responses[-1]
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(json.dumps(item).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    monkeypatch.setattr(mod.time, "sleep", lambda s: calls["slept"].append(s))
    monkeypatch.setattr(sys, "argv", ["drift_check.py", command, "--repo", str(repo)])
    return mod.main(), calls


def record_lineage(repo, commit=LINEAGE):
    m = repo / "syndicate.yaml"
    m.write_text(m.read_text(encoding="utf-8").replace('"RECORD-AT-ACTIVATION"',
                                                       '"%s"' % commit), encoding="utf-8")
    return repo


def _compare(files, ahead=3):
    return {"ahead_by": ahead, "files": [{"filename": f} for f in files]}


def test_drift_check_refuses_the_mold(generated, monkeypatch, capsys):
    """A template has no lineage - it IS the lineage. Same marker anchor.py
    keys on, so a mold cannot report itself in sync with itself.

    The lineage is recorded FIRST on purpose. Without it the unrecorded-lineage
    guard answers too, and this test would pass with the mold check deleted -
    which is how it was written the first time, and what mutation caught.
    """
    record_lineage(generated)
    code, calls = _drift(monkeypatch, generated, [{"sha": UPSTREAM_HEAD}])
    assert code == 1, "the mold drift-checked itself"
    assert "refusing to drift-check" in capsys.readouterr().out, \
        "refused for some other reason than being the mold"
    assert calls["n"] == 0, "asked upstream before noticing it was the mold"


def test_unrecorded_lineage_is_never_reported_as_in_sync(generated, monkeypatch):
    """The failure this whole tool exists to prevent, turned on itself: a repo
    that never recorded a lineage must say so, not report a clean bill."""
    provision(generated)
    code, calls = _drift(monkeypatch, generated, [{"sha": UPSTREAM_HEAD}])
    assert code == 1, "a repo with no lineage reported %d, not 'needs a human'" % code
    assert calls["n"] == 0


def test_drift_lists_machinery_and_ignores_narrative(generated, monkeypatch, capsys):
    """Instances inherit machinery and rules, never narrative."""
    record_lineage(provision(generated))
    code, _ = _drift(monkeypatch, generated, [
        {"sha": UPSTREAM_HEAD},
        _compare(["tools/anchor.py", "FINDINGS.md", "ROADMAP.md",
                  "docs/DISCOVERY.md", ".github/workflows/anchor.yml"])])
    out = capsys.readouterr().out
    assert code == 3, "drift found but exit was %d" % code
    assert "tools/anchor.py" in out and ".github/workflows/anchor.yml" in out
    for narrative in ("FINDINGS.md", "ROADMAP.md", "docs/DISCOVERY.md"):
        assert narrative not in out, narrative + " was reported as drift"


def test_narrative_only_change_is_not_drift(generated, monkeypatch):
    record_lineage(provision(generated))
    code, _ = _drift(monkeypatch, generated, [
        {"sha": UPSTREAM_HEAD},
        _compare(["FINDINGS.md", "ROADMAP.md", "docs/PUBLICATION.md"])])
    assert code == 0, "the template's own scar tissue was reported as this repo's work"


def test_an_unknown_upstream_directory_counts_as_drift(generated, monkeypatch, capsys):
    """The filter is a denylist on purpose: machinery added upstream after this
    tool was written must still show up. An allowlist would silently miss it."""
    record_lineage(provision(generated))
    code, _ = _drift(monkeypatch, generated, [
        {"sha": UPSTREAM_HEAD}, _compare(["oracle/kernel.py"])])
    assert code == 3 and "oracle/kernel.py" in capsys.readouterr().out


def test_drift_in_sync_does_not_compare(generated, monkeypatch):
    record_lineage(provision(generated), commit=UPSTREAM_HEAD)
    code, calls = _drift(monkeypatch, generated, [{"sha": UPSTREAM_HEAD}])
    assert code == 0 and calls["n"] == 1, "compared a head against itself"


def test_drift_transient_and_refusal_do_not_share_an_exit_code(generated, monkeypatch, capsys):
    """Row 51's lesson one API over: 'I could not look' must never read as
    'nothing changed', and must not read as 'fix your config' either."""
    record_lineage(provision(generated))
    code, calls = _drift(monkeypatch, generated, [_http(503)] * 6)
    assert code == 2, "a transient failure exited %d" % code
    assert calls["n"] == 4 and calls["slept"], "gave up without retrying"

    record_lineage(provision(generated))
    code, calls = _drift(monkeypatch, generated, [_http(404)] * 6)
    out = capsys.readouterr().out
    assert code == 1, "an unrecognised repo/ref exited %d" % code
    assert calls["n"] == 1, "retried a 404 %d times" % calls["n"]
    # A 404 and a blanket refusal share an exit code, so the message is the
    # only thing that separates "your template.repo is wrong" from "your token
    # is". Assert the message, or the branch is untested.
    assert "template repo or ref is wrong" in out, \
        "a 404 was reported without saying what to go and look at"


def test_drift_a_disowned_lineage_commit_says_so(generated, monkeypatch, capsys):
    """422 from compare means upstream cannot reach the recorded commit - a
    force-push, or a lineage recorded against a fork. Same exit as any other
    refusal, so again the message is the guard."""
    record_lineage(provision(generated))
    code, calls = _drift(monkeypatch, generated, [{"sha": UPSTREAM_HEAD}, _http(422)])
    assert code == 1 and calls["n"] == 2
    assert "not an ancestor" in capsys.readouterr().out


def test_drift_rate_limit_is_retried_not_read_as_refusal(generated, monkeypatch):
    record_lineage(provision(generated))
    code, calls = _drift(monkeypatch, generated, [
        _http(403, {"X-RateLimit-Remaining": "0"}),
        {"sha": UPSTREAM_HEAD}, _compare(["FINDINGS.md"])])
    assert code == 0 and calls["n"] == 3, "throttling 403 not retried"


def test_record_writes_lineage_without_reserialising_the_manifest(generated, monkeypatch):
    """The manifest is edited in place because re-serialising drops the comments
    that carry the governance rules - including the gate cap that closed row 9."""
    provision(generated)
    manifest = generated / "syndicate.yaml"
    before = manifest.read_text(encoding="utf-8")
    assert "cap at max(members-1, 1)" in before

    code, calls = _drift(monkeypatch, generated, [{"sha": UPSTREAM_HEAD}], command="record")
    after = manifest.read_text(encoding="utf-8")
    assert code == 0, "record failed"
    assert UPSTREAM_HEAD in after and "RECORD-AT-ACTIVATION" not in after
    assert "cap at max(members-1, 1)" in after, "re-serialised and dropped the comments"
    assert yaml.safe_load(after)["template"]["recorded"], "recorded no date"
    assert yaml.safe_load(after)["members"] == yaml.safe_load(before)["members"]


def test_record_refuses_the_mold(generated, monkeypatch):
    code, calls = _drift(monkeypatch, generated, [{"sha": UPSTREAM_HEAD}], command="record")
    assert code == 1 and calls["n"] == 0
    assert "RECORD-AT-ACTIVATION" in (generated / "syndicate.yaml").read_text(encoding="utf-8")


def test_bootstrap_never_strips_the_molds_own_narrative(generated):
    """bootstrap.sh removes FINDINGS.md and ROADMAP.md from a generated repo.
    Run inside the mold, that same step would delete the originals - so it is
    guarded on the placeholder member row, and answering 'yes' cannot override it.
    """
    git("config", "user.email", "ID+handle@users.noreply.github.com", cwd=generated)
    r = subprocess.run(["bash", "bootstrap.sh"], cwd=generated, input="y\n",
                       text=True, capture_output=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (generated / "FINDINGS.md").exists(), "bootstrap stripped the mold's findings"
    assert (generated / "ROADMAP.md").exists(), "bootstrap stripped the mold's roadmap"
    assert (generated / "docs").is_dir(), "bootstrap stripped the mold's docs"
    assert "mold detected" in r.stdout
