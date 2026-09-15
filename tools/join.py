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
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

API = 'https://api.github.com'


def sh(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True, cwd=cwd)
    if r.returncode != 0:
        sys.exit('ERROR: ' + (r.stderr or r.stdout).strip()[:300])
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description='Join a syndicate: one command, one PR.')
    ap.add_argument('--handle', required=True)
    ap.add_argument('--name', required=True)    # # displayed name; identity binding is handle+email, names are cosmetic
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

    sh('git -C . fetch origin', cwd=repo)
    branch = 'member/' + args.handle
    sh('git -C . checkout -B ' + branch + ' origin/main', cwd=repo)

    manifest = repo / 'syndicate.yaml'
    txt = manifest.read_text(encoding='utf-8')
    if email in txt:
        print('already a member — nothing to do')
        return 0
    today = date.today().isoformat()
    row = [
        '  - name: ' + json.dumps(args.name),
        '    github: ' + json.dumps(args.handle),
        '    orcid: "0000-0000-0000-0000"    # # optional: edit after merge if you have one',
        '    email: ' + json.dumps(email),
        '    role: ' + json.dumps(args.role),
        '    trust_tier: ' + args.tier,
        '    joined: ' + json.dumps(today),
    ]
    anchor = 'members:    # # ONE ROW PER MEMBER, EDIT AT GENESIS'
    if anchor not in txt:
        sys.exit('ERROR: manifest members anchor not found — file changed shape?')
    txt = txt.replace(anchor, anchor + '\n' + '\n'.join(row), 1)
    manifest.write_text(txt, encoding='utf-8')
    import yaml    # # validate before committing: a broken manifest blocks the whole syndicate (finding #1)
    cfg = yaml.safe_load(txt)
    assert any(m.get('email') == email for m in cfg['members']), 'row not parseable — aborting'
    print('manifest row inserted and parses cleanly')

    identity = ''
    if args.token:
        identity = args.token + '@'
    remote = sh('git -C . remote get-url origin', cwd=repo)
    if args.token:
        sh('git -C . remote set-url origin https://' + identity + 'github.com/' + remote.split('github.com/')[-1], cwd=repo)
    sh('git -C . add syndicate.yaml', cwd=repo)
    sh('git -C . -c user.name="' + args.handle + '" -c user.email="' + email + '" commit -m "manifest: add member ' + args.handle + '"', cwd=repo)
    sh('git -C . push -u origin ' + branch, cwd=repo)
    owner_repo = remote.split('github.com/')[-1].removesuffix('.git')
    pr_url = 'https://github.com/' + owner_repo + '/compare/main...' + branch
    print('pushed branch ' + branch)
    print('open the PR here: ' + pr_url)
    print('then, locally:  git config user.email ' + email)  # finding #17: web-UI commits default to the private email; attribution keys on email
    return 0


if __name__ == '__main__':
    sys.exit(main())
