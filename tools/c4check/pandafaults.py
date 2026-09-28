#!/usr/bin/env python3
"""Panda 결함/통신 카운터. noOutput은 오프로드와 점화 상태를 함께 해석한다."""
import collections
from checklib import Audit, CounterSeries, emit, live_samples, seconds_arg


def main():
  seconds = seconds_arg(); audit = Audit(); counters = CounterSeries(); samples = 0
  states = []; flags = collections.Counter(); device_started = None
  for name,data in live_samples(['pandaStates','deviceState'],seconds,audit):
    if name == 'deviceState':
      device_started = data.started
      continue
    samples += 1
    if not len(data): audit.missing('pandaStates 목록 비어 있음')
    states = []
    for i,p in enumerate(data):
      row = dict(type=str(p.pandaType),faultStatus=str(p.faultStatus),faults=[str(f) for f in p.faults],
                 safety=str(p.safetyModel),ignitionLine=p.ignitionLine,ignitionCan=p.ignitionCan)
      states.append(row)
      if len(p.faults) or str(p.faultStatus) != 'none': flags['fault'] += 1
      for field in ('heartbeatLost','safetyRxChecksInvalid'):
        if getattr(p,field): flags[field] += 1
      if str(p.safetyModel) == 'noOutput' and (device_started or p.ignitionLine or p.ignitionCan):
        flags['noOutput_with_started_or_ignition'] += 1
      for field in ('spiChecksumErrorCount','safetyRxInvalid','safetyTxBlocked','rxBufferOverflow','txBufferOverflow'):
        counters.add(f'panda{i}.{field}',getattr(p,field))
      for bus in range(3):
        can = getattr(p,f'canState{bus}')
        if can.busOff: flags[f'can{bus}.busOff'] += 1
        for field in ('totalErrorCnt','busOffCnt','totalTxLostCnt','totalRxLostCnt'):
          counters.add(f'panda{i}.can{bus}.{field}',getattr(can,field))
  if flags: audit.review('Panda/점화 전환 상태 확인 필요')
  if any(r['increase'] or r['resets'] for r in counters.values.values()): audit.review('관찰 중 통신 카운터 증가/초기화')
  return emit(audit,seconds=seconds,samples=samples,device_started=device_started,states=states,
              observations=dict(flags),counters=counters.values,
              scope='점화 꺼짐+오프로드의 noOutput은 정상 대기. 시동 전환/주행 상태의 noOutput은 별도 확인.')


if __name__ == '__main__': raise SystemExit(main())
