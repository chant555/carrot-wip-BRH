"""Bounded, best-effort startup failure evidence outside the checkout."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

STATE = Path('/data/startup_failure.json')
# Representative error: an exception/failure statement ("ModuleNotFoundError: …", "SConsLockFailure: …"),
# or an unindented compiler/linker diagnostic with or without a location ("foo.cc:3:10: fatal error: …",
# "fatal error: …", "collect2: error: …"). Python traceback source lines are skipped, so code such as
# raise RuntimeError("foo.cc:1:2: error: …") is never mistaken for the failure itself.
EXCEPTION = re.compile(r'(?:[\w.]*(?:Error|Exception|Failure):|DEPENDENCY_INVALID:)')
COMPILER = re.compile(r'(?:\S+?:\d+(?::\d+)?: |[\w.+-]+: )?(?:fatal )?error: ')
TRACEBACK_FRAME = re.compile(r'\s*File ".*", line \d+')


def diagnostic_line(error, fallback):
  frame_indent = None
  for line in error.splitlines():
    stripped = line.strip()
    expanded = line.expandtabs()
    indent = len(expanded) - len(expanded.lstrip())
    # Frames can be consecutive when Python cannot retrieve source text.
    if TRACEBACK_FRAME.match(line):
      frame_indent = indent
      continue
    if frame_indent is not None:
      previous_indent, frame_indent = frame_indent, None
      # Python indents source text further than its frame header. An exception
      # immediately after a source-less frame must still be examined below.
      if stripped and indent > previous_indent:
        continue
    if EXCEPTION.match(stripped) or (line[:1].strip() and COMPILER.match(line)):
      return stripped
  return fallback


def read_text(path, limit=16384):
  try:
    with Path(path).open('rb') as stream:
      stream.seek(max(0, Path(path).stat().st_size - limit))
      return stream.read(limit).decode('utf-8', 'replace').strip()
  except OSError:
    return ''


def git_value(repo, *args):
  try:
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, timeout=3)
    return result.stdout.strip()[:256] if result.returncode == 0 else ''
  except (OSError, subprocess.TimeoutExpired):
    return ''


def load_state(path):
  try:
    data = json.loads(read_text(path, 65536))
    return data if isinstance(data, dict) else {}
  except ValueError:
    return {}


def save_state(path, data):
  # Same-directory replace survives interruption without a half-written record.
  # Never follow an existing state-file symlink or append an unbounded history.
  name = None
  try:
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.startup-failure-', delete=False) as stream:
      name = stream.name
      json.dump(data, stream, ensure_ascii=False)
      stream.flush()
      os.fsync(stream.fileno())
    os.replace(name, path)
    name = None
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
      os.fsync(directory)
    finally:
      os.close(directory)
  finally:
    if name is not None:
      Path(name).unlink(missing_ok=True)


def package_info():
  result = {}
  for name, distribution in (('catch2', 'comma-deps-catch2'), ('eigen', 'eigen'),
                             ('libjpeg', 'libjpeg'), ('json11', 'comma-deps-json11')):
    try:
      spec = importlib.util.find_spec(name)
      origin = spec.origin if spec else None
    except (ImportError, ValueError, AttributeError):
      origin = None
    try:
      version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
      version = None
    result[name] = {'origin': str(origin)[:512], 'distribution': distribution, 'version': version}
  return result


def record_failure(repo, reason, log, path=STATE, boot_id=None):
  error = read_text(log) if log else ''
  error = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', error)
  diagnostic = diagnostic_line(error, reason)
  head = git_value(repo, 'rev-parse', 'HEAD')
  fingerprint = hashlib.sha256((head + '\n' + reason + '\n' + diagnostic).encode()).hexdigest()
  boot_id = boot_id or read_text('/proc/sys/kernel/random/boot_id', 128)
  previous = load_state(path)
  same = bool(head) and previous.get('status') == 'failed' and previous.get('fingerprint') == fingerprint
  old_count = previous.get('count', 1)
  if not isinstance(old_count, int) or old_count < 1:
    old_count = 1
  count = min(old_count + int(not boot_id or boot_id != previous.get('boot_id')), 9999) if same else 1
  dependency = 'DEPENDENCY_INVALID:' in error or 'dependency' in reason.lower()
  hint = ''
  if count > 1:
    hint = '같은 오류가 반복됐습니다. 환경 복구나 업데이트 확인이 필요합니다.\nSame failure repeated; check dependencies or updates.\n'
  if dependency:
    hint += '필수 패키지 복구에 실패했습니다. 재빌드만으로 해결되지 않을 수 있습니다.\nDependency repair failed; rebuilding alone may not help.'
  data = dict(status='failed', fingerprint=fingerprint, count=count, boot_id=boot_id,
              commit=head, branch=git_value(repo, 'branch', '--show-current'), reason=reason[:512],
              agnos_actual=read_text('/VERSION', 128), agnos_required=os.environ.get('AGNOS_VERSION', '')[:128],
              rebuild_requested=os.environ.get('CARROT_REBUILD_REQUESTED') == '1',
              diagnostic=diagnostic[:2048], log=error, packages=package_info())
  # A full/read-only disk must not hide the cause or prevent the recovery UI.
  try:
    save_state(path, data)
  except OSError as exc:
    print(f'Cannot persist startup failure: {exc}', file=sys.stderr)
  return hint.strip()


def resolve(path=STATE):
  previous = load_state(path)
  # Runs on every healthy boot; only write when a failure streak actually ends.
  if previous and previous.get('status') != 'build_validated':
    previous['status'] = 'build_validated'
    save_state(path, previous)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--repo', type=Path)
  parser.add_argument('--reason', default='Startup failed')
  parser.add_argument('--log', type=Path)
  parser.add_argument('--resolved', action='store_true')
  args = parser.parse_args()
  try:
    if args.resolved:
      resolve()
    elif args.repo:
      print(record_failure(args.repo, args.reason, args.log))
    else:
      parser.error('--repo is required when recording a failure')
  except Exception as exc:
    print(f'Startup failure record unavailable: {exc}', file=sys.stderr)


if __name__ == '__main__':
  main()
