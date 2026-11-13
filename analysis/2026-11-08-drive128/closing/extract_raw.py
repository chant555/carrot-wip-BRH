import json, warnings, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from openpilot.tools.lib.logreader import LogReader
from opendbc.can import CANPacker
from opendbc.can.parser import get_raw_value
root=Path('/data/media/0/realdata');route='00000128--996b87d9ef'
sigs=CANPacker('hyundai_canfd_generated').dbc.name_to_msg['SCC_CONTROL'].sigs
keys=['TFollowGap1','TFollowGap2','TFollowGap3','TFollowGap4','StopDistanceCarrot','ComfortBrake','LeadAccelResponse','LeadAccelResponseTF1','LeadAccelResponseTF2','LeadAccelResponseTF3','LeadAccelResponseTF4','LongActuatorDelay','LeadDecelResponse','LeadDecelResponseTF1','SpeedTFFactor','DynamicTFollow','UseBigModel']
for seg in [23,25,26,29]:
 path=root/f'{route}--{seg}'/'rlog.zst';st={};times={};offset=None;meta={'seg':seg,'path':str(path),'size':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()};n=0
 with warnings.catch_warnings(record=True) as caught:
  warnings.simplefilter('always')
  for m in LogReader(str(path),sort_by_time=True):
   k=m.which();t=m.logMonoTime/1e9
   if k=='initData':
    offset=(m.initData.wallTimeNanos-m.logMonoTime)/1e9;meta['commit']=m.initData.gitCommit
    try:
     ps={p.key:bytes(p.value).decode(errors='replace') for p in m.initData.params.entries};meta['params']={k:ps.get(k) for k in keys}
    except Exception as e:meta['params_error']=str(e)
   elif k=='clocks':offset=m.clocks.wallTimeNanos/1e9-t
   elif k=='carState':
    c=m.carState;st['car']={q:getattr(c,q) for q in ('vEgo','aEgo','gasPressed','brakePressed','standstill','canValid','steeringAngleDeg','leftBlinker','rightBlinker')};times['car']=t
   elif k=='carControl':
    c=m.carControl;st['control']={'enabled':c.enabled,'longActive':c.longActive,'accel':c.actuators.accel};times['control']=t
   elif k=='radarState':
    st['leads']=[{q:getattr(l,q) for q in ('status','radarTrackId','dRel','vRel','vLead','aLeadK','radar')} for l in (m.radarState.leadOne,m.radarState.leadTwo)];times['leads']=t
   elif k=='sendcan':
    for x in m.sendcan:
     if x.address==0x1a0 and x.src==0:
      st['scc']={q:get_raw_value(x.dat,sigs[q])*sigs[q].factor+sigs[q].offset for q in ('ACCMode','StopReq','aReqRaw','aReqValue','JerkUpperLimit','JerkLowerLimit')};times['scc']=t
   elif k=='longitudinalPlan' and offset is not None:
    wall=datetime.fromtimestamp(t+offset,timezone(timedelta(hours=9))).isoformat()
    p=m.longitudinalPlan
    plan={q:getattr(p,q) for q in ('aTarget','aTargetBase','leadPreviewSeconds','leadPreviewAccel','aChangeCost','tFollow','desiredDistance','fcw','allowBrake','shouldStop')}
    plan['source']=str(p.longitudinalPlanSource);plan['fastLeadReason']=str(p.fastLeadReason)
    plan['fastLeadTrackId']=p.fastLeadTrackId;plan['liveTracksAge']=t-p.liveTracksMonoTime/1e9
    print(json.dumps(dict(kind='sample',seg=seg,mono=t,wall=wall,age={q:t-v for q,v in times.items()},plan=plan,**st)),flush=False);n+=1
  meta['warnings']=[str(w.message) for w in caught]
 meta['kind']='segment';meta['samples']=n;print(json.dumps(meta),flush=True)
