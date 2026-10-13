# Rebuild All 제출 요약 (2026-10-13, 미게시)

> **[10-13 게시 완료]** 사용자가 `ajouatom/openpilot` 의 `carrot-wip` 에 등록했습니다. A는 이슈 [#544](https://github.com/ajouatom/openpilot/issues/544)와 PR [#541](https://github.com/ajouatom/openpilot/pull/541), B는 [#545](https://github.com/ajouatom/openpilot/issues/545)와 [#542](https://github.com/ajouatom/openpilot/pull/542), D는 [#546](https://github.com/ajouatom/openpilot/issues/546)과 [#543](https://github.com/ajouatom/openpilot/pull/543)입니다. PR은 모두 초안(draft)입니다. C와 E는 제출에서 빠졌고, 제출 코드의 기준은 `b98d5053` 입니다. 아래는 제출 전 계획이며, 최종 상태는 [게시 현황](Rebuild-All-GitHub-게시현황-261013.md)을 따릅니다.

이 문서는 이슈와 PR(변경 사항 병합 요청)을 올릴 때 쓸 요점만 추렸습니다. 시험 조건과 제한의 상세 해석은 [제출 요점(Codex)](Rebuild-All-이슈-PR-제출요점-261013.md)과 아래 시험 기록에 있습니다.

## 제출 단위

| 순서 | 제목 | 패치 |
|---|---|---|
| 1 | Rebuild All이 실제 정리 없이 성공으로 표시되어 손상된 빌드를 복구하지 못합니다 | [A](rebuild_all-A-910bd82f.patch) |
| 2 | 시동 실패 화면의 터치 좌표가 갱신되지 않아 복구 버튼이 반응하지 않습니다 | [D](startup-touch-D-626b887d-v2.patch) (+[E](startup-touch-usability-E-626b887d.patch)) |
| 3 | SCons 캐시 잠금 오류의 자동 복구와 동시 실행 보호 | [B](scons_cache_guard-B-910bd82f.patch) (+[C](solver_autoreset-C-910bd82f.patch)) |

적용 순서는 A → B → C, A → D → E입니다. 실기 시험의 기준 커밋은 `626b887d` 입니다.

## 1. Rebuild All (A)

- **문제**: 로그인 셸이 `PYTHONPATH` 를 덮어써 `scons` 가 실패하는데도 `ok: true` 를 돌려줍니다. 최상위 `scons -c` 는 아무것도 지우지 않고 종료코드 0으로 끝납니다. `/data/scons_cache` 도 지우지 않아, 손상된 생성물(0 B 솔버 등)이 캐시에서 되살아납니다.
- **수정**: 버튼은 요청 파일만 쓰고 재부팅합니다. 다음 부팅의 런처가 `.sconsign.dblite`·캐시·`prebuilt` 를 지우고 삭제 결과를 확인합니다. 실패하면 요청을 보존합니다.
- **실기**: A만 적용한 기기에서 0 B 솔버와 오염 캐시로 `plannerd` 가 불러오기에 실패하게 만든 뒤, 웹 버튼으로 복구했습니다(약 7분). 리커버리(6999) 버튼과 본체 버튼 경로에서도 각각 복구를 확인했습니다.

## 2. 시동 실패 화면 터치 (D, E)

- **문제**: COMMA 백엔드의 `EndDrawing` 은 입력을 갱신하지 않습니다. 그래서 터치 좌표가 `(0, 0)` 에 머물러 버튼이 눌리지 않습니다. 비교 진단에서 갱신이 없을 때는 누름 4회가 모두 `(0, 0)` 이었고, 갱신을 켜자 버튼 판정이 회복됐습니다.
- **수정(D)**: COMMA 백엔드에서 `poll_input_events()` 를 호출합니다. 조건에 `raylib._BACKEND` 를 쓰는데, 비공개 이름이므로 검토가 필요합니다. 터치 장치를 열지 못해 마우스 대체 경로를 쓸 때도 입력 갱신이 필요하므로, `touch.fd` 조건으로는 대체하지 않습니다. 재부팅 뒤에도 남는 터치·판정 기록(약 256 KiB에서 순환)도 넣었습니다.
- **개선(E)**: 버튼 아래쪽 판정 영역을 넓히고, 작업 중에 누르면 안내를 표시합니다.
- **실기**: A+D+E에서 짧은 터치 한 번(`(143, 207)`, 수락)으로 정리 → 전체 빌드 → 정상 기동을 확인했습니다(약 7분).

## 3. 캐시 잠금 (B, C)

- **문제**: `SConsLockFailure` 는 남은 `config.lock` 과, 쓸 수 없는 캐시(예: `sudo scons` 로 만들어진 root 소유 캐시)에서 똑같이 납니다. 뒤의 경우는 재부팅해도 풀리지 않습니다.
- **수정(B)**: 캐시 밖에 공통 `flock` 잠금을 둡니다. 잠금을 잡았을 때만 남은 잠금 파일과 쓸 수 없는 캐시를 지웁니다. 빌드끼리는 서로 기다립니다.
- **C**: 손상된 MPC(모델 예측 제어) 솔버를 감지하면 커밋당 한 번 자동으로 초기화합니다. B 위에서만 적용합니다.
- **실기**: 두 경우 모두 실제 부팅에서 복구를 확인했습니다.

## 남은 한계

- 본체 버튼의 성공 사례는 한 번뿐입니다. 이전 첫 무응답과 접촉이 한 번 더 잡힌 현상의 원인은 미확정입니다.
- D·E에는 시험 코드가 아직 들어 있지 않습니다. E는 버튼 표시 크기도 바꾸며, 안내는 한국어만 있습니다.
- 전원 차단 중 복구와 재시도 횟수 제한은 다루지 않습니다.

근거: [본체 실기](../analysis/2026-10-13-rebuild-ADE-screen/validation.md) · [A 단독·6999](../analysis/2026-10-13-rebuild-A-recovery/validation.txt) · [터치 진단](../analysis/2026-10-13-touch-followup/validation.md) · [캐시 복구 부팅 시험](../analysis/2026-10-13-rebuild-heal-boot/validation.txt) · [상세 이슈 초안](Rebuild-All-이슈본문-261011.md)
