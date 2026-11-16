# [클코] 상류 carrot-wip a31a59ca 반영과 decel-2 병합(2026-11-16)

상류 `ajouatom/openpilot` `carrot-wip`의 `b1c82746..a31a59ca`(86개)를 두 브랜치에 리베이스하고, `carrot-wip-brh-decel-2`의 네 커밋을 두 브랜치에 넣었습니다.

- 리베이스 전 끝은 다음 백업 참조에 있습니다.
  - `refs/backup/20261116-brh`(`8dd0723d`)
  - `refs/backup/20261116-loc`(`623f8c90`)
  - `refs/backup/20261116-brh-decel-2`(`95e0ac8a`)
- 모델은 그대로입니다. 상류는 모델 파일을 바꾸지 않았습니다.
  - brh는 `c0a49eda`("Use BRH as the built-in driving model")를 그대로 지녀 BRH 모델(`5c0e06da`)입니다.
  - loc는 상류 기본 모델(`1aac351c`)입니다.
  - 두 브랜치의 차이는 이 모델 파일 하나입니다.

## 충돌과 해결

- 정지 진입 전 하한 대역 되돌림: 상류의 새 import(`CAR`, `apply_signal_stop_object`)는 두고, 쓰이지 않는 `STOP_LOWER_BAND`만 뺐습니다.
- 원터치 깜빡이 제한: 상류의 크루즈 취소 시 유지 해제와 로컬의 원터치 제한 인자를 함께 둡니다. 시험 도우미는 양쪽 매개변수를 모두 받습니다.
- 독립 SoftHOLD: 로컬의 독립 유지 조건에 상류의 패들 해제 대기를 더했습니다. 설정 안내서는 상류 목록에 로컬 `AutoCruiseControl` 설명을 둡니다.
- decel-2: `long_mpc.update()`와 계획기 호출에 상류의 `tesla_stop_distance`와 로컬의 `lead_anticipation_enabled`를 함께 둡니다.
- `CarState` 필드 번호: 로컬 `independentSoftHoldReady`를 `@113`에서 `@120`으로 옮겼습니다(상류 `@113..@119`).
- 숨은 충돌:
  - 로컬 커밋이 지운 `CAR` import를 상류 계기판 표가 써서 되살렸습니다.
  - 로컬 SoftHOLD 시험이 직접 만든 크루즈 객체에 상류의 새 속성을 넣었습니다.

## 검사

- 보존 검사(`analysis/2026-11-16-rebase/preservation.json`, 작업 공간):
  - 상류만 바꾼 파일은 상류와 같습니다.
  - 로컬만 바꾼 파일은 의도한 시험 한 개 말고는 그대로입니다.
  - 양쪽이 바꾼 파일 가운데 로컬 차이가 달라진 것은 위 충돌 해결 다섯 곳뿐입니다.
- 시험 묶음 7개(`hyundai`, `car`, `controls`, `server`, `jetlink`, `modeld`, `docs`)를 리베이스 전·후 같은 작업 트리에서 비교했습니다.
  - 새 실패는 상류가 새로 넣은 `test_tesla_three_finger.py` 수집 오류 하나입니다. PC에 `msgq` 네이티브 모듈이 없어서입니다.
  - 리베이스 전 `controls` 실패 11개는 통과하게 됐습니다.
  - loc의 `modeld` 묶음도 brh와 같습니다.
- Panda 펌웨어(`fdcan.h`, 안전 코드)가 바뀌었으므로 C4에 적용하면 Panda를 다시 플래시해야 합니다.
