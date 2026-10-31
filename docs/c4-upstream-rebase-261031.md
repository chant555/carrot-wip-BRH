# 2026-10-31 상류 8개 커밋 리베이스와 `CarState` 번호 충돌 정정

## 반영 범위

상류 `carrot-wip`의 `34caa6ecbf78c17a2b28122bfeaf8a0e8fa1e366` 이후 8개 커밋을 `7e88bb724d9ccad2480673e866f606e0934d4caa`까지 반영했습니다. `carrot-wip-brh`의 사용자 커밋 16개와 `carrot-wip-loc`의 사용자 커밋 15개를 새 상류 위에 다시 적용했습니다. 두 브랜치의 파일 차이는 이전과 같이 `openpilot/selfdrive/modeld/models/driving_supercombo.onnx` 하나입니다.

| 상류 커밋 | 내용 | C4 영향 |
| --- | --- | --- |
| `d66d445b`, `7e03c763`, `10bf0a56` | 외부 GPU·젯슨용 주행 모델 Light speed를 외부 모델 목록에 추가했습니다. 기본 모델은 N16 그대로입니다. | C4에는 외부 USB GPU가 없고 이 모델을 선택하지 않았으므로 영향이 없습니다. |
| `8429f745`, `7e88bb72` | 다른 차량의 Light speed 프레임 손실·시간 초과 분석 문서입니다. | 동작 변경이 없습니다. |
| `dcd5f9eb` | 젯슨 쪽 ATC(자동 턴 제어) 방향지시등의 회전 통과 추적과 미점등 1회 재요청을 추가했습니다. | `AutoBlinkerControl=0`이므로 영향이 없습니다. |
| `f85599bd` | 아이오닉 5 PE `modeld`에 수동 경계 접근 관찰 기록기를 추가했습니다. 램프·조향 요청은 만들지 않습니다. | `ManualLaneChangeIndicator=0`이면 기록을 내지 않습니다. |
| `71518339` | 수동 조향 방향지시를 확인된 옆 차로 방향으로만 요청하도록 좁히고 `CarState.laneLineInfoMonoTime @112`를 추가했습니다. | 기능은 꺼져 있지만 아래 번호 충돌의 원인입니다. |

## 번호 충돌과 정정

사용자 필드 `independentSoftHoldReady`는 10-27 리베이스부터 `CarState`의 `@112`를 썼습니다. 상류 `71518339`가 같은 구조체에 `laneLineInfoMonoTime @112`를 추가했습니다. 두 변경은 파일의 다른 위치에 있어서 `git rebase`와 `git merge-file`은 충돌 표시 없이 병합합니다. 그러나 병합된 `car.capnp`는 `Duplicate ordinal number`로 컴파일되지 않으며, 그대로 기기에 올리면 빌드가 실패합니다.

상류 번호는 바꾸지 않고, 사용자 필드를 다음 빈 번호 `@113`으로 옮겼습니다. 이 정정은 필드를 처음 넣은 커밋(`fix: allow independent SoftHOLD before first cruise button press`)과 번호 검사를 넣은 커밋(`Reduce independent soft hold wait to ten seconds and verify upstream integration`)에 합쳤습니다. 따라서 리베이스된 모든 커밋에서 `car.capnp`가 컴파일됩니다. 검사 `test_independent_hold_schema_roundtrip_does_not_alias_auto_indicator`는 이제 두 필드의 직렬화·복원과 `@113`·`@112` 번호를 함께 확인합니다.

코드는 필드 이름으로 읽고 쓰므로 `carstate.py`, `hyundaicanfd.py`, `cruise.py`의 동작은 바뀌지 않습니다. 10-30 이전에 기록한 로그는 `@112`가 독립 홀드 준비 값이므로, 그 로그는 당시 스키마로 해석해야 합니다. 새 스키마로 읽으면 이 필드만 다르게 해석됩니다.

## 다음 리베이스 절차

사용자 `CarState` 필드는 상류가 다음 번호를 추가할 때마다 다시 겹칠 수 있습니다. 충돌 표시가 없어도 아래를 확인합니다.

1. 리베이스 후 `opendbc_repo/opendbc/car/car.capnp`를 pycapnp로 컴파일합니다. `Duplicate ordinal number`가 나오면 상류 필드 번호를 유지합니다.
2. 사용자 필드를 `CarState` 최상위의 가장 큰 번호 + 1로 옮깁니다. 필드를 넣은 커밋과 번호 검사 커밋에 각각 `git commit --fixup`으로 정정하고 `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <상류>`로 합칩니다.
3. `test_independent_soft_hold.py`의 번호 검사를 새 번호로 고치고, 새 상류 필드도 직렬화 검사에 넣습니다.
4. 리베이스된 모든 커밋에서 `car.capnp`가 컴파일되는지 확인하고, 이전 로그의 해석 기준이 바뀐다는 점을 기록합니다.

## 검사 결과와 한계

- 사용자 핵심 검사(원터치 4회 제한, 방향지시 유지, 정지 제어, 독립 SoftHOLD, 레버 차로변경, 차간거리 회복) 391개가 통과했습니다.
- 현대 차량·크루즈 검사 2,292개, 제어 검사 1,134개, 상류 방향지시·경계 관찰·모델 목록 검사 601개, `modeld` 외부 모델 검사 83개, 문서 생성·검증 검사 32개가 통과했습니다.
- 개인용 컴퓨터에 `msgq`, `casadi`, `zmq`, `hypothesis`, `pyray` 같은 네이티브·선택 모듈이 없어 실패하거나 수집되지 않은 검사가 있습니다. 리베이스 전 `ddbc2fa`에서 같은 검사를 실행해 비교했고, 리베이스 후 새로 생긴 실패는 없습니다.
- 상류만 바꾼 파일 43개는 상류와 같고, 상류와 겹치지 않는 사용자 수정 파일은 번호 정정 2개를 빼면 이전과 같습니다. `cruise.py`는 리베이스 전과 같습니다.
- 이 결과는 로컬 회귀·정적 검사입니다. 기기 빌드·부팅 결과와 실제 주행 동작은 외부 작업 기록에 따로 남깁니다.
