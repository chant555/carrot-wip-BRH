# Rebuild All 수정 제안 (상류 제출용 초안)

- **작성**: 2026-09-19
- **대상 저장소**: `ajouatom/openpilot` (carrot)
- **기준 커밋**: `32209300` (`happymaj11r/carrot-wip-model_selector`)
- **패치**: [rebuild_all.patch](rebuild_all.patch) — 4개 파일. 기준 커밋에 `git apply --check` 통과 (솔버 자동 감지를 추가한 뒤 다시 확인)
- **상태**: 초안. 상류에 제출하지 않았다.
- **재확인 (2026-09-25)**: 현재 c4 HEAD `76794719`(`happymaj11r/carrot-wip-model_selector`, AGNOS `19.8-carrot-bt1`)에서도 결함 1~4가 코드에 그대로 있고, 19.8의 `/etc/profile` 도 `PYTHONPATH=/data/pythonpath` 로 덮어쓴다. 패치는 이 커밋에도 `git apply --check` 를 통과한다. 확장 설계안은 [Rebuild-All-수정제안2.md](Rebuild-All-수정제안2.md).

---

## 1. 요약

웹UI **Rebuild All**은 이상이 생긴 기기를 살리는 **유일한 GUI 대책**이다. 그런데 이 버튼은 지금 AGNOS 19 기기에서 **아무것도 하지 않으면서 성공으로 표시된다.** 설령 명령이 끝까지 돌더라도 손상된 빌드를 고치지 못한다.

| # | 결함 | 결과 |
|---|---|---|
| 1 | `bash -lc` 로그인 셸이 `/etc/profile` 을 읽어 `PYTHONPATH=/data/pythonpath` 로 덮어쓴다 | `scons` 가 `No module named 'libjpeg'` 로 실패한다. `&&` 사슬이 끊겨 정리도 재부팅도 일어나지 않는다 |
| 2 | 서버가 명령을 백그라운드로 던지고 결과를 확인하지 않은 채 `ok: true` 로 끝낸다 | 실패가 사용자에게 보이지 않는다 |
| 3 | 최상위 `scons -c` 가 `CompilationDatabase` 노드에서 실패하면 나머지 정리를 전부 버리고 **종료코드 0** 으로 끝난다 | 환경이 정상이어도 아무것도 지워지지 않는다. `-k` 를 붙여도 같다 |
| 4 | `/data/scons_cache` 가 지워지지 않는다. 리커버리 `git_rebuild` 는 `/tmp/scons_cache` 를 지우는데, AGNOS의 캐시는 `/data/scons_cache` 다 | **오염된 캐시가 손상된 생성물을 계속 되살린다** |

리커버리(6999)의 `rebuild_all`·`git_rebuild` 도 로그인 셸 PTY(`sudo -i bash -lc`)에서 `scons -c &&` 로 시작하므로 **결함 1·3을 그대로 가진다.**

**제안하는 방향**: 버튼은 **재빌드 요청 파일 하나만 쓰고 재부팅**한다. 실제 초기화는 다음 부팅 때 `launch_chffrplus.sh` 가 빌드 직전에 한다. 이때 `scons -c` 는 되는 데까지만 시도하고, 성공 여부와 상관없이 **빌드 상태 DB(`.sconsign.dblite`)와 캐시를 반드시 지운다.** 그러면 빌드 환경이 깨져 있어도 버튼이 동작하고, 손상된 생성물도 소스부터 다시 만들어진다.

**여기에 더해, 부팅 때 MPC 솔버 손상을 스스로 감지해 같은 초기화를 자동으로 건다.** 주기적으로 업데이트하는 사용자에게 빌드 문제는 자주 생기고, 그때마다 사람이 알아채 버튼을 누르기를 기다릴 이유가 없다. *(2026-09-19 추가)*

---

## 2. 계기가 된 사고 (c4, 2026-09-16 ~ 09-19)

**증상**: 주행 중 체결이 전혀 되지 않았다(`commIssue`, 체결률 0%). CPU는 100%에 고정됐다.

**원인**: `plannerd` 가 import 단계에서 죽고, manager가 다시 띄우면 또 죽기를 반복했다. 주행 하나에서 crash가 수천 건 나왔다.

```
ImportError: dynamic module does not define module export function (PyInit_acados_ocp_solver_pyx)
```

| 시각 | 사건 |
|---|---|
| 09-16 12:07 | pull `f9594fc9` |
| 09-16 12:09:06 | 부팅 빌드 도중 Cython 생성이 끊겼다. 종방향·횡방향 `acados_ocp_solver_pyx.c` 가 **0 B**로 남았고, 0 B `*.o.tmp` 도 남았다. 같은 시각 **`/data/scons_cache` 에 0 B 항목 2개가 들어갔다** |
| 09-19 15:45·15:52 | 주행 d7·d8은 정상이었다(기존 `.so` 가 살아 있었다) |
| 09-19 15:52→15:54 | 체크아웃 후 재부팅. 부팅 빌드가 0 B `.c` 를 다시 만들지 않고, 그것으로 `.o`(720 B)와 `.so`(`PyInit` 없음)를 다시 링크했다 |
| 이후 | 두 브랜치의 모든 주행에서 `plannerd` crash가 났다. 생성물은 `.gitignore` 대상이라 체크아웃이나 `reset --hard` 로 바뀌지 않는다 |
| 09-19 16:15~18:12 | 사용자가 **Rebuild All을 7번 눌렀다.** 7번 모두 `ok: true` 로 기록됐지만 재부팅은 한 번도 없었다. 18:12:09에 눌렀는데 가동 시작은 18:09:06 그대로였고, 서버 로그에 `libjpeg` 오류가 남았다 |

**수동 복구**: 손상 생성물 4종과 오염된 캐시 2항목을 치우고 재부팅했다. 부팅 빌드가 소스에서 다시 만들었고(`.c` 1.79 MB, `.so` 1.14 MB, `PyInit` 1), import가 정상으로 돌아왔다. 절차는 [index.md](../index.md) "빌드 생성물 손상" 절에 있다.

---

## 3. 결함별 근거

### 결함 1 — 로그인 셸이 PYTHONPATH를 지운다

```
$ env PYTHONPATH=/data/openpilot/pydeps:/data/openpilot:/data/pythonpath bash -lc 'echo $PYTHONPATH'
/data/pythonpath                       ← /etc/profile:34  export PYTHONPATH="/data/pythonpath"
$ env PYTHONPATH=... bash -c 'echo $PYTHONPATH'
/data/openpilot/pydeps:/data/openpilot:/data/pythonpath
```

`libjpeg` 는 `/data/openpilot/pydeps/libjpeg` 에만 있다. SConstruct 52행이 `pkg_names` 를 import하다가 실패한다.

### 결함 3 — 최상위 `scons -c` 는 조용히 아무것도 하지 않는다

올바른 PYTHONPATH로 시험 실행(`-n`)한 결과다.

| 명령 | 삭제 대상 |
|---|---|
| `scons -c` / `scons -c .` / `scons -c /data/openpilot` / `scons -c -k` | **0** (종료코드 0) |
| `scons -c openpilot msgq_repo opendbc_repo` | 396 |
| `scons -c` + **SConstruct 수정안** | **3,192** (손상된 솔버 파일과 `/data/scons_cache` 포함) |

`--taskmastertrace` 로 보면 `compile_commands.json` 의 하위 항목 하나가 `Task.fail_stop()` 으로 실패한다. 그 순간 `.` 의 나머지 하위 노드가 모두 버려진다. 인자 없는 정리에 대해 실험용 SConstruct에서는 이런 현상이 없었다. 원래 의도했던 `Clean(["."], cache_dir)` 도 이 때문에 작동하지 않는다.

### 결함 4 — 캐시가 손상을 되살린다

`Decider('MD5-timestamp')` + `CacheDir` 로 된 실험용 프로젝트에서 재현했다(c4에서 실행).

| 조건 | 결과 |
|---|---|
| 생성물(`gen.c`)을 0 B로 만든 뒤 빌드 | `gen.c` 를 다시 만들지 않는다. 0 B 파일로 하위 결과물만 다시 만든다 ← 이번 사고와 같다 |
| `.sconsign.dblite` 만 삭제 | 캐시에서 복원한다 |
| 캐시가 오염된 상태에서 `.sconsign.dblite` 와 생성물을 삭제 | **캐시에서 0 B를 다시 꺼내 온다** |
| **`.sconsign.dblite` + 캐시 삭제** | **소스에서 다시 빌드한다** |

**생성물·빌드 상태·캐시를 함께 지워야만** 확실하게 복구된다. 리커버리 `git_reset_repo` 의 `git clean -xfd` 도 저장소 밖에 있는 `/data/scons_cache` 는 건드리지 않는다.

---

## 4. 설계 원칙

1. **버튼 쪽에는 빌드 도구에 기대는 코드가 없어야 한다.** 버튼이 필요한 순간은 scons나 파이썬 의존성이 깨진 때다. 버튼은 파일 하나를 쓰고 재부팅만 한다.
2. **정리는 부팅 스크립트가 빌드와 같은 환경에서 한다.** `launch_chffrplus.sh` 는 `PYTHONPATH="$PYDEPS:$PWD"` 를 이미 설정한 상태이고, `build.py` 가 같은 환경에서 돈다.
3. **`scons -c` 는 되는 데까지만 시도하고 결과에 기대지 않는다.** 확실한 부분은 `.sconsign.dblite`·`/data/scons_cache`·`prebuilt` 삭제다. 이것만으로 모든 대상이 소스부터 다시 빌드된다.
4. **요청은 먼저 소비한다.** 빌드가 실패해도 재부팅이 반복되지 않는다. 빌드 실패는 기존 `build.py` 의 TextWindow가 보여 준다.
5. **요청 파일은 저장소 밖(`/data/rebuild_all.request`)에 둔다.** `reset --hard`·`git clean -xfd` 에 지워지지 않게 하기 위해서다. 쓰기 전에 `fsync` 하고, 재부팅 직전에 원자적으로 교체한다.
6. **성공 보고는 사실만 담는다.** 요청 파일 쓰기가 실패하면 실패로 보고하고 재부팅하지 않는다.
7. **자동 감지는 오탐이 없어야 한다.** 결과물이 없는 것(첫 빌드)은 정상으로 본다. 판정은 **파일 내용만으로** 한다. 파이썬 import로 판정하면 환경 차이만으로 오탐이 난다. 실제로 ssh 셸의 `python3`(`/usr/bin/python3`)로는 정상 솔버도 numpy 오류로 import에 실패했다.
8. **자동 초기화는 커밋당 한 번만 한다.** 전체 재빌드로도 안 고쳐지면 원인이 다른 데 있는 것이다. 그 상태에서 매 부팅 전체 재빌드를 반복하면 부팅만 느려진다. 새 커밋을 받으면 다시 한 번 허용한다.

---

## 5. 변경 내용

전문은 [rebuild_all.patch](rebuild_all.patch)에 있다.

| 파일 | 변경 |
|---|---|
| `SConstruct` | `scons -c` 일 때는 `env.CompilationDatabase(...)` 를 등록하지 않는다. 최상위 정리와 `Clean(["."], cache_dir)` 가 되살아난다 |
| `launch_chffrplus.sh` | ① `reset_build_state`(공통 초기화: `.sconsign.dblite`·`/data/scons_cache`·`prebuilt` 삭제, `FORCE_REBUILD=1`) ② **`check_mpc_solvers`** — 종방향·횡방향 솔버에 0 B `acados_ocp_solver_pyx.c` 가 있거나, `.so` 안에 `PyInit_acados_ocp_solver_pyx` 문자열이 없으면 손상으로 보고 초기화한다. 커밋당 한 번이며 `/data/build_autoreset.stamp` 로 기록한다 ③ `consume_rebuild_request` — 요청 파일을 먼저 소비하고 `timeout 600 scons -c` 를 시도(실패해도 계속)한 뒤 초기화한다. 로그는 `/data/rebuild_all.last.log`. ②·③은 `invalidate_native_build_if_needed` 다음에 호출한다 |
| `server/features/tools/dispatcher.py` | `request_rebuild_all()` 신설. 비동기 작업 경로와 동기 경로 모두 요청 파일을 쓴 뒤 `sudo reboot` 한다. 쓰기에 실패하면 `ok: false` 를 돌려주고 재부팅하지 않는다. 셸은 쓰지 않는다 |
| `recovery/server.py` | `rebuild_all` → `touch /data/rebuild_all.request && sync && sudo reboot`. `git_rebuild`("다음 부팅에 재빌드") → `touch /data/rebuild_all.request && sync`. 확인창 문구를 실제 동작에 맞게 고친다 |

부팅 쪽 핵심은 다음과 같다.

```bash
function reset_build_state {                     # 공통 초기화
  rm -rf "$DIR/.sconsign.dblite" /data/scons_cache "$DIR/prebuilt"
  FORCE_REBUILD=1
}

function check_mpc_solvers {                     # 자동 감지 (커밋당 1회)
  for lib in longitudinal_mpc_lib lateral_mpc_lib; do
    gen=".../$lib/c_generated_code"
    [ -e "$gen/acados_ocp_solver_pyx.c" ] && [ ! -s "$gen/acados_ocp_solver_pyx.c" ]  → 손상
    [ -f "$gen/acados_ocp_solver_pyx.so" ] && ! grep -qa PyInit_acados_ocp_solver_pyx ... → 손상
  done
  손상이면: 스탬프 == HEAD 이면 경고만, 아니면 스탬프 기록 후 reset_build_state
}

function consume_rebuild_request {               # 버튼 요청
  [ -f "$REBUILD_REQUEST" ] || return 0
  rm -f "$REBUILD_REQUEST"                       # 먼저 소비 → 재부팅 반복 방지
  (cd "$DIR" && timeout 600 scons -c) || echo "scons -c failed; continuing"
  reset_build_state                              # 확실한 부분
}
```

(위는 요약이다. 실제 코드는 패치에 있다.)

---

## 6. 검증한 것 / 하지 않은 것

**검증함** (c4, AGNOS 19.6.3-carrot, 기준 커밋 `32209300`)

- 결함 1~4를 모두 재현했다(위 3절).
- SConstruct 수정안: 임시 사본(`scons -f`)으로 `scons -c -n` 을 돌려 3,192개가 삭제 대상이 됐다. 손상 솔버 `.c`·`.so` 와 캐시가 포함된다.
- `consume_rebuild_request`: 경로만 `/tmp` 로 바꾼 격리 환경에서 **`scons -c` 가 import 오류로 실패하는 경우**, 캐시 오염, 0 B 생성물을 모두 걸어 놓고 실행했다. 요청 소비, 상태·캐시 삭제, `FORCE_REBUILD=1`, 로그 기록이 모두 확인됐다. 이어진 빌드는 소스에서 다시 만들었다(`gen.c` 0 B → 6 B). 요청이 없으면 아무것도 하지 않는다.
- `check_mpc_solvers`: 같은 격리 방식으로 6가지 경우를 시험했다. 결과는 모두 설계대로였다.

  | 경우 | 결과 |
  |---|---|
  | 정상 | 아무것도 안 함 |
  | 결과물 없음(첫 빌드) | 아무것도 안 함 |
  | 0 B `.c` | 감지 → 초기화 |
  | `PyInit` 없는 `.so`(빈 소스로 만든 69,160 B, 사고 때 파일은 69,464 B) | 감지 → 초기화 |
  | 같은 커밋에서 두 번째 감지 | 경고만 하고 초기화 안 함 |
  | 새 커밋 | 다시 초기화 |

  실제 c4 저장소에서도 초기화 함수를 빈 함수로 바꿔 돌렸고, "정상"으로 판정했다. 점검에 걸리는 시간은 두 모듈 합쳐 19 ms다.
- 파이썬 2개 파일은 구문 검사, `launch_chffrplus.sh` 는 `bash -n` 을 통과했다. 패치 전체가 `git apply --check` 를 통과했다.

**하지 않음**

- 패치를 적용한 코드로 **실제 기기에서 버튼을 눌러 전체 재빌드를 끝까지 돌려 보지는 않았다.** 전체 재빌드에 걸리는 시간도 재지 않았다.
- 웹UI 프런트(`runtime.js`, 번역 문구 "Rebuild+reboot started")는 바꾸지 않았다. 서버 응답 형식은 그대로다.
- 09-16 빌드가 끊긴 원인(전원 차단 등)과, 0 B 결과물이 어떻게 캐시에 들어갔는지는 규명하지 못했다.

---

## 7. 상류에 함께 전할 것

- **`bash -lc` 를 쓰는 다른 경로도 같은 위험이 있다.** 파이썬이나 scons를 부르는 경로는 PYTHONPATH가 지워진다. `reset_calib` 의 `sleep 1 && sudo reboot` 처럼 파이썬을 쓰지 않는 명령은 영향이 없다.
- **손상 생성물이 스스로 복구되지 않는다.** 소스 신호가 바뀌지 않으면 scons는 망가진 중간 생성물을 그대로 쓴다(`MD5-timestamp`). 이 제안의 자동 감지는 **이번에 실제로 난 MPC 솔버 손상만** 대상으로 한다. 같은 방식(0 B 생성물, 초기화 함수 없는 확장 모듈)을 `params_pyx`·`ipc_pyx`·`visionipc_pyx` 등 다른 Cython 모듈로 넓힐 수 있다. 다만 이 모듈들이 실제로 손상된 사례는 보지 못했다.
