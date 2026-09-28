"""Shared coverage and exit policy: 0 complete, 1 review, 2 incomplete/error."""
import argparse
import collections
import json
import math
from pathlib import Path
import re
import warnings


class Audit:
  def __init__(self):
    self.incomplete = []
    self.findings = []

  def missing(self, text):
    if text not in self.incomplete:
      self.incomplete.append(text)

  def review(self, text):
    if text not in self.findings:
      self.findings.append(text)

  @property
  def code(self):
    return 2 if self.incomplete else 1 if self.findings else 0


def emit(audit, **data):
  result = dict(status=['분석 완료', '확인 필요', '판정 불가/부분 분석'][audit.code],
                exit_code=audit.code, incomplete=audit.incomplete, findings=audit.findings, **data)
  print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
  return audit.code


def route_name(value):
  if not re.fullmatch(r'[A-Za-z0-9_-]+', value) or '--' not in value:
    raise argparse.ArgumentTypeError('route에는 영문·숫자·밑줄·하이픈만 허용합니다')
  return value


def parser(description, segments=False):
  p = argparse.ArgumentParser(description=description)
  p.add_argument('route', type=route_name)
  if segments:
    p.add_argument('segments', nargs='+', type=int)
  p.add_argument('--root', type=Path, default=Path('/data/media/0/realdata'))
  return p


def route_paths(root, route, audit, kind='qlog', segments=None):
  if segments is None:
    found = {}
    for path in root.glob(route + '--*'):
      suffix = path.name[len(route)+2:]
      if path.is_dir() and suffix.isdigit():
        found[int(suffix)] = path / (kind + '.zst')
    nums = sorted(found)
    if nums:
      gaps = [n for n in range(nums[-1]+1) if n not in found]
      if gaps:
        audit.missing(f'주행 세그먼트 누락 {len(gaps)}개: {gaps[:30]}')
    paths = [found[n] for n in nums]
  else:
    if any(n < 0 for n in segments):
      audit.missing('세그먼트 번호는 0 이상이어야 합니다')
      return []
    paths = [root / f'{route}--{n}' / (kind+'.zst') for n in sorted(set(segments))]
  if not paths:
    audit.missing('입력 로그 없음')
  return paths


def read_events(path, audit, reader=None):
  """Preserve readable prefixes AND record reader warnings/exceptions."""
  if reader is None:
    from openpilot.tools.lib.logreader import LogReader
    reader = lambda name: LogReader(name, sort_by_time=True)
  seen = 0
  with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    try:
      for event in reader(str(path)):
        seen += 1
        yield event
    except Exception as exc:
      audit.missing(f'{path}: {type(exc).__name__}: {exc}')
    finally:
      for item in caught:
        audit.missing(f'{path}: {item.category.__name__}: {item.message}')
  if not seen:
    audit.missing(f'{path}: 읽은 메시지 0개')


def coverage(counts, required, audit):
  for name in required:
    if not counts.get(name):
      audit.missing(f'필수 서비스 표본 없음: {name}')


def stats(values):
  values = sorted(float(v) for v in values if math.isfinite(v))
  if not values:
    return None
  return dict(n=len(values), mean=sum(values)/len(values), min=values[0], max=values[-1], p99=values[int((len(values)-1)*.99)])


def log_record(raw):
  record = json.loads(raw)
  if not isinstance(record, dict):
    raise ValueError('로그 JSON 객체가 아님')
  message = record.get('msg$s', record.get('msg', ''))
  if isinstance(message, str) and message.lstrip().startswith('{'):
    try:
      message = json.loads(message)
    except ValueError:
      pass
  return record, message


class CounterSeries:
  def __init__(self):
    self.values = {}

  def add(self, key, value):
    row = self.values.setdefault(key, dict(first=value, last=value, increase=0, resets=0, n=0))
    if row['n']:
      row['increase'] += max(0, value-row['last'])
      row['resets'] += value < row['last']
    row['last'] = value
    row['n'] += 1


def live_samples(services, seconds, audit, messaging=None, clock=None):
  import time
  if messaging is None:
    from openpilot.cereal import messaging
  clock = clock or time.monotonic
  sm = messaging.SubMaster(services)
  counts = collections.Counter()
  end = clock()+seconds
  while clock() < end:
    sm.update(200)
    for name in services:
      if sm.updated[name]:
        counts[name] += 1
        if not sm.valid[name]:
          audit.missing(f'{name}: invalid 메시지')
        yield name, sm[name]
  coverage(counts, services, audit)
  for name in services:
    if not sm.alive[name] or not sm.valid[name]:
      audit.missing(f'{name}: 종료 시 alive/valid 불충족')


def seconds_arg():
  p = argparse.ArgumentParser()
  p.add_argument('--seconds', type=float, default=5)
  args = p.parse_args()
  if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 60:
    p.error('--seconds는 1~60초')
  return args.seconds
