#!/usr/bin/env python3
"""Guards whose premise is a fact about the outside world, and its date.

ROW 61, AND WHAT THIS IS NOT

  A guard is a claim about the world, and the world moves. The pq-verify pin
  was guarded at >= 3.12 because that package declared >=3.8 while its source
  only parsed from 3.12. True when measured. Then upstream fixed it, and the
  guard went on passing while enforcing a real constraint for a reason that
  had stopped existing - its docstring asserting a disproven fact to anyone
  who read it. Nothing here re-checks a premise, so nothing would ever have
  said so; it surfaced because the package's author happened to mention it.

  This is NOT a detector. A premise like "this upstream package is broken on
  3.11" cannot be re-tested offline, and a test that fails on a calendar date
  is a time bomb that goes red in CI with no code change - which teaches its
  reader to ignore CI, the failure this repository keeps naming.

  What it is: the list, complete and dated, with the exact command that
  re-checks each one. A machine cannot tell you the world moved. It can
  refuse to let a world-dependent guard exist without saying what it depends
  on, when that was last true, and how you would find out.

  ADD A ROW when a guard's justification is a fact you measured about
  something you do not control. Do not add one for a guard about this
  repository's own contents - that is not a premise, it is an invariant, and
  it belongs in tests/test_invariants.py where it can simply be checked.
"""

PREMISES = [
    dict(
        guard="test_every_workflow_runs_the_same_python",
        premise="pq-verify's package parses on the Python this repo pins. "
                "2.6.7 declared >=3.8 and did not parse below 3.12 (PEP 701); "
                "2.8.0 declares >=3.9 and parses on 3.9.",
        measured="2026-09-20",
        recheck="pip download pq-verify --no-deps -d /tmp/pq && "
                "python -c \"import ast,zipfile,glob;[ast.parse(zipfile.ZipFile(z)"
                ".read(n),feature_version=(3,9)) for z in glob.glob('/tmp/pq/*.whl') "
                "for n in zipfile.ZipFile(z).namelist() if n.endswith('.py')]\"",
        expires_if="pq-verify changes its requires-python or its source syntax",
    ),
    dict(
        guard="test_no_tool_exits_zero_when_its_source_failed",
        premise="arXiv answers GitHub Actions' Azure egress with HTTP 406 "
                "(ledger row 51). The fault matrix models 406 because this is "
                "the refusal actually observed, not a hypothetical.",
        measured="2026-09-17",
        recheck="dispatch .github/workflows/ingest-arxiv.yml and read the "
                "status code in the log",
        expires_if="arXiv changes its egress policy, or the runner's egress "
                   "moves off Azure",
    ),
    dict(
        guard="test_an_unreachable_calendar_is_not_a_pending_anchor",
        premise="`ots upgrade` prints one 'Calendar <url>: <error>' line per "
                "calendar it could not reach, and exits non-zero. The fixture "
                "reproduces that exact string shape.",
        measured="2026-09-20",
        recheck="ots upgrade on a pending .ots with the network blocked; "
                "compare the output shape to CALENDAR_LINE in tests/faultkit.py",
        expires_if="opentimestamps-client changes its per-calendar log format",
    ),
    dict(
        guard="test_every_action_is_pinned_to_a_commit",
        premise="a git tag is mutable and its owner can move what a pinned "
                "action executes; a commit SHA cannot be moved.",
        measured="2026-09-20",
        recheck="none needed - this is a property of git, not of a vendor. "
                "Listed because the guard's WORDING cites GitHub Actions "
                "behaviour, and that part is a vendor fact.",
        expires_if="GitHub makes action tags immutable",
    ),
]

REQUIRED = ("guard", "premise", "measured", "recheck", "expires_if")
