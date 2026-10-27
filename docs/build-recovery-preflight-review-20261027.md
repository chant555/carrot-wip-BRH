# 리빌드 전 의존성 검증 — 검토와 보완 (2026-10-27)

[리빌드 전 의존성 검증과 반복 실패 안내](build-recovery-preflight-20261026.md)(커밋 `ecea7803`, `46cf2085`)를 검토하고 세 가지를 보완했습니다. 처음 올린 보완(`2d755d4a`)을 Codex가 다시 검토해, 오류 식별의 남은 빈틈 두 가지와 설치 경로에 대한 잘못된 설명을 짚었습니다. 이 문서는 그 정정까지 반영한 최종본입니다. 브랜치는 상류 `carrot-wip` `604bc0a2` 위로 리베이스한 `fix/rebuild-all-request-261027` 입니다.

## 검토 결론

설계와 기기 검증은 적정합니다. 의존성을 import만이 아니라 헤더·라이브러리 파일까지 확인하고, 복구에 실패하면 캐시 정리 전에 멈춰 Rebuild All 요청과 캐시를 보존합니다. 반복 실패는 다른 부팅에서 같은 커밋·단계·대표 오류가 나올 때만 세고, 기록은 크기를 제한하며 원자적으로 교체합니다. C4에서 catch2 고장 재현, 자동 복구, 복구 실패 시 캐시 보존, 본체 버튼의 반복 안내, 원복 뒤 전체 재빌드를 확인했습니다.

다만 아래 세 가지를 고쳤습니다. 처음에 함께 넣었던 pip `--force-reinstall` 은 불필요한 것으로 확인돼 되돌렸습니다(아래 ②).

## 보완 내용

### ① 대표 오류 식별의 퇴보 수정 (`startup_failure.py`)

`46cf2085` 는 traceback의 소스 줄(`raise RuntimeError(f'DEPENDENCY_INVALID: …')`)을 대표 오류로 잡던 결함을 고치려고, 줄 맨 앞의 `…Error:` 만 찾도록 바꿨습니다. 그 결과 경로로 시작하는 컴파일러 오류를 놓치게 됐습니다. 대표 오류를 놓치면 실패 사유 문구로 대체되므로, 같은 커밋의 서로 다른 빌드 오류가 같은 오류로 묶이고 기록에서 원인을 찾기 어려워집니다.

이제 `diagnostic_line()` 이 다음 규칙으로 고릅니다.

- 줄 맨 앞(공백 제거 후)의 예외·실패 문장: `[\w.]*(Error|Exception|Failure):` 또는 `DEPENDENCY_INVALID:`
- **들여쓰지 않은 줄의 맨 앞**에 있는 컴파일러·링커 오류: 위치가 있는 `파일:행(:열): (fatal )error: `, 위치가 없는 `fatal error: …`, `cc1plus: fatal error: …`, `collect2: error: …`
- Python traceback의 `File "…", line N` **바로 다음 줄(소스 줄)은 건너뜁니다.**

처음 보완(`2d755d4a`)은 컴파일러 형식을 줄 **중간까지** 찾았고 위치가 없는 `fatal error:` 는 놓쳤습니다. 그래서 `raise RuntimeError("foo.cc:3:10: fatal error: …")` 같은 소스 줄을 오류로 잘못 고르거나, 위치 없는 오류를 놓칠 수 있었습니다(Codex 검토). 지금 규칙은 둘 다 막습니다.

| 로그 줄 | 원래(`ecea7803`) | `46cf2085` | 첫 보완(`2d755d4a`) | 최종 |
|---|---|---|---|---|
| `foo.cc:3:10: fatal error: 'bar.h' file not found` | 잡음 | 놓침 | 잡음 | 잡음 |
| `….c:1:2: error: …` | 놓침 | 놓침 | 잡음 | 잡음 |
| `fatal error: no input files`(위치 없음) | 잡음 | 놓침 | **놓침** | 잡음 |
| `cc1plus: fatal error: …`, `collect2: error: …` | 일부 | 놓침 | 놓침 | 잡음 |
| `SConsLockFailure: Timeout waiting for lock …` | 놓침 | 놓침 | 잡음 | 잡음 |
| `ModuleNotFoundError: …`, `RuntimeError: DEPENDENCY_INVALID: …` | 잡음 | 잡음 | 잡음 | 잡음 |
| 소스 줄 `raise RuntimeError(f'DEPENDENCY_INVALID…` | 잘못 잡음 | 무시 | 무시 | 무시 |
| 소스 줄 `raise RuntimeError("foo.cc:3:10: fatal error: …")` | 잘못 잡음 | 무시 | **잘못 잡음** | 무시 |
| `File "…", line 52, in <module>`, `scons: *** […] Error 1` | 무시 | 무시 | 무시 | 무시 |

`SConsLockFailure` 는 사용자들이 실제로 보고한 빌드 오류입니다([캐시 잠금 분석](pr-records-2026-10-13/docs/SCons-캐시잠금-분석-261011.md) 참고).

### ② pip `--force-reinstall` — 넣었다가 되돌림

처음 보완(`2d755d4a`)에서는 "pip는 같은 버전이 이미 있으면 교체하지 않는다"고 보고 pip 경로 두 곳에 `--force-reinstall` 을 넣었습니다. **이 근거는 틀렸습니다.** 런처는 `pip install --target "$PYDEPS" --upgrade` 를 쓰는데, `--target` 설치는 대상 폴더의 기존 설치를 "이미 만족됨"으로 보지 않고 늘 새로 설치하며, `--upgrade` 가 기존 폴더를 교체합니다. 같은 버전 패키지의 파일을 손상시키거나 지운 뒤 같은 명령으로 다시 설치해 보니, `--force-reinstall` 없이도 원래대로 복구됐습니다(pip 22.0.2, Codex도 같은 결과). 그래서 이 변경을 되돌렸고, pip 설치 줄은 상류와 같습니다.

또 처음 문서에 "C4는 uv 경로를 쓴다"고 썼지만 **틀렸습니다.** 10-26 기기 시험 기록에 따르면 C4의 설치는 pip 경로였고, uv 경로(`--reinstall`, Codex의 `ecea7803`)는 로컬 시험으로만 확인했습니다. 10-26의 C4 catch2 복구가 성공한 것도 위 `--target` 동작 덕분입니다.

### ③ 정상 부팅에서 기록을 다시 쓰지 않음 (`startup_failure.py`)

`--resolved` 는 Params 검증을 통과한 모든 부팅에서 불립니다. 이전에는 기록이 이미 `build_validated` 여도 매번 fsync하며 다시 썼습니다. 이제 실패 상태가 실제로 끝날 때만 씁니다.

### ④ 실패 문구 범위 조정 (`launch_chffrplus.sh`)

`bootstrap_runtime_dependencies` 는 빌드용 패키지뿐 아니라 aiohttp 같은 실행용 패키지도 설치합니다. 실패 사유를 "Build dependency repair failed; …"에서 "Dependency repair failed; rebuilding cache cannot fix this"로 넓혔습니다. 사유에 `dependency` 가 들어 있으므로 의존성 안내는 그대로 표시됩니다.

## 시험

- 새 시험: `test_diagnostic_line_covers_compiler_and_build_failures`(14가지 로그 줄, Codex가 짚은 두 사례 포함), `test_traceback_source_line_is_never_the_representative_error`, `test_healthy_boot_does_not_rewrite_validated_record` 입니다. 기존 문구 시험은 새 문구를 확인하도록 고쳤습니다. 설치 시험은 상류·원래 커밋과 같게 되돌렸습니다.
- `openpilot/system/tests` 와 carrot 서버 시험(로컬 Python 3.12, `--noconftest`)을 상류 `604bc0a2` 와 비교했습니다. 통과는 505 → 526(리베이스) → 542(최종 보완)개입니다. 실패 10건과 오류 16건은 상류에도 똑같이 있고, 로컬에 없는 네이티브 모듈과 기존 `idna-3.11` 설치 파일·잠금 목록 불일치 때문입니다. 보완 뒤에만 실패하는 시험은 없습니다.
- `bash -n launch_chffrplus.sh` 와 공백 검사를 통과했습니다.
- 기기 시험은 하지 않았습니다. 최종적으로 바뀐 부분은 오류 기록의 대표 줄 선택, 기록 쓰기 조건, 실패 사유 문구입니다. 설치 명령(C4가 쓰는 pip 경로 포함)과 복구 흐름은 원래 커밋과 같습니다.
