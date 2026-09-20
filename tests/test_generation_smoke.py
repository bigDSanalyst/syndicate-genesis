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
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
import yaml

TEMPLATE = Path(__file__).resolve().parent.parent
TOOLS = TEMPLATE / "tools"
sys.path.insert(0, str(TOOLS))
from manifest import formation_ok as manifest_formation_ok   # noqa: E402


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
    # The floor of 1 is deliberate and is NOT a claim that one member can satisfy
    # a gate of 1 - nobody approves their own PR. It exists so a gate can never be
    # relaxed to 0. What makes a one-member syndicate legitimate is the declared
    # formation (test_a_solo_syndicate_must_declare_itself); this assertion only
    # catches gates above the roster.
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

# GitHub's search API always returns total_count alongside items; a
# fixture missing it is a fixture that has drifted from the API it
# stands in for (#38, in miniature).
REPO_PAYLOAD = json.dumps({"total_count": 1, "incomplete_results": False,
                           "items": [{
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


def test_a_syndicates_own_audit_is_never_drift(generated, monkeypatch, capsys):
    """The strip list strips inheritance, not identity.

    audits/ is a record organ beside ledger/ and agreements/: an audit written
    about THIS repo is this repo's history even though it reads like narrative.
    Its README is the exception - the drawer's label ships from the template.
    """
    record_lineage(provision(generated))
    code, _ = _drift(monkeypatch, generated, [
        {"sha": UPSTREAM_HEAD},
        _compare(["audits/AUDIT-001-opus.md", "audits/README.md"])])
    out = capsys.readouterr().out
    assert code == 3, "the drawer's label stopped tracking the template"
    assert "audits/README.md" in out
    assert "AUDIT-001-opus.md" not in out, "reported a syndicate's own audit as drift"


def offline_path(tmp_path):
    """PATH shim that stubs the one bootstrap step which would reach the network.

    The suite is offline by contract; bootstrap's lineage record is the only
    step that calls out. Stubbing it here keeps that contract and lets the strip
    itself run for real, which is the part under test.
    """
    binf = tmp_path / "shim"
    binf.mkdir(exist_ok=True)
    shim = binf / "python3"
    shim.write_text('#!/bin/sh\n'
                    'case "$*" in *drift_check.py*) echo "stub: lineage recorded"; exit 0;; esac\n'
                    'exec %s "$@"\n' % sys.executable, encoding="utf-8")
    shim.chmod(0o755)
    env = dict(os.environ, PATH=str(binf) + os.pathsep + os.environ["PATH"])
    return env


def test_bootstrap_never_strips_the_audits_drawer(generated, tmp_path):
    """docs/ is inherited and stripped; audits/ is identity and is not.

    Answers "y" deliberately. Declining the prompt saves everything, so a test
    that declines proves nothing about the strip list - which is what mutation
    caught: adding audits/ to that list left the earlier version green.
    """
    provision(generated)
    (generated / "audits").mkdir(exist_ok=True)
    (generated / "audits" / "AUDIT-001-someone.md").write_text("found\n", encoding="utf-8")
    # the manifest's own address, so the identity gate does not eat the "y"
    git("config", "user.email", "ID+handle@users.noreply.github.com", cwd=generated)
    git("add", "-A", cwd=generated)
    git("commit", "-q", "-m", "audit", cwd=generated)

    r = subprocess.run(["bash", "bootstrap.sh"], cwd=generated, input="y\n",
                       text=True, capture_output=True, env=offline_path(tmp_path))
    assert not (generated / "FINDINGS.md").exists(), \
        "the strip never ran, so this proves nothing: " + r.stdout + r.stderr
    assert (generated / "audits" / "AUDIT-001-someone.md").exists(), \
        "bootstrap stripped a record organ: " + r.stdout + r.stderr


def test_bootstrap_warns_before_stripping_instance_history_in_docs(generated):
    """A repo that kept its audit in docs/ must be told before it says yes -
    the shakedown is exactly that repo, so the warning is not hypothetical."""
    provision(generated)
    (generated / "docs" / "AUDIT-001-opus.md").write_text("found\n", encoding="utf-8")
    git("config", "user.email", "ID+handle@users.noreply.github.com", cwd=generated)
    git("add", "-A", cwd=generated)
    git("commit", "-q", "-m", "audit in docs", cwd=generated)

    r = subprocess.run(["bash", "bootstrap.sh"], cwd=generated, input="n\n",
                       text=True, capture_output=True)
    assert "move them to audits/" in r.stdout, \
        "offered to delete this repo's own audit without saying so: " + r.stdout


def test_template_ships_the_audits_drawer(generated):
    """An empty convention is a convention nobody follows."""
    readme = generated / "audits" / "README.md"
    assert readme.exists(), "template ships no audits/ drawer"
    assert "strips inheritance, not identity" in readme.read_text(encoding="utf-8")


def test_the_drawer_a_syndicate_inherits_is_empty(generated):
    """Same shape as the anchor chain: a generated syndicate begins its own.

    An audit OF the template is the template's scar tissue - the same category as
    FINDINGS.md - so it lives in docs/ and is stripped. If the mold kept one in
    the drawer instead, every syndicate ever generated would carry someone else's
    audit as its own history, and the never-strip rule would protect it there
    forever.
    """
    found = [f.name for f in (generated / "audits").iterdir() if f.name != "README.md"]
    assert not found, "the mold ships audits every instance would inherit: %s" % found


# ──────────────────────────── solo formation ─────────────────────────────
def formation_of(repo):
    cfg = yaml.safe_load((repo / "syndicate.yaml").read_text(encoding="utf-8"))
    return (cfg.get("governance") or {}).get("formation")


def set_manifest(repo, **kw):
    """Rewrite manifest scalars in place, the way a member editing it would."""
    m = repo / "syndicate.yaml"
    t = m.read_text(encoding="utf-8")
    for key, value in kw.items():
        t, n = re.subn(r"(?m)^(\s*%s:\s*)\S+" % key, r"\g<1>" + value, t, count=1)
        assert n == 1, "no %s: line to set" % key
    m.write_text(t, encoding="utf-8")
    return repo


def add_second_member(repo):
    m = repo / "syndicate.yaml"
    t = m.read_text(encoding="utf-8")
    row = ('\n  - name: "Second"\n    github: "second"\n'
           '    orcid: "0000-0000-0000-0000"\n'
           '    email: "2+second@users.noreply.github.com"\n'
           '    role: "theory"\n    trust_tier: verified\n    joined: "2026-09-18"\n')
    i = re.search(r"(?m)^members:.*$", t).end()
    m.write_text(t[:i] + row + t[i:], encoding="utf-8")
    return repo


def test_a_solo_syndicate_must_declare_itself(generated):
    """One member and no declaration is the shape that always deadlocks.

    It is also indistinguishable from a two-person syndicate whose second member
    never arrived - which is what happened on this repo in PRs #6-#8. The guard
    refuses it so the first gated PR is not where an adopter finds out.
    """
    provision(generated)
    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))
    assert len(cfg["members"]) == 1 and formation_of(generated) == "multi", \
        "fixture is not the undeclared one-member shape"

    ok, why = manifest_formation_ok(cfg)
    assert not ok, "an undeclared one-member syndicate was accepted"
    assert "formation: solo" in why, "the refusal does not say how to fix it: " + why


def test_a_declared_solo_syndicate_is_allowed(generated):
    """Solo is supported: the unaffiliated independent usually starts alone, and
    one human with stakes is a signer seat. The declaration is what makes merging
    on the founder's own authority legible, with the anchor chain as the
    compensating control (row 48's posture, stated rather than stumbled into)."""
    provision(generated)
    set_manifest(generated, formation="solo")
    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))

    ok, why = manifest_formation_ok(cfg)
    assert ok, "a declared solo syndicate was refused: " + why


def test_the_solo_marker_is_sticky(generated):
    """A second member ends solo formation. A stale marker would leave a
    two-person syndicate declaring itself alone - and the declaration is what the
    bypass posture rests on, so it must not outlive the roster it describes."""
    provision(generated)
    set_manifest(generated, formation="solo")
    add_second_member(generated)
    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))
    assert len(cfg["members"]) == 2

    ok, why = manifest_formation_ok(cfg)
    assert not ok, "solo formation survived the arrival of a second member"
    assert "sticky" in why, why


def test_join_clears_the_solo_marker(generated, monkeypatch):
    """The transition is a governance act, so it rides the PR that causes it.
    join.py clearing it is what stops the tool handing an adopter a manifest
    their own suite rejects."""
    provision(generated)
    set_manifest(generated, formation="solo")
    git("add", "-A", cwd=generated)
    git("commit", "-q", "-m", "solo formation", cwd=generated)
    git("push", "-q", "origin", "main", cwd=generated)

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(
        json.dumps({"id": 205302507, "login": "second"}).encode()))
    monkeypatch.setattr(sys, "argv", [
        "join.py", "--handle", "second", "--name", "Second",
        "--role", "theory", "--repo", str(generated)])
    src = (TOOLS / "join.py").read_text(encoding="utf-8")
    try:
        exec(compile(src, "join.py", "exec"), {"__name__": "__main__"})
    except SystemExit as e:
        assert e.code in (0, None), "join.py failed: " + str(e.code)

    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))
    assert len(cfg["members"]) == 2, "the second member never landed"
    assert formation_of(generated) == "multi", \
        "join added the second member and left the syndicate declaring itself solo"
    ok, why = manifest_formation_ok(cfg)
    assert ok, why


def test_the_mold_is_exempt_from_formation(generated):
    """A mold is not a syndicate (operator rule #10): it ships one placeholder
    row and declares nothing, and that is correct rather than undeclared-solo."""
    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))
    from manifest import is_unprovisioned_template
    assert is_unprovisioned_template(cfg), "fixture is not a mold"
    assert len(cfg["members"]) == 1 and \
        (cfg["governance"].get("formation")) != "solo", "not the shape under test"

    ok, why = manifest_formation_ok(cfg)
    assert ok, "the template refuses its own shipped manifest: " + why


# ─────────────────────── attribution: exact arithmetic ───────────────────
def _attribution_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("attribution", TOOLS / "attribution.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def _run_attribution(repo, monkeypatch, commits):
    """Drive a window over `commits` = [(email, filename, bytes)], no network."""
    mod = _attribution_mod()
    # Land any pending setup (the manifest edit) under a NON-member address
    # first. Otherwise it rides in the first member's commit and that member
    # starts the window ahead - which is how the tie test caught this fixture.
    if git("status", "--porcelain", cwd=repo).strip():
        git("add", "-A", cwd=repo)
        git("-c", "user.name=Setup", "-c", "user.email=setup@example.invalid",
            "commit", "-q", "-m", "setup", cwd=repo)
    for email, name, size in commits:
        (repo / "vault" / "20-notes" / name).write_text("x" * size, encoding="utf-8")
        git("add", "-A", cwd=repo)
        git("-c", "user.name=M", "-c", "user.email=" + email,
            "commit", "-q", "-m", "work " + name, cwd=repo)
    git("remote", "set-url", "origin", "https://github.com/example/syn.git", cwd=repo)
    monkeypatch.setattr(mod, "api_get", lambda url: ([], ""))
    monkeypatch.setattr(mod, "api_paged", lambda url: [])
    monkeypatch.setattr(sys, "argv", ["attribution.py", "--repo", str(repo)])
    mod.main()
    shares = {}
    for csv in (repo / "ledger" / "windows").rglob("attribution.csv"):
        for ln in csv.read_text(encoding="utf-8").splitlines()[1:]:
            f = ln.split(",")
            if f[0] != "github-handle":            # skip the shipped placeholder
                shares[f[0]] = f[-1]
    return mod, shares


def two_members(repo):
    """Provisions as two members. Does its own placeholder rename - do NOT
    call provision() first, or this one finds nothing to replace."""
    m = repo / "syndicate.yaml"
    t = m.read_text(encoding="utf-8").replace('"github-handle"', '"alpha"').replace(
        '    email: "ID+handle@users.noreply.github.com"',
        '    email: "1+alpha@users.noreply.github.com"')
    row = ('\n  - name: "Beta"\n    github: "beta"\n'
           '    orcid: "0000-0000-0000-0000"\n'
           '    email: "2+beta@users.noreply.github.com"\n'
           '    role: "theory"\n    trust_tier: verified\n    joined: "2026-09-18"\n')
    i = re.search(r"(?m)^members:.*$", t).end()
    m.write_text(t[:i] + row + t[i:], encoding="utf-8")
    return repo


def test_attribution_is_exact_not_floating(generated, monkeypatch):
    """These numbers decide revenue splits, so they are Decimal end to end.

    Binary floats make the result depend on summation order, so a member
    recomputing a window on another machine can get different digits - and a
    number that changes when you recompute it is not evidence.
    """
    mod = _attribution_mod()
    from decimal import Decimal
    assert isinstance(mod.SURVIVOR_WEIGHT, Decimal), "survivor weight is a float"
    assert mod.dec(0.35) == Decimal("0.35"), "weights inherit binary float error"
    assert mod.q(Decimal("0.12345"), 4) == Decimal("0.1234"), "not half-to-even"
    assert mod.q(Decimal("0.12355"), 4) == Decimal("0.1236")


def test_equal_work_splits_exactly_evenly(generated, monkeypatch):
    """The tie case. Two members, identical work: the shares must be equal to
    the last digit, not 0.4999/0.5001 from summation order."""
    two_members(generated)
    _, shares = _run_attribution(generated, monkeypatch, [
        ("1+alpha@users.noreply.github.com", "a.md", 40),
        ("2+beta@users.noreply.github.com", "b.md", 40)])
    assert set(shares) == {"alpha", "beta"}, shares
    assert shares["alpha"] == shares["beta"], "identical work split unevenly: %r" % shares


def test_a_window_with_no_work_yields_zeros_not_an_equal_split(generated, monkeypatch):
    """The honest answer to 'nobody did anything' is zero each, not 50/50.

    An equal split of nothing would put unearned shares in the ledger, and the
    ledger is what a member's claim is read from.
    """
    two_members(generated)
    _, shares = _run_attribution(generated, monkeypatch, [])
    assert set(shares) == {"alpha", "beta"}, shares
    assert all(float(v) == 0 for v in shares.values()), \
        "an empty window invented shares: %r" % shares


def test_a_solo_window_gives_the_only_member_everything(generated, monkeypatch):
    """Solo formation still has to produce a coherent ledger: one member who
    did the work holds the whole share, with no division-by-zero on the way."""
    provision(generated)
    set_manifest(generated, formation="solo")
    _, shares = _run_attribution(generated, monkeypatch, [
        ("ID+handle@users.noreply.github.com", "solo.md", 40)])
    assert list(shares) == ["realmember"], shares
    assert float(shares["realmember"]) == 1.0, "solo share was not whole: %r" % shares


# ────────────────────────── supply chain & record ────────────────────────
def test_every_action_is_pinned_to_a_commit(generated):
    """A tag is mutable: whoever controls it can move what runs in CI, with the
    repo's write token. Disabled workflows are checked too - enabling one must
    not silently un-pin you."""
    unpinned = []
    for wf in sorted((generated / ".github" / "workflows").iterdir()):
        for i, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r"uses:\s*([\w./-]+)@(\S+)", line)
            if m and not re.fullmatch(r"[0-9a-f]{40}", m.group(2)):
                unpinned.append("%s:%d %s@%s" % (wf.name, i, *m.groups()))
    assert not unpinned, "actions pinned to mutable refs: " + "; ".join(unpinned)


def test_ots_verify_job_reads_and_never_writes(generated):
    """The chain is solo formation's compensating control, so something has to
    prove the stored receipts still verify. Failure is a finding, not a repair:
    a broken chain means tampered bytes or a lost manifest, and neither is fixed
    by a bot commit - so the job is given no permission to make one."""
    wf = generated / ".github" / "workflows" / "ots-verify.yml"
    assert wf.exists(), "no ots-verify workflow"
    cfg = _strict_load(wf)
    assert cfg["permissions"] == {"contents": "read"}, \
        "the verify job can write: " + str(cfg["permissions"])
    body = wf.read_text(encoding="utf-8")
    assert "anchor.py verify" in body
    assert "--exclude=.git" in body, "verifies the checkout, not the bare export"
    for writer in ("git commit", "git push", "github.token", "secrets."):
        assert writer not in body, "verify job touches " + writer


def test_citation_file_makes_no_identifier_it_cannot_back(generated):
    """A placeholder ORCID in a citation file resolves to nothing and reads as a
    real claim. The manifest ships 0000-0000-0000-0000; the citation must not."""
    cff = generated / "CITATION.cff"
    assert cff.exists(), "a research-attribution tool with no CITATION.cff"
    cfg = yaml.safe_load(cff.read_text(encoding="utf-8"))
    assert {"cff-version", "title", "authors", "message", "type"} <= set(cfg)
    assert "0000-0000-0000-0000" not in cff.read_text(encoding="utf-8"), \
        "placeholder ORCID in the citation file"


def test_the_counsel_disclaimer_is_where_a_contributor_meets_it(generated):
    """Three places: the README a visitor reads, the agreement itself, and the
    PR template of anyone about to change it."""
    for path in ("README.md", "agreements/consortium-agreement.md",
                 ".github/pull_request_template.md"):
        text = (generated / path).read_text(encoding="utf-8").lower()
        assert "counsel" in text or "legal advice" in text, \
            path + " carries no counsel disclaimer"


# ─────────────────────────── signed commits ──────────────────────────────
def signing_repo(repo, members=("alpha",)):
    """Provision with real SSH signing keys and a signing epoch of today."""
    # Keys live OUTSIDE the repo: `git add -A` would otherwise commit the private
    # halves and change the very tree under test. ssh needs the private key at
    # the public key's path minus ".pub", so the pair is never renamed apart.
    keydir = repo.parent / "keys"
    keydir.mkdir(exist_ok=True)
    keys = {}
    for who in members:
        priv = keydir / who
        if not priv.exists():
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                            "-f", str(priv), "-C", who], check=True)
        keys[who] = (keydir / (who + ".pub")).read_text(encoding="utf-8").strip()

    m = repo / "syndicate.yaml"
    t = m.read_text(encoding="utf-8").replace('"github-handle"', '"alpha"').replace(
        '    email: "ID+handle@users.noreply.github.com"',
        '    email: "1+alpha@users.noreply.github.com"').replace(
        'signing_since: "YYYY-MM-DD"', 'signing_since: "2000-01-01"')
    t = t.replace("    keys: []", '    keys: ["%s"]' % keys["alpha"], 1)
    for who in members[1:]:
        t = t.replace("\nmembers:", "\nmembers:", 1)
        i = re.search(r"(?m)^members:.*$", t).end()
        t = (t[:i] + '\n  - name: "%s"\n    github: "%s"\n'
             '    orcid: "0000-0000-0000-0000"\n'
             '    email: "2+%s@users.noreply.github.com"\n'
             '    role: "theory"\n    trust_tier: verified\n'
             '    joined: "2026-09-18"\n    keys: ["%s"]\n' % (who, who, who, keys[who])
             + t[i:])
    m.write_text(t, encoding="utf-8")
    # The harness redirects gpg.ssh.program globally; point it back at ssh-keygen.
    git("config", "gpg.format", "ssh", cwd=repo)
    git("config", "gpg.ssh.program", "ssh-keygen", cwd=repo)
    return repo, keys


def sign_commit(repo, who, email, name, signed=True, gitignore=True):
    (repo / "vault" / "20-notes" / name).write_text("x" * 20, encoding="utf-8")
    git("add", "-A", cwd=repo)
    args = ["-c", "user.name=" + who, "-c", "user.email=" + email]
    if signed:
        args += ["-c", "user.signingkey=" + str(repo.parent / "keys" / (who + ".pub")),
                 "-c", "commit.gpgsign=true"]
    else:
        args += ["-c", "commit.gpgsign=false"]
    git(*(args + ["commit", "-q", "-m", "work " + name]), cwd=repo)


def run_verify(repo):
    r = subprocess.run([sys.executable, str(TOOLS / "verify_signatures.py"),
                        "--repo", str(repo)], text=True, capture_output=True)
    return r.returncode, r.stdout + r.stderr


def test_a_signed_member_commit_passes(generated):
    repo, _ = signing_repo(generated)
    sign_commit(repo, "alpha", "1+alpha@users.noreply.github.com", "a.md")
    code, out = run_verify(repo)
    assert code == 0, "a properly signed commit was rejected:\n" + out


def test_an_unsigned_member_commit_fails(generated):
    """Fail, not warn. A rule the machinery states and does not enforce is a
    receipt machine for a later dispute (rows 44 and 48)."""
    repo, _ = signing_repo(generated)
    sign_commit(repo, "alpha", "1+alpha@users.noreply.github.com", "a.md", signed=False)
    code, out = run_verify(repo)
    assert code == 1, "an unsigned member commit passed:\n" + out
    assert "not signed" in out


def test_a_good_signature_by_another_members_key_fails(generated):
    """THE one git does not catch.

    `git verify-commit` answers "is this key in the allowed signers file", not
    "does this key belong to this author": measured here, a commit authored by
    one member and signed with another's key reports G and exits 0. Binding the
    fingerprint to the author's own row is the entire guarantee.
    """
    repo, _ = signing_repo(generated, members=("alpha", "beta"))
    # alpha's commit, signed with BETA's key - both keys are in the manifest
    (repo / "vault" / "20-notes" / "a.md").write_text("x" * 20, encoding="utf-8")
    git("add", "-A", cwd=repo)
    git("-c", "user.name=alpha", "-c", "user.email=1+alpha@users.noreply.github.com",
        "-c", "user.signingkey=" + str(repo.parent / "keys" / "beta.pub"), "-c", "commit.gpgsign=true",
        "commit", "-q", "-m", "alpha's work, beta's key", cwd=repo)

    # git itself is satisfied - this is the assertion that proves the gap is real
    signers = repo / "allowed"
    cfg = yaml.safe_load((repo / "syndicate.yaml").read_text(encoding="utf-8"))
    signers.write_text("".join(
        '%s namespaces="git" %s\n' % (m["email"], k)
        for m in cfg["members"] for k in m["keys"]), encoding="utf-8")
    g = subprocess.run(["git", "-c", "gpg.ssh.allowedSignersFile=" + str(signers),
                        "verify-commit", "HEAD"], cwd=repo, capture_output=True)
    assert g.returncode == 0, "git rejected it after all - re-check the premise"

    code, out = run_verify(repo)
    assert code == 1, "impersonation passed: a good signature by the wrong " \
                      "member's key was accepted:\n" + out
    assert "does not list" in out


def test_commits_before_the_epoch_are_not_checked(generated):
    """Every repo adopting signing has unsigned history behind it."""
    repo, _ = signing_repo(generated)
    sign_commit(repo, "alpha", "1+alpha@users.noreply.github.com", "old.md", signed=False)
    m = repo / "syndicate.yaml"
    m.write_text(m.read_text(encoding="utf-8").replace(
        'signing_since: "2000-01-01"', 'signing_since: "2999-01-01"'), encoding="utf-8")
    code, out = run_verify(repo)
    assert code == 0, "an unsigned commit before the epoch was checked:\n" + out


def test_an_unset_epoch_is_refused_rather_than_defaulted(generated):
    """Same shape as formation: a decision, refused until made. Defaulting to
    'all history' fails every repo on day one; defaulting to 'nothing' ships a
    rule that never fires."""
    repo, _ = signing_repo(generated)
    m = repo / "syndicate.yaml"
    m.write_text(m.read_text(encoding="utf-8").replace(
        'signing_since: "2000-01-01"', 'signing_since: "YYYY-MM-DD"'), encoding="utf-8")
    code, out = run_verify(repo)
    assert code == 1 and "signing_since" in out, out


def test_a_non_members_commit_is_ignored_not_failed(generated):
    """The anchor and ingest bots commit as themselves. They hold no key, are in
    no manifest row, and have no member to impersonate."""
    repo, _ = signing_repo(generated)
    sign_commit(repo, "alpha", "anchor-bot@users.noreply.github.com", "bot.md",
                signed=False)
    code, out = run_verify(repo)
    assert code == 0, "a bot commit was held to the member signing rule:\n" + out


def test_the_mold_has_nobody_to_verify(generated):
    """Operator rule #10: a mold ships a placeholder row and no keys."""
    code, out = run_verify(generated)
    assert code == 0 and "not a syndicate yet" in out, out


def test_every_workflow_runs_the_same_python(generated):
    """Row 61. This guard replaces one whose reason expired underneath it.

    It used to assert `>= 3.12` on the pq-verify workflow alone, because
    pq-verify 2.6.7 declared requires-python >=3.8 while its package used
    f-string escapes that only parse from 3.12 (PEP 701) - pip installed it and
    the import raised. That was measured, and it was true. It is no longer:
    2.8.0 declares >=3.9 and its package and tests both parse against the 3.9
    grammar, re-measured 2026-09-20.

    Nothing in this repository re-checks a guard's premise, so the old one
    would have gone on enforcing a rule for a reason that had stopped existing
    - green, and quietly wrong about why. The pin itself was never the problem
    and has not moved; what changed is that it is now justified by something
    still true.

    One Python across every workflow, disabled ones included. A workflow on its
    own version is a difference nobody chose, found the day it behaves unlike
    the other six.
    """
    versions = {}
    for wf in sorted((generated / ".github" / "workflows").iterdir()):
        for i, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r'python-version:\s*"?(\d+\.\d+)"?', line)
            if m:
                versions.setdefault(m.group(1), []).append("%s:%d" % (wf.name, i))

    assert versions, "no python-version found in any workflow - the parse is wrong"
    assert len(versions) == 1, "workflows disagree about Python:\n" + "\n".join(
        "  %s  <- %s" % (v, ", ".join(w)) for v, w in sorted(versions.items()))


# ──────────────────── the helper an adopter meets first ─────────────────────
#
# doctor.py is the one command someone runs before anything works, and the
# agent brief is what an agent reads before it touches the repository. Both are
# load-bearing in the same way a green check is: they are believed. These
# guards exist because the cost of a wrong line in either is not a broken
# build, it is a confident wrong answer.

def run_doctor(repo, *args):
    r = subprocess.run([sys.executable, str(TOOLS / "doctor.py"), "--repo", str(repo)]
                       + list(args), text=True, capture_output=True)
    return r.returncode, r.stdout + r.stderr


def doctor_json(repo):
    code, out = run_doctor(repo, "--json")
    return code, json.loads(out)


def test_doctor_does_not_hand_the_mold_a_wall_of_red(generated):
    """Operator rule #10: a mold is not a syndicate.

    The template legitimately has no lineage, no keys, no executed agreement
    and no member whose git identity could match - every one of those is a
    placeholder waiting for genesis, not a defect. A first-run helper that
    reports six failures on a repository behaving exactly as designed teaches
    its reader to ignore it, which is the one thing a helper must not do.

    Asserted on the message, not the exit code: the mold path and a clean
    syndicate both exit 0, so a code-only assertion would pass for the wrong
    reason.
    """
    code, data = doctor_json(generated)
    assert code == 0, "doctor blocked on the unmodified template"
    assert data["is_template"] is True, "doctor did not recognise the mold"
    keys = {c["check"] for c in data["checks"]}
    for absent in ("identity", "signing.epoch", "lineage", "agreement", "anchors"):
        assert absent not in keys, (
            "doctor asked the mold '%s', a question only a real syndicate can "
            "answer" % absent)

    _, text = run_doctor(generated)
    assert "template itself" in text, text


def test_doctor_writes_nothing(generated):
    """It is the first command an adopter runs, often before they trust it.

    A diagnosis that mutates the thing it is diagnosing cannot be run twice
    with confidence. __pycache__ is excluded because importing a module is how
    Python works and .gitignore already covers it; everything else must be
    untouched.
    """
    provision(generated)
    git("add", "-A", cwd=generated)
    git("commit", "-q", "-m", "provisioned", cwd=generated)
    before = git("status", "--porcelain", cwd=generated)
    head = git("rev-parse", "HEAD", cwd=generated)

    run_doctor(generated)
    run_doctor(generated, "--json")

    after = [ln for ln in git("status", "--porcelain", cwd=generated).splitlines()
             if "__pycache__" not in ln]
    assert after == [ln for ln in before.splitlines() if "__pycache__" not in ln], (
        "doctor changed the working tree: " + "\n".join(after))
    assert git("rev-parse", "HEAD", cwd=generated) == head, "doctor committed something"


def test_doctor_names_a_command_for_everything_it_blocks(generated):
    """A diagnosis without a next step is a support conversation, not a tool.

    Every BLOCK must carry a fix, and the fix must be an act - a command or a
    named change - rather than a restatement of the problem.
    """
    provision(generated)
    _, data = doctor_json(generated)
    blocked = [c for c in data["checks"] if c["status"] == "BLOCK"]
    assert blocked, "expected a provisioned-but-unconfigured repo to block"
    for c in blocked:
        assert c["fix"].strip(), "BLOCK '%s' names no next step" % c["check"]
        assert c["fix"].strip() != c["headline"].strip()
    assert data["next"] is not None and data["next"]["fix"].strip()


def test_doctor_catches_the_unregistered_author_address(generated):
    """Operator rule #9, and the failure that never announces itself.

    An unregistered author address does not break a commit. It makes the commit
    invisible to attribution.py, which scores it zero in every window until
    someone reconciles a payout by hand. This is the single highest-value thing
    doctor checks, so it is asserted on the address it found, not just on the
    status: a check that blocks for some other reason would otherwise pass.
    """
    provision(generated)
    git("config", "user.email", "stranger@example.com", cwd=generated)
    code, data = doctor_json(generated)
    assert code == 1
    ident = [c for c in data["checks"] if c["check"] == "identity"]
    assert ident and ident[0]["status"] == "BLOCK", data["checks"]
    assert "stranger@example.com" in ident[0]["headline"]

    # and it clears when the address is one the manifest claims
    cfg = yaml.safe_load((generated / "syndicate.yaml").read_text(encoding="utf-8"))
    git("config", "user.email", cfg["members"][0]["email"], cwd=generated)
    _, data = doctor_json(generated)
    ident = [c for c in data["checks"] if c["check"] == "identity"]
    assert ident[0]["status"] == "ok", ident[0]


def test_doctor_calls_an_unmade_decision_a_decision(generated):
    """A fresh syndicate owes several decisions. None of them is a fault.

    signing_since is unset by design - manifest.signing_epoch explains why it
    is refused rather than defaulted - so reporting it as BLOCK on day zero
    would be crying wolf at every adopter. It must still name the tool that
    refuses until the decision is made, or the consequence arrives as a
    surprise in CI instead.
    """
    provision(generated)
    _, data = doctor_json(generated)
    epoch = [c for c in data["checks"] if c["check"] == "signing.epoch"]
    assert epoch and epoch[0]["status"] == "DECIDE", data["checks"]
    assert "verify_signatures" in epoch[0]["detail"], (
        "the decision does not name the tool that will refuse until it is made")


def test_doctor_does_not_restate_a_rule_manifest_owns(generated):
    """A rule stated twice is a rule that will disagree with itself (#38).

    doctor touches every rule in the repository and owns none of them. This
    asserts agreement by behaviour rather than by reading the source: for each
    roster shape, doctor blocks on formation exactly when manifest.formation_ok
    refuses it.
    """
    m = generated / "syndicate.yaml"
    provision(generated)
    original = m.read_text(encoding="utf-8")

    for formation in ("solo", "multi"):
        m.write_text(original.replace("formation: multi", "formation: " + formation),
                     encoding="utf-8")
        cfg = yaml.safe_load(m.read_text(encoding="utf-8"))
        want_ok, _ = manifest_formation_ok(cfg)
        _, data = doctor_json(generated)
        got = [c for c in data["checks"] if c["check"] == "formation"][0]
        assert (got["status"] == "ok") == want_ok, (
            "formation=%s: manifest says ok=%s, doctor says %s"
            % (formation, want_ok, got["status"]))


def test_doctor_blocks_on_a_gate_the_roster_cannot_satisfy(generated):
    """Operator rule #2. The deadlock is discovered at merge, after the work.

    Two members, because at one member the cap floors at 1 rather than 0 -
    Agreement 10.1 needs an approving review to exist, so a solo syndicate's
    tension is resolved by declaring formation, not by lowering the gate. That
    floor is finding #55: it once blessed the single roster that always
    deadlocks. The boundary this asserts only exists from two members up.
    """
    two_members(generated)
    m = generated / "syndicate.yaml"
    n = len(yaml.safe_load(m.read_text(encoding="utf-8"))["members"])
    original = m.read_text(encoding="utf-8")

    # A gate equal to the roster size is the deadlock boundary: it needs n
    # approvals from n members, and GitHub will not let the author be one.
    m.write_text(original.replace('"ledger/**": 1', '"ledger/**": %d' % n), encoding="utf-8")
    code, data = doctor_json(generated)
    gates = [c for c in data["checks"] if c["check"] == "gates"][0]
    assert code == 1 and gates["status"] == "BLOCK", gates
    assert "ledger/**" in gates["detail"] or "ledger/**" in gates["fix"], gates

    # and the gate one below it must not block, or the cap is wrong the other way
    m.write_text(original.replace('"ledger/**": 1', '"ledger/**": %d' % max(n - 1, 1)),
                 encoding="utf-8")
    _, data = doctor_json(generated)
    gates = [c for c in data["checks"] if c["check"] == "gates"][0]
    assert gates["status"] == "ok", "a satisfiable gate was reported as a deadlock: %s" % gates


def test_doctor_warns_before_the_strip_eats_an_audit(generated):
    """The landmine: docs/ is inherited, an audit of this syndicate is not.

    bootstrap.sh offers to delete docs/. If this syndicate's own audit is still
    sitting in it, answering yes destroys the record - and it is the record
    organ the strip list was explicitly amended to protect. The strip list
    strips inheritance, not identity.
    """
    provision(generated)
    (generated / "docs").mkdir(exist_ok=True)
    (generated / "docs" / "AUDIT-001-external.md").write_text("found\n", encoding="utf-8")
    code, data = doctor_json(generated)
    nar = [c for c in data["checks"] if c["check"] == "narrative"][0]
    assert code == 1 and nar["status"] == "BLOCK", nar
    assert "AUDIT-001-external.md" in nar["detail"]
    assert nar["fix"].strip().startswith("git mv "), (
        "the fix must be a git mv - a copy leaves the audit's history behind, "
        "and the history is half of what makes it citable: " + nar["fix"])
    assert "audits/" in nar["fix"], nar["fix"]


# ───────────────────────────── the agent brief ──────────────────────────────

def test_the_agent_brief_tells_an_agent_to_compute_rather_than_narrate(generated):
    """CLAUDE.md is inherited by every fork, and read by an agent that will
    otherwise form its own impression of the manifest and state it confidently.
    Operator rule #8 generalises: to a human reading its output, an agent is a
    check, and a check must never lie."""
    brief = (generated / "CLAUDE.md").read_text(encoding="utf-8")
    assert "doctor.py --json" in brief, (
        "the brief does not point the agent at the tool that computes state")
    for organ in ("ledger/", "agreements/EXECUTION-LOG.md", "audits/"):
        assert organ in brief, "the brief omits the record organ " + organ


def test_the_agent_briefs_exit_codes_match_the_tools(generated):
    """The brief makes a specific, checkable claim about every tool. A stale
    row there is the exact failure the brief spends a section warning about, so
    it is checked rather than trusted.

    A tool's own docstring wins where it documents its codes. Where it does not,
    the brief must claim only 0/1 - and the tool must contain no 2 or 3 exit,
    so that adding one fails here rather than silently outdating the table.
    """
    brief = (generated / "CLAUDE.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\|\s*`(tools/\w+\.py)`\s*\|[^|]*\|([^|]*)\|", brief, re.M)
    assert len(rows) >= 6, "the tool table did not parse: %r" % rows

    for path, codes in rows:
        tool = generated / path
        assert tool.exists(), "the brief names a tool that does not exist: " + path
        claimed = set(re.findall(r"\b([0-3])\b", codes))
        src = tool.read_text(encoding="utf-8")

        # The block is every indented line after the heading, continuations
        # included. A previous version required each line to start with four
        # spaces and a digit, so it stopped at the first wrapped description -
        # it read anchor.py's "0, 1, 2" as "0, 1" and agreed with a brief that
        # was already stale. Row 63: the guard parsed less than it looked like
        # it parsed, and passing meant nothing.
        documented = re.search(r"Exit codes[^\n]*\n((?:[ \t]+\S.*\n)+)", src)
        if documented:
            actual = set(re.findall(r"^[ \t]{4}([0-3])\s", documented.group(1), re.M))
            assert claimed == actual, (
                "%s documents exit codes %s; the brief claims %s"
                % (path, sorted(actual), sorted(claimed)))
            continue

        for code in ("2", "3"):
            has = re.search(r"(?:return|sys\.exit\()\s*" + code + r"\b", src)
            assert (code in claimed) == bool(has), (
                "%s %s an exit %s; the brief %s"
                % (path, "has" if has else "has no", code,
                   "claims it" if code in claimed else "does not claim it"))


def test_every_workflow_pins_one_version_of_an_action(generated):
    """Two ways a pin goes stale that nothing here was watching.

    Dependabot opens a PR against the files that exist when it opens it. A
    workflow added while that PR is still open is never covered by it, and a
    merged PR is not revisited - so the new file keeps the old pin until the
    next release of that action happens to trigger a fresh PR. That is how
    verify-signatures.yml (added in #23) ended up on setup-python v5.6.0 while
    every other workflow had moved to v7.0.0 in #19.

    The second way is structural: Dependabot does not parse `.yml.disabled`, so
    those pins are frozen forever. The suite already insists a disabled
    workflow be pinned to a SHA, on the reasoning that enabling one must not
    silently un-pin you - the same reasoning says enabling one must not
    silently hand you actions from whenever the file was written.

    Limits, stated because a guard that overclaims is worse than none: this is
    offline, so it cannot check a SHA against the upstream tag. It checks that
    the repository agrees with itself - one SHA per action, and one version
    comment per SHA. A comment that lies about its SHA in every file at once
    survives this; a bump that half-lands does not.
    """
    pins = {}            # action -> {sha: [locations]}
    comments = {}        # sha    -> {comment: [locations]}
    for wf in sorted((generated / ".github" / "workflows").iterdir()):
        for i, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r"uses:\s*([\w./-]+)@([0-9a-f]{40})\s*(?:#\s*(\S+))?", line)
            if not m:
                continue
            action, sha, comment = m.group(1), m.group(2), m.group(3) or "(none)"
            where = "%s:%d" % (wf.name, i)
            pins.setdefault(action, {}).setdefault(sha, []).append(where)
            comments.setdefault(sha, {}).setdefault(comment, []).append(where)

    assert pins, "no pinned actions found - the parse is wrong, not the repo"

    split = {a: v for a, v in pins.items() if len(v) > 1}
    assert not split, "an action is pinned to more than one commit:\n" + "\n".join(
        "  %s\n%s" % (action, "\n".join(
            "    %s  <- %s" % (sha[:12], ", ".join(w)) for sha, w in sorted(versions.items())))
        for action, versions in sorted(split.items()))

    disagree = {s: v for s, v in comments.items() if len(v) > 1}
    assert not disagree, "one commit, two version comments:\n" + "\n".join(
        "  %s: %s" % (sha[:12], "; ".join(
            "%s at %s" % (c, ", ".join(w)) for c, w in sorted(versions.items())))
        for sha, versions in sorted(disagree.items()))


def test_the_template_does_not_tell_an_instance_to_import_this_suite(generated):
    """Row 60. The drift checklist is advice an adopter follows literally.

    Measured, not reasoned: copied into a provisioned instance, this suite
    fails 37 of 75. Eight assert mold behaviour and can never pass there. The
    rest fail because every fixture here starts by pretending the tree under
    test still carries the placeholder member row - `provision()` is a no-op in
    a real syndicate, so `two_members()` yields that repo's actual roster while
    the assertions name alpha and beta, and `test_doctor_writes_nothing` dies
    on `git commit` with nothing to commit. No amount of remediation makes
    those green, because they are not about the instance at all.

    Listing the suite as inherited told every adopter to import something
    permanently half red, and a check that is always red teaches its reader to
    ignore CI - operator rule #8 inverted, which is the same failure as a green
    check that lies.

    The exclusion is not the final answer and this guard does not pretend it
    is: the suite conflates tests OF GENERATION, template-only by definition,
    with tests of the machinery's invariants - and one of those, the action-pin
    guard, is exactly what the shakedown needed and did not have. Splitting
    them is the fix. Until then the checklist must not give the bad advice.
    """
    sys.path.insert(0, str(generated / "tools"))
    import importlib
    import drift_check
    importlib.reload(drift_check)

    for path in ("tests/test_generation_smoke.py", "tests/requirements.txt",
                 ".github/workflows/smoke.yml"):
        assert not drift_check.inherited(path), (
            "the drift checklist tells an instance to import %s, which cannot "
            "run green there" % path)

    # and the exclusion must not have swallowed the machinery, which is the
    # whole point of a drift checklist existing
    for path in ("tools/doctor.py", "tools/manifest.py", "bootstrap.sh",
                 ".github/workflows/anchor.yml", "audits/README.md"):
        assert drift_check.inherited(path), (
            "%s stopped being inherited; the exclusion over-reached" % path)


def _ots_shim(tmp_path, body):
    """A fake `ots` earlier on PATH than any real one. Keeps the suite offline."""
    d = tmp_path / "shimbin"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "ots"
    p.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    p.chmod(0o755)
    return d


def _run_anchor(repo, env_path, *args):
    env = dict(os.environ, PATH=str(env_path) + os.pathsep + os.environ["PATH"])
    r = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), *args, "--repo", str(repo)],
                       text=True, capture_output=True, env=env)
    return r.returncode, r.stdout + r.stderr


def test_an_unreachable_calendar_is_not_a_pending_anchor(generated, tmp_path):
    """Row 62, and the one that matters most of these.

    Measured on the live shakedown chain before it was fixed: all four
    OpenTimestamps calendars refused (`Tunnel connection failed: 403`), `ots`
    exited 1 - and anchor.py printed "pending #0010 - not yet in a Bitcoin
    block" and exited 0. The return code was discarded, so a network failure
    was reported as a statement about Bitcoin.

    That is a green run meaning "I could not look", in the tool the entire
    priority claim rests on. A member on bad wifi would see "pending" forever
    and never learn the chain had stopped advancing - and for a solo syndicate
    the chain is the only external witness there is.

    The fixture reproduces the exact strings that failure produced.
    """
    provision(generated)
    log = generated / "ledger" / "anchors"
    log.mkdir(parents=True, exist_ok=True)
    (log / "0001-x.json").write_text('{"a":1}', encoding="utf-8")
    (log / "0001-x.json.ots").write_text("stub", encoding="utf-8")
    (log / "log.jsonl").write_text(json.dumps({
        "seq": 1, "anchor_id": "0001-x", "manifest": "ledger/anchors/0001-x.json",
        "manifest_sha256": "0" * 64, "status": "pending",
        "created": "2099-01-01T00:00:00Z"}) + "\n", encoding="utf-8")

    unreachable = _ots_shim(tmp_path, (
        'if [ "$1" = "upgrade" ]; then\n'
        '  echo "Calendar https://alice.btc.calendar.opentimestamps.org: '
        'Tunnel connection failed: 403 Forbidden" >&2\n'
        '  echo "Failed! Timestamp not complete" >&2\n'
        '  exit 1\n'
        'fi\n'
        'exit 0'))
    code, out = _run_anchor(generated, unreachable, "upgrade")
    assert code == 2, (
        "a network failure exited %d; 0 would be a green run meaning 'I could "
        "not look', 1 would send a human to fix a chain that is fine:\n%s" % (code, out))
    assert "could not reach" in out, out
    assert "not yet in a Bitcoin block" not in out, (
        "it still claims Bitcoin has not confirmed an anchor nobody asked about:\n" + out)

    # and the honest pending case must stay exit 0, or the fix has just
    # converted every unconfirmed anchor into a transient error
    reachable = _ots_shim(tmp_path / "ok", 'exit 0')
    code, out = _run_anchor(generated, reachable, "upgrade")
    assert code == 0, "a reachable calendar with nothing new is not an error:\n" + out
    assert "not yet in a Bitcoin block" in out, out


def test_upgrade_without_the_ots_cli_does_not_report_success(generated, tmp_path):
    """Same failure, second door. With no `ots` on PATH the tool printed its
    'stamps deferred' line and exited 0 - and a workflow reads the exit code,
    not the line. Nothing was checked, so the honest answer is transient."""
    provision(generated)
    log = generated / "ledger" / "anchors"
    log.mkdir(parents=True, exist_ok=True)
    (log / "log.jsonl").write_text(json.dumps({
        "seq": 1, "anchor_id": "0001-x", "manifest": "ledger/anchors/0001-x.json",
        "manifest_sha256": "0" * 64, "status": "pending",
        "created": "2099-01-01T00:00:00Z"}) + "\n", encoding="utf-8")

    empty = tmp_path / "nobin"
    empty.mkdir(exist_ok=True)
    env = {"PATH": str(empty), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    r = subprocess.run([sys.executable, str(TOOLS / "anchor.py"), "upgrade",
                        "--repo", str(generated)], text=True, capture_output=True, env=env)
    assert r.returncode == 2, (
        "with no ots installed nothing was checked, and it exited %d:\n%s"
        % (r.returncode, r.stdout + r.stderr))
