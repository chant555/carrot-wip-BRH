"""Validate native build packages without importing device services."""
import os
from pathlib import Path


def validate_native_package(module, header: str, library: str | None = None):
  """Use the same contract before and after installation, not import alone."""
  origin = getattr(module, '__file__', None)
  for attribute in ('INCLUDE_DIR', 'LIB_DIR'):
    value = getattr(module, attribute, None)
    if not isinstance(value, (str, os.PathLike)) or not Path(value).is_dir():
      raise RuntimeError(f'DEPENDENCY_INVALID: {module.__name__} from {origin}: invalid {attribute}')
  if not (Path(module.INCLUDE_DIR) / header).is_file():
    raise RuntimeError(f'DEPENDENCY_INVALID: {module.__name__} from {origin}: missing {header}')

  if library and not (Path(module.LIB_DIR) / library).is_file():
    raise RuntimeError(f'DEPENDENCY_INVALID: {module.__name__} from {origin}: missing {library}')
