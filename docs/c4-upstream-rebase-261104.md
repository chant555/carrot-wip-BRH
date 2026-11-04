# 2026-11-04 상류 21개 리베이스·기존 수정 보존

## 반영 범위

사용자 요청에 따라 상류 기준 `36fbbbae3afa124f6d16c7ca6fe5122434a4ebe7`에서 `14c5398fca00d298c2791ecf43f46b3e3fd6cc38`까지 21개 커밋을 반영했습니다. 기존 브랜치는 `carrot-wip-brh=348093a0f171326916fcb9cf90b044b91c5c2470`, `carrot-wip-loc=4e98847e35a9084321fb73602de4d1d171a2f7ff`입니다. 로컬 복구 참조 `refs/backup/20261104-brh`·`refs/backup/20261104-loc`에 이전 이력을 보존했습니다.

두 브랜치의 사용자 커밋 20개·19개를 충돌 없이 재적용했습니다. 모든 사용자 커밋은 `git range-diff`에서 동일한 패치로 대응합니다. 문서 추가 전 끝 커밋은 `a7c1cc62`·`fb7720ab`입니다.

## 상류 변경 내용

- Comma Pedal 관련 8개는 레이 전기차의 별도 가속 페달 장치 지원, 기본 꺼짐 설정, 차량별 제한과 검사입니다. C4의 차량 통신 방식과 카메라 기반 크루즈는 이 기능 대상에서 제외됩니다. 공통 Panda 펌웨어 소스가 변경되므로 기기에서는 재빌드·펌웨어 갱신 여부를 확인해야 합니다. C4용 `safety_hyundai_canfd.h`는 변경되지 않았습니다.
- Carrot-B1 관련 12개는 ESP32-S3 기반 방향지시등 모듈을 BLE(저전력 블루투스)로 등록·제어하는 기능입니다. 연결 상태 표시, 제한된 송신 재시도, 실제 램프 반응 확인과 운전자 입력 구분을 추가했습니다. 등록된 모듈은 방향지시 요청이 없는 유휴 조건에서 주행 중에도 자동 펌웨어 갱신이 가능하며, 갱신 중에는 해당 모듈의 자동 방향지시 기능이 중단됩니다. 모듈 자동 갱신과 수동 정차 갱신의 조건은 서로 다릅니다.
- 마지막 `14c5398f`는 가까운 끼어들기 차량의 진입을 전방·코너 레이더의 독립적인 이동으로 확인하는 경로를 추가합니다. 코너 기준 12m 이내, 예상 진입 1.9초 이내, 전방 추적 이력 0.5초 이상, 두 관측의 실제 횡이동 1m 이상 등의 조건이 있습니다. 카메라가 아직 기존 앞차를 추적하는 동안에도 두 번째 선행 차량 후보로 인정할 수 있습니다. 평행 주행·자차 회전·추적 대상 변경에 대한 제외 검사가 포함됩니다.

상류 커밋 목록은 다음과 같습니다. 제목은 원문을 보존했습니다.

```text
506f7436 Add Comma Pedal support for Kia Ray EV
f8ffb1ff Generalize Comma Pedal shared identifiers
dfbbba75 Reuse generic Hyundai LFA DBC for Ray
33c04773 Add opt-in Comma Pedal setting
f9593483 Reintegrate opt-in Comma Pedal support with isolated vehicle profiles
01b8bf5d Restore pedal DBC calibration and require CC-only cruise-off operation
a2b4460f Merge PR #569 with isolated Comma Pedal support and regression coverage
ed7fe4a0 Update Wiki catalog assertions for Comma Pedal setting
7dbda6c3 Move B1 indicator output to an enrolled ESP32-S3 BLE controller
5dc24270 Enroll new Carrot-B1 controllers by BLE name and show radio status on comma displays
6619fb95 Confirm B1 link over longer BLE intervals and guard parked service taps
d7b181a6 Keep a parked tap visible across BLE polls without replaying it
046caa78 Sample the B1 guard clock after CAN admission and retain tap diagnostics
4990fb6f Support B1 firmware maintenance from a parked comma with CAN attached
c89a7a6f Retry a single lost B1 arbitration within the original frame deadline
fe5293d7 Drop redundant updater lint suppression
ecd93ff1 Distinguish bounded B1 stalk feedback from an independent driver input
2f14e1e7 Update enrolled Carrot-B1 firmware automatically after Git Pull
dda78d2b Allow automatic S3 updates onroad between indicator requests
2eb759df Recover B1 taps from bounded arbitration losses and confirm observed actuation
14c5398f Recognize a close cut-in from sustained independent radar motion
```

## 기존 수정 보존

상류와 겹치는 파일은 `carstate.py`, `carrot_settings.json`, 한국어·영어 설정 안내 4개입니다. 이 파일들의 상류 대비 사용자 추가·삭제 내용은 리베이스 전후 동일합니다. 상류가 건드리지 않은 사용자 파일은 각각 31개·30개가 내용까지 동일하며, 상류만 수정한 45개 파일은 상류와 같습니다. 두 브랜치의 차이는 기존 주행 모델 파일 하나입니다.

- SoftHOLD의 전진 기어 후 18km/h 이상 주행 이력, 전진 이외 기어 전환 시 초기화, 새 진입 시 조향각 절댓값 180도 미만 조건을 유지합니다. 이미 유지 중인 홀드를 각도만으로 해제하지 않으며, 짧은 브레이크 재입력 해제와 크루즈 대기 상태의 독립 동작을 유지합니다.
- 일반 크루즈의 기존 조향각·대기 조건을 유지합니다. `cruise.py` 전체가 이전과 같습니다.
- 원터치 최대 4회·3.2초 제한, 예약 만료 시 후속 차로변경 허용 해제, 진행 중 첫 차로변경의 조향 유지 조건을 보존했습니다.
- 순정 크루즈 MAIN 자동 요청은 유지하되, C4의 캐럿 크루즈 대기는 운전자 MAIN·SET·RES 버튼으로만 켜지도록 분리한 수정을 유지합니다.
- 계기판 `0x161`은 순정 MAIN이 켜진 C4에서 대기 화면을 표시하되 실제 크루즈 대기를 켜지 않습니다. 수동 끔과 MAIN 꺼짐 처리, 다른 차종의 기존 표시를 유지합니다.
- 저속 조향 평활화, 차간거리 여유 구간 원복, 정차 진입 가속도 하한 원복, 웹에서 전환한 브랜치를 따르는 업데이트 처리와 각 모델 파일을 유지합니다.
- `CarState.independentSoftHoldReady @113`과 상류 `laneLineInfoMonoTime @112`를 유지합니다. 과거 문서의 SoftHOLD `@112`는 현재 필드 번호가 아닙니다.

## 로컬 검사

| 묶음 | 결과 |
| --- | --- |
| SoftHOLD·크루즈 버튼·정차·저크·원터치·대기 분리·계기판 표시·대기 상태 조합 | 547개 통과, 네이티브 상태기계 의존 6개 제외입니다. |
| Pedal 호스트·끼어들기·B1 등록 및 갱신·방향지시 프로토콜 | 중복 제외 344개 통과입니다. |
| 차간거리 회복·물리 램프 유지·레버 입력·설정 스키마 | 154개 통과입니다. |
| 새로 빌드한 네이티브 안전 라이브러리의 Pedal 검사 | 57개 통과입니다. |
| 설정 문서 생성·검증 | 25개 통과입니다. |

총 1,127개 통과, 6개 제외입니다. 초기 통합 실행에서 동명 `server` 모듈을 잘못 선택한 방향지시 검사 1개가 실패했습니다. 별도 실행에서 경로를 명시해 해당 파일 36개가 모두 통과했습니다. 안전 검사 첫 직접 실행은 `openpilot` 경로가 없어 수집에 실패했으며, 기존 시험 실행기로 실행한 결과 57개가 통과했습니다. 제품 코드는 이 검사 환경 문제로 수정하지 않았습니다. 최초 실패 출력도 보존했습니다.

검사·비교 증거는 작업 공간 `analysis/2026-11-04-rebase/`에 있습니다. 실제 주행 동작과 외부 B1 장치 동작은 이 로컬 검사로 검증되지 않습니다. 기기 적용과 재부팅 결과는 작업 공간의 후속 기록에 추가합니다.
