# 2026-11-08 음성 비서·음성 차선 변경 방향지시등 상류 14개 반영

상류 `0afb2eb3..b1c82746`의 14개를 두 브랜치에 충돌 없이 리베이스했습니다. 반영 전 끝은 `carrot-wip-brh=5c7e17b39f611409724df3a8ab7d5a35f11a17ff`·`carrot-wip-loc=feb534152ffdad11696927849a4a13cb7bf9957d`이며 `refs/backup/20261108-brh`·`refs/backup/20261108-loc`에 보존했습니다.

## 상류 변경

- 11개는 CarrotAssist 음성 비서의 안드로이드 앱, 비서 서버, Carrot Web 도구 화면과 안내 문서입니다. 차량 제어 코드는 없습니다.
- `ed1e3cdb`·`a109f648`·`b1c82746`은 음성 차선 변경의 방향지시등 경로를 일반(ordinary)·차량 자체 출력(native)·외부 수신기로 나눕니다. 장치가 없으면 일반 경로로 기존 차선 변경 조건만 적용하고, `controlsd.py`의 방향지시등 지령은 `set_lane_change_blinkers()`로 옮겨졌습니다.
- 스키마에는 `CarControl.assistantLaneSignalId @18`과 `ModelDataV2.MetaData @35·@36`이 추가됐습니다. 로컬 `CarState.independentSoftHoldReady @113`과 겹치지 않습니다.

## C4 영향

C4는 `HYUNDAI_IONIQ_5_PE`이지만 `ENABLE_BLINKERS`가 없고(`CanfdBlinkerControl=0`) `AutoBlinkerControl=0`이라 외부 수신기도 없습니다. 따라서 일반 경로이며, 음성 차선 변경의 허가 조건과 방향지시등 지령은 반영 전과 같습니다.

## 기존 수정 보존과 검사

- 상류가 건드리지 않은 사용자 수정 파일 41개·40개는 내용이 같고, 상류만 바꾼 파일 69개는 상류와 같습니다. 겹친 5개(`car.capnp`, `controlsd.py`, `desire_helper.py`, 설정 설명서 2개)의 사용자 차이도 그대로입니다.
- `git range-diff`에서 사용자 커밋 36개·35개 가운데 1개만 달라졌습니다. 상류가 주변 변수 이름(`stalk_press` → `physical_stalk_press`)을 바꿔 문맥 줄만 달라졌고, 원터치 제한으로 더한 줄은 같습니다.
- 같은 검사 묶음 7개를 반영 전·후 코드에 돌려 실패 목록을 비교했습니다.
  - 반영 뒤에 새로 생긴 실패는 세 종류이며, 모두 로컬 수정과 관계없습니다.
  - `test_lateral_startup_control.py` 10개와 `test_live_lateral_geometry.py` 1개는 `controlsd.py`의 함수 일부만 떼어 실행하는데, 상류가 새 함수 `set_lane_change_blinkers`를 검사 준비물에 넣지 않아 실패합니다. 상류 원본 `b1c82746`에서도 같은 11개가 실패합니다. 실제 `controlsd.py`는 이 함수를 정상적으로 불러옵니다.
  - 서버 묶음의 새 상류 검사 `test_assistant_connection_http.py`는 PC에 `pytest_asyncio`가 없어 수집되지 않습니다.
  - `test_model_library.py` 1개는 묶음 실행에서만 실패하고 단독으로는 양쪽 모두 통과합니다.
  - 반영 전에 실패하던 `test_tesla_auto_signal_intent.py` 26개와 차량 묶음 6개는 상류 수정으로 통과합니다.
- 사용자 문서 검사에서는 운전자 감시 대응표의 `controlsd.py` 항목이 남습니다. 11-03에도 나온 기존 항목입니다. 이번 두 끝 사이의 `controlsd.py` 차이는 상류의 방향지시등 함수 분리뿐이며, 운전자 감시 입력·정책·경고는 바뀌지 않았습니다.

원본 결과는 작업 공간 `analysis/2026-11-08-rebase/`에 있습니다.
