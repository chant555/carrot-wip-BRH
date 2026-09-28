#!/usr/bin/env python3
"""첫 비메타 메시지 기준 t 앞 span초~뒤 1초의 qlog 타임라인."""
from checklib import Audit, emit, parser, read_events, route_paths


def main():
  p = parser(__doc__); p.add_argument('t',type=float); p.add_argument('span',type=float)
  args = p.parse_args()
  if not 0 <= args.t < 86400 or not 0 < args.span <= 600: p.error('t=0~86400, span=0~600초')
  audit = Audit(); origin = None; state = {}; rows = []; events = []; last = None
  for path in route_paths(args.root,args.route,audit):
    for m in read_events(path,audit):
      try:
        w = m.which()
        if w in ('initData','sentinel'): continue
        now = m.logMonoTime/1e9
        if origin is None: origin = now
        t = now-origin; last = t
        if w in ('carState','carControl','selfdriveState'): state[w] = (now,m.valid,getattr(m,w))
        if not args.t-args.span <= t <= args.t+1: continue
        if w == 'radarState':
          fresh = m.valid and all(n in state and state[n][1] and 0 <= now-state[n][0] <= .5
                                  for n in ('carState','carControl','selfdriveState'))
          if not fresh: audit.missing('선택 구간에 오래됨/누락/invalid 결합 상태')
          cs = state.get('carState',(0,False,None))[2]; cc = state.get('carControl',(0,False,None))[2]
          ss = state.get('selfdriveState',(0,False,None))[2]; lead = m.radarState.leadOne
          rows.append(dict(t=round(t,3),fresh=fresh,v_kph=cs.vEgo*3.6 if cs else None,
                           accel=cs.aEgo if cs else None,command=cc.actuators.accel if cc else None,
                           longActive=cc.longActive if cc else None,enabled=ss.enabled if ss else None,
                           brake=cs.brakePressed if cs else None,gas=cs.gasPressed if cs else None,
                           lead=lead.status,dRel=lead.dRel if lead.status else None))
        elif w == 'onroadEvents':
          for e in m.onroadEvents: events.append(dict(t=round(t,3),event=str(e.name)))
      except Exception as exc: audit.missing(f'{path}: 타임라인 해석 실패: {exc}')
  if not rows: audit.missing('선택 시간대 radarState 행 없음')
  if last is None or last < args.t+1: audit.missing('요청 구간 끝까지 데이터가 없음')
  return emit(audit,route=args.route,origin='첫 비메타 메시지(initData/sentinel 제외)',rows=rows,events=events)


if __name__ == '__main__': raise SystemExit(main())
