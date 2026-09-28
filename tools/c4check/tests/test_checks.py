import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import warnings

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from checklib import Audit, CounterSeries, live_samples, read_events, route_paths
import drive
import stops
import counters
import cpu
import jetlink


def ev(name,t=1,**fields):
  payload = types.SimpleNamespace(**fields)
  return types.SimpleNamespace(which=lambda:name,logMonoTime=int(t*1e9),valid=True,**{name:payload})


def stop_messages(active=True,brake=False,lead=True,stale=False):
  result=[]
  for i,speed in enumerate([4,3,2,1,0]):
    t=10+i*.1
    if not stale or i==0:
      result += [ev('selfdriveState',t-.03,enabled=True),
                 ev('carControl',t-.02,longActive=active,actuators=types.SimpleNamespace(accel=-.5)),
                 ev('radarState',t-.01,leadOne=types.SimpleNamespace(status=lead,dRel=5))]
    result.append(ev('carState',t,vEgo=speed,aEgo=-.5,brakePressed=brake,gasPressed=False))
  return result


class Checks(unittest.TestCase):
  def test_missing_route_is_unknown(self):
    audit=Audit()
    with tempfile.TemporaryDirectory() as d:
      paths=route_paths(Path(d),'test--route',audit)
      data=drive.analyze(paths,audit,lambda p:[])
    self.assertEqual(audit.code,2)
    self.assertIsNone(data['enabled_sample_pct'])

  def test_segment_missing_at_start_and_middle(self):
    audit=Audit()
    with tempfile.TemporaryDirectory() as d:
      for n in (1,3): (Path(d)/f'test--route--{n}').mkdir()
      route_paths(Path(d),'test--route',audit)
    self.assertEqual(audit.code,2)

  def test_corruption_warning_preserves_prefix_and_marks_unknown(self):
    audit=Audit()
    def reader(_):
      warnings.warn('Corrupted events detected',RuntimeWarning)
      return [ev('carState')]
    self.assertEqual(len(list(read_events('sample',audit,reader))),1)
    self.assertEqual(audit.code,2)
    self.assertIn('Corrupted',audit.incomplete[0])

  def test_exception_keeps_prefix(self):
    audit=Audit()
    def reader(_):
      yield ev('carState')
      raise ValueError('truncated')
    self.assertEqual(len(list(read_events('sample',audit,reader))),1)
    self.assertEqual(audit.code,2)

  def test_live_no_messages_is_unknown(self):
    class Empty:
      def __init__(self,services):
        self.updated={s:False for s in services}; self.valid=self.updated; self.alive=self.updated
      def update(self,_): pass
    audit=Audit(); clock=iter(range(20)).__next__
    self.assertEqual(list(live_samples(['pandaStates'],5,audit,types.SimpleNamespace(SubMaster=Empty),clock)),[])
    self.assertEqual(audit.code,2)

  def test_live_missing_one_service_is_unknown(self):
    class Half:
      def __init__(self,services):
        self.updated={'managerState':True,'deviceState':False};self.valid=self.updated;self.alive=self.updated
      def update(self,_): pass
      def __getitem__(self,_): return object()
    audit=Audit()
    list(live_samples(['managerState','deviceState'],3,audit,types.SimpleNamespace(SubMaster=Half),iter(range(20)).__next__))
    self.assertTrue(any('deviceState' in s for s in audit.incomplete))

  def test_jetlink_error_and_model_drop_are_visible(self):
    msg=ev('errorLogMessage')
    msg.errorLogMessage=json.dumps({'ctx':{'daemon':'jetlinkd'},'msg':'Jetlink connection failed','levelnum':40})
    data=drive.analyze([Path('test--0/qlog.zst')],Audit(),lambda _:[msg,ev('drivingModelData',2,modelExecutionTime=.15,frameDropPerc=25)])
    self.assertEqual(data['jetlink_log_count'],1)
    self.assertEqual(data['metrics']['model_ms']['max'],150)
    self.assertEqual(data['observations']['startup_15s']['drop_pct_nonzero_samples'],1)

  def test_invalid_control_message_is_reported(self):
    msg=ev('carControl');msg.valid=False
    data=drive.analyze([Path('test--0/qlog.zst')],Audit(),lambda _:[msg])
    self.assertEqual(data['observations']['startup_15s']['invalid_carControl'],1)

  def test_complete_healthy_sample_is_not_unknown(self):
    panda=types.SimpleNamespace(faults=[],faultStatus='none',heartbeatLost=False,safetyRxChecksInvalid=False,
      spiChecksumErrorCount=1,safetyRxInvalid=0,safetyTxBlocked=0,rxBufferOverflow=0,txBufferOverflow=0)
    for bus in range(3):
      setattr(panda,f'canState{bus}',types.SimpleNamespace(busOff=False,totalErrorCnt=0,busOffCnt=0,totalTxLostCnt=0,totalRxLostCnt=0))
    pm=ev('pandaStates');pm.pandaStates=[panda]
    messages=[ev('initData',0,gitCommit='test'),ev('carState',1,canValid=True,canTimeout=False,
      steerFaultTemporary=False,steerFaultPermanent=False,accFaulted=False),ev('carControl'),
      ev('selfdriveState',enabled=True),pm,
      ev('managerState',processes=[types.SimpleNamespace(name='modeld',shouldBeRunning=True,running=True)]),
      ev('deviceState',cpuTempC=[42],cpuUsagePercent=[30]),
      ev('livePose',inputsOK=True,sensorsOK=True,posenetOK=True),
      ev('drivingModelData',modelExecutionTime=.03,frameDropPerc=0)]
    audit=Audit();data=drive.analyze([Path('test--0/qlog.zst')],audit,lambda _:messages)
    self.assertEqual(audit.code,0)
    self.assertEqual(data['metrics']['model_ms']['mean'],30)

  def test_malformed_json_marks_incomplete(self):
    msg=ev('logMessage');msg.logMessage='broken'
    audit=Audit();drive.analyze([Path('test--0/qlog.zst')],audit,lambda _:[msg])
    self.assertTrue(any('메시지 해석 실패' in s for s in audit.incomplete))

  def test_metadata_does_not_set_time_origin(self):
    messages=[ev('initData',1,gitCommit='a'),ev('drivingModelData',100,modelExecutionTime=.03,frameDropPerc=1)]
    data=drive.analyze([Path('test--0/qlog.zst')],Audit(),lambda _:messages)
    self.assertEqual(data['observations']['startup_15s']['drop_pct_nonzero_samples'],1)

  def test_manual_stop_excluded_and_auto_stop_retained(self):
    for active,brake,lead,expected in [(True,False,True,1),(False,True,False,0),(True,True,True,0),(True,False,False,0)]:
      audit=Audit()
      data=stops.analyze([Path('test--0/qlog.zst')],audit,lambda _:stop_messages(active,brake,lead))
      self.assertEqual(data['accepted_candidates'],expected)
      self.assertEqual(audit.code,0)

  def test_stale_status_and_old_motion_excluded(self):
    rows=[dict(t=1,v=4,fresh=True,enabled=True,long_active=True,brake=False,gas=False,lead=True),
          dict(t=1.1,v=0,fresh=False,enabled=True,long_active=True,brake=False,gas=False,lead=True)]
    self.assertIn('결합 상태 누락/오래됨/invalid',stops.classify(rows))
    rows[0]['v']=1
    self.assertIn('최근 이동 근거 부족',stops.classify(rows))

  def test_counter_wrap_continuity_and_boundaries(self):
    seq=counters.Sequence()
    for seg,t,value in [(10,0,254),(10,.01,255),(10,.02,0),(12,120,10),(12,120.01,11),(12,120.02,12)]:
      seq.add(seg,t,value,8,.1)
    self.assertEqual(dict(seq.deltas),{1:4})
    self.assertEqual(seq.breaks,1)
    seq.add(13,120.03,13,8,.1)
    self.assertEqual(seq.deltas[1],5)
    seq.add(13,125,40,8,.1)
    self.assertEqual(seq.breaks,2)

  def test_counter_reset_not_negative_increase(self):
    series=CounterSeries()
    for v in (1,4,0,2):series.add('spi',v)
    self.assertEqual(series.values['spi']['increase'],5)
    self.assertEqual(series.values['spi']['resets'],1)

  def test_cpu_uses_common_duration_for_short_lived_process(self):
    messages=[]
    for t in (0,2,4,6,8,10):
      procs=[] if t>2 else [types.SimpleNamespace(pid=1,cmdline=['worker'],cpuUser=t,cpuSystem=0)]
      messages.append(ev('procLog',t,procs=procs))
      messages.append(ev('deviceState',t,cpuTempC=[40]))
    result=cpu.analyze(messages,Audit())
    self.assertAlmostEqual(result['process_cpu_sum_pct'],20)

  def test_empty_cpu_does_not_divide_by_zero(self):
    audit=Audit();result=cpu.analyze([],audit)
    self.assertEqual(audit.code,2)
    self.assertIsNone(result['cpu_temp_c'])

  def test_jetlink_stale_and_retry(self):
    audit=Audit();jetlink.inspect({'state':'waiting','updated':1},10,audit)
    self.assertEqual(audit.code,2)
    audit=Audit();jetlink.inspect({'state':'retrying','updated':10},10,audit)
    self.assertEqual(audit.code,1)
    audit=Audit();jetlink.inspect({'state':'waiting','updated':10},10,audit)
    self.assertEqual(audit.code,0)

  def test_remote_wrapper_keeps_failure_and_runs_next_check(self):
    # Run the actual aggregation function only; no SSH or device writes.
    src=(Path(__file__).resolve().parents[1]/'remote.sh').read_text()
    fn=src[src.index('result=0'):src.index('mode=${1:-}')]
    result=subprocess.run(['bash','-c',fn+'\nrun_check bash -c "exit 2"\nrun_check echo continued\nexit "$result"'],capture_output=True,text=True)
    self.assertEqual(result.returncode,2)
    self.assertIn('continued',result.stdout)


if __name__ == '__main__':unittest.main()
