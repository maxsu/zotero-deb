#!/usr/bin/env python3

import sys, os
from util import run, Config
from pathlib import Path
from requests import Session

BASEURL = 'https://zotero.retorque.re/file/apt-package-archive'
URL = sys.argv[1]
UPDATE = sys.argv[2]

update = '_true_' in UPDATE
if not update:
  baseurl = URL
  if baseurl[-1] != '/':
    baseurl += '/'
  for asset in ['Packages']:
    asset = baseurl + asset
    response = get(asset)
    if response.status_code >= 400:
      print(asset, 'missing, force republish')
      update = True
if not update:
  sys.exit(1) # confusing, but returning an "error" here will cause the exit code to be falsish and *not* force a rebuild

readme = Config.readme_meta + Path('README.md').read_text()

repo = Path(config.repo)
for asset in sorted(repo.rglob('*'), key=lambda f: str(f)):
  if asset.is_file():
    asset = str(asset.relative_to(repo))
    assetname = asset.replace('_', '\\_')
    readme += f'* [{assetname}]({asset})\n'

with open('index.md', 'w') as f:
  f.write(readme)
run('pandoc index.md -s --css pandoc.css -o index.html')
