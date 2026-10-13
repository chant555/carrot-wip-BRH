# Build Recovery 수정 제안 — pull 후 빌드 실패의 분류·복구 체계

- **작성**: 2026-09-21
- **대상 저장소**: `ajouatom/openpilot` (CarrotPilot)
- **전제 문서**: [Rebuild All 수정 제안](Rebuild-All-수정제안.md)
- **상태**: 설계 제안. 구현·기기 적용·상류 제출 전.

## 1. 결론

기존 **Rebuild All**은 09-16에 발생한 Cython 산출물·SCons 캐시 오염을 복구하는 데 필요한 방향이다. 그러나 pull 뒤의 빌드 실패에는 캐시 오염 외에도 AGNOS 불일치, 디스크 부족, 의존성 부트스트랩 실패, 소스 컴파일 오류, Git 상태 오류, eGPU 준비 실패가 있다. 이들을 모두 `rm -rf` 후 재빌드로 처리하면 실패 원인을 숨기거나 불필요하게 긴 재빌드를 반복할 수 있다.

따라서 버튼의 목표는 **“모든 오류를 자동으로 고친다”가 아니라, 모든 pull 후 빌드 실패를 안전하게 분류하고, 복구 가능한 상태는 결정적으로 초기화·재빌드하며, 복구 불가능한 상태는 정확한 원인과 다음 조치를 남긴다”**여야 한다.

이 문서에서는 기능 이름을 **Build Recovery**로 제안한다. 기존 Rebuild All은 그 안의 가장 강한 `Full rebuild` 모드가 된다.

## 2. 문제 정의

현재 웹UI·리커버리의 Rebuild All은 대략 다음을 로그인 셸에서 백그라운드 실행한다.

```bash
cd /data/openpilot && scons -c && rm -rf prebuilt && sudo reboot
```

이 방식에는 두 층의 문제가 있다.

1. `bash -lc`가 `/etc/profile`을 읽으며 `PYTHONPATH`를 덮으면, `scons`가 의존성을 import하지 못하고 `&&` 뒤의 정리·재부팅도 실행되지 않는다.
2. `scons -c`가 성공처럼 끝나도 top-level clean이 실제 산출물을 지우지 않을 수 있고, `/data/scons_cache`에 남은 손상 결과가 다음 빌드에서 되살아난다.

전제 문서의 패치는 위 문제를 해결한다. 하지만 다음 유형은 캐시 초기화로 해결되지 않는다.

| 실패 유형 | 예 | 캐시 삭제로 해결되는가 |
|---|---|---|
| 산출물·캐시 오염 | 0 B Cython C 파일, `PyInit_*` 없는 `.so` | **예** |
| 증분 상태 불일치 | 오래된 `prebuilt`, `.sconsign.dblite` | **예** |
| 필수 산출물 누락 | native 바이너리·모델 pkl 없음 | 대개 예 |
| 저장 공간 부족 | `/` 또는 `/data` 부족 | 아니오 |
| OS/브랜치 불일치 | 요구 AGNOS와 `/VERSION` 불일치 | 아니오 |
| 의존성 부트스트랩 실패 | offline wheel·Python 모듈·시스템 라이브러리 누락 | 아니오 |
| 소스/툴체인 오류 | 컴파일러·헤더·소스 회귀 | 아니오 |
| Git 상태 오류 | 충돌, merge 진행 중, 원격 이력 분기 | 아니오 |
| 선택 eGPU 오류 | 전원·USB·PCIe 준비 실패 | 보통 아니오 |

## 3. 제안: 부팅 기반 복구 트랜잭션

버튼은 빌드 도구를 직접 실행하지 않는다. 복구 요청만 영속적으로 기록한 뒤 재부팅한다. 실제 진단·정리·빌드는 `launch_chffrplus.sh`의 정상 부팅 환경에서 수행한다.

```text
웹UI / 리커버리
  │  요청 파일을 fsync 후 원자적으로 교체
  │  성공할 때만 재부팅
  ▼
launch_chffrplus.sh
  │  환경 사전 진단
  ├─ 복구 불가 → 원인 기록, recovery 유지, manager 미기동
  │
  └─ 복구 가능 → 선택 모드에 맞게 초기화 → 깨끗한 빌드 → 사후 검증
                                                │
                                      통과 ────┴──── 실패
                                      manager 시작     원인 기록, recovery 유지
```

### 요청 파일

경로는 저장소 밖의 `/data/build_recovery.request`를 쓴다. `git reset --hard`나 `git clean -xfd`로 지워지지 않아야 한다.

```json
{
  "version": 1,
  "requested_at": 0,
  "mode": "full",
  "requested_by": "web"
}
```

- 임시 파일에 JSON을 쓰고 `flush`·`fsync`한 뒤 `os.replace`한다.
- 쓰기가 실패하면 API는 실패를 돌려주며 재부팅하지 않는다.
- 부팅 스크립트는 **빌드 시작 전에 요청을 소비**한다. 같은 실패로 무한 재부팅하지 않는다.

## 4. 사용자에게 보일 세 가지 모드

| 모드 | 초기화 범위 | 권장 상황 |
|---|---|---|
| **Diagnostics only** | 삭제·재부팅 없이 진단만 수행 | 원인 파악, 지원 요청 전 |
| **Quick repair** | 확인된 누락·불일치 산출물과 `prebuilt`만 무효화 | 평소 pull 직후의 가벼운 불일치 |
| **Full rebuild** | SCons 상태·캐시·Git-무시 빌드 산출물을 전부 무효화 | 0 B 결과물, 반복 crash, Quick repair 실패 |

`Full rebuild`은 기존 Rebuild All을 대체한다. UI에는 “다음 부팅에서 전체 재빌드가 실행되며 수 분 걸릴 수 있음”을 명시한다. 버튼을 눌렀다는 사실은 성공이 아니며, **빌드와 검증까지 끝난 결과**만 성공으로 표시한다.

## 5. 부팅 사전 진단

초기화를 시작하기 전에 다음을 순서대로 검사한다. 이 단계는 파괴적 동작을 하지 않는다.

1. **Git 상태**: merge/rebase/cherry-pick 진행 여부, HEAD 해석 가능 여부.
2. **OS 호환성**: 현재 브랜치 `launch_env.sh`의 요구 AGNOS와 `/VERSION` 비교.
3. **디스크 여유**: `/`·`/data`의 최소 여유 공간. 필요한 기준은 실제 full rebuild의 최대 사용량을 측정해 정한다.
4. **런타임 의존성**: `bootstrap_runtime_dependencies`, Params 빌드에 필요한 offline wheel과 import 가능 여부.
5. **필수 입력**: 선택된 driving model의 ONNX·매니페스트·컴파일 입력 존재 여부.
6. **선택 eGPU 상태**: eGPU가 필수인 모델만 준비 상태를 판정한다. 내부 모델 폴백이 가능한 경우는 실패가 아니라 경고로 기록한다.

여기서 실패하면 캐시를 지우지 않는다. 예를 들어 디스크가 부족한 상태에서 1.9GB 캐시를 지우는 것은 일시적으로 공간을 만들 수 있지만, 빌드 도중 다시 실패해 원인을 더 복잡하게 만들 수 있다. 먼저 필요한 여유 공간과 부족량을 결과에 남긴다.

## 6. 복구 가능한 산출물 검증과 초기화

### 검증 대상

Python import의 성공 여부만으로 네이티브 산출물을 판정하지 않는다. SSH와 부팅 환경의 `PYTHONPATH`가 다를 수 있기 때문이다. 파일 존재·크기·필요 심볼 같은 환경 독립적인 검사를 우선한다.

초기 대상은 다음과 같다.

- 종방향·횡방향 MPC `acados_ocp_solver_pyx.c`가 0 B가 아닌지
- 같은 `.so`에 `PyInit_acados_ocp_solver_pyx`가 있는지
- `loggerd`, `encoderd`, `camerad`가 실행 가능한지
- Params 레지스트리가 현재 키 정의와 일치하는지
- 모델 tinygrad pkl·chunkmanifest·build stamp가 선택 모델과 일치하는지

추후 실제 손상 사례가 생겼을 때만 `params_pyx`, `ipc_pyx`, `visionipc_pyx` 등으로 확대한다. 모든 `.so`를 무차별 검사하면 오탐과 부팅 비용만 늘어난다.

### Full rebuild 초기화

`Full rebuild`은 다음 상태를 함께 무효화한다.

```bash
rm -rf "$DIR/.sconsign.dblite" /data/scons_cache "$DIR/prebuilt"
FORCE_REBUILD=1
```

`SConstruct`는 clean 실행 시 `CompilationDatabase`를 등록하지 않아야 한다. 그래야 `scons -c`가 정리 도중 조용히 멈추지 않는다. `scons -c`의 성공 여부는 보조 정보로만 기록하고, 상태 DB·캐시·prebuilt 초기화는 반드시 수행한다.

삭제 범위는 구현 시 명시적 목록으로 유지한다. `/data` 전체나 저장소 전체에 대한 광범위한 삭제는 복구 기능의 범위가 아니다.

## 7. 빌드와 사후 검증

초기화 뒤에는 기존 `build.py`를 사용한다. Build Recovery가 별도 빌드 시스템을 갖거나 SCons의 오류를 감추면 안 된다.

빌드가 끝나면 manager를 시작하기 전에 다음을 검증한다.

1. `params_check.py`를 **부팅과 같은 환경**에서 통과하는지
2. 필수 native 실행 파일이 존재하고 실행 가능한지
3. 감시 대상 MPC 산출물이 정상 크기·심볼 조건을 만족하는지
4. 선택된 모델의 컴파일 산출물과 stamp가 존재하는지
5. build 프로세스와 검증 단계의 종료 코드가 모두 0인지

하나라도 실패하면 manager를 시작하지 않고 recovery를 유지한다. 이렇게 해야 “빌드는 성공으로 보이나 `plannerd`가 crash-loop하여 체결 불가”인 상태를 피할 수 있다.

## 8. 결과 계약과 관측성

각 요청은 `/data/build_recovery/<timestamp>.json`과 대응 로그를 남긴다.

```json
{
  "request_id": "…",
  "mode": "full",
  "started_at": "…",
  "finished_at": "…",
  "result": "succeeded | failed | blocked",
  "phase": "preflight | clean | build | verify",
  "code": "OK | DISK_LOW | AGNOS_MISMATCH | DEPENDENCY_BOOTSTRAP_FAILED | SOURCE_BUILD_FAILED | VERIFY_FAILED",
  "detail": "…",
  "log_path": "/data/build_recovery/….log"
}
```

웹UI의 작업 상태도 다음처럼 구분한다.

- `scheduled`: 요청 파일 기록과 재부팅 요청까지만 성공
- `running`: 부팅 후 복구 실행 중
- `succeeded`: 사후 검증까지 통과
- `blocked`: 환경 문제로 빌드를 시작하지 않음
- `failed`: 빌드 또는 사후 검증 실패

기존의 `ok: true`는 `scheduled`에만 해당하며, 최종 성공을 뜻하면 안 된다.

## 9. 재시도 규칙

자동 초기화는 같은 HEAD에서 한 번만 한다. full rebuild 뒤에도 같은 산출물 손상이 남는다면 캐시가 아니라 소스·도구체인·디스크·하드웨어 문제일 가능성이 높다. 매 부팅 전체 재빌드를 반복하면 장비를 사용할 수 없게 된다.

- 자동 감지: HEAD별 1회 `Quick repair` 또는 지정된 산출물 초기화
- 사용자가 누른 `Full rebuild`: 명시적 요청 1회 실행
- 같은 요청의 빌드 실패: 요청은 이미 소비됐으므로 재부팅 반복 금지
- 새 HEAD: 자동 복구 허용 횟수를 다시 계산

## 10. 기존 제안에서의 구현 확장

[Rebuild All 수정 제안](Rebuild-All-수정제안.md)의 네 파일 변경을 기반으로 한다.

| 기존 변경 | Build Recovery 확장 |
|---|---|
| `SConstruct`: clean 때 `CompilationDatabase` 생략 | 유지 |
| `launch_chffrplus.sh`: cache·state reset, MPC 감지 | preflight·모드 해석·사후 검증·구조화 결과 추가 |
| dispatcher: 원자적 요청 파일 후 reboot | JSON 요청·상태 조회 API·`scheduled` 응답 추가 |
| recovery: 요청 파일 후 reboot | 진단 결과·마지막 실패 로그 표시 추가 |

기존 `rebuild_all.request`는 마이그레이션 기간에 `mode: full` 요청으로 호환 처리할 수 있다.

## 11. 검증 계획

실제 적용 전에는 격리 환경과 기기에서 다음을 검증한다.

1. 정상 트리에서 `Diagnostics only`가 어떠한 파일도 바꾸지 않는다.
2. 0 B MPC C 파일, `PyInit` 없는 `.so`, 오염 캐시에서 `Full rebuild`가 소스 재생성까지 완료한다.
3. 로그인 셸의 `PYTHONPATH`가 깨진 상태에서도 웹UI 요청 기록·재부팅은 성공한다.
4. `/`·`/data` 공간 부족, AGNOS 불일치, offline wheel 누락에서 삭제 없이 `blocked`와 정확한 코드가 나온다.
5. 의도적으로 소스 컴파일 오류를 만들었을 때 요청이 한 번만 소비되고, manager가 시작되지 않으며 recovery에서 로그를 볼 수 있다.
6. 실제 C4에서 버튼 경로로 요청 → 재부팅 → clean → build → verify → manager 기동을 끝까지 한 번 측정한다.

## 12. 범위와 비범위

이 기능은 pull 뒤의 빌드 상태를 복구하고, 실패를 진단 가능한 결과로 바꾸는 기능이다. AGNOS를 자동 교체하거나, Git 이력을 강제로 재설정하거나, 디스크를 임의로 삭제하거나, 소스 코드 결함을 숨기는 기능이 아니다.

따라서 사용자 문구도 “모든 빌드 오류를 자동 해결”이 아니라 다음처럼 써야 한다.

> **Build Recovery**는 pull 뒤 손상되거나 오래된 빌드 산출물을 안전하게 초기화하고 재빌드합니다. 환경 또는 소스 오류는 원인을 표시하고 recovery 화면을 유지합니다.
