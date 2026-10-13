import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch
from startup_touch_log import TouchLog
BASE=Path(__file__).resolve().parent

def dispatch(backend, point, accepted=True, clicked=True):
 tree=ast.parse((BASE/'startup_recovery_DE.py').read_text())
 main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
 loop=next(n for n in ast.walk(main) if isinstance(n,ast.While))
 start=next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='rl.end_drawing')
 actions=[];logs=[]
 class Ray:
  def __init__(self): self.polls=0;self.pos=(0,0) if backend=='comma' else point
  def poll_input_events(self):self.polls+=1;self.pos=point
  def get_touch_position(self,slot):return SimpleNamespace(x=self.pos[0],y=self.pos[1])
  def check_collision_point_rec(self,p,r):return r[0]<=p.x<r[0]+r[2] and r[1]<=p.y<r[1]+r[3]
 def action(name):actions.append(name);return accepted
 ray=Ray();ns=dict(rl=ray,RAYLIB_BACKEND=backend,touch=SimpleNamespace(fd=1,pressed=lambda:clicked),time=SimpleNamespace(monotonic=lambda:100),busy_notice_until=0,page=0,pages=[[],[]],rebuild_button=(16,188,246,52),update_button=(274,188,246,52),error_area=(16,63,504,79),touch_log=SimpleNamespace(record=lambda *a,**k:logs.append((a,k))),update=SimpleNamespace(state=('waiting' if accepted else 'updating',''),start_rebuild=lambda:action('rebuild'),start=lambda:action('update')))
 exec(compile(ast.Module(body=loop.body[start+1:-1],type_ignores=[]),'dispatch','exec'),ns)
 return actions,logs,ns,ray

class PatchTests(unittest.TestCase):
 def test_edges_and_gap(self):
  for p,expected in [((143,239),['rebuild']),((407,238),['update']),((268,239),[]),((140,240),[])]:
   a,l,n,r=dispatch('comma',p);self.assertEqual(a,expected);self.assertEqual(r.polls,1)
 def test_press_is_persisted_before_action(self):
  a,l,n,r=dispatch('comma',(140,210));self.assertEqual(l[0][0],('press',));self.assertTrue(l[0][1]['sync']);self.assertEqual(l[1][0],('action',))
 def test_busy_notice_does_not_change_controller_state(self):
  a,l,n,r=dispatch('comma',(140,210),False);self.assertEqual(n['busy_notice_until'],103);self.assertEqual(n['update'].state[0],'updating');self.assertFalse(l[1][1]['accepted'])
 def test_desktop_is_not_polled_twice(self):
  a,l,n,r=dispatch('desktop',(140,210));self.assertEqual(a,['rebuild']);self.assertEqual(r.polls,0)
 def test_no_press_no_action(self):
  a,l,n,r=dispatch('comma',(140,210),clicked=False);self.assertEqual(a,[]);self.assertEqual(l,[])
 def test_error_area(self):
  a,l,n,r=dispatch('comma',(283,108));self.assertEqual(a,[]);self.assertEqual(n['page'],1)
 def test_record_failure_does_not_raise(self):
  with tempfile.TemporaryDirectory() as d:
   log=TouchLog(Path(d)/'log')
   with patch('startup_touch_log.os.fsync',side_effect=OSError('disk error')):self.assertFalse(log.record('press',sync=True))
 def test_rotation(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'log.jsonl';log=TouchLog(path,max_bytes=1)
   self.assertTrue(log.record('press',sync=True));self.assertTrue(log.record('reboot',sync=True))
   self.assertEqual(json.loads(path.read_text())['event'],'reboot');self.assertEqual(json.loads(path.with_suffix('.jsonl.1').read_text())['event'],'press')
if __name__=='__main__':unittest.main(verbosity=2)
