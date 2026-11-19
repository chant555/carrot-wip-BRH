import ast
import hashlib
from pathlib import Path

from openpilot.selfdrive.modeld import cheddar_model as client
from openpilot.selfdrive.modeld.cheddar_runtime import MODEL_SHA256
from openpilot.selfdrive.modeld.internal_model import INTERNAL_MODEL_NAME, INTERNAL_MODEL_USES_CHEDDAR


def test_internal_default_bytes_match_the_compiler_contract():
  expected = {
    'Cheddar': MODEL_SHA256,
    'CD210': 'f73a9e535523d5e9acb9e642c64e33d631825dc8ba74123757d107cedd047bb5',
    'BRH': '433f85f956837606ad1f1cbee4aa7e2158ad23c768dea914b20436c97232741b',
  }
  path = Path(__file__).parents[1] / 'models/driving_supercombo.onnx'
  with path.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected[INTERNAL_MODEL_NAME]


def test_model_factory_selects_the_branch_internal_model_and_keeps_legacy_external(monkeypatch):
  # Exercise the production factory without loading vehicle-only native modules.
  path = Path(__file__).parents[1] / 'modeld.py'
  cls = next(node for node in ast.parse(path.read_text(encoding='utf8')).body
             if isinstance(node, ast.ClassDef) and node.name == 'ModelState')
  method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__new__')
  minimal = ast.ClassDef(name='ModelState', bases=[], keywords=[], body=[method], decorator_list=[])
  scope = {'modeld_pkl_path': lambda external: Path('internal.pkl'),
           'INTERNAL_MODEL_USES_CHEDDAR': INTERNAL_MODEL_USES_CHEDDAR}
  exec(compile(ast.fix_missing_locations(ast.Module(body=[minimal], type_ignores=[])), str(path), 'exec'), scope)
  calls = []
  monkeypatch.setattr(client, 'CheddarModelState', lambda *args: calls.append(args) or 'internal')
  state = scope['ModelState'](1928, 1208, False)
  if INTERNAL_MODEL_NAME == 'Cheddar':
    assert state == 'internal'
    assert calls == [(1928, 1208, Path('internal.pkl'))]
  else:
    assert isinstance(state, scope['ModelState'])
    assert calls == []
  assert isinstance(scope['ModelState'].__new__(scope['ModelState'], 1928, 1208, True), scope['ModelState'])
