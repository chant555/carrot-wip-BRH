import os
import subprocess

from openpilot.selfdrive.carrot.server.features.tools import dispatcher


class FakeParams:
  puts = {}

  def put(self, key, value):
    FakeParams.puts[key] = value


def make_repo(tmp_path, branch):
  repo = tmp_path / "repo"
  subprocess.run(["git", "init", "-q", "-b", branch, str(repo)], check=True)
  subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init"], check=True)
  return repo


def make_marker(tmp_path, monkeypatch):
  marker = tmp_path / "staging" / "finalized" / ".overlay_consistent"
  marker.parent.mkdir(parents=True)
  marker.touch()
  monkeypatch.setenv("STAGING_ROOT", str(tmp_path / "staging"))
  return marker


def test_checkout_retargets_updater(tmp_path, monkeypatch):
  monkeypatch.setattr(dispatcher, "HAS_PARAMS", True)
  monkeypatch.setattr(dispatcher, "Params", FakeParams)
  FakeParams.puts = {}
  repo = make_repo(tmp_path, "carrot-wip-loc")
  marker = make_marker(tmp_path, monkeypatch)

  assert dispatcher._follow_checked_out_branch_sync(str(repo)) == "carrot-wip-loc"
  assert FakeParams.puts == {"UpdaterTargetBranch": "carrot-wip-loc"}
  assert not marker.exists()


def test_detached_head_keeps_updater_target(tmp_path, monkeypatch):
  monkeypatch.setattr(dispatcher, "HAS_PARAMS", True)
  monkeypatch.setattr(dispatcher, "Params", FakeParams)
  FakeParams.puts = {}
  repo = make_repo(tmp_path, "carrot-wip-loc")
  subprocess.run(["git", "-C", str(repo), "checkout", "-q", "--detach"], check=True)
  marker = make_marker(tmp_path, monkeypatch)

  assert dispatcher._follow_checked_out_branch_sync(str(repo)) == ""
  assert FakeParams.puts == {}
  assert marker.exists()
