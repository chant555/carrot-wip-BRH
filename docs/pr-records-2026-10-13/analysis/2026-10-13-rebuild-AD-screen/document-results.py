from pathlib import Path
import json,re,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
p=Path(__file__).resolve().parent;root=p.parents[1]
request=json.loads((p/'physical-button-request.json').read_text())
ready_line=next(s for s in (p/'rebuilt-wait.log').read_text().splitlines() if s.endswith(' ready'))
ready=datetime.fromisoformat(ready_line.split()[0]);requested=datetime.fromisoformat(request['request_observed_at'])
elapsed=(ready-requested).total_seconds()
restored=json.loads((p/'restored-state.json').read_text())
final=json.loads((p/'final-runtime.json').read_text())
source_before=json.loads((p/'source-evidence-before.json').read_text());source_after=json.loads((p/'source-evidence-after.json').read_text())
assert source_before==source_after
health={}
for phase in ('rebuilt','restored'):
 checks={}
 for part in re.split(r'^=== ',(p/(phase+'-boot-check.txt')).read_text(),flags=re.M)[1:]:
  name,body=part.split('\n',1);r=json.loads(body);checks[name]={'exit_code':r['exit_code'],'findings':r['findings']}
 health[phase]=checks
 assert len(checks)==5 and all(r['exit_code']==0 for r in checks.values())
cleanup=(p/'physical-button-cleanup.log').read_text()
r={'status':'physical_button_recovery_confirmed_on_second_attempt_with_observation_prints_restored_backups_deleted','base_commit':source_before['head'],'patches':source_before['patches'],'first_touch':{'operator':'user','source_variant':'A+D','response':'no visible response','request_observed':False,'cause':'undetermined; no press coordinates retained'},'second_touch':{'operator':'user','source_variant':'A+D plus two observation-only print statements','requested_hold_seconds':1,'response':'reboot started','request_observed_at':requested.isoformat(),'ready_observed_at':ready.isoformat(),'elapsed_seconds_with_observation_delay':elapsed,'touch_coordinates_retained':False},'cleanup':{'removed_cache_files':sum(s.startswith('Removed /data/scons_cache/') for s in cleanup.splitlines()),'removed_file_lines':sum(s.startswith('Removed ') and not s.startswith('Removed directory ') for s in cleanup.splitlines()),'removed_directories':sum(s.startswith('Removed directory ') for s in cleanup.splitlines()),'reset_completed':'state/cache reset done (full build still pending)' in cleanup},'solvers':json.loads((p/'rebuilt-solvers.json').read_text()),'healthchecks':health,'source_matches_before_after_trace_removal':True,'restoration_checks':{k:restored[k] for k in ('original_head_restored','original_dirty_patch_identical','original_status_identical','original_git_config_identical','original_web_settings_identical','control_params_restored','user_settings_match')},'final_runtime':final,'backup_deletion':json.loads((p/'backup-deletion.json').read_text()),'limitations':['First touch failed and its cause is not determined.','Successful attempt included observation-only print statements and a requested one-second hold.','No proof that every brief tap succeeds; center area and same-frame press/release remain outside this test.','No issues or pull requests published.']}
assert all(r['restoration_checks'].values())
(p/'results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
(p/'validation.txt').write_text(f'''2026-10-13 A+D와 본체 시동 실패 화면의 실제 복구 시험입니다.

1. 결론과 제한입니다.
두 번째 본체 터치에서 요청 생성 → 재부팅 → 생성물·캐시 정리 → 전체 빌드 → 정상 기동을 확인했습니다.
첫 터치는 A+D만 적용한 상태에서 무응답이었고 요청도 생성되지 않았습니다.
두 번째는 좌표와 버튼 판정을 출력하는 임시 관측 두 줄을 추가하고 약 1초간 누르도록 요청한 조건입니다.
그러므로 무관측 A+D에서 첫 누름부터 성공했다거나 모든 짧은 터치를 해결했다고 기록하지 않습니다.
첫 실패의 좌표를 확보하지 못했으며 원인은 미확정입니다. 성공한 두 번째 터치의 좌표 출력도 재부팅 전 로컬에 보존하지 못했습니다.
관측용 두 줄은 조건 분기나 요청 동작을 바꾸지 않았지만 출력에 따른 실행 시점 영향까지 배제한 시험은 아닙니다.
실제 요청 파일 감시는 읽기만 했으며 웹 버튼이나 터미널 명령으로 요청을 대신 만들지 않았습니다.

2. 기준과 보존입니다.
원래 기기는 carrot-wip-brh의 8399bb8362c1f2e833c9d507865588e23ac5728a입니다.
정차 상태를 확인하고 원래 저장소·캐시 전체, 기존 변경, 사용자·업데이트 설정을 보존했습니다.
15:50:30부터 15:52:24까지 백업했으며 codex/rebuild-AD-626b887d로 전환했습니다.
기준은 626b887d527ff3c619e885ff65c303255e2933c6이며 앞서 검증한 A와 D의 패치 해시가 그대로 일치합니다.
B와 C는 적용하지 않았고 A의 정리 단위 시험 12개가 기기에서 통과했습니다.
15:53:18에 정상 기동을 관측하고 두 솔버와 plannerd 불러오기를 확인했습니다.

3. 실제 컴파일 실패입니다.
15:53:50에 추적되지 않는 생성 솔버 소스에 #error C4_AD_SCREEN_COMPILE_TEST를 넣고 대응하는 목적 파일·공유 라이브러리를 제거했습니다.
원본 추적 소스 자체에 오류를 넣은 것은 아닙니다. 요청 정리가 생성물을 제거하고 재생성하는 경로를 시험했습니다.
재부팅 후 15:55:51에 시동 실패 화면을 관측했습니다.
compile-failure-state.json에서 컴파일 오류, SCons 실패, 본체 실패 화면 실행, manager 부재, 요청 부재를 확인했습니다.

4. 사용자 조작과 관측입니다.
첫 요청은 버튼 중앙을 한 번 누르는 것이었으며 사용자는 ‘한 번 눌렀지만 반응이 없습니다.’라고 응답했습니다.
first-touch-observation.txt에는 A+D 적용과 COMMA 백엔드 실행, 요청 부재가 기록돼 있습니다.
이후 RECOVERY_TOUCH_READY와 RECOVERY_TOUCH 출력 두 줄만 추가했습니다. touch-observation-only.patch에 정확한 차이를 보존했습니다.
같은 컴파일 오류가 유지된 상태에서 화면을 다시 띄웠고, 왼쪽 버튼 글자 중앙을 약 1초간 누르도록 요청했습니다.
사용자는 ‘재부팅이 시작됐습니다.’라고 응답했습니다. user-actions.json에 두 시도를 구분했습니다.
두 번째 요청은 한국 시각 {requested.astimezone(ZoneInfo('Asia/Seoul')).isoformat()}에 관측했습니다.
부팅 식별자는 453809f4-ea6b-41e7-a896-0dd78f0f03c0에서 4f59739f-80f6-4da1-915a-c49b0a1c491b로 바뀌었습니다.

5. 정리와 실제 복구입니다.
정리 로그에는 캐시 파일 {r['cleanup']['removed_cache_files']}개, 전체 파일 삭제 줄 {r['cleanup']['removed_file_lines']}개, 디렉터리 삭제 {r['cleanup']['removed_directories']}개가 있습니다.
scons: done cleaning targets.와 state/cache reset done (full build still pending)를 확인했습니다.
16:08:44에 정상 화면 실행을 관측했습니다. 요청 관측부터 약 {elapsed:.1f}초이며 10초 간격의 확인 지연을 포함합니다.
정상 기동 후 생성된 두 솔버 소스는 시험 전 정상 소스와 해시가 같습니다. 시험용 오류는 사라졌습니다.
두 공유 라이브러리의 초기화 심볼과 두 솔버·plannerd의 실제 불러오기가 모두 통과했습니다.
재빌드 요청 파일과 자동 복구 스탬프는 없습니다. 기기 점검 다섯 항목은 모두 종료코드 0입니다.
완료 표식은 기기 점검 도구가 당시 tmux 보존 범위에서 확인했습니다. 별도 보존한 롤링 시작 로그에는 완료 표식이 남아 있지 않습니다.
이 롤링 로그의 캐시 가져오기 문구가 0건이라는 사실만으로 캐시 미사용을 추가로 주장하지 않습니다.

6. 관측 코드 제거와 원상 복원입니다.
정상 기동 후 임시 출력 두 줄을 제거했으며 A+D 소스 전체 해시가 시험 전과 일치했습니다.
16:11:29에 원래 저장소·캐시·설정을 복원했고 재부팅 후 16:12:55에 정상 기동을 관측했습니다.
원래 커밋·브랜치, 추적 변경, 전체 상태 목록, 저장소 설정, 웹 설정, 사용자·제어 설정 비교가 모두 일치합니다.
원래 모델 소스와 모델 목록 파일의 해시도 보존본과 일치합니다.
복원 후 기기 점검 다섯 항목은 모두 종료코드 0입니다. 시험 브랜치와 요청 파일은 없으며 정상 화면·관리 프로그램·업데이터가 실행 중입니다.
업데이트 준비 영역 상태는 final-runtime.json의 관측 시점 값이며 이후 업데이터가 바꿀 수 있습니다.

7. 백업 삭제와 문서 상태입니다.
원출력을 로컬에 보존하고 복원 검증을 마친 뒤 이번 시험 백업과 전달 폴더를 삭제했습니다.
삭제한 백업의 논리적 크기는 4,915,043,042바이트이며 공통 캐시 잠금 파일은 같은 inode(파일 식별 번호) 20을 유지했습니다.
다른 유지보수 백업은 삭제 대상이 아닙니다. 실제 삭제 결과는 backup-deletion.json에 있습니다.
이슈와 PR(변경 사항 병합 요청) 문서는 로컬 초안으로 갱신했으며 제출하지 않았습니다.
''')
latest='''## 10-13 16시대 추가 시험: A+D 본체 버튼으로 실제 복구

`626b887d`에 [A](../analysis/2026-10-13-rebuild-AD-screen/rebuild_all-A-626b887d.patch)와 [D](../analysis/2026-10-13-rebuild-AD-screen/startup-touch-D-626b887d.patch)를 함께 적용했습니다. B와 C는 제외했습니다. 정상 기동을 먼저 확인한 뒤 생성된 솔버 소스에 시험용 컴파일 오류를 넣어 실제 시동 실패 화면으로 진입했습니다.

**첫 터치는 무응답이었고 두 번째 터치에서 실제 복구됐습니다.** 첫 번째는 A+D 상태에서 요청 파일이 생기지 않았습니다. 이후 입력 좌표와 기존 버튼 판정을 출력하는 [관측용 두 줄](../analysis/2026-10-13-rebuild-AD-screen/touch-observation-only.patch)을 추가하고, 사용자가 버튼 글자 중앙을 약 1초간 눌렀습니다. 그때 16:01:38에 요청이 생성되고 재부팅이 시작됐습니다. 웹 버튼이나 터미널 명령으로 요청을 대신 만들지 않았습니다.

다음 부팅에서 캐시 파일 2,522개를 포함한 생성물·빌드 상태를 정리했고, 16:08:44에 정상 기동했습니다. 약 7분 6초이며 관측 지연을 포함합니다. 시험용 오류가 사라졌고 두 솔버 소스의 해시가 시험 전 정상값으로 돌아왔습니다. 두 솔버와 `plannerd` 불러오기 및 기기 점검 다섯 항목이 모두 통과했습니다.

첫 무응답의 원인은 미확정입니다. 성공 당시에는 임시 출력 두 줄과 약 1초 누름이라는 조건이 있었으므로, **수정본에서 모든 짧은 터치가 해결됐다는 근거로 사용하지 않습니다.** 두 시도의 좌표 원출력을 보존하지 못했으므로 버튼 경계·누름 길이·입력 시점 중 무엇이 첫 실패를 일으켰는지도 단정하지 않습니다. 앞선 가운데 영역·추가 누름·한 프레임 안의 누름과 놓음 문제는 별도로 남습니다.

정상 기동 후 관측 코드를 제거해 A+D 원본 해시 일치를 확인했고, 원래 `carrot-wip-brh`의 `8399bb83`과 기존 변경·모델·캐시·설정을 복원했습니다. 복원 후 점검 다섯 항목도 통과했습니다. 이번 시험 백업과 전달 폴더는 삭제했으며 시험 브랜치도 남아 있지 않습니다. 운용 코드에는 A와 D가 남아 있지 않습니다.

[전체 검증 기록](../analysis/2026-10-13-rebuild-AD-screen/validation.txt), [사용자 조작](../analysis/2026-10-13-rebuild-AD-screen/user-actions.json), [요청 관측](../analysis/2026-10-13-rebuild-AD-screen/physical-button-request.json), [정리 로그](../analysis/2026-10-13-rebuild-AD-screen/physical-button-cleanup.log), [솔버 검증](../analysis/2026-10-13-rebuild-AD-screen/rebuilt-solvers.json), [최종 판정](../analysis/2026-10-13-rebuild-AD-screen/results.json), [복원 비교](../analysis/2026-10-13-rebuild-AD-screen/restored-state.json), [백업 삭제](../analysis/2026-10-13-rebuild-AD-screen/backup-deletion.json)를 보존했습니다. 이슈와 PR(변경 사항 병합 요청)은 제출하지 않았습니다.
'''
for name in ('Rebuild-All-이슈요약-261011.md','Rebuild-All-이슈본문-261011.md','Rebuild-All-PR본문-261013.md'):
 f=root/'docs'/name;s=f.read_text()
 if name=='Rebuild-All-이슈요약-261011.md':
  s=s.replace('D를 적용한 실제 복구 동작과 아래에 기록한 입력 경계 조건은 추가 검증이 필요합니다.','A+D의 실제 복구는 후속 두 번째 터치에서 확인했습니다. 첫 무응답과 입력 경계 조건은 추가 검증이 필요합니다.')
 elif name=='Rebuild-All-이슈본문-261011.md':
  s=s.replace('실제 재빌드와 연결한 수정본의 검증은 남아 있습니다.','후속 A+D 시험의 두 번째 터치에서 실제 재빌드 복구를 확인했습니다. 첫 무응답과 짧은 터치의 신뢰성은 남은 검증 사항입니다.')
 else:
  s=s.replace('A와 D를 함께 적용한 본체 버튼의 실제 복구 검증은 남아 있습니다.','A와 D를 함께 적용한 후속 시험에서는 관측 출력 추가와 약 1초 누름 조건의 두 번째 터치로 실제 복구됐습니다. 첫 무응답의 원인은 미확정이며 모든 짧은 터치의 신뢰성을 입증한 것은 아닙니다.')
 f.write_text(s+'\n\n'+latest)
f=root/'HANDOFF.md';s=f.read_text()
block='''## 2026-10-13 16시대 A+D 본체 버튼 복구 시험 — 복원·백업 삭제 완료

- `626b887d`에 A와 D만 적용하고 생성 솔버 소스에 실제 컴파일 오류를 넣었습니다. 첫 본체 터치는 무응답이었습니다. 이후 관측 출력 두 줄을 추가하고 약 1초간 누른 두 번째 터치에서 요청이 생성됐습니다. 첫 실패의 원인은 미확정입니다.
- 16:01:38 요청 → 캐시 파일 2,522개 정리 → 16:08:44 정상 기동을 확인했습니다. 두 솔버 소스가 정상 해시로 돌아왔고 두 솔버·`plannerd` 불러오기와 기기 점검 다섯 항목이 통과했습니다. 모든 짧은 터치가 해결됐다고 기록하지 않습니다.
- 원래 `carrot-wip-brh`의 `8399bb83`과 기존 변경·모델·캐시·설정을 복원했습니다. 복원 후 점검 다섯 항목도 통과했고 시험 브랜치·백업·전달 폴더를 삭제했습니다. 운용 코드에는 A와 D가 남아 있지 않습니다.
- [검증 기록](analysis/2026-10-13-rebuild-AD-screen/validation.txt), [사용자 조작](analysis/2026-10-13-rebuild-AD-screen/user-actions.json), [최종 판정](analysis/2026-10-13-rebuild-AD-screen/results.json), [삭제 결과](analysis/2026-10-13-rebuild-AD-screen/backup-deletion.json)를 보존했습니다. 이슈와 PR(변경 사항 병합 요청)은 제출하지 않았습니다. 아래의 실제 복구 ‘미검증’ 표기는 이번 시험 전 기록입니다.

'''
f.write_text(s.replace('\n\n','\n\n'+block,1))
f=root/'index.md';s=f.read_text();marker='- **[10-13 15시대 후속]**';i=s.index(marker)
s=s[:i]+'- **[10-13 16시대 후속]** [A+D 본체 버튼 실제 복구 시험](analysis/2026-10-13-rebuild-AD-screen/validation.txt)을 마쳤습니다. 첫 누름은 무응답이며 관측 출력 추가 후 약 1초간 누른 두 번째 시도에서 실제 재빌드와 정상 기동을 확인했습니다. 원래 브랜치·설정을 복원하고 시험 백업을 삭제했습니다.\n'+s[i:];f.write_text(s)
print(json.dumps({'elapsed_seconds':elapsed,'restoration':r['restoration_checks'],'backups_deleted':True},ensure_ascii=False))
