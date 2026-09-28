#!/usr/bin/env python3
"""MDPS/TCS 송신 요청 카운터 점검. CRC·실제 CAN 송신 보장은 검사하지 않는다."""
import collections
from pathlib import Path
import re
from checklib import Audit, emit, parser, read_events, route_paths


class Sequence:
  def __init__(self):
    self.previous = None
    self.deltas = collections.Counter()
    self.samples = 0
    self.breaks = 0

  def add(self,segment,t,value,bits,max_gap):
    self.samples += 1
    if self.previous:
      oldseg,oldt,oldvalue = self.previous
      if segment in (oldseg,oldseg+1) and 0 <= t-oldt <= max_gap:
        self.deltas[(value-oldvalue) % (1 << bits)] += 1
      else:
        self.breaks += 1
    self.previous = (segment,t,value)


def main():
  p = parser(__doc__,segments=True)
  p.add_argument('--dbc',type=Path,default=Path('/data/openpilot/opendbc_repo/opendbc/dbc/hyundai_canfd_generated.dbc'))
  p.add_argument('--max-gap',type=float,default=.1,help='연속성 비교 최대 간격(초), 런타임 설정 아님')
  args = p.parse_args(); audit = Audit(); spec = {}; seqs = {}
  if not 0 < args.max_gap <= 1: p.error('--max-gap은 0~1초')
  try:
    dbc = args.dbc.read_text()
    for name in ('MDPS','TCS'):
      block = re.search(rf'^BO_ (\d+) {name}: (\d+).*?\n(.*?)(?=^BO_|\Z)',dbc,re.M|re.S)
      counter = re.search(r'SG_ COUNTER : (\d+)\|(\d+)@1\+',block[3])
      spec[int(block[1])] = (name,int(counter[1]),int(counter[2]),int(block[2]))
  except Exception as exc:
    audit.missing(f'DBC 해석 실패: {exc}')
    return emit(audit)
  for path in route_paths(args.root,args.route,audit,'rlog',args.segments):
    seg = int(path.parent.name.rsplit('--',1)[1])
    for m in read_events(path,audit):
      try:
        kind = m.which()
        if kind not in ('can','sendcan'): continue
        for c in getattr(m,kind):
          if c.address not in spec or (kind == 'can' and c.src != 0): continue
          name,st,bits,length = spec[c.address]
          if len(c.dat) != length:
            audit.missing(f'{path}: {name} payload 길이 불일치')
            continue
          key = f'{name}:{kind}:bus{c.src}'
          seq = seqs.setdefault(key,Sequence())
          value = (int.from_bytes(bytes(c.dat),'little') >> st) & ((1 << bits)-1)
          seq.add(seg,m.logMonoTime/1e9,value,bits,args.max_gap)
      except Exception as exc:
        audit.missing(f'{path}: CAN 해석 실패: {exc}')
  rows = {}
  for key,seq in seqs.items():
    rows[key] = dict(n=seq.samples,deltas=dict(sorted(seq.deltas.items())),uncompared_boundaries=seq.breaks)
    if 'sendcan' in key and any(d != 1 for d in seq.deltas): audit.review(f'{key}: 연속 구간에 +1 이외 증분; 원인 별도 확인')
  for name in ('MDPS','TCS'):
    if not any(k.startswith(name+':sendcan:') and s.deltas for k,s in seqs.items()): audit.missing(f'{name}: 비교 가능한 TX 표본 없음')
  return emit(audit,route=args.route,segments=sorted(set(args.segments)),sequences=rows,
              scope='sendcan=송신 요청. 단절 경계는 미비교. +1 이외 값만으로 코드 회귀라고 단정하지 않음.')


if __name__ == '__main__': raise SystemExit(main())
