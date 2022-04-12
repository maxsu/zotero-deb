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

class Packages:
  """Collects package information for build"""
  
  _packages = []
  
  def add(self, client, version, arch, url_template):
    """Given package information, create a package name and url"""
    base_client = client.split('-')[0] 
    self._packages.append(
      (
        Config.repo / repository.packagename(
          client,
          Config[base_client].bumped(version),
          Config.archmap[arch]
        ),
        url_template.format(arch=arch, version=version)
      )
    )
  
  def __iter__(self):
    yield from self._packages

packages = Packages()

# zotero
print('Finding Zotero versions...')
for arch in Config.archmap:
  for release in get(Config.zotero.release_url).json():
    version = release['version']
    packages.add('zotero', version, arch, Config.zotero.app_url)

# zotero beta
print('Finding Zotero beta versions...')
for arch in Config.archmap:
  beta_app_url = get(Config.zotero.beta_url.format(arch=arch)).url
  version = unquote(re.match(Config.zotero.beta_version_regex, beta_app_url).group(1))
  packages.add('zotero-beta', version, arch, beta_app_url)


# jurism
print('Finding Juris-M versions...')
for arch in Config.archmap:
  versions = get(Config.jurism.release_url).text.splitlines()
  versions = filter(None, versions)
  versions = sorted(versions, key=lambda k: tuple(int(v) for v in re.split('[m.]', k)))
  versions = {v.rsplit('m')[0] : v for v in versions}.values()

  for version in versions:
    packages.add('jurism', version, arch, Config.jurism.app_url)

print([pkg.stem for pkg, _ in packages])

prebuilt = set(repository.prebuilt())

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
