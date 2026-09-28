#!/usr/bin/env python3
"""qlog 표본의 건강 요약. 종료코드 0도 실차 전체 정상 보증은 아니다."""
import collections
import json
import re
from checklib import Audit, CounterSeries, coverage, emit, log_record, parser, read_events, route_paths, stats


def analyze(paths, audit, reader=None):
  counts = collections.Counter(); faults = collections.Counter()
  issues = {'startup_15s': collections.Counter(), 'later': collections.Counter()}
  values = collections.defaultdict(list); counters = CounterSeries()
  logs = []; jetlink = []; jet_count = 0; commits = set(); enabled = 0
  origin = last = None
  for path in paths:
    for m in read_events(path, audit, reader):
      try:
        w = m.which(); counts[w] += 1
        if w == 'initData':
          commits.add(m.initData.gitCommit)
          continue
        if w == 'sentinel':
          continue
        now = m.logMonoTime/1e9
        if origin is None:
          origin = now
        last = now if last is None else max(last, now)
        t = now-origin
        bucket = issues['startup_15s' if t < 15 else 'later']
        if w in ('carState','carControl','selfdriveState','managerState','deviceState','pandaStates','radarState','drivingModelData','livePose','cameraOdometry') and not m.valid:
          bucket['invalid_'+w] += 1
        if w == 'selfdriveState':
          enabled += bool(m.selfdriveState.enabled)
        elif w == 'managerState':
          if not len(m.managerState.processes): audit.missing('managerState 프로세스 목록 비어 있음')
          for p in m.managerState.processes:
            if p.shouldBeRunning and not p.running:
              bucket['not_running_'+p.name] += 1
        elif w == 'deviceState':
          d = m.deviceState
          if len(d.cpuTempC): values['cpu_max_c'].append(max(d.cpuTempC))
          if len(d.cpuUsagePercent): values['cpu_mean_cores_pct'].append(sum(d.cpuUsagePercent)/len(d.cpuUsagePercent))
        elif w == 'carState':
          d = m.carState
          if not d.canValid: bucket['can_invalid'] += 1
          for name in ('canTimeout','steerFaultTemporary','steerFaultPermanent','accFaulted'):
            if getattr(d,name): bucket[name] += 1
        elif w == 'pandaStates':
          if not len(m.pandaStates): audit.missing('빈 pandaStates 표본')
          for i,p in enumerate(m.pandaStates):
            for f in p.faults: faults[str(f)] += 1
            if str(p.faultStatus) != 'none': bucket['panda_faultStatus_'+str(p.faultStatus)] += 1
            for name in ('heartbeatLost','safetyRxChecksInvalid'):
              if getattr(p,name): bucket[name] += 1
            for name in ('spiChecksumErrorCount','safetyRxInvalid','safetyTxBlocked','rxBufferOverflow','txBufferOverflow'):
              counters.add(f'panda{i}.{name}',getattr(p,name))
            for bus in range(3):
              can = getattr(p,f'canState{bus}')
              if can.busOff: bucket[f'panda{i}.can{bus}.busOff'] += 1
              for name in ('totalErrorCnt','busOffCnt','totalTxLostCnt','totalRxLostCnt'):
                counters.add(f'panda{i}.can{bus}.{name}',getattr(can,name))
        elif w == 'livePose':
          for name in ('inputsOK','sensorsOK','posenetOK'):
            if not getattr(m.livePose,name): bucket['pose_'+name] += 1
        elif w == 'drivingModelData':
          values['model_ms'].append(m.drivingModelData.modelExecutionTime*1000)
          values['drop_pct'].append(m.drivingModelData.frameDropPerc)
          if t >= 15:
            values['model_ms_after_15s'].append(m.drivingModelData.modelExecutionTime*1000)
            values['drop_pct_after_15s'].append(m.drivingModelData.frameDropPerc)
          if m.drivingModelData.frameDropPerc > 0: bucket['drop_pct_nonzero_samples'] += 1
        elif w == 'onroadEvents':
          for e in m.onroadEvents:
            if str(e.name) == 'commIssue' or e.softDisable or e.immediateDisable:
              bucket['event_'+str(e.name)] += 1
        elif w in ('logMessage','errorLogMessage'):
          j,message = log_record(getattr(m,w)); daemon = j.get('ctx',{}).get('daemon','?')
          text = message if isinstance(message,str) else json.dumps(message,ensure_ascii=False)
          if 'jetlink' in daemon.lower() or re.match(r'^Jetlink\b',text,re.I):
            jet_count += 1
            if len(jetlink) < 30: jetlink.append(dict(t=round(t,3),daemon=daemon,message=text[:400]))
          if message == 'crash': bucket['crash_'+daemon] += 1
          if isinstance(message,dict) and message.get('event') == 'commIssue': bucket['commIssue_log'] += 1
          if 'CAM_SYNC error' in text: bucket['CAM_SYNC_log'] += 1
          match = re.search(r'camera dropped (\d+) frames',text)
          if match: bucket['reported_dropped_frames'] += int(match[1])
          if j.get('levelnum',0) >= 40 or message == 'crash':
            bucket['error_log_samples'] += 1
            if len(logs) < 30: logs.append(dict(t=round(t,3),daemon=daemon,message=text[:300]))
      except Exception as exc:
        audit.missing(f'{path}: 메시지 해석 실패: {type(exc).__name__}: {exc}')
  coverage(counts,('initData','carState','carControl','selfdriveState','pandaStates','managerState','deviceState','livePose','drivingModelData'),audit)
  if len(commits) != 1: audit.missing(f'커밋 식별이 단일하지 않음: {sorted(commits)}')
  if faults or any(issues.values()): audit.review('초기화/이후 관측 항목 확인 필요; 표본 수와 독립 사건 수는 다름')
  if any(v['increase'] or v['resets'] for v in counters.values.values()): audit.review('누적 카운터 증가/초기화 확인 필요')
  return dict(segments=len(paths),commits=sorted(commits),counts=dict(counts),
              observed_span_s=None if origin is None else round(last-origin,3),
              enabled_sample_pct=100*enabled/counts['selfdriveState'] if counts['selfdriveState'] else None,
              faults=dict(faults),observations=issues,counters=counters.values,
              metrics={k:stats(v) for k,v in values.items()},error_log_examples=logs,
              jetlink_log_count=jet_count,jetlink_log_examples=jetlink,
              jetlink_history='미확인: qlog에 상태·USB 역할 전체 이력이 없어 로그 0건도 waiting 유지의 증거가 아님',
              scope='qlog 표본. 시간 원점=첫 비메타 메시지. 첫 15초는 분류만 하며 무해 판정하지 않음. 정밀 카메라 간격은 rlog 필요.')


def main():
  args = parser(__doc__).parse_args(); audit = Audit()
  return emit(audit,route=args.route,**analyze(route_paths(args.root,args.route,audit),audit))


if __name__ == '__main__':
  raise SystemExit(main())
