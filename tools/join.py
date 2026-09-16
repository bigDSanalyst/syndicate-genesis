#!/usr/bin/env python3
"""Join a syndicate from this template: one command, one PR.

Looks up your noreply email from the public GitHub API (no secrets),
fetches, branches member/<handle>, inserts your manifest row, commits,
pushes, and opens the PR. The assertion stays yours (your credentials,
your email, self-confirmed by the lookup); the ceremony is compressed.

Usage:  python tools/join.py --handle <github-username> --name "Full Name" \
             [--role systems] [--repo /path/to/clone] [--token $GH_TOKEN]

After the PR merges, set your LOCAL git email to the printed address or
commits will not attribute (finding #17):  git config user.email <addr>
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

API = 'https://api.github.com'


def sh(*args, cwd=None):
    """Run git as an argv list - never a shell string. A handle or name is
    untrusted input; shell=True made it executable."""
    r = subprocess.run(args, text=True, capture_output=True, cwd=cwd)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()[:300]
        sys.exit('ERROR: ' + redact(msg))
    return redact(r.stdout.strip())


def redact(text):
    """git echoes the remote URL on failure; never let a PAT reach the terminal."""
    return re.sub(r"https://[^@/\s]+@", "https://***@", text)


def main():
    ap = argparse.ArgumentParser(description='Join a syndicate: one command, one PR.')
    ap.add_argument('--handle', required=True)
    ap.add_argument('--name', required=True)    # displayed name; identity binding is handle+email, names are cosmetic
    ap.add_argument('--role', default='contributor')
    ap.add_argument('--tier', default='standard', choices=['verified', 'standard', 'provisional'])
    ap.add_argument('--repo', type=Path, default=Path('.'))
    ap.add_argument('--token', default=None, help='PAT with repo scope; else git credentials must already work')
    args = ap.parse_args()
    repo = args.repo.resolve()

    req = urllib.request.Request(API + '/users/' + args.handle, headers={'User-Agent': 'syndicate-join/1.0'})
    try:
        user = json.load(urllib.request.urlopen(req, timeout=20))
    except Exception as e:
        sys.exit('ERROR: could not look up ' + args.handle + ' — ' + str(e)[:120])
    email = str(user['id']) + '+' + user['login'] + '@users.noreply.github.com'
    print('identity: ' + user['login'] + ' -> ' + email)

    sh('git', '-C', '.', 'fetch', 'origin', cwd=repo)
    branch = 'member/' + args.handle
    sh('git', '-C', '.', 'checkout', '-B', branch, 'origin/main', cwd=repo)

    manifest = repo / 'syndicate.yaml'
    txt = manifest.read_text(encoding='utf-8')
    if email in txt:
        print('already a member — nothing to do')
        return 0
    today = date.today().isoformat()
    row = [
        '  - name: ' + json.dumps(args.name),
        '    github: ' + json.dumps(args.handle),
        '    orcid: "0000-0000-0000-0000"    # optional: edit after merge if you have one',
        '    email: ' + json.dumps(email),
        '    role: ' + json.dumps(args.role),
        '    trust_tier: ' + args.tier,
        '    joined: ' + json.dumps(today),
    ]
    # Match the 'members:' key itself, never its trailing comment: comment text
    # drifts between template versions and an exact-string anchor bricks the tool.
    m = re.search(r'^members:.*$', txt, re.MULTILINE)
    if not m:
        sys.exit('ERROR: no top-level members: key in syndicate.yaml — file changed shape?')
    txt = txt[:m.end()] + '\n' + '\n'.join(row) + txt[m.end():]
    manifest.write_text(txt, encoding='utf-8')
    import yaml    # validate before committing: a broken manifest blocks the whole syndicate (finding #1)
    cfg = yaml.safe_load(txt)
    assert any(m.get('email') == email for m in cfg['members']), 'row not parseable — aborting'
    print('manifest row inserted and parses cleanly')

    remote = sh('git', '-C', '.', 'remote', 'get-url', 'origin', cwd=repo)
    owner_path = remote.split('github.com/')[-1]
    sh('git', '-C', '.', 'add', 'syndicate.yaml', cwd=repo)
    sh('git', '-C', '.', '-c', 'user.name=' + args.handle, '-c', 'user.email=' + email,
       'commit', '-m', 'manifest: add member ' + args.handle, cwd=repo)
    if args.token:
        # Push to a one-shot authenticated URL. Never `remote set-url` - that
        # writes the PAT into .git/config in plaintext, where it persists long
        # after this script exits (SECURITY.md threat #2).
        push_url = 'https://' + args.token + '@github.com/' + owner_path
        sh('git', '-C', '.', 'push', '-u', push_url, branch, cwd=repo)
        sh('git', '-C', '.', 'branch', '--set-upstream-to=origin/' + branch, branch, cwd=repo)
    else:
        sh('git', '-C', '.', 'push', '-u', 'origin', branch, cwd=repo)
    owner_repo = owner_path.removesuffix('.git')
    pr_url = 'https://github.com/' + owner_repo + '/compare/main...' + branch
    print('pushed branch ' + branch)
    print('open the PR here: ' + pr_url)
    print('then, locally:  git config user.email ' + email)  # finding #17: web-UI commits default to the private email; attribution keys on email
    return 0


if __name__ == '__main__':
    sys.exit(main())
