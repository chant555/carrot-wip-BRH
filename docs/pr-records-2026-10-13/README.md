# 2026-10-13 복구 기능 변경 요청 기록

이번 PR(코드 변경 요청)의 분석, 제출, 기존 시험 근거, 코드 대조, 상류 반영 및 종료 기록을 보관합니다. 세 제출 브랜치에 같은 자료를 보관하되 각 브랜치의 기존 실행 코드는 유지합니다.

| 구분 | 변경 요청 | 이슈 | 원래 제출 커밋 |
|---|---|---|---|
| A: Rebuild All 복구 | [#541](https://github.com/ajouatom/openpilot/pull/541) | [#544](https://github.com/ajouatom/openpilot/issues/544) | `c691f1097119f492c22d8af285b9f8810108f5a2` |
| B: 빌드 캐시 잠금과 복구 | [#542](https://github.com/ajouatom/openpilot/pull/542) | [#545](https://github.com/ajouatom/openpilot/issues/545) | `e5e96114167324da8a595fb50f39cb39201ec67b` |
| D: 시동 실패 화면 터치 | [#543](https://github.com/ajouatom/openpilot/pull/543) | [#546](https://github.com/ajouatom/openpilot/issues/546) | `f7f36343fc53d816f1b6442f90e2d65c7fc0021c` |

2026-10-13에 `gh`로 확인한 결과 여섯 건 모두 닫혔습니다. 변경 요청 자체를 병합한 것은 아닙니다. 상류가 [62fa1acb](https://github.com/ajouatom/openpilot/commit/62fa1acb72041c2e066932d8a21754910ed890dc)에서 보완하여 별도로 통합했습니다. 이슈는 해결 완료(`completed`)로 종료됐으며 삭제하지 않았습니다. [조회 기록](analysis/2026-10-13-github-submission/closed-verified-gh.json)을 보관했습니다.

상류는 캐시 경로 일치, 심볼릭 링크 보호, `_BACKEND` 속성 호환성 및 시험 경로를 보완했습니다. 기존 패치를 다시 적용하면 상류 보완을 되돌릴 수 있어 코드 재적용은 하지 않았습니다. [상류 검토 기록 사본](analysis/2026-10-13-conflict-resolution/upstream-review.md)과 [대조 결과](analysis/2026-10-13-conflict-resolution/comparison.json)를 참고합니다.

기존 기기 시험 조합은 A, A+B+C, A+D+E입니다. B 제출에는 A가 포함됐습니다. C와 E는 미제출 보류 패치이며 자료로만 보관합니다. 제출 기준은 `b98d5053`, 실기 시험 기준은 `626b887d`입니다. 제출 코드와 시험 원본의 실행 코드 대조 결과는 [검증 기록](analysis/2026-10-13-submission-audit/audit.json)에 있습니다. 상류 통합본 전체를 실기 시험본과 동일하다고 주장하지 않습니다. 이번 보관 작업에서 프로그램 실행 시험과 기기 시험은 추가하지 않았습니다.

[게시 현황](docs/Rebuild-All-GitHub-게시현황-261013.md), [제출 요점](docs/Rebuild-All-이슈-PR-제출요점-261013.md), [제출 패치와 출처](docs/pr-submission-261013/README.md), [보류 패치와 후속 조건](docs/Rebuild-All-이슈요약-261011.md)을 함께 보관합니다. 과거 문서의 초안·열림·미게시·권한 오류는 작성 당시의 경과이며 현재 상태는 이 문서와 종료 조회 기록을 우선합니다.

`manifest.json`은 보관한 원본 파일의 경로, 크기와 내용 해시를 기록합니다. 전체 저장소 사본, 임시 실행 환경, 관련 없는 주행 자료와 원시 기기 로그는 이 묶음에 넣지 않았으며 로컬 원본을 유지합니다. 과거 문서가 가리키는 일부 원시 기록은 로컬에서만 확인할 수 있습니다. 이 폴더의 소스 사본과 패치는 참고 자료이며 실제 실행 경로에 적용하지 않습니다.
