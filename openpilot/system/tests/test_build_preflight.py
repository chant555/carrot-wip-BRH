import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest

from openpilot.common import build_preflight, startup_failure

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('broken', ['attribute', 'directory', 'header', 'library', 'healthy'])
def test_native_package_contract(tmp_path, broken):
  module = SimpleNamespace(__name__='catch2', __file__='/old/catch2/__init__.py',
                           INCLUDE_DIR=str(tmp_path), LIB_DIR=str(tmp_path))
  (tmp_path / 'header.h').touch()
  (tmp_path / 'lib.a').touch()
  if broken == 'attribute':
    del module.INCLUDE_DIR
  elif broken == 'directory':
    module.LIB_DIR = str(tmp_path / 'absent')
  elif broken in ('header', 'library'):
    (tmp_path / ('header.h' if broken == 'header' else 'lib.a')).unlink()
  if broken == 'healthy':
    build_preflight.validate_native_package(module, 'header.h', 'lib.a')
  else:
    with pytest.raises(RuntimeError, match='DEPENDENCY_INVALID: catch2 from /old/'):
      build_preflight.validate_native_package(module, 'header.h', 'lib.a')


@pytest.mark.parametrize('name,glob,header,library', [
  ('catch2', '*catch2*', 'catch2/catch.hpp', None),
  ('eigen', 'eigen-*', 'eigen3/Eigen/Dense', None),
  ('json11', '*json11*', 'json11/json11.hpp', 'libjson11.a'),
  ('libjpeg', 'libjpeg-*', 'jpeglib.h', 'libjpeg.a'),
])
def test_contract_matches_bundled_wheel(tmp_path, name, glob, header, library):
  # Read the actual shipped wrapper and headers without installing native wheels.
  with zipfile.ZipFile(next((ROOT / 'third_party/wheels').glob(glob))) as archive:
    archive.extractall(tmp_path)
  init = next(tmp_path.rglob(f'{name}/__init__.py'))
  namespace = {'__file__': str(init), '__name__': name}
  exec(init.read_text(), namespace)
  build_preflight.validate_native_package(SimpleNamespace(**namespace), header, library)


@pytest.mark.parametrize('repair', [True, False])
def test_importable_broken_package_is_repaired_and_revalidated(tmp_path, repair):
  source = (ROOT / 'launch_chffrplus.sh').read_text()
  functions = source[source.index('function ensure_python_package {'):source.index('function bootstrap_runtime_dependencies {')]
  # Force device/offline mode without writing host markers.
  functions = functions.replace('[ ! -f /TICI ]', 'false')
  module_dir = tmp_path / 'catch2'
  module_dir.mkdir()
  (module_dir / '__init__.py').write_text('# import succeeds but attributes are absent\n')
  payload = "from pathlib import Path\np=Path(__file__).parent\nINCLUDE_DIR=str(p)\nLIB_DIR=str(p)\n"
  (tmp_path / 'fixed.py').write_text(payload)
  script = '''
DIR="$PWD"
function install_runtime_python_package {
  echo "REPAIR:$*"
'''
  if repair:
    script += 'cp fixed.py catch2/__init__.py\nmkdir -p catch2/catch2\ntouch catch2/catch2/catch.hpp\n'
  script += '''return 0
}
'''
  check = "catch2; from openpilot.common.build_preflight import validate_native_package; validate_native_package(catch2, 'catch2/catch.hpp')"
  script += functions + '\nensure_python_package "' + check + '" "comma-deps-catch2==2.13.10.post96" 1\n'
  env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(tmp_path), str(ROOT)]), PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'])
  result = subprocess.run(['bash', '-c', script], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
  assert (result.returncode == 0) == repair, result.stdout + result.stderr
  assert result.stdout.count('REPAIR:') == 1
  assert '--no-index' in result.stdout
  assert 'DEPENDENCY_INVALID:' in result.stderr
  if not repair:
    assert 'not starting openpilot' in result.stdout


def test_failure_streak_survives_boots_and_resets(tmp_path, monkeypatch):
  head = ['commit-a']
  monkeypatch.setattr(startup_failure, 'git_value', lambda *args: head[0])
  monkeypatch.setattr(startup_failure, 'package_info', lambda: {'catch2': {'origin': '/old/catch2'}})
  path, log = tmp_path / 'state.json', tmp_path / 'error.log'
  log.write_text('RuntimeError: DEPENDENCY_INVALID: catch2\n')
  def record(boot):
    return startup_failure.record_failure(tmp_path, 'dependency repair failed', log, path, boot)
  assert '필수 패키지' in record('boot-1')
  assert '반복' not in record('boot-1')
  assert '반복' in record('boot-2')
  assert json.loads(path.read_text())['count'] == 2
  startup_failure.resolve(path)
  assert '반복' not in record('boot-3')
  head[0] = 'commit-b'
  assert '반복' not in record('boot-4')
  log.write_text('RuntimeError: another cause\n')
  assert '반복' not in record('boot-5')


@pytest.mark.parametrize('contents', ['bad json', '[]', '{"count":"bad"}'])
def test_corrupt_record_does_not_block_recovery(tmp_path, monkeypatch, contents):
  monkeypatch.setattr(startup_failure, 'git_value', lambda *args: 'commit')
  path = tmp_path / 'state.json'
  path.write_text(contents)
  startup_failure.record_failure(tmp_path, 'build failed', None, path, 'boot')
  assert json.loads(path.read_text())['count'] == 1


def test_unwritable_record_still_returns_dependency_hint(tmp_path, monkeypatch):
  monkeypatch.setattr(startup_failure, 'save_state', lambda *args: (_ for _ in ()).throw(OSError('full disk')))
  assert '필수 패키지' in startup_failure.record_failure(tmp_path, 'dependency failed', None, tmp_path / 'state', 'boot')


def test_log_is_bounded_and_symlink_is_replaced(tmp_path, monkeypatch):
  monkeypatch.setattr(startup_failure, 'git_value', lambda *args: 'commit')
  log, path, sentinel = (tmp_path / name for name in ('log', 'state', 'sentinel'))
  log.write_text('x' * 100000)
  sentinel.write_text('keep')
  path.symlink_to(sentinel)
  startup_failure.record_failure(tmp_path, 'build failed', log, path, 'boot')
  assert sentinel.read_text() == 'keep'
  assert len(json.loads(path.read_text())['log']) == 16384
  assert not path.is_symlink()


def test_bootstrap_precedes_cleanup_and_build():
  source = (ROOT / 'launch_chffrplus.sh').read_text().split('function launch {', 1)[1]
  assert source.index('run_startup_command bootstrap_runtime_dependencies') < source.index('if ! consume_rebuild_request')
  assert source.index('if ! consume_rebuild_request') < source.index('run_startup_command bash')
  assert 'show_startup_failure "Build dependency repair failed' in source
  assert source.index('startup_failure --resolved') > source.index('run_startup_command python3 "$DIR/openpilot/system/manager/params_check.py"')


@pytest.mark.parametrize('bootstrap_ok', [True, False])
def test_launcher_stops_before_deletion_if_dependency_repair_fails(tmp_path, bootstrap_ok):
  request = tmp_path / 'request'
  request.touch()
  source = (ROOT / 'launch_chffrplus.sh').read_text()
  section = source[source.index('  # Remember the user'):source.index('  # Build Params before')]
  mocks = '''
REBUILD_REQUEST="$PWD/request"
run_startup_command() { "$@"; }
bootstrap_runtime_dependencies() { return BOOTSTRAP_RESULT; }
show_startup_failure() { echo "BLOCKED:$CARROT_REBUILD_REQUESTED:$*"; exit 42; }
heal_scons_cache() { echo CACHE; }
consume_rebuild_request() { echo CLEAN; rm "$REBUILD_REQUEST"; }
'''.replace('BOOTSTRAP_RESULT', '0' if bootstrap_ok else '1')
  result = subprocess.run(['bash', '-c', mocks + section], cwd=tmp_path, capture_output=True, text=True, timeout=5)
  if bootstrap_ok:
    assert result.returncode == 0
    assert 'CLEAN' in result.stdout and not request.exists()
  else:
    assert result.returncode == 42
    assert 'BLOCKED:1:Build dependency repair failed' in result.stdout
    assert 'CACHE' not in result.stdout and 'CLEAN' not in result.stdout
    assert request.exists()


def test_fingerprint_uses_exception_not_traceback_source(tmp_path, monkeypatch):
  monkeypatch.setattr(startup_failure, 'git_value', lambda *args: 'commit')
  path, log = tmp_path / 'state', tmp_path / 'log'
  source_line = "    raise RuntimeError(f'DEPENDENCY_INVALID: {module.__name__}')\n"
  log.write_text(source_line + 'RuntimeError: DEPENDENCY_INVALID: catch2 invalid INCLUDE_DIR\n')
  startup_failure.record_failure(tmp_path, 'dependency failed', log, path, 'boot-a')
  assert json.loads(path.read_text())['diagnostic'] == 'RuntimeError: DEPENDENCY_INVALID: catch2 invalid INCLUDE_DIR'
  log.write_text(source_line + 'RuntimeError: DEPENDENCY_INVALID: json11 missing header\n')
  assert '반복' not in startup_failure.record_failure(tmp_path, 'dependency failed', log, path, 'boot-b')
