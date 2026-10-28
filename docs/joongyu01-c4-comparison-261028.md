# joongyu01 공개 코드와 C4 구현 비교

검토일은 2026년 10월 28일이며 한국 시각을 기준으로 합니다.

공개 개발 코드의 주요 차이는 차선 횡단 감지에 따른 방향지시등 자동 점등과 저속 정지·출발 보정입니다. 우리 C4의 원터치 방향지시등 4회 제한 및 독립 SoftHOLD와는 목적과 제어 경로가 다릅니다. 기능별로 비교해야 하며, 개발 브랜치 전체를 독립 SoftHOLD의 대체 구현으로 해석하지 않습니다.

## 비교 기준과 확인 범위

| 대상 | 비교 기준 |
| --- | --- |
| 공개 개발 코드 | `ajouatom/openpilot`의 `joongyu01/carrot-wip-dev`, 커밋 `0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5`입니다. |
| 우리 활성 브랜치 | `chant555/carrot-wip-BRH`의 `carrot-wip-brh`, 커밋 `4a48823961780e9973c213361c369a5241710e25`입니다. |
| 우리 다른 운용 브랜치 | `carrot-wip-loc`, 커밋 `d81eeddc5468e583f645dfc916d286993675ebc7`입니다. |
| 공통 상류 기준 | 우리 브랜치에 반영한 `604bc0a22733e648ec05b268da1ffaae7db52a69`입니다. |

공개 개발 브랜치는 공통 상류 기준 이후 134개 커밋을 포함합니다. 이는 비교 범위의 이력 수이며, 조정한 기능의 개수나 특정 작성자 혼자 만든 커밋 수를 뜻하지 않습니다.

10월 28일 C4 접속 시도는 기기를 찾지 못해 실패했습니다. 따라서 기기 비교는 10월 27일 적용·재부팅을 확인한 위 커밋과 보존된 설정을 기준으로 합니다. 이 검토에서 코드를 적용하거나 새 회귀 검사·실차 시험을 실행하지 않았습니다.

- [공개 개발 기준 커밋](https://github.com/ajouatom/openpilot/commit/0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5)
- [상류 기준과 공개 개발 코드 비교](https://github.com/ajouatom/openpilot/compare/604bc0a22733e648ec05b268da1ffaae7db52a69...0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5)
- 기기 적용 원본 결과는 별도 작업 공간의 `analysis/2026-10-27-pause-docs-device/results.json`에 보존돼 있습니다.

## 공개 저장소의 역할

| 저장소 | 역할 |
| --- | --- |
| [joongyu01/openpilot](https://github.com/joongyu01/openpilot) | 차량 소프트웨어 저장소입니다. 관련 개발은 상류 저장소의 `joongyu01/carrot-wip-dev` 브랜치에서도 진행됩니다. 이번 차량 제어 비교는 그 개발 브랜치를 대상으로 합니다. |
| [Pilot_Demo](https://github.com/joongyu01/Pilot_Demo) | 상류의 웹 설정 화면과 서버 코드를 브라우저에서 사용하는 데모입니다. 차량 없이 설정을 살펴보는 용도입니다. |
| [carrot-wip-watch](https://github.com/joongyu01/carrot-wip-watch) | 상류 변경을 확인하고 커밋과 변경 요약을 알리는 도구입니다. |

프로필에 소개된 통신 역공학·임베디드 개발·차량 진단이라는 전문 분야와, 특정 차량 제어 패치의 구현·검증 결과는 구분합니다. 위 목록은 이번 검토에 관련된 공개 저장소이며 전체 공개 작업 목록은 아닙니다.

## 방향지시등 구현의 차이

CAN(차량 제어기 통신망) 메시지의 송신 방식과 점등을 요청하는 정책을 나누어 비교합니다. SPAS(스마트 주차 보조 시스템)는 방향지시등 명령을 보내는 차량 메시지 경로의 하나입니다.

| 항목 | 공개 개발 코드 | 우리 기준 코드 |
| --- | --- | --- |
| 점등을 요청하는 계기 | `CanfdBlinkerKick`은 깜박이 없이 차선을 넘어가기 시작하는 움직임을 모델 차선으로 감지합니다. 크루즈 연결 여부와 무관하며 D에서 동작합니다. | 사용자 수정은 운전자의 원터치 입력에 따른 유지 연장을 제한하고, 후속 차로변경 예약을 해제합니다. 상류의 다른 자동 점등 경로도 포함돼 있습니다. |
| 점등 요청의 길이 | 차선 횡단 감지 후 약 1초의 점등 요청을 생성합니다. 실제 램프의 점멸 횟수를 직접 제한하는 방식은 아닙니다. | 네 번째 점등 또는 약 3.2초의 기한에서 소프트웨어의 원터치 유지 연장을 해제합니다. 차량 자체의 점멸이나 운전자가 걸어 둔 레버까지 강제로 취소하는 기능은 아닙니다. |
| 자동주차 제어기 처리 | 확장 진단 세션을 요청하고 50밀리초 뒤 통신 중지를 요청합니다. 응답을 확인하지 않고 다음 단계로 진행합니다. | 일반 SPAS 경로의 `Session`은 긍정 응답과 순정 메시지 송신 중단을 확인한 뒤 진행합니다. 별도의 원본 재현 시험 경로와 구분해야 합니다. |
| SPAS 송신 주기 | 해당 경로에서는 제어 갱신마다 메시지를 생성하므로 초당 100회입니다. | 일반 `Session`의 활성 송신 간격은 20밀리초로, 최대 초당 50회입니다. |
| 레버 메시지 재생 | `CanfdBlinkerStalk`는 `0x3C1`을 유지형 또는 짧은 탭 형태로 재생합니다. 유지형은 초당 20회, 순간 탭은 초당 5회이며 탭 구간은 0.35초입니다. | 제한된 정차 재생 시험과 외부 어댑터 경로가 포함돼 있습니다. 메시지를 보내는 통신망과 시험 조건을 함께 비교해야 합니다. |

공개 `LaneCrossing`은 최근 양쪽 차선을 확인했는지, 가까운 차선으로 접근하면서 반대쪽 차선과 멀어지는지, 차선 재인식 직후인지 등을 검사합니다. 가까운 차선까지의 거리, 접근 속도, 과거 거리 이력과 재작동 대기 조건을 사용합니다. 코드 주석의 자체 로그 분석에는 오검출도 기록돼 있습니다. 해당 수치는 공개 작성자의 분석 기록이며 우리 C4에서 재현한 결과는 아닙니다.

공개 설정 설명은 아이오닉 5 PE에서 SPAS 방식의 램프 점등을 확인했다고 기록합니다. 반면 레버 메시지의 E-CAN(차량의 해당 통신 버스) 재생으로는 같은 차량의 램프가 켜지지 않았다고 설명합니다. 차체 제어기가 다른 통신망의 레버 신호를 본다는 설명은 추정으로 남아 있습니다. 이를 우리 차량의 성공·실패 판정으로 옮기지 않습니다.

10월 27일 우리 C4에서 마지막으로 확인한 설정은 `CanfdBlinkerControl=0`, `CanfdBlinkerTest=0`, `AutoBlinkerControl=0`, `AutoTurnControl=1`입니다. 코드에 외부 어댑터 경로가 있다는 사실만으로 해당 경로가 실행 중이라고 해석하지 않습니다.

근거 코드는 다음과 같습니다.

- [공개 점등·레버 재생 코드](https://github.com/ajouatom/openpilot/blob/0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5/opendbc_repo/opendbc/car/hyundai/carcontroller.py#L301-L382)
- [공개 차선 횡단 감지 코드](https://github.com/ajouatom/openpilot/blob/0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5/opendbc_repo/opendbc/car/hyundai/lane_crossing.py)
- [공개 차량 메시지 생성 코드](https://github.com/ajouatom/openpilot/blob/0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5/opendbc_repo/opendbc/car/hyundai/hyundaicanfd.py#L625-L641)
- [우리 일반 SPAS 세션과 별도 재현 경로](https://github.com/chant555/carrot-wip-BRH/blob/4a48823961780e9973c213361c369a5241710e25/opendbc_repo/opendbc/car/hyundai/spas.py)
- [우리 원터치 유지 연장 제한](https://github.com/chant555/carrot-wip-BRH/blob/4a48823961780e9973c213361c369a5241710e25/opendbc_repo/opendbc/car/common/blinker.py)
- 마지막 기기 설정 원본은 별도 작업 공간의 `analysis/2026-10-27-pause-docs-device/device-post.json`에 보존돼 있습니다.

코드 링크는 위 비교 기준 커밋의 파일을 가리킵니다. 별도 작업 공간의 원본 결과 파일은 이 저장소에 포함하지 않습니다.

## 저속 정지와 출발 보정의 차이

공개 개발 브랜치의 `StopGoAssist`는 계획기가 계산한 가속도에 저속 보정을 적용합니다. 1단계는 정지 제동을 보강하고, 2단계는 앞차 출발에 따른 출발 보정을 더하며, 3단계는 정지 직전 감속 완화를 추가합니다. 저속 정차 위치와 출발 지연을 조정하는 기능입니다.

`lead_close_brake`는 가까운 앞차에 접근할 때 추종 시간에 최대 0.3초를 추가하고, 장애물 관련 비용과 앞차 감속 시 가속도 변화 비용을 조정합니다. 차속에 따른 효과는 시속 45킬로미터 이하에서 온전히 적용되고 시속 65킬로미터 이상에서 사라지도록 구성됩니다. 시간 간격의 추가량은 서서히 증감합니다.

이 두 보정 파일은 우리 비교 기준 코드에 없습니다. 사용자는 앞서 감속 중 갑작스러운 감속을 경험해 `TFollowDecelBoost`를 0으로 낮췄습니다. 공개 보정도 추종 간격과 감속 응답을 바꾸므로, 도입을 검토한다면 기존 사용자 수정과 함께 응답을 확인해야 합니다. 같은 증상을 만든다는 인과관계가 확인된 것은 아닙니다.

- [공개 저속 정지·출발 보정](https://github.com/ajouatom/openpilot/blob/0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5/openpilot/selfdrive/controls/lib/stop_go_assist.py)
- [공개 근접 추종 제동 보정](https://github.com/ajouatom/openpilot/blob/0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5/openpilot/selfdrive/controls/lib/lead_close_brake.py)
- [계획기에서 보정을 적용하는 조건](https://github.com/ajouatom/openpilot/blob/0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5/openpilot/selfdrive/controls/lib/longitudinal_planner.py#L380)

## 독립 SoftHOLD와의 차이

공개 개발 브랜치의 `cruise.py`에는 `independentSoftHoldReady`와 16km/h 주행 이력 상태가 없습니다. 기존 홀드 진입은 크루즈 사용 가능 상태와 타이머를 사용하며, 전진 이외의 기어에서 타이머를 20초로 설정합니다. 크루즈 버튼으로 타이머를 해제하는 경로도 있으므로 매번 반드시 20초를 기다린다는 의미는 아닙니다.

우리 아이오닉 5 PE의 독립 SoftHOLD는 D 전환 후 시속 16킬로미터 이상 주행 이력을 사용합니다. 주차·후진·중립 전환 시 초기화하고, 홀드만으로 크루즈를 자동 연결하지 않으며, 짧은 브레이크 재입력에 따른 해제를 유지합니다. 자동 크루즈의 별도 타이머는 10초입니다.

앞서 수행한 크루즈 일시정지 조합과 기존 검사 119개 통과 결과는 우리 구현의 로컬 검사입니다. 이번 공개 코드 검토에서 다시 실행한 검사나 공개 개발 브랜치에 대한 실차 검증 결과가 아닙니다.

- [공개 크루즈 코드](https://github.com/ajouatom/openpilot/blob/0fbd9c29ffa5abec8f4cc7b8c1763ea18c56dba5/openpilot/selfdrive/car/cruise.py)
- [우리 독립 SoftHOLD의 구현·검사·기기 적용 기록](c4-softhold-speed-history-20261027.md)
- 일시정지 조합의 원본 검사 결과는 별도 작업 공간의 `analysis/2026-10-27-softhold-pause/results.json`에 보존돼 있습니다.

## 검토 판단과 후속 확인 항목

차선 감지 조건과 차량별 신호 해석은 참고할 가치가 있습니다. 실제 도입 여부는 방향지시등 송신, 저속 정지·출발 보정, 독립 홀드를 각각 나눠 판단하는 편이 타당합니다. 같은 메시지라도 연결된 통신망과 순정 제어기의 응답이 다르면 수용 결과가 달라질 수 있습니다.

방향지시등은 점등 요청·실제 램프 피드백·점멸 종료·순정 제어기 복귀를 함께 확인해야 합니다. 저속 보정은 기존 차간거리 수정과 함께 감속 변화 및 출발 응답을 비교해야 합니다. 독립 홀드는 크루즈 자동 연결 차단, 짧은 브레이크 재입력 해제와 주행 이력 초기화를 계속 보존해야 합니다.

이 문서는 공개 코드와 마지막 확인된 기기 적용 기록의 비교입니다. 이번 작업에서 코드 반영, 설정 변경, 기기 재부팅 또는 실차 시험을 수행하지 않았습니다.
