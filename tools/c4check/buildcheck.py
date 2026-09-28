#!/usr/bin/env python3
"""빌드 산출물·현재 모델 컴파일 호환성·HTTP 응답을 읽기 전용 확인."""
import importlib
from pathlib import Path
import subprocess
import urllib.request
from checklib import Audit, emit


def main():
  audit = Audit(); solvers = {}; ports = {}; model = {}
  try:
    pane = subprocess.check_output(['tmux','capture-pane','-p','-t','comma:0','-S','-3000'],text=True,timeout=5)
    if 'scons: done building targets.' not in pane:
      audit.missing('tmux 보존 범위에서 SCons 완료 표식 미확인(빌드 실패 단정 아님)')
  except Exception as exc:
    audit.missing(f'빌드 로그 접근 실패: {exc}')
  for name in ('longitudinal_mpc_lib','lateral_mpc_lib'):
    try:
      importlib.import_module(f'openpilot.selfdrive.controls.lib.{name}.c_generated_code.acados_ocp_solver_pyx')
      solvers[name] = 'import OK'
    except Exception as exc:
      solvers[name] = str(exc); audit.review(f'{name}: solver import 실패')
  try:
    from carrot.model_selector.config import compile_env_tag, model_compile_env_is_current
    folder = Path('/data/models')
    model = dict(name=Path('/data/params/d/DrivingModelName').read_text().strip(),
                 expected_stamp=compile_env_tag(),current=model_compile_env_is_current(folder))
    if not model['current']: audit.review('현재 코드와 모델 컴파일 스탬프 불일치')
    if (folder/'.recompile_failed').exists(): audit.review('모델 재컴파일 실패 마커 존재')
  except Exception as exc:
    audit.missing(f'모델 상태 확인 실패: {exc}')
  for name in ('Offroad_BuildFailed','Offroad_PandaFirmwareMismatch'):
    if (Path('/data/params/d')/name).exists(): audit.review(name+' 표시 존재')
  for port in (7000,6999):
    try:
      with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=3) as response: ports[port] = response.status
    except Exception as exc:
      ports[port] = str(exc); audit.review(f'HTTP {port} 응답 확인 실패')
  return emit(audit,solvers=solvers,model=model,http=ports,
              scope='빌드/로드/HTTP 점검. 모델 실제 추론과 주행 제어 검증은 별도.')


if __name__ == '__main__': raise SystemExit(main())
