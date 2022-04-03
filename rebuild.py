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

print('Finding Zotero versions...')
# zotero
packages += [
  ('zotero', Config.zotero.bumped(release['version']), Config.archmap[arch], Config.zotero.app.format(arch=arch, version=release["version"]))
  for release in get(Config.zotero.releases).json()
  for arch in Config.archmap
] + [
  ('zotero-beta', Config.zotero.bumped(unquote(re.search(Config.zotero.beta_version_regex, url).group(1))), Config.archmap[arch], url)
  for arch, url in [
    (arch, get(Config.zotero.beta.format(arch=arch)).url)
    for arch in Config.archmap
  ]
]

print('Finding Juris-M versions...')
# jurism
packages += [
  ('jurism', Config.jurism.bumped(version), Config.archmap[arch], Config.jurism.app.format(arch=arch, version=version))

  for version in ({
    version.rsplit('m', 1)[0] : version
    for version in sorted([
      version
      for version in get(Config.jurism.releases).text.split('\n')
      if version != ''
    ], key=lambda k: tuple([int(v) for v in re.split('[m.]', k)]))
  }.values())
  for arch in Config.archmap
]
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
