# 2026-09-28 업데이트·재부팅·빌드 점검

> 2026-09-28 공개 보관본. 본문의 현재/미설치 표현은 각 분석 시점 기준이다. 같은 날 후속 업데이트와 도구 보완 결과는 [README](README.md) 및 [인계 요약](HANDOFF.md)을 참고한다.

## 수행 결과

- C4의 IsOnroad=0을 확인하고 현재 모델 선택 브랜치를 업데이트했다.
- 설치본: `5cb0f3e590a28d0138ad9f48506f65743cdaa326` → `addd48d9c731efbdb2c6430ac00c0dcb1d4047d0`.
- 85개 커밋을 fast-forward로 적용했다. 원격 변경 파일과 기존 변경·미추적 파일 간 경로 충돌 없음.
- 기존 변경 파일 6개는 C4 `/data/maintenance-backups/<백업 폴더>/`에 백업했다. 업데이트 직후 파일 해시가 모두 기존과 같음을 확인했다.
- 재부팅 직전 다시 IsOnroad=0을 확인했다. 재연결 후 boot ID가 바뀌었고 새 커밋을 확인했다.
- OS는 `19.8-carrot-bt1`로 유지되었다.

## 빌드와 모델

- 자동 SCons 빌드: `scons: done building targets.` 확인.
- BRH 실행 환경 태그 변경으로 보존된 ONNX에서 자동 재컴파일했다. 실패가 아니라 호환성 확인에 따른 재생성이다.
- `model_selector: installing` 및 `model_selector: installed BRH` 확인 후 manager와 서비스가 시작되었다.
- 컴파일 태그: `tg-env:dd47a460f8c01d54` → `tg-env:68339fabc5a6a3a1`.
- 현재 코드로 검사한 `model_compile_env_is_current(/data/models)`는 True.
- 생성된 driving_tinygrad.pkl 크기 125,875,609 bytes; BRH ONNX 96,599,486 bytes 유지.
- `.recompile_failed`, `Offroad_BuildFailed`, `Offroad_PandaFirmwareMismatch` 없음.
- DrivingModelName=BRH, VEgoStopping=10 확인.

## 부팅 후 상태

25초 동안 Panda 메시지 240개와 manager/device 상태를 관찰했다.

- 실행되어야 하지만 중지된 서비스 없음. UI, Panda, 하드웨어, 내비, Bluetooth, Jetlink 등 정상 실행.
- managerState / pandaStates / deviceState 모두 alive 및 valid.
- Panda faults=[], faultStatus=none. registerDivergent, heartbeatLost, safetyRxChecksInvalid 없음.
- Panda 펌웨어 서명 `6bfdee531e06bc5c`가 요구 서명과 일치.
- SPI checksum 카운터는 시작 시 1, 관찰 종료 시 1로 추가 증가 없음.
- CAN 세 버스의 오류·busOff 없음. 단, 점화가 꺼져 CAN 송수신 자체가 없는 상태이므로 주행 통신 검증으로 해석하지 않는다.
- CPU 관찰 최고 43°C.
- Jetlink 상태 waiting, peer=null: 외부 장치 미연결 대기. 상태 파일의 Cinque v2 표기는 외부 경로 모델 설명이며 BRH가 교체됐다는 뜻이 아니다.
- 로컬 Carrot Web 7000 포트 HTTP 200.

## 로그 주의 항목과 범위

- 시작 로그에 SPI incorrect header sync/checksum 한 줄이 있다. 초기 누적값 1 이후 위 관찰 구간에서는 증가하지 않았다.
- UI 시작 시 `FPS dropped below 20: 7` 한 건 확인. 확인한 시작 로그에서 반복 경고는 없었다. 실제 화면 프레임률을 장시간 측정한 것은 아니다.
- PWD 경고와 로컬 변경으로 overlay 설치를 건너뛴 안내가 있었지만 현재 코드 빌드와 새 커밋 부팅은 성공했다.
- 점검은 오프로드에서 수행했다. modeld·카메라·주행 제어 서비스가 실행되지 않는 정상 상태이며, 새 BRH 실행 파일의 실제 추론·카메라 타이밍·주행 제동 성능은 아직 측정하지 않았다. 강제 주행 모드 전환이나 설정 변경은 하지 않았다.

변경 분석: [85개 커밋 분석](2026-09-28-commit-review.md).
