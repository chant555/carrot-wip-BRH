"""[클코] 코덱 extract.py(2026-11-08-drive12ab)의 일반화 사본입니다. 사용: extract_raw.py 경로ID 구간번호... 기기에서 읽기 전용으로 실행합니다."""
import json, warnings, hashlib, sys
from pathlib import Path
from datetime import datetime
from openpilot.tools.lib.logreader import LogReader
from opendbc.can import CANPacker
from opendbc.can.parser import get_raw_value

root=Path('/data/media/0/realdata')
sigs=CANPacker('hyundai_canfd_generated').dbc.name_to_msg['SCC_CONTROL'].sigs
route=sys.argv[1]
segments=[{'route':route,'seg':int(x)} for x in sys.argv[2:]]
st={};times={};previous=None
lo,hi=float('-inf'),float('inf')
for meta0 in segments:
 route=meta0['route']
 if Path('/data/params/d/IsOffroad').read_text().strip()!='1':raise RuntimeError('device no longer offroad')
 if previous!=route:st={};times={};previous=route
 seg=meta0['seg'];path=root/f'{route}--{seg}'/'rlog.zst';offset=None;n=0
 meta=dict(meta0,kind='segment',raw_path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 with warnings.catch_warnings(record=True) as caught:
  warnings.simplefilter('always')
  for m in LogReader(str(path),sort_by_time=True):
   k=m.which();t=m.logMonoTime/1e9
   if k=='initData':offset=(m.initData.wallTimeNanos-m.logMonoTime)/1e9
   elif k=='clocks':offset=m.clocks.wallTimeNanos/1e9-t
   elif k=='carState':
    c=m.carState;st['car']={q:getattr(c,q) for q in ('vEgo','aEgo','gasPressed','brakePressed','standstill','canValid','steeringAngleDeg','leftBlinker','rightBlinker','vCruise')};times['car']=t
   elif k=='carControl':
    c=m.carControl;st['control']={'enabled':c.enabled,'longActive':c.longActive,'accel':c.actuators.accel};times['control']=t
   elif k=='controlsState':
    c=m.controlsState;st['controls']={'forceDecel':c.forceDecel,'longControlState':str(c.longControlState)};times['controls']=t
   elif k=='selfdriveState':
    c=m.selfdriveState;st['selfdrive']={'personality':str(c.personality),'experimentalMode':c.experimentalMode,'enabled':c.enabled,'active':c.active};times['selfdrive']=t
   elif k=='modelV2':st['laneChange']=str(m.modelV2.meta.laneChangeState);times['model']=t
   elif k=='radarState':
    st['radarValid']=m.valid
    st['leads']=[{q:getattr(l,q) for q in ('status','radarTrackId','dRel','vRel','vLead','aLeadK','radar','aLeadTau','modelProb','cutOutTime','cutOutConfidence')} for l in (m.radarState.leadOne,m.radarState.leadTwo)];times['leads']=t
   elif k=='sendcan':
    for x in m.sendcan:
     if x.address==0x1a0 and x.src==0:
      st['scc']={q:get_raw_value(x.dat,sigs[q])*sigs[q].factor+sigs[q].offset for q in ('ACCMode','StopReq','aReqRaw','aReqValue','JerkUpperLimit','JerkLowerLimit')};times['scc']=t
   elif k=='longitudinalPlan' and offset is not None and lo<=t+offset<=hi:
    p=m.longitudinalPlan
    plan={q:getattr(p,q) for q in ('aTarget','aTargetBase','leadPreviewSeconds','leadPreviewAccel','aChangeCost','tFollow','desiredDistance','fcw','allowBrake','shouldStop','myDrivingMode','xState','cruiseTarget','solverExecutionTime','plannerExecutionTime','fastLeadTrackId','fastLeadMask')}
    for q in ('longitudinalPlanSource','fastLeadReason','planningTrigger'):plan[q]=str(getattr(p,q))
    plan['v0']=p.speeds[0] if len(p.speeds) else None;plan['a0']=p.accels[0] if len(p.accels) else None
    plan['j0']=p.jerks[0] if len(p.jerks) else None;plan['liveTracksAge']=t-p.liveTracksMonoTime/1e9
    print(json.dumps(dict(kind='sample',route=route,seg=seg,mono=t,wall=t+offset,valid=m.valid,age={q:t-v for q,v in times.items()},plan=plan,**st)),flush=False);n+=1
  meta['warnings']=[str(w.message) for w in caught]
 meta['samples']=n;print(json.dumps(meta),flush=True)
 print(f'{route} segment {seg}: {n} samples, {len(caught)} warnings',file=sys.stderr,flush=True)
