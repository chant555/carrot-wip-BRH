#!/usr/bin/env python3
"""rlog 프로세스 CPU. 각 프로세스 누적시간 증분을 동일 관측 시간으로 나눈다(1코어=100%)."""
import collections
from checklib import Audit, coverage, emit, parser, read_events, route_paths, stats


def analyze(messages,audit):
  counts = collections.Counter(); previous = {}; totals = collections.Counter(); times = []; temps = []
  for m in messages:
    try:
      w = m.which(); counts[w] += 1
      if w == 'procLog':
        now = m.logMonoTime/1e9
        if times and now <= times[-1]:
          audit.missing('procLog 시각 역행/중복'); previous.clear(); continue
        if times and now-times[-1] > 5: audit.missing('procLog 표본 사이 5초 초과 공백')
        times.append(now); current = {}
        for p in m.procLog.procs:
          key = (p.pid,' '.join(p.cmdline)); value = p.cpuUser+p.cpuSystem
          if key in previous:
            delta = value-previous[key]
            if delta < 0: audit.review('프로세스 CPU 카운터 초기화/PID 재사용')
            else: totals[key] += delta
          current[key] = value
        previous = current
      elif w == 'deviceState' and len(m.deviceState.cpuTempC): temps.append(max(m.deviceState.cpuTempC))
    except Exception as exc: audit.missing(f'CPU 메시지 해석 실패: {exc}')
  coverage(counts,('procLog','deviceState'),audit)
  span = times[-1]-times[0] if len(times)>1 else 0
  if span < 5 or not totals: audit.missing('CPU 비교에 필요한 5초/두 표본 이상의 누적값 부족')
  rows = sorted([dict(pid=k[0],command=k[1],pct=100*v/span) for k,v in totals.items()],key=lambda r:r['pct'],reverse=True) if span else []
  return dict(span_s=span,process_cpu_sum_pct=sum(r['pct'] for r in rows) if rows else None,
              top_processes=rows[:12],jetlink_processes=[r for r in rows if 'jetlink' in r['command'].lower()],
              cpu_temp_c=stats(temps),counts=dict(counts),
              scope='관측 프로세스 누적시간 기준. 생성/종료 사이 미관측 CPU·IRQ 등은 빠질 수 있으며 전체 코어 부하와 다름.')


def main():
  args = parser(__doc__,segments=True).parse_args(); audit = Audit(); reports = []
  for path in route_paths(args.root,args.route,audit,'rlog',args.segments):
    reports.append(dict(file=str(path),**analyze(read_events(path,audit),audit)))
  return emit(audit,segments=reports)


if __name__ == '__main__': raise SystemExit(main())
