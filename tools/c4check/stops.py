#!/usr/bin/env python3
"""최근 12초 접근 이력에서 자동 가감속 정지 후보를 찾는다. 밀림·정지 유지 검증은 별도."""
import collections
from checklib import Audit, coverage, emit, parser, read_events, route_paths

FRESH_SECONDS = 0.5  # offline qlog join bound, not a vehicle setting


def classify(rows):
  reasons = set()
  if len(rows) < 2 or not any(r['v'] > 3 for r in rows): reasons.add('최근 이동 근거 부족')
  if any(b['t']-a['t'] <= 0 or b['t']-a['t'] > FRESH_SECONDS for a,b in zip(rows,rows[1:])):
    reasons.add('carState 시간 공백/역행')
  for r in rows:
    if not r['fresh']: reasons.add('결합 상태 누락/오래됨/invalid')
    if not r['enabled'] or not r['long_active']: reasons.add('자동 가감속 비활성 구간')
    if r['brake'] or r['gas']: reasons.add('운전자 페달 개입')
    if not r['lead']: reasons.add('선행차 없는 구간')
  return sorted(reasons)


def analyze(paths,audit,reader=None):
  counts = collections.Counter(); state = {}; buf = collections.deque(); scenes = []
  origin = None; armed = False; previous_segment = None
  for path in paths:
    segment = int(path.parent.name.rsplit('--',1)[1])
    if previous_segment is not None and segment != previous_segment+1:
      state.clear(); buf.clear(); armed = False
    previous_segment = segment
    for m in read_events(path,audit,reader):
      try:
        w = m.which(); counts[w] += 1
        if w in ('initData','sentinel'): continue
        now = m.logMonoTime/1e9
        if origin is None: origin = now
        if w in ('selfdriveState','carControl','radarState'):
          state[w] = (now,m.valid,getattr(m,w))
        elif w == 'carState':
          c = m.carState
          def get(name): return state.get(name,(None,False,None))
          ss = get('selfdriveState')[2]; cc = get('carControl')[2]; rs = get('radarState')[2]
          fresh = m.valid and all(ts is not None and valid and 0 <= now-ts <= FRESH_SECONDS
                                  for ts,valid,_ in (get(n) for n in ('selfdriveState','carControl','radarState')))
          row = dict(t=now,v=c.vEgo,a=c.aEgo,cmd=cc.actuators.accel if cc else None,
                     enabled=bool(ss and ss.enabled),long_active=bool(cc and cc.longActive),
                     brake=c.brakePressed,gas=c.gasPressed,fresh=fresh,
                     lead=bool(rs and rs.leadOne.status),distance=rs.leadOne.dRel if rs and rs.leadOne.status else None)
          if buf and (now <= buf[-1]['t'] or now-buf[-1]['t'] > FRESH_SECONDS):
            buf.clear(); armed = False
          buf.append(row)
          while buf and now-buf[0]['t'] > 12: buf.popleft()
          if c.vEgo > 3: armed = True
          if armed and c.vEgo < .1:
            armed = False; rows = list(buf); reasons = classify(rows)
            scenes.append(dict(t=round(now-origin,3),accepted=not reasons,excluded_reasons=reasons,
                               samples=len(rows),span_s=round(rows[-1]['t']-rows[0]['t'],3),
                               min_accel=min(r['a'] for r in rows),stop_command=row['cmd'],stop_lead_distance=row['distance']))
      except Exception as exc:
        audit.missing(f'{path}: 정지 메시지 해석 실패: {exc}')
        state.clear(); buf.clear(); armed = False
  coverage(counts,('carState','carControl','selfdriveState','radarState'),audit)
  return dict(counts=dict(counts),accepted_candidates=sum(s['accepted'] for s in scenes),
              excluded_candidates=sum(not s['accepted'] for s in scenes),scenes=scenes,
              scope='관측된 최근 12초 내 자동 가감속·무페달 개입·유효한 선행차를 만족하는 후보. 정지 유지/뒤로 밀림은 판정하지 않음.')


def main():
  args = parser(__doc__).parse_args(); audit = Audit()
  return emit(audit,route=args.route,**analyze(route_paths(args.root,args.route,audit),audit))


if __name__ == '__main__':
  raise SystemExit(main())
