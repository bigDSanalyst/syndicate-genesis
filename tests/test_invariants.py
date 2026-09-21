#!/usr/bin/env python3
"""Invariants of a syndicate repository — portable, and meant to travel.

    pytest tests/test_invariants.py -q

WHY THIS FILE IS SEPARATE FROM THE GENERATION SUITE (row 60)

  tests/test_generation_smoke.py answers "can a syndicate be generated from
  this template, and does every tool run against what generation produced?"
  Every fixture in it starts by pretending the tree under test still carries
  the placeholder member row, because that is what it is testing. Copied
  into a provisioned instance it fails 37 of 75 - eight assert mold behaviour
  and can never pass there, and the rest sit on fixtures that are no-ops in a
  real syndicate. So `tests/` is excluded from the inherited set.

  That exclusion threw something real away. `test_every_action_is_pinned_to_a
  _commit` lived in that file, and syndicate-shakedown ran eight actions on
  mutable tags - with a write-scoped PAT - for weeks. The guard existed. It
  was in the one file the drift checklist had to stop recommending.

  This file is the other half: assertions about the repository they are run
  in, whatever that repository is. No `generated` fixture, no provisioning,
  no placeholder assumptions - just `repo`, which is the tree this file sits
  in. It passes in the mold and in every syndicate generated from it, and it
  is marked inherited so instances actually receive it.

  THE TEST FOR WHETHER SOMETHING BELONGS HERE: would it still be true, and
  still worth asserting, in a two-year-old syndicate with forty members and
  nothing of the template's narrative left? If the answer needs a mold, it
  belongs in the generation suite.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"


@pytest.fixture
def repo():
    """The repository this file is in. The whole point: no copy, no
    provisioning, no assumption about whether it is a mold or a syndicate."""
    return REPO


def _strict_load(path: Path):
    """YAML that refuses duplicate keys - a silently-dropped workflow key is
    how a job loses its permissions block without anyone noticing."""
    class Strict(yaml.SafeLoader):
        pass

    def no_dupes(loader, node, deep=False):
        seen, out = set(), {}
        for k, v in node.value:
            key = loader.construct_object(k, deep=deep)
            if key in seen:
                raise AssertionError("duplicate key %r in %s" % (key, path))
            seen.add(key)
            out[key] = loader.construct_object(v, deep=deep)
        return out

    Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_dupes)
    return yaml.load(path.read_text(encoding="utf-8"), Strict)


def test_bot_exclusion_patterns_match_real_bots(repo):
    """Finding #33. The manifest's exclusion regexes must match bots that run."""
    import re
    cfg = yaml.safe_load((repo / "syndicate.yaml").read_text(encoding="utf-8"))
    pats = [re.compile(p) for p in cfg["attribution"]["exclude_authors_matching"]]

    def excluded(s):
        return any(p.search(s) for p in pats)

    for bot in ("syndicate-anchor[bot]", "syndicate-ingest[bot]",
                "dependabot[bot]", "github-actions[bot]",
                "anchor-bot@users.noreply.github.com"):
        assert excluded(bot), bot + " is not excluded - attribution firewall inert"
    assert not excluded("1+founder@users.noreply.github.com")


def test_arxiv_queries_carry_no_inline_comments(repo):
    """Finding #13. A # inside the quotes is sent to arXiv as search text."""
    cfg = yaml.safe_load((repo / "agents" / "queries.yaml").read_text(encoding="utf-8"))
    for q in cfg["arxiv_subscriptions"]:
        assert "#" not in q, "query carries comment text into the search: " + q


def test_template_ships_the_audits_drawer(repo):
    """An empty convention is a convention nobody follows."""
    readme = repo / "audits" / "README.md"
    assert readme.exists(), "template ships no audits/ drawer"
    assert "strips inheritance, not identity" in readme.read_text(encoding="utf-8")


def test_every_action_is_pinned_to_a_commit(repo):
    """A tag is mutable: whoever controls it can move what runs in CI, with the
    repo's write token. Disabled workflows are checked too - enabling one must
    not silently un-pin you."""
    unpinned = []
    for wf in sorted((repo / ".github" / "workflows").iterdir()):
        for i, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r"uses:\s*([\w./-]+)@(\S+)", line)
            if m and not re.fullmatch(r"[0-9a-f]{40}", m.group(2)):
                unpinned.append("%s:%d %s@%s" % (wf.name, i, *m.groups()))
    assert not unpinned, "actions pinned to mutable refs: " + "; ".join(unpinned)


def test_ots_verify_job_reads_and_never_writes(repo):
    """The chain is solo formation's compensating control, so something has to
    prove the stored receipts still verify. Failure is a finding, not a repair:
    a broken chain means tampered bytes or a lost manifest, and neither is fixed
    by a bot commit - so the job is given no permission to make one."""
    wf = repo / ".github" / "workflows" / "ots-verify.yml"
    assert wf.exists(), "no ots-verify workflow"
    cfg = _strict_load(wf)
    assert cfg["permissions"] == {"contents": "read"}, \
        "the verify job can write: " + str(cfg["permissions"])
    body = wf.read_text(encoding="utf-8")
    assert "anchor.py verify" in body
    assert "--exclude=.git" in body, "verifies the checkout, not the bare export"
    for writer in ("git commit", "git push", "github.token", "secrets."):
        assert writer not in body, "verify job touches " + writer


def test_every_workflow_runs_the_same_python(repo):
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
    for wf in sorted((repo / ".github" / "workflows").iterdir()):
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


def test_the_agent_brief_tells_an_agent_to_compute_rather_than_narrate(repo):
    """CLAUDE.md is inherited by every fork, and read by an agent that will
    otherwise form its own impression of the manifest and state it confidently.
    Operator rule #8 generalises: to a human reading its output, an agent is a
    check, and a check must never lie."""
    brief = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "doctor.py --json" in brief, (
        "the brief does not point the agent at the tool that computes state")
    for organ in ("ledger/", "agreements/EXECUTION-LOG.md", "audits/"):
        assert organ in brief, "the brief omits the record organ " + organ


def test_the_agent_briefs_exit_codes_match_the_tools(repo):
    """The brief makes a specific, checkable claim about every tool. A stale
    row there is the exact failure the brief spends a section warning about, so
    it is checked rather than trusted.

    A tool's own docstring wins where it documents its codes. Where it does not,
    the brief must claim only 0/1 - and the tool must contain no 2 or 3 exit,
    so that adding one fails here rather than silently outdating the table.
    """
    brief = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\|\s*`(tools/\w+\.py)`\s*\|[^|]*\|([^|]*)\|", brief, re.M)
    assert len(rows) >= 6, "the tool table did not parse: %r" % rows

    for path, codes in rows:
        tool = repo / path
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


def test_every_workflow_pins_one_version_of_an_action(repo):
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
    for wf in sorted((repo / ".github" / "workflows").iterdir()):
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


_THIS = "test_these_invariants_do_not_smuggle_in_a_mold_assumption"


def test_these_invariants_do_not_smuggle_in_a_mold_assumption(repo):
    """The file's own admission ticket, enforced.

    Row 60's split is only worth having if this half genuinely travels. The
    failure mode is quiet: someone adds a test here that happens to pass in
    the template because the template still has a placeholder row, and every
    instance that inherits it goes red - which is the permanently-red check
    the split exists to prevent, arriving through the door marked "portable".

    So the markers of a mold assumption are barred outright. A test that
    needs any of them is a generation test and belongs in the other file.
    """
    src = Path(__file__).read_text(encoding="utf-8")
    # Everything between the fixture and this test's own definition. Its own
    # body is excluded because it necessarily NAMES every marker it bars -
    # a scanner that matches its own pattern list is a guard that can only
    # fail, which is no more useful than one that can only pass.
    body = src[src.index("@pytest.fixture"):src.index("def " + _THIS)]
    # A scanner that scans nothing passes every time. Same sentinel the fault
    # matrix and the python-version guard carry, and it is not paranoia: this
    # exact mutation (body = "") survived the first mutation pass.
    assert "def test_every_action_is_pinned_to_a_commit(" in body, (
        "the scanned region does not contain the tests it is supposed to be "
        "scanning - this guard is passing vacuously")
    for marker in ("github-handle", "provision(", "two_members(",
                   "is_unprovisioned", "RECORD-AT-ACTIVATION",
                   "signing_repo(", "shutil.copytree"):
        assert marker not in body, (
            "%r appears in the invariants file. That is a mold assumption, "
            "and an instance inheriting it goes red forever - row 60's "
            "failure arriving through the door marked 'portable'." % marker)
