#!/usr/bin/env python3
"""정해진 관찰 구간의 manager/device 메시지와 프로세스 상태."""
import collections
from checklib import Audit, emit, live_samples, seconds_arg, stats


def main():
  seconds = seconds_arg(); audit = Audit(); counts = collections.Counter(); bad = collections.Counter()
  temps = []; last_processes = []; device = None
  for name,d in live_samples(['managerState','deviceState'],seconds,audit):
    counts[name] += 1
    if name == 'managerState':
      if not len(d.processes): audit.missing('managerState 프로세스 목록 비어 있음')
      last_processes = [dict(name=p.name,pid=p.pid,running=p.running,expected=p.shouldBeRunning,exit=p.exitCode) for p in d.processes]
      for p in d.processes:
        if p.shouldBeRunning and not p.running: bad[p.name] += 1
    else:
      if len(d.cpuTempC): temps.append(max(d.cpuTempC))
      device = dict(thermal=str(d.thermalStatus),memory_pct=d.memoryUsagePercent,free_pct=d.freeSpacePercent,started=d.started)
  if bad: audit.review('실행되어야 하지만 중지된 프로세스 관측')
  return emit(audit,seconds=seconds,counts=dict(counts),unexpected_stopped=dict(bad),
              processes=last_processes,device=device,cpu_max_c=stats(temps))


if __name__ == '__main__': raise SystemExit(main())
