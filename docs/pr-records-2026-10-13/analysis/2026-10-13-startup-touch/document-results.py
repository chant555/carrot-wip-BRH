from pathlib import Path
import json
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
root = Path(__file__).resolve().parents[2]
p = Path(__file__).resolve().parent
rows = [json.loads(s) for s in (p/'events.jsonl').read_text().splitlines()]
summary = {}
for phase in ('baseline','fixed'):
 presses=[r for r in rows if r['kind']=='press' and r['phase']==phase]
 summary[phase]={'press_count':len(presses),'hits':dict(Counter(r['hit'] for r in presses)),'positions':[[r['x'],r['y']] for r in presses]}
result = {'status':'diagnostic_verified_original_state_restored_backup_deleted','device_branch':'carrot-wip-brh','device_head':'8399bb8362c1f2e833c9d507865588e23ac5728a','source_base':'626b887d527ff3c619e885ff65c303255e2933c6','source_matches_original_device':True,'phases':summary,'patch_check':json.loads((p/'patch-check.json').read_text()),'local_tests_passed':5,'production_patch_installed':False,'reboot_performed':False,'recovery_actions_enabled':False,'center_area_verified':False,'same_frame_press_release_verified':False,'extra_press_in_last_sequence_unexplained':True,'restoration_matched':json.loads((p/'before.json').read_text())==json.loads((p/'after.json').read_text()),'healthcheck_exit':int((p/'restored-boot-check.exit').read_text()),'healthcheck_functional_passed':4,'healthcheck_log_error_count':5,'healthcheck_log_errors':['athenad.ws_recv.exception (4)','athenad.ws_send.exception (1)'],'healthcheck_crashes':0,'backup_deletion':json.loads((p/'backup-deletion.json').read_text())}
(p/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(p/'user-observations.json').write_text(json.dumps([
 {'phase':'baseline','request':'왼쪽·오른쪽·가운데를 각각 두 번 누르도록 요청했습니다.','reply':'화면에 버튼은 두개가 나온다. 왼쪽 오른쪽을 두번씩 눌렀다'},
 {'phase':'fixed','request':'왼쪽과 오른쪽을 두 번씩, 왼쪽을 빠르게 세 번, 오른쪽을 약 2초간 누르도록 요청했습니다.','reply':'순서대로 눌렀고 숫자가 증가합니다.'},
 {'phase':'fixed-extra','request':'오른쪽 중앙 한 번, 가운데 표시 영역 두 번, 위 제목 한 번, 왼쪽 중앙을 아주 짧게 다섯 번 누르도록 요청했습니다.','reply':'모두 눌렀습니다.'}],ensure_ascii=False,indent=2)+'\n')
start=datetime.fromtimestamp(rows[0]['time'],ZoneInfo('Asia/Seoul')).isoformat()
end=datetime.fromtimestamp(rows[-1]['time'],ZoneInfo('Asia/Seoul')).isoformat()
validation=f'''2026-10-13 시동 실패 화면의 터치 비교 시험과 패치 D 검토입니다.

1. 결론과 범위입니다.
입력 갱신을 끄면 실제 누름 네 번이 감지되지만 좌표는 모두 (0, 0)이며 버튼 밖으로 판정됩니다.
같은 프로세스에서 poll_input_events() 호출을 켜면 실제 좌표가 갱신되고 두 버튼이 판정됩니다.
따라서 이번 기기의 재현에서는 좌표 갱신 누락이 버튼 무응답을 일으키는 것을 확인했습니다.
시험한 upstream 626b887d와 운용 브랜치 8399bb83의 화면 소스 해시는 같습니다.
패치 A가 수정하지 않은 기존 화면의 문제이며, 원인 보완을 독립적인 패치 D로 준비했습니다.
실제 재빌드 요청·삭제·업데이트·재부팅 동작은 진단에 연결하지 않았습니다.
D를 실제 시동 실패 화면에 적용해 재빌드까지 완료한 시험은 아닙니다.

2. 시험 환경과 실행입니다.
기기는 carrot-wip-brh의 8399bb8362c1f2e833c9d507865588e23ac5728a이며 IsOnroad=0입니다.
진단은 {start}부터 {end}까지 실행했습니다.
536×240 화면과 기기에 설치된 COMMA 백엔드를 사용했습니다.
startup_recovery_baseline.py는 626b887d의 원본이며 진단은 그 TouchPress와 draw_screen을 사용했습니다.
표시 문구와 계수만 바꾸고 RecoveryUpdate는 생성하지 않았습니다. 코드의 입력 갱신 유무만 단계별로 전환했습니다.
원래 저장소·캐시·브랜치를 변경하지 않고 별도 폴더에서 실행했습니다.
comma 서비스를 잠시 정지했으며 진단 서비스의 ExecStopPost로 종료 후 자동 복구했습니다.
처음 실행은 파이썬 실행 인자 때문에 pyray를 찾지 못해 실패했고 자동 복구됐습니다.
전체 실행 경로를 지정한 뒤 라이브러리 불러오기를 먼저 확인하고 재실행했습니다. 상세 내용은 diagnostic-journal.txt에 있습니다.

3. 사용자의 실제 터치와 관측 결과입니다.
첫 단계에서 사용자는 왼쪽·오른쪽 버튼을 각각 두 번 눌렀습니다.
네 번 모두 누름은 감지했으나 좌표가 (0, 0)이어서 버튼 판정은 0회입니다.
입력 갱신을 켠 첫 순서에서는 총 8회이며 왼쪽 5회, 오른쪽 2회, 버튼 밖 1회입니다.
오른쪽 첫 누름은 (392, 232)로 아래 경계에 걸렸습니다. 원본 버튼 범위는 188 <= y < 232입니다.
오른쪽 길게 누르기는 약 2.34초이며 한 번만 집계됐습니다.
추가 순서에서는 10회의 누름이 관측됐습니다. 총합은 왼쪽 9회, 오른쪽 6회, 가운데 0회, 버튼 밖 3회입니다.
마지막 짧은 터치 5회 중 네 번은 왼쪽이며 한 번은 (154, 235)로 버튼 아래쪽 밖입니다.
화면 위쪽의 (145, 35)는 버튼 밖으로 판정됐습니다.

4. 과장하지 않아야 할 한계입니다.
사용자는 가운데 영역을 두 번 눌렀다고 응답했지만 해당 영역 판정은 0회였습니다.
그 순서에 대응하는 기록은 오른쪽 버튼의 (293, 220), (291, 221), (290, 223)입니다.
추가 지시의 누름 수는 9회였으나 실제 누름 판정은 10회였습니다.
원시 입력 보고서와 손가락 움직임을 동시에 보존하지 않아 추가 1회의 원인은 확정하지 못했습니다.
그러므로 가운데 영역 검증이나 모든 터치의 일대일 대응이 통과했다고 기록하지 않습니다.
모든 press 기록의 최종 down은 true입니다. 누름·놓음이 같은 한 프레임에서 끝나는 경우는 이번 실기로 입증하지 못했습니다.
짧은 터치가 검출되고 놓은 뒤 좌표가 유지되는 것은 보았지만 위 경계 조건의 완전한 검증과 구분합니다.
기존 화면의 두 버튼 판정 회복이 이번 실기에서 확인한 범위입니다.

5. 수정안과 로컬 검증입니다.
startup-touch-D-626b887d.patch는 실제로 불러온 raylib의 _BACKEND를 읽고 comma일 때만 입력을 갱신합니다.
현재 라이브러리의 내부 선택 값에 의존하므로 다른 raylib 버전으로 제출할 때에는 해당 선택 값도 확인해야 합니다.
일반 컴퓨터용 EndDrawing은 이미 PollInputEvents를 호출합니다. desktop-EndDrawing.txt에 설치된 라이브러리의 근거가 있습니다.
따라서 무조건 추가 호출하는 수정은 피하며 일반 컴퓨터의 새 클릭 상태를 보존합니다.
실제 수정 소스에서 버튼 처리 부분을 추출한 회귀 시험 5개가 통과했습니다.
기존 누락 재현, 두 버튼, 가운데·경계 밖, 일반 컴퓨터의 클릭 보존, 누름 없음의 동작을 확인했습니다.
입력 라이브러리는 모델로 대체한 검사이므로 전체 그래픽 환경의 실기 시험을 대신하지 않습니다.
기준 소스의 패치 적용·적용 후 파일 일치·문법 검사를 통과했습니다. 패치 해시는 patch-check.json에 있습니다.

6. 복원과 정리입니다.
시험 전후 HEAD, 브랜치, 전체 변경 목록, 추적 변경의 해시, 설정, 요청·스탬프 유무, 화면 소스, 부팅 식별자가 일치합니다.
브랜치를 전환하지 않았으므로 별도의 checkout 없이 원래 carrot-wip-brh가 유지됐습니다.
정상 화면과 manager·업데이터를 다시 실행했습니다. 재부팅과 캐시 정리를 하지 않았습니다.
복원 후 기능 점검 4개는 통과했습니다. 로그 점검은 athenad 외부 수신 오류 4건·송신 오류 1건으로 종료코드 1이며 비정상 종료는 0건입니다.
원출력을 로컬에 보존한 뒤 /data/maintenance-backups/startup-touch-20261013 및 /tmp/startup-touch-snapshot.py를 삭제했습니다.
다른 유지보수 백업은 삭제 대상이 아닙니다. backup-deletion.json에 결과를 보존했습니다.
운용 저장소에는 D를 적용하지 않았으며 이슈와 PR(변경 사항 병합 요청)은 제출하지 않았습니다.
'''
(p/'validation.txt').write_text(validation)

latest='''## 10-13 15시대 정정: 실제 터치 비교와 별도 패치 D

[이전 터치 분석](../analysis/2026-10-13-rebuild-A-recovery/touch-analysis.txt)의 원인 후보를 실제 기기에서 비교했습니다. 원본 `TouchPress`와 화면 배치를 사용하는 진단에서 입력 갱신을 끄면 누름 네 번의 좌표가 모두 `(0, 0)`으로 남았고 버튼 밖으로 판정됐습니다. 같은 과정에서 입력 갱신을 켜자 좌표와 두 버튼의 판정이 회복됐습니다. 이 재현에서는 **좌표 갱신 누락이 무응답의 원인임을 확인했습니다.** `626b887d`와 운용 중인 `8399bb83`의 화면 소스 해시도 같으므로 A와 별개로 기존 화면에 있던 문제입니다.

기기용 백엔드에서만 입력을 갱신하는 [별도 패치 D](../analysis/2026-10-13-startup-touch/startup-touch-D-626b887d.patch)를 준비했습니다. 일반 컴퓨터용 `EndDrawing`은 이미 입력을 갱신하므로 무조건 추가 호출하지 않습니다. 패치 적용·문법 검사와 로컬 회귀 시험 다섯 개가 통과했습니다. D는 `626b887d` 기준의 별도 수정이며 기존 A 시험본에 합치지 않았습니다.

**실제 재빌드 동작까지 검증한 것은 아닙니다.** 진단은 누름·좌표·버튼 판정만 기록했습니다. 입력 갱신 후 판정은 왼쪽 9회, 오른쪽 6회, 가운데 0회, 버튼 밖 3회입니다. 약 2.34초간 길게 누르기는 한 번만 집계됐습니다. 아래 경계와 버튼 밖의 누름을 성공에 포함하지 않았습니다. 사용자가 가운데 영역을 눌렀다고 한 순서에서도 오른쪽 판정이 나왔으며, 추가 순서의 의도한 9회보다 한 번 많은 10회가 관측됐습니다. 이 차이의 원인은 미확정입니다. 가운데 영역과 한 프레임 안에서 끝나는 누름·놓음은 미검증으로 남깁니다.

원래 `carrot-wip-brh`의 `8399bb83`을 유지한 채 별도 진단을 실행했습니다. 종료 후 정상 화면·관리 프로그램·업데이터를 복구했고 브랜치·기존 변경·설정·화면 소스·부팅 식별자가 시험 전과 일치합니다. 기능 점검 네 항목은 통과했으며 로그 점검은 외부 연결 오류 다섯 건으로 종료코드 1입니다. 이번 시험 전용 백업과 전달 도구는 삭제했습니다. 운용 코드에는 D를 적용하지 않았고 이슈와 PR(변경 사항 병합 요청)은 제출하지 않았습니다.

[상세 검증 기록](../analysis/2026-10-13-startup-touch/validation.txt), [누름·좌표 원출력](../analysis/2026-10-13-startup-touch/events.jsonl), [사용자 응답](../analysis/2026-10-13-startup-touch/user-observations.json), [최종 판정](../analysis/2026-10-13-startup-touch/results.json), [백업 삭제](../analysis/2026-10-13-startup-touch/backup-deletion.json)를 보존했습니다.
'''
for name in ('Rebuild-All-이슈요약-261011.md','Rebuild-All-이슈본문-261011.md','Rebuild-All-PR본문-261013.md'):
 f=root/'docs'/name
 s=f.read_text()
 if name=='Rebuild-All-이슈요약-261011.md':
  s=s.replace('기기 본체 시동 실패 화면의 터치 무응답은 미해결입니다.','기기 본체의 터치 무응답은 후속 진단에서 원인과 버튼 판정 회복을 확인했습니다. 별도 패치 D를 준비했으며 운용 코드에는 적용하지 않았습니다.')
  s=s.replace('본체 시동 실패 화면의 터치는 사용자가 무응답을 확인했으며 수정·재검증이 필요합니다.','본체 시동 실패 화면의 터치는 후속 진단에서 좌표 갱신 누락과 버튼 판정 회복을 확인했습니다. D를 적용한 실제 복구 동작과 아래에 기록한 입력 경계 조건은 추가 검증이 필요합니다.')
 elif name=='Rebuild-All-이슈본문-261011.md':
  s=s.replace('본체 터치 무응답은 미해결이며 아래에 구분합니다.','본체 터치 무응답은 후속 진단에서 원인과 버튼 판정 회복을 확인했으며 아래에 구분합니다. 운용 코드에는 수정안을 적용하지 않았습니다.')
  s=s.replace('본체 시동 실패 화면의 터치는 무응답으로 확인됐으며 수정·재검증이 필요합니다.','본체 시동 실패 화면의 터치는 후속 진단에서 원인과 버튼 판정 회복을 확인했습니다. 실제 재빌드와 연결한 수정본의 검증은 남아 있습니다.')
 else:
  s=s.replace('본체 터치 버튼의 수정과 실제 터치 재검증이 필요합니다.','별도 패치 D의 입력 갱신은 실제 진단에서 버튼 판정을 회복시켰습니다. A와 D를 함께 적용한 본체 버튼의 실제 복구 검증은 남아 있습니다.')
 s += '\n\n' + latest
 f.write_text(s)

handoff=root/'HANDOFF.md'
s=handoff.read_text()
block='''## 2026-10-13 15시대 터치 비교 완료 — 원인 확인, D 초안, 원상 복구·백업 삭제

- 사용자의 실제 터치로 입력 갱신 없음에서 누름 4회·좌표 `(0, 0)`·버튼 판정 0회를 확인했습니다. 입력 갱신을 켜자 두 버튼 판정이 회복됐습니다. 기존 `8399bb83`과 시험 기준 `626b887d`의 화면 소스는 같습니다.
- [패치 D](analysis/2026-10-13-startup-touch/startup-touch-D-626b887d.patch)는 기기용 백엔드에만 입력 갱신을 추가합니다. 로컬 회귀 시험 5개와 패치 적용 검사가 통과했습니다. A에는 합치지 않았고 운용 코드에도 적용하지 않았습니다.
- 가운데 영역 판정은 0회이며 추가 순서의 의도보다 누름이 1회 더 기록됐습니다. 원인은 미확정입니다. 한 프레임에서 끝나는 누름·놓음과 실제 재빌드 연동도 미검증입니다. 성공 범위를 두 버튼의 입력 판정 회복으로 한정합니다.
- 기기는 `carrot-wip-brh`의 `8399bb83`이며 기존 변경·설정·화면 소스·부팅 식별자가 일치합니다. 브랜치 전환과 재부팅 없이 별도 진단 후 정상 화면·관리 프로그램·업데이터를 복구했습니다. 기능 점검 4개 통과, 로그 점검은 외부 연결 오류 5건으로 종료코드 1입니다.
- 이번 터치 시험 백업과 전달 도구는 삭제했습니다. [상세 기록](analysis/2026-10-13-startup-touch/validation.txt), [최종 판정](analysis/2026-10-13-startup-touch/results.json), [삭제 결과](analysis/2026-10-13-startup-touch/backup-deletion.json)를 보존했습니다. 이슈와 PR(변경 사항 병합 요청)은 제출하지 않았습니다. 아래의 터치 ‘원인 후보·미해결’은 이번 진단 이전 기록입니다.

'''
s=s.replace('\n\n','\n\n'+block,1)
handoff.write_text(s)
f=root/'index.md';s=f.read_text()
marker='- [Rebuild All 최신 검증 요약]'
i=s.index(marker)
s=s[:i]+'- **[10-13 15시대 후속]** [본체 터치 진단](analysis/2026-10-13-startup-touch/validation.txt)에서 입력 갱신 누락과 두 버튼의 판정 회복을 확인했습니다. [패치 D](analysis/2026-10-13-startup-touch/startup-touch-D-626b887d.patch)를 별도로 준비했습니다. 가운데 영역·추가 누름·실제 복구 연동의 제한을 기록했고, 원래 상태 복구와 시험 백업 삭제를 마쳤습니다. 운용 코드에는 적용하지 않았습니다.\n'+s[i:]
f.write_text(s)
# Preserve the earlier observation and append the newer evidence rather than rewriting history.
f=root/'analysis/2026-10-13-rebuild-A-recovery/touch-analysis.txt'
s=f.read_text()+'\n[2026-10-13 15시대 정정] 후속 실제 터치 진단에서 입력 갱신 없음은 누름 4회의 좌표가 모두 (0, 0)이었고, 입력 갱신을 켜자 두 버튼 판정이 회복됐습니다. 별도 패치 D를 준비했습니다. 가운데 영역·추가 누름·실제 재빌드 연동의 제한은 ../2026-10-13-startup-touch/validation.txt에 기록했습니다. 운용 코드에는 적용하지 않았습니다.\n'
f.write_text(s)
print('검증 결과와 이슈·병합 요청 초안, 요약·인계·색인을 갱신했습니다.')
