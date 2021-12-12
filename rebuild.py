#!/usr/bin/env python3

from urllib.request import urlopen
import json
from urllib.parse import quote_plus as urlencode, unquote
import re
import os, sys
import configparser
import glob
import shlex
import shutil
from pathlib import Path
from types import SimpleNamespace
import argparse

parser = argparse.ArgumentParser()
# 3.9 has argparse.BooleanOptionalAction
def add_boolean_optional_argument(parser, arg):
  eg = parser.add_mutually_exclusive_group()
  eg.add_argument(arg.replace('--', '--no-'), action='store_false', dest=arg.replace('-', ''))
  eg.add_argument(arg, action='store_true', dest=arg.replace('-', ''))
#parser.add_argument('--fetch', action=argparse.BooleanOptionalAction)
add_boolean_optional_argument(parser, '--fetch')
#parser.add_argument('--send', action=argparse.BooleanOptionalAction)
add_boolean_optional_argument(parser, '--send')
parser.add_argument('--clear', action='store_true')
parser.add_argument('--host', default='sourceforge')
parser.add_argument('--force', action='store_true')
args = parser.parse_args()

exclusive_grp = parser.add_mutually_exclusive_group()
exclusive_grp.add_argument('--foo', action='store_true', help='do foo')
exclusive_grp.add_argument('--no-foo', action='store_true', help='do not do foo')

def system(cmd, execute=True):
  if execute:
    print(cmd)
    if (exitcode := os.system(cmd)) != 0:
      sys.exit(exitcode)
  else:
    print('#', cmd)

class Sync:
  def __init__(self):
    self.repo = {
      'sourceforge': SimpleNamespace(local='./repo/', remote='retorquere@frs.sourceforge.net:/home/frs/project/zotero-deb/'),
      'b2': SimpleNamespace(local='repo', remote='b2://zotero-apt/'),
    }[args.host]

    self.sync = {
      'sourceforge': self.rsync,
      'b2': self.b2sync,
    }[args.host]

  def fetch(self):
    return self.sync(self.repo.remote, self.repo.local)

  def publish(self):
    return self.sync(self.repo.local, self.repo.remote)

  def rsync(self, _from, _to):
    return f'rsync --progress -e "ssh -o StrictHostKeyChecking=no" -avhz --delete {shlex.quote(_from)} {shlex.quote(_to)}'

  def b2sync(self, _from, _to):
    return f'./b2-linux sync --replaceNewer --delete {shlex.quote(_from)} {shlex.quote(_to)}'
Sync=Sync()

if args.clear:
  if os.path.exists('repo'):
    shutil.rmtree('repo')
  os.makedirs('repo')

system(Sync.fetch())

def load(url,parse_json=False):
  response = urlopen(url).read()
  if type(response) is bytes: response = response.decode('utf-8')
  if parse_json:
    return json.loads(response)
  else:
    return response

config = configparser.RawConfigParser()
config.read('config.ini')
bump = lambda client, version, beta=None: (version + '-' + bumped) if (bumped := config[client].get(beta or version)) else version

archmap = {
  'i686': 'i386',
  'x86_64': 'amd64',
}

debs = []

# zotero
debs += [
  ('zotero', bump('zotero', release['version']), archmap[arch], f'https://www.zotero.org/download/client/dl?channel=release&platform=linux-{arch}&version={release["version"]}')
  for release in load('https://www.zotero.org/download/client/manifests/release/updates-linux-x86_64.json', parse_json=True)
  for arch in [ 'i686', 'x86_64' ]
] + [
  ('zotero-beta', bump('zotero', unquote(re.match(r'https://download.zotero.org/client/beta/([^/]+)', url)[1]).replace('-beta', ''), 'beta'), archmap[arch], url)
  for arch, url in [
    (arch, urlopen(f'https://www.zotero.org/download/standalone/dl?platform=linux-{arch}&channel=beta').geturl())
    for arch in [ 'i686', 'x86_64' ]
  ]
]

# jurism
debs += [
  ('jurism', bump('jurism', version), archmap[arch], f'https://github.com/Juris-M/assets/releases/download/client%2Frelease%2F{version}/Jurism-{version}_linux-{arch}.tar.bz2')
  
  for version in ({
    version.rsplit('m', 1)[0] : version
    for version in sorted([
      version
      for version in load('https://github.com/Juris-M/assets/releases/download/client%2Freleases%2Fincrementals-linux/incrementals-release-linux').split('\n')
      if version != ''
    ], key=lambda k: tuple([int(v) for v in re.split('[m.]', k)]))
  }.values())
  for arch in [ 'i686', 'x86_64' ]
]

debs = [ (f'repo/{client}_{version}_{arch}.deb', url) for client, version, arch, url in debs ]

modified = not os.path.exists('repo/Packages')

for deb in (set(glob.glob('repo/*.deb')) - set( [_deb for _deb, _url in debs])):
  print('delete', deb)
  os.remove(deb)
  modified = True

if os.path.exists('staging'):
  shutil.rmtree('staging')
for deb, url in debs:
  if os.path.exists(deb):
    continue
  staging = os.path.join('staging', Path(deb).stem)
  os.makedirs(staging)
  print('staging', staging)
  system(f'curl -sL {shlex.quote(url)} | tar xjf - -C {shlex.quote(staging)} --strip-components=1')
  modified = True

if args.force or modified:
  if modified:
    system('./build.py staging/*')
  system('cp install.sh repo')
  system(Sync.publish(), args.send or args.force)
  print('::set-output name=modified::true')
else:
  print('echo nothing to do')
  