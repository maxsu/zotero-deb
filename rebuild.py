#!/usr/bin/env python3

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)

import os, sys
import argparse
from urllib.parse import quote_plus as urlencode, unquote
import re
import glob
import shutil
from pathlib import Path
import shlex
#import configparser
#import contextlib
#import types
#from github3 import login as ghlogin
import html

from util import run, Config, get

if Config.mode == 'apt':
  import apt as repository

Config.repo.mkdir(parents=True, exist_ok=True)

packages = []

# zotero
print('Finding Zotero versions...')
for arch, deb_arch in Config.archmap.items():
  for release in get('https://www.zotero.org/download/client/manifests/release/updates-linux-x86_64.json').json():
    packages.append(
      (
        'zotero',
        Config.zotero.bumped(release['version']),
        deb_arch,
        f'https://www.zotero.org/download/client/dl?channel=release&platform=linux-{arch}&version={release["version"]}'
      )
    )

print('Finding Zotero beta versions...')
for arch, deb_arch in Config.archmap.items():
  beta_url = get(f'https://www.zotero.org/download/standalone/dl?platform=linux-{arch}&channel=beta').url
  beta_version = unquote(re.match(r'https://download.zotero.org/client/beta/([^/]+)-beta', beta_url).group(1))
  packages.append(
    (
      'zotero-beta',
      Config.zotero.bumped(beta_version),
      deb_arch,
      beta_url
    )
  ) 


print('Finding Juris-M versions...')
# jurism
for arch, deb_arch in Config.archmap.items():
  versions = get('https://github.com/Juris-M/assets/releases/download/client%2Freleases%2Fincrementals-linux/incrementals-release-linux').text.splitlines()
  versions = filter(None, versions)
  versions = sorted(versions, key=lambda k: tuple(int(v) for v in re.split('[m.]', k)))
  versions = {v.rsplit('m')[0] : v for v in versions}.values()

  for version in versions:
    packages.append(
      (
        'jurism',
        Config.jurism.bumped(version),
        deb_arch,
        f'https://github.com/Juris-M/assets/releases/download/client%2Frelease%2F{version}/Jurism-{version}_linux-{arch}.tar.bz2'
      )
    )

print([v[:3] for v in packages])

prebuilt = set(repository.prebuilt())
packages = [ (Config.repo / repository.packagename(client, version, arch), url) for client, version, arch, url in packages ]

modified = False
allowed = set([pkg for pkg, url in packages])
for pkg in prebuilt - allowed:
  print('rebuild: delete', pkg)
  modified = True
  pkg.unlink()

Config.staged = []
for pkg, url in packages:
  if pkg.exists():
    continue
  print('rebuild: packaging', pkg)
  modified = True
  staged = Config.staging / Path(pkg).stem
  Config.staged.append(staged)
  if not staged.exists():
    staged.mkdir(parents=True)
    run(f'curl -sL {shlex.quote(url)} | tar xjf - -C {shlex.quote(str(staged))} --strip-components=1')

  repository.package(staged)

if Config.staging.exists():
  for unstage in Config.staging.iterdir():
    if unstage not in Config.staged:
      print('unstaged', unstage)
      shutil.rmtree(unstage)

if modified:
  repository.mkrepo()
  print(f'::set-output name=publish::true')
