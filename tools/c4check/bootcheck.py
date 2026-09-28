#!/usr/bin/env python3
"""mtime으로 고른 부팅 로그 후보. 시계 보정/파일 재사용 때문에 정확한 부팅 범위는 보장하지 않는다."""
import collections
import re
from pathlib import Path
import time
from checklib import Audit, emit, log_record


def main():
  audit = Audit(); boot = time.time()-float(Path('/proc/uptime').read_text().split()[0])
  files = [p for p in Path('/data/log').glob('swaglog.*') if p.stat().st_mtime >= boot-5]
  levels = collections.Counter(); errors = collections.Counter(); jets = collections.Counter(); crashes = []; records = 0
  if not files: audit.missing('현재 부팅 mtime 후보 로그 없음')
  for path in files:
    try:
      with path.open(errors='replace') as stream:
        for line_no,line in enumerate(stream,1):
          if not line.strip(): continue
          try:
            j,msg = log_record(line); records += 1
            daemon = j.get('ctx',{}).get('daemon','?'); text = str(msg); level = j.get('levelnum',0)
            levels[str(j.get('level',level))] += 1
            if 'jetlink' in daemon.lower() or re.match(r'^Jetlink\b',text,re.I): jets[(daemon,text[:300])] += 1
            if msg == 'crash': crashes.append(dict(daemon=daemon,exception=str(j.get('exc_info',''))[-600:]))
            if level >= 40: errors[(daemon,text[:300])] += 1
          except (ValueError,TypeError,AttributeError) as exc:
            audit.missing(f'{path}:{line_no}: JSON 해석 실패: {exc}')
    except OSError as exc:
      audit.missing(f'{path}: {exc}')
  if not records: audit.missing('읽은 로그 레코드 0개')
  if errors or crashes: audit.review('부팅 후보 로그의 ERROR/crash 원인 확인 필요')
  return emit(audit,files=[str(p) for p in files],records=records,levels=dict(levels),crashes=crashes[:20],
              crash_count=len(crashes),error_count=sum(errors.values()),
              error_examples=[dict(daemon=k[0],message=k[1],n=n) for k,n in errors.most_common(20)],
              jetlink_count=sum(jets.values()),jetlink_examples=[dict(daemon=k[0],message=k[1],n=n) for k,n in jets.most_common(20)],
              scope='파일 mtime 기반 후보 범위. 시계 보정 전 닫힌 파일 누락/이전 부팅 혼입 가능. ERROR 0도 부팅 전체 무오류 보증 아님.')


if __name__ == '__main__': raise SystemExit(main())
