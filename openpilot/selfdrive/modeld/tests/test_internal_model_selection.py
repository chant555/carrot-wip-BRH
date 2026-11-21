import hashlib
from pathlib import Path

from openpilot.selfdrive.modeld.internal_model import INTERNAL_MODEL_NAME


def test_internal_default_bytes_match_the_branch_model():
  expected = {
    'CD210': 'f73a9e535523d5e9acb9e642c64e33d631825dc8ba74123757d107cedd047bb5',
    'BRH': '433f85f956837606ad1f1cbee4aa7e2158ad23c768dea914b20436c97232741b',
  }
  path = Path(__file__).parents[1] / 'models/driving_supercombo.onnx'
  with path.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected[INTERNAL_MODEL_NAME]
