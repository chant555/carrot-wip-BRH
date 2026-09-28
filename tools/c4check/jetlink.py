#!/usr/bin/env python3
"""현재 관찰 구간의 Jetlink 상태·USB 역할. 과거 주행 이력으로 해석하지 않는다."""
import json
from pathlib import Path
import time
from checklib import Audit, emit, seconds_arg


def inspect(status,now,audit):
  if not isinstance(status,dict) or not isinstance(status.get('updated'),(int,float)):
    audit.missing('Jetlink 상태 형식 오류')
    return
  if not 0 <= now-status['updated'] < 3:
    audit.missing('Jetlink 상태 오래됨/다른 부팅 시각')
  state = status.get('state')
  if state not in ('waiting','connecting','loading','ready','retrying','stopped'):
    audit.missing(f'알 수 없는 Jetlink 상태: {state}')
  if state in ('retrying','stopped') or status.get('error'):
    audit.review('Jetlink 재시도/중지/오류 관측')


def main():
  seconds = seconds_arg(); audit = Audit(); end = time.monotonic()+seconds
  samples = 0; changes = []; previous = None
  while time.monotonic() < end:
    try:
      status = json.loads(Path('/dev/shm/carrot-jetlink.json').read_text())
      inspect(status,time.monotonic(),audit)
      role = Path('/sys/class/power_supply/usb/typec_mode').read_text().strip()
      row = dict(state=status.get('state'),error=status.get('error'),peer=status.get('peer'),typec_mode=role)
      if row != previous:
        changes.append(dict(monotonic=time.monotonic(),**row)); previous = row
      samples += 1
    except (OSError,ValueError,TypeError) as exc:
      audit.missing(f'Jetlink 상태 읽기 실패: {exc}')
    time.sleep(.5)
  return emit(audit,seconds=seconds,samples=samples,changes=changes,
              scope='이 관찰 구간만 점검. waiting은 외부 미연결 대기이며 전 주행 정상 증거가 아님.')


if __name__ == '__main__': raise SystemExit(main())
