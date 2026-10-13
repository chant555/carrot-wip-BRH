from pathlib import Path
import json,re,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
p=Path(__file__).resolve().parent;root=p.parents[1]
load=lambda name:json.loads((p/name).read_text())
request=load('physical-button-request.json');before=load('source-evidence-before.json');after=load('source-evidence-after.json');restored=load('restored-state.json');final=load('final-runtime.json');deleted=load('backup-deletion.json')
assert before==after
ready=next(datetime.fromisoformat(s.split()[0]) for s in (p/'rebuilt-wait.log').read_text().splitlines() if s.endswith(' ready'))
requested=datetime.fromisoformat(request['request_observed_at']);elapsed=(ready-requested).total_seconds()
press=[json.loads(s) for s in (p/'touch.jsonl').read_text().splitlines()]
hit=next(r for r in press if r['event']=='press');action=next(r for r in press if r['event']=='action');reboot=next(r for r in press if r['event']=='reboot')
assert hit['hit']=='rebuild' and action['accepted'] and reboot['request_exists']
cleanup=(p/'physical-button-cleanup.log').read_text();count=sum(s.startswith('Removed /data/scons_cache/') for s in cleanup.splitlines())
assert 'state/cache reset done (full build still pending)' in cleanup
keys=('original_head_restored','original_dirty_patch_identical','original_status_identical','original_git_config_identical','original_web_settings_identical','control_params_restored','user_settings_match')
assert all(restored[k] for k in keys)
health={}
for phase in ('rebuilt','restored'):
 checks={}
 for part in re.split(r'^=== ',(p/(phase+'-boot-check.txt')).read_text(),flags=re.M)[1:]:
  name,body=part.split('\n',1);r=json.loads(body);checks[name]={'exit_code':r['exit_code'],'findings':r['findings']}
 assert len(checks)==5
 health[phase]=checks
solvers=load('rebuilt-solvers.json');healthy=load('healthy-solvers.json')
assert [r['c_sha256'] for r in solvers['solvers']]==[r['c_sha256'] for r in healthy['solvers']]
assert all(r['returncode']==0 for r in solvers['imports'])
assert all(r['absent_after'] for r in deleted['targets'])
result={'status':'physical_short_press_recovery_verified_restored_backups_deleted','base_commit':before['head'],'patches':before['patches'],'source_before_after_identical':True,'user_action':load('user-actions.json'),'touch':{'press':hit,'action':action,'reboot':reboot},'request_at':requested.isoformat(),'ready_at':ready.isoformat(),'elapsed_seconds_including_observation_delay':elapsed,'cache_files_removed':count,'solvers':solvers,'healthchecks':health,'restoration':{k:restored[k] for k in keys},'final_runtime':final,'backup_deletion':deleted,'limitations':['One short physical press with A+D(v2)+E; not a reliability percentage.','Earlier A+D first missed touch remains unexplained because no coordinates were retained.','Boundary and busy-message diagnosis used a no-action diagnostic screen; busy refusal was also locally tested.','Recontact origin remains undetermined; no debounce introduced.','A lacks B concurrency protection; B and C were not applied.','No issue or pull request published.']}
(p/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
healthtext='\n'.join(f"- {phase}: "+', '.join(f"{name}={v['exit_code']}" for name,v in checks.items()) for phase,checks in health.items())
text=f'''# 2026-10-13 A+D+E 본체 버튼 실제 복구 시험

사용자가 본체 시동 실패 화면의 왼쪽 버튼을 평소처럼 짧게 한 번 눌렀고, 첫 시도에서 요청 생성 → 재부팅 → 정리 → 전체 빌드 → 정상 기동을 확인했습니다. 추가 관측 코드를 중간에 넣거나 길게 누르도록 다시 요청하지 않았습니다. 파일 기록은 시험에 사용한 D 수정본의 기능입니다. 웹 버튼이나 터미널로 요청을 대신 만들지 않았습니다.

기준은 `626b887d`이며 A와 D 두 번째 수정본, 별도 사용성 패치 E를 적용했습니다. B와 C는 제외했습니다. 원래 `carrot-wip-brh`의 `8399bb83`과 기존 수정·설정·저장소·캐시를 먼저 백업했습니다. 기기 내부 정리 검증 12개와 로컬 입력·기록 검증 8개가 통과했습니다. 패치 적용 후 정상 기동을 확인하고, 추적되지 않는 생성 솔버 소스에 `#error C4_ADE_SCREEN_COMPILE_TEST`를 넣어 실제 컴파일 실패와 본체 실패 화면을 확인했습니다.

재부팅 후에도 남은 [터치 원출력](touch.jsonl)에 좌표 `({hit['x']:.0f}, {hit['y']:.0f})`, `hit=rebuild`, 작업 수락, 재부팅 직전 요청 파일 존재가 기록됐습니다. 누름 당시 상태는 `{hit['state']}`였습니다. 터치 길이 자체는 이 로그에서 측정하지 않았으며, 짧게 한 번 누르라는 요청과 사용자의 재부팅 응답을 [조작 기록](user-actions.json)에 보존했습니다.

요청 관측은 {requested.astimezone(ZoneInfo('Asia/Seoul')).isoformat()}이며, 정상 기동 관측은 {ready.isoformat()}입니다. 약 {elapsed:.1f}초로 관측 간격의 지연을 포함합니다. [정리 로그](physical-button-cleanup.log)에는 캐시 파일 {count:,}개의 삭제와 초기화 완료가 있습니다. 두 솔버 소스의 해시는 시험 전 정상값과 일치하며 시험용 오류가 사라졌습니다. 두 솔버와 `plannerd`를 실제로 불러오는 검증도 통과했습니다. [빌드 화면 원출력](rebuilt-pane.log)과 [솔버 확인](rebuilt-solvers.json)을 보존했습니다.

기기 점검의 종료코드는 다음과 같습니다. 세부 내용은 각 원출력과 [최종 판정](results.json)에 보존했습니다.

{healthtext}

복원 비교 일곱 항목이 모두 일치했습니다. 원래 모델 해시와 설정, 저장소·캐시를 복원했으며 정상 화면·관리 프로그램·업데이터를 확인했습니다. [최종 상태](final-runtime.json)의 업데이트 준비 영역 값은 해당 관측 시점에 한정됩니다. 시험 브랜치와 요청 파일은 남아 있지 않습니다. 영구 터치 기록 파일도 시험 전 상태로 복원했습니다. [백업 삭제](backup-deletion.json)에 따라 이번 시험 백업과 전달 폴더를 삭제했으며 다른 유지보수 백업과 공통 잠금 파일은 유지했습니다.

이번 성공은 A+D+E 조합의 단일 실기 사례입니다. 모든 짧은 터치의 성공률을 입증하거나, 좌표 기록이 없던 이전 A+D 첫 실패의 원인을 확정하지 않습니다. [앞선 진단](../2026-10-13-touch-followup/validation.md)에서 아래 경계의 누름 실패와 확장 후 판정, 같은 입력 묶음의 짧은 접촉 좌표 보존을 확인했습니다. 의도한 횟수보다 접촉이 추가로 잡힌 원인은 남아 있습니다. E의 작업 중 안내는 진단 화면과 로컬 코드 검증으로 확인했으며 실제 업데이트 작업을 일부러 오래 실행하지는 않았습니다.

이슈와 풀 리퀘스트는 로컬 초안만 수정하며 게시하지 않았습니다.
'''
(p/'validation.md').write_text(text)
for name in ('startup-touch-D-626b887d-v2.patch','startup-touch-usability-E-626b887d.patch'):
 (root/'docs'/name).write_bytes((p/name).read_bytes())
latest=f'''## 10-13 후속 정정: 터치 경계 진단과 A+D+E 첫 누름 복구

[후속 진단](../analysis/2026-10-13-touch-followup/validation.md)에서 기존 버튼 아래 경계 밖의 누름을 재현했고, 아래쪽 영역을 넓히자 판정됐습니다. 가운데 영역도 판정됐으며, 같은 읽기 묶음에 누름과 놓음이 들어온 짧은 접촉의 좌표가 보존된 사례를 확인했습니다. 의도한 세 번이 네 접촉으로 잡힌 현상은 원시 입력에도 나타났습니다. 접촉 흔들림의 원인은 미확정이므로 임의의 입력 억제 시간은 추가하지 않았습니다.

[새 D](startup-touch-D-626b887d-v2.patch)는 실제로 로드된 기기용 백엔드에서 입력을 갱신하고 터치·판정·수락·재부팅 기록을 파일에 남깁니다. 일반 컴퓨터에서 중복 갱신하지 않으며, 원시 입력 장치가 열렸는지만으로 백엔드를 판단하지 않습니다. 기록 실패는 복구를 막지 않습니다. [별도 E](startup-touch-usability-E-626b887d.patch)는 버튼 영역을 아래 끝까지 넓히고 작업 거부 시 안내를 표시합니다. 두 패치는 `626b887d` 기준이며 D → E 순서입니다. 이전 D의 원출력과 패치는 당시 시험 근거로 유지합니다.

A+D+E 실제 시험에서는 사용자가 본체 버튼을 평소처럼 짧게 한 번 누른 첫 시도에서 복구됐습니다. 재부팅 후에도 좌표 `({hit['x']:.0f}, {hit['y']:.0f})`, 리빌드 판정, 요청 수락과 요청 파일 존재가 남았습니다. 캐시 파일 {count:,}개를 정리한 뒤 약 {elapsed/60:.2f}분 만에 정상 기동했고, 시험용 컴파일 오류가 사라졌으며 두 솔버와 `plannerd` 불러오기가 통과했습니다. 짧은 누름의 길이를 수치로 측정한 것은 아닙니다.

원래 브랜치·기존 수정·모델·캐시·설정을 복원했고 시험 브랜치와 이번 백업·전달 폴더를 삭제했습니다. 운용 코드에는 시험 패치를 남기지 않았습니다. [실기 검증](../analysis/2026-10-13-rebuild-ADE-screen/validation.md), [터치 기록](../analysis/2026-10-13-rebuild-ADE-screen/touch.jsonl), [최종 판정](../analysis/2026-10-13-rebuild-ADE-screen/results.json), [복원 비교](../analysis/2026-10-13-rebuild-ADE-screen/restored-state.json), [백업 삭제](../analysis/2026-10-13-rebuild-ADE-screen/backup-deletion.json)를 연결합니다.

이는 해당 조건의 한 번의 성공이며 모든 짧은 누름이 해결됐다는 보장은 아닙니다. 이전 A+D 첫 무응답의 원인은 여전히 미확정입니다. 앞선 ‘가운데·같은 묶음의 짧은 접촉 미검증’ 표기는 당시 시험 범위이며, 이번 결과로 해당 사례를 보완합니다. A의 동시 실행 보호는 별도 B의 범위입니다. 이슈와 풀 리퀘스트는 게시하지 않았습니다.
'''
for name in ('Rebuild-All-이슈요약-261011.md','Rebuild-All-이슈본문-261011.md','Rebuild-All-PR본문-261013.md'):
 f=root/'docs'/name;s=f.read_text()
 if name=='Rebuild-All-이슈요약-261011.md':
  s=s.replace('별도 패치 D를 준비했으며 운용 코드에는 적용하지 않았습니다.', 'D의 파일 기록과 별도 E의 사용성 개선을 준비했고, A+D+E 후속 시험에서 짧게 한 번 누른 첫 시도의 실제 복구를 확인했습니다. 운용 코드에는 시험 패치를 남기지 않았습니다.',1)
  s=s.replace('A+D의 실제 복구는 후속 두 번째 터치에서 확인했습니다. 첫 무응답과 입력 경계 조건은 추가 검증이 필요합니다.', '이전 A+D의 두 번째 터치에 이어 A+D+E 후속 시험에서는 짧게 한 번 누른 첫 시도에서 실제 복구됐습니다. 아래 경계와 짧은 접촉은 후속 진단으로 보완했지만, 이전 첫 무응답과 추가 접촉의 원인은 미확정입니다.',1)
 if name=='Rebuild-All-PR본문-261013.md':
  s=s.replace('A와 D를 함께 적용한 후속 시험에서는 관측 출력 추가와 약 1초 누름 조건의 두 번째 터치로 실제 복구됐습니다. 첫 무응답의 원인은 미확정이며 모든 짧은 터치의 신뢰성을 입증한 것은 아닙니다.', '최신 A+D+E 시험에서는 짧게 한 번 누른 첫 시도에서 실제 복구됐고 좌표와 수락 기록도 보존됐습니다. 이전 A+D 첫 무응답의 원인은 미확정이며 모든 짧은 터치의 신뢰성을 입증한 것은 아닙니다.',1)
  s=s.replace('요청 처리 상태의 영속적 기록과 재시도 횟수 제한은 아직 없으며,', 'D에 터치와 요청 수락 기록을 추가했지만 전체 복구 단계의 상태 관리와 재시도 횟수 제한은 아직 없으며,',1)
 f.write_text(s+'\n\n'+latest)
f=root/'HANDOFF.md';s=f.read_text();cut=s.index('## 2026-10-13 16시대 A+D')
f.write_text(f'''# 인계 문서 — C4_500 세션

## 2026-10-13 A+D+E 후속 시험 완료: 복원·백업 삭제 완료

짧게 한 번 누른 첫 시도에서 본체 리빌드 요청과 재부팅 후 실제 복구를 확인했습니다. 좌표 `({hit['x']:.0f}, {hit['y']:.0f})`와 수락 기록이 남았으며 캐시 파일 {count:,}개를 정리했습니다. 원래 `carrot-wip-brh`의 `8399bb83`, 기존 수정·모델·캐시·설정을 복원했습니다. 시험 브랜치·백업·전달 폴더는 삭제했습니다. 이슈와 풀 리퀘스트는 게시하지 않았습니다.

[진단 기록](analysis/2026-10-13-touch-followup/validation.md), [실기 결과](analysis/2026-10-13-rebuild-ADE-screen/validation.md), [최종 판정](analysis/2026-10-13-rebuild-ADE-screen/results.json), [새 D](docs/startup-touch-D-626b887d-v2.patch), [별도 E](docs/startup-touch-usability-E-626b887d.patch)를 보존했습니다. 이전 첫 무응답과 추가 접촉의 원인은 미확정입니다. 아래 기록은 앞선 시험의 조건과 한계입니다.

'''+s[cut:])
f=root/'index.md';s=f.read_text();marker='- **[10-13 16시대 후속]**';i=s.index(marker);f.write_text(s[:i]+'- **[10-13 후속 완료]** [터치 진단](analysis/2026-10-13-touch-followup/validation.md)과 [A+D+E 본체 버튼 실기 시험](analysis/2026-10-13-rebuild-ADE-screen/validation.md)을 마쳤습니다. 짧게 한 번 누른 첫 시도에서 복구됐고 좌표와 수락 기록을 보존했습니다. 원래 상태로 복원하고 시험 백업을 삭제했습니다.\n'+s[i:])
print(json.dumps({'elapsed_seconds':elapsed,'cache_files_removed':count,'healthchecks':health,'restoration':result['restoration']},ensure_ascii=False))
