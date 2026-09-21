#!/usr/bin/env python3
"""Continuous priority anchoring for the syndicate vault (v2, CLI-based).

In a no-custody protocol, provable priority IS the enforcement layer
(Agreement section 7.4). Each run writes a canonical-JSON manifest of git
HEAD, tree hash, and sha256 of every ledger file; appends an entry to
ledger/anchors/log.jsonl (an append-only hash chain over entry cores);
and submits the manifest to OpenTimestamps calendars through the
official ots command-line client.

v2 replaced the python-opentimestamps library API with the ots CLI
after release 0.4.5 broke imports and serialization silently. Status
flow: unsubmitted -> (ots stamp) -> pending -> (ots upgrade + Bitcoin
attestation) -> confirmed.

The ots info output is the machine interface: the File sha256 hash line
proves which bytes a stamp covers; a BitcoinBlockHeaderAttestation line
marks Bitcoin confirmation. verify works on a bare file export (no git,
no Bitcoin node); the ots CLI is needed only for .ots digest checks.

Commands: run, upgrade, verify, milestone --tag T --message M.

Exit codes:
    0  done - every anchor's state was established
    1  needs a human: an anchor unsubmitted past the stale window, or a broken
       chain on `verify`
    2  transient: the OpenTimestamps calendars could not be reached, so some
       anchors' state is unknown. NOT the same as unconfirmed, which is a
       statement about Bitcoin rather than about the network.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STALE_DAYS = 14
PLACEHOLDER_HANDLE = "github-handle"


def is_unprovisioned_template(repo) -> bool:
    """True only when the manifest still carries the template's placeholder row.

    A template is the mold, not a syndicate (operator rule #10), and anchoring
    is a syndicate act: a chain in the mold is inherited by every repo generated
    from it, whose own first anchor then chains to a manifest describing someone
    else's tree. This was reverted once and recreated by a single dispatch 43
    minutes later, so the refusal belongs in the tool rather than in discipline.

    `oracle_ref: "template"` is NOT the marker - generated repos carry it too,
    and gating on it would stop real syndicates from anchoring. Fails open: only
    a positive placeholder sighting refuses, because wrongly blocking a live
    syndicate's priority proof is worse than wrongly allowing a mold's.
    """
    manifest = repo / "syndicate.yaml"
    try:
        import yaml
        cfg = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        members = cfg.get("members") or []
        return any(m.get("github") == PLACEHOLDER_HANDLE for m in members if isinstance(m, dict))
    except Exception:
        return False
CORE_FIELDS = ["seq", "anchor_id", "git_head", "git_tree", "manifest", "manifest_sha256", "prev", "created"]


def sh(*args, cwd):
    r = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if r.returncode != 0:
        sys.exit("ERROR: git command failed: " + r.stderr.strip())
    return r.stdout.strip()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def core_hash(entry):
    return sha256_bytes(canonical({k: entry[k] for k in CORE_FIELDS}).encode())


def load_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(ln) for ln in log_path.read_text().splitlines() if ln.strip()]


def rewrite_log(log_path, entries):
    log_path.write_text("".join(canonical(e) + "\n" for e in entries))


def repo_state(repo):
    head = sh("git", "rev-parse", "HEAD", cwd=repo)
    tree = sh("git", "rev-parse", "HEAD^{tree}", cwd=repo)
    ledger = []
    for p in sorted((repo / "ledger").rglob("*")):
        if p.is_file() and "anchors" not in p.relative_to(repo).parts:
            ledger.append({"path": p.relative_to(repo).as_posix(), "sha256": sha256_file(p)})
    return {"git_head": head, "git_tree": tree, "ledger_files": ledger}


def make_anchor(repo, anchors_dir, log_path):
    entries = load_log(log_path)
    state = repo_state(repo)
    head = state["git_head"]
    if any(e["git_head"] == head for e in entries):
        last = max(e["seq"] for e in entries if e["git_head"] == head)
        print("skip: HEAD " + head[:12] + " already anchored #" + format(last, "04d"))
        return None
    prev = entries[-1] if entries else None
    seq = (prev["seq"] + 1) if prev else 1
    anchor_id = format(seq, "04d") + "-" + datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state["anchor_id"] = anchor_id
    manifest_path = anchors_dir / (anchor_id + ".json")
    manifest_path.write_bytes(canonical(state).encode())
    entry = {
        "seq": seq,
        "anchor_id": anchor_id,
        "git_head": head,
        "git_tree": state["git_tree"],
        "manifest": "ledger/anchors/" + anchor_id + ".json",
        "manifest_sha256": sha256_file(manifest_path),
        "prev": core_hash(prev) if prev else None,
        "status": "unsubmitted",
        "created": now(),
    }
    with log_path.open("a") as f:
        f.write(canonical(entry) + "\n")
    print("anchor #" + format(seq, "04d") + " " + anchor_id + ": head " + head[:12] + ", " + str(len(state["ledger_files"])) + " ledger files")
    return entry


def ots_cli():
    path = shutil.which("ots")
    if path is None:
        print("ots CLI not found (pip install opentimestamps-client); entries recorded, stamps deferred")
    return path


BROKEN_INSTALL = "ots-broken-install"


def run_ots(*args):
    """Run ots, and distinguish the three ways it can let you down.

    shutil.which() answers "is there a file here", and exec answers "can it
    run". They disagree more often than they look like they would: a pipx or
    uv tool install whose interpreter was upgraded out from under it leaves a
    shim which() finds happily and exec refuses with FileNotFoundError - for
    the shim itself, not for ots. This function used to catch only
    TimeoutExpired, so that case reached the operator as a raw traceback
    (row 73), where every other tool in this repository names its reason.

    It also matters WHICH failure it is: a broken install is a human's job
    (reinstall), not a transient the caller should retry when the network is
    back. Returning them as the same thing sends someone to wait for weather
    that was never the problem.

    (The distinction is lifted from Panniantong/Agent-Reach's probe.py, which
    names missing / broken / timeout as three modes that shutil.which()
    flattens into one.)
    """
    try:
        return subprocess.run(["ots", *args], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="ots timed out")
    except OSError as e:
        # FileNotFoundError: dead shebang or vanished between which() and exec.
        # PermissionError: present, found, and not executable.
        return subprocess.CompletedProcess(
            args=[], returncode=1, stdout="",
            stderr=BROKEN_INSTALL + ": ots is on PATH but will not execute (%s). "
                   "Reinstall it - `pip install --force-reinstall "
                   "opentimestamps-client` - this is not a network problem and "
                   "retrying will not help." % e.__class__.__name__)


# A calendar we could not talk to is not a calendar that told us "not yet".
# ots logs one line per calendar it tried; a connection failure looks like
#   Calendar https://alice.btc.calendar.opentimestamps.org: Tunnel connection failed: 403 Forbidden
# Read as an allowlist of known-good statuses rather than a denylist of
# failures, deliberately: an unrecognised status becomes "could not look",
# which is the safe direction. Claiming "not yet confirmed" about a calendar
# that never answered is the failure this whole function exists to stop.
CALENDAR_LINE = re.compile(r"^Calendar\s+(\S+):\s*(.+)$", re.M)
CALENDAR_OK = ("pending", "attestation", "complete", "success")


def calendars_answered(r):
    """(answered, first_problem). False when no calendar gave us a real answer."""
    if r is None:
        return False, "ots was never run"
    text = ((r.stderr or "") + "\n" + (r.stdout or ""))
    problems = [(u, t.strip()) for u, t in CALENDAR_LINE.findall(text)
                if not any(k in t.lower() for k in CALENDAR_OK)]
    if problems:
        return False, "%s: %s" % problems[0]
    if r.returncode != 0 and not CALENDAR_LINE.search(text):
        # ots failed and said nothing about any calendar - we cannot claim we
        # looked. "Failed! Timestamp not complete" alone does not distinguish
        # "the block has not happened yet" from "the network was not there".
        tail = [l for l in text.strip().splitlines() if l.strip()]
        return False, (tail[-1] if tail else "ots exited %d with no output" % r.returncode)
    return True, ""


def parse_info(text):
    out = {"digest": None, "confirmed": False, "height": None}
    if not text:
        return out
    m = re.search(r"File sha256 hash:\s*([0-9a-f]+)", text)
    if m:
        out["digest"] = m.group(1)
    heights = [int(h) for h in re.findall(r"BitcoinBlockHeaderAttestation\((\d+)\)", text)]
    if heights:
        out["confirmed"] = True
        # earliest attesting block is the strongest priority claim
        out["height"] = min(heights)
    return out


def info_for(ots_path):
    r = run_ots("info", str(ots_path))
    if r.returncode != 0:
        return None
    return r.stdout + r.stderr


def ensure_stamps(repo, log_path):
    """Returns the number of anchors whose state could not be established.

    Not the number that are unconfirmed - the number nobody managed to ask
    about. Those are two different facts and this function used to print the
    first when it meant the second.
    """
    if not ots_cli():
        # The message is printed above, but a message is not an exit code, and
        # a workflow reads the exit code. Every still-unconfirmed anchor here
        # is one we did not check.
        return len([e for e in load_log(log_path) if e["status"] != "confirmed"])
    entries = load_log(log_path)
    changed = False
    unchecked = 0
    broken = []
    for e in entries:
        manifest = repo / e["manifest"]
        ots = Path(str(manifest) + ".ots")
        if not manifest.exists():
            print("error #" + format(e["seq"], "04d") + ": manifest file missing")
            continue
        if not ots.exists():
            r = run_ots("stamp", str(manifest))
            if ots.exists():
                e["status"] = "pending"
                changed = True
                info = parse_info(info_for(ots))
                print("submitted #" + format(e["seq"], "04d") + " (digest " + (info["digest"] or "?")[:12] + ")")
            else:
                tail = (r.stderr or r.stdout or "").strip().splitlines()
                print("stamp failed #" + format(e["seq"], "04d") + ": " + (tail[-1] if tail else "unknown"))
        elif e["status"] != "confirmed":
            r = run_ots("upgrade", str(ots))
            answered, problem = calendars_answered(r)
            info = parse_info(info_for(ots))
            if e["status"] == "unsubmitted":
                e["status"] = "pending"
                changed = True
            if info["digest"] and info["digest"] != e["manifest_sha256"]:
                print("error #" + format(e["seq"], "04d") + ": .ots covers different bytes than the log claims")
            if info["confirmed"]:
                e["status"] = "confirmed"
                e["confirmed_at"] = now()
                if info["height"]:
                    e["height"] = info["height"]
                changed = True
                print("confirmed #" + format(e["seq"], "04d") + " in Bitcoin (block " + str(info["height"] or "?") + ")")
            elif BROKEN_INSTALL in (r.stderr or ""):
                # Not transient. Nobody should be told to try again later.
                broken.append(format(e["seq"], "04d"))
            elif not answered:
                unchecked += 1
                print("unknown #" + format(e["seq"], "04d") + " - could not reach the "
                      "calendars, so nothing was checked (" + problem + "). This is "
                      "NOT 'not yet confirmed': that would be a claim about Bitcoin, "
                      "and no one answered.")
            else:
                print("pending #" + format(e["seq"], "04d") + " - not yet in a Bitcoin block")
    if changed:
        rewrite_log(log_path, entries)
    if broken:
        print("ots is installed but will not run, so anchors " + ", ".join(broken)
              + " were not checked. Reinstall opentimestamps-client; this is "
              "not a network problem.")
        return -1      # needs a human, not a retry
    return unchecked


def stale_unsubmitted(log_path):
    bad = []
    for e in load_log(log_path):
        if e["status"] == "unsubmitted":
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(e["created"].replace("Z", "+00:00"))).days
            if age > STALE_DAYS:
                bad.append(e["seq"])
    return bad


def milestone(repo, anchors_dir, log_path, tag, message):
    entries = load_log(log_path)
    head = sh("git", "rev-parse", "HEAD", cwd=repo)
    entry = None
    for e in entries:
        if e["git_head"] == head:
            entry = e
    if entry:
        print("skip: HEAD already anchored #" + format(entry["seq"], "04d") + " - tagging existing anchor")
    else:
        entry = make_anchor(repo, anchors_dir, log_path)
        if entry is None:
            sys.exit("error: could not anchor HEAD")
    tag_msg = "milestone: " + message + "\nanchor: " + entry["anchor_id"] + "\nmanifest_sha256: " + entry["manifest_sha256"] + "\ngit_head: " + entry["git_head"]
    sh("git", "tag", "-a", tag, "-m", tag_msg, head, cwd=repo)
    print("tag " + tag + " -> " + head[:12] + " (anchor #" + format(entry["seq"], "04d") + ")")


def verify(repo, log_path):
    entries = load_log(log_path)
    if not entries:
        print("no anchors yet")
        return True
    ok = True
    prev_hash = None
    cli = ots_cli()
    for e in entries:
        if e.get("prev") != prev_hash:
            print("error #" + format(e["seq"], "04d") + ": chain broken (prev mismatch)")
            ok = False
        prev_hash = core_hash(e)
        m = repo / e["manifest"]
        if not m.exists():
            print("error #" + format(e["seq"], "04d") + ": manifest missing")
            ok = False
            continue
        if sha256_file(m) != e["manifest_sha256"]:
            print("error #" + format(e["seq"], "04d") + ": manifest digest mismatch - tampered?")
            ok = False
        ots = Path(str(m) + ".ots")
        if e["status"] != "unsubmitted" and not ots.exists():
            print("error #" + format(e["seq"], "04d") + ": status " + e["status"] + " but no .ots file")
            ok = False
        if ots.exists():
            if cli:
                info = parse_info(info_for(ots))
                if info["digest"] and info["digest"] != e["manifest_sha256"]:
                    print("error #" + format(e["seq"], "04d") + ": .ots covers different bytes than the log claims")
                    ok = False
                if info["confirmed"]:
                    print("  #" + format(e["seq"], "04d") + " attested at Bitcoin block " + str(info["height"] or "?"))
            else:
                print("  #" + format(e["seq"], "04d") + ": .ots present (ots CLI absent - digest check skipped)")
    n_conf = 0
    for e in entries:
        if e["status"] == "confirmed":
            n_conf += 1
    print(str(len(entries)) + " anchor(s), " + str(n_conf) + " Bitcoin-confirmed - " + ("OK" if ok else "FAILURES PRESENT"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="Continuous priority anchoring for the syndicate vault (ots CLI).")
    ap.add_argument("command", choices=["run", "upgrade", "verify", "milestone"])
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--tag", help="tag name for milestone (e.g. v0.1-preprint)")
    ap.add_argument("--message", "-m", help="milestone description")
    args = ap.parse_args()
    repo = args.repo.resolve()
    anchors_dir = repo / "ledger" / "anchors"
    anchors_dir.mkdir(parents=True, exist_ok=True)
    log_path = anchors_dir / "log.jsonl"
    if args.command in ("run", "milestone") and is_unprovisioned_template(repo):
        sys.exit(
            "refusing to anchor: syndicate.yaml still carries the template's\n"
            "placeholder member row, so this repository is a mold, not a\n"
            "syndicate. Anchoring here writes a chain that every generated repo\n"
            "inherits (operator rule #10). Edit the manifest with real members\n"
            "first; the workflow itself is already proven by its run history.")
    unchecked = 0
    if args.command == "run":
        make_anchor(repo, anchors_dir, log_path)
        unchecked = ensure_stamps(repo, log_path)
    elif args.command == "upgrade":
        unchecked = ensure_stamps(repo, log_path)
    elif args.command == "milestone":
        if not (args.tag and args.message):
            sys.exit("milestone requires --tag and --message")
        milestone(repo, anchors_dir, log_path, args.tag, args.message)
        unchecked = ensure_stamps(repo, log_path)
    elif args.command == "verify":
        return 0 if verify(repo, log_path) else 1
    stale = stale_unsubmitted(log_path)
    if stale:
        print("error: anchors " + str(stale) + " unsubmitted for more than " + str(STALE_DAYS) + " days")
        return 1
    if unchecked < 0:
        return 1       # broken toolchain: a human has to fix the install
    if unchecked:
        # Transient, not a failure to route to a human: the calendars were not
        # reachable, so this run establishes nothing about those anchors. Exit
        # 0 here would be a green run meaning "I could not look" - operator
        # rule #8 - in the tool the whole priority claim rests on.
        print(str(unchecked) + " anchor(s) could not be checked at all. Run this "
              "again when the network is back; nothing is wrong with the chain.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
