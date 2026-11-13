from pathlib import Path
import csv,json,hashlib
import numpy as np
from collections import Counter
D=Path(__file__).resolve().parent;BASE=D.parent
rows=[r for p in sorted((BASE/'data').glob('*.csv')) for r in csv.DictReader(p.open()) if '15:39:00'<=r['wall']<'15:50:00'];rows.sort(key=lambda r:int(r['mono']))
def a(k):return np.array([float(r[k]) if r[k] else np.nan for r in rows])
t=a('mono')/1e9;dt=np.diff(t,append=t[-1]+.05);v=a('vEgo');dist=a('l1dRel');valid=(a('l1Status')==1)&np.isfinite(dist);th=dist/v
mask=valid&(v>3)&(th<1)
start=np.flatnonzero(mask&~np.r_[False,mask[:-1]]);end=np.flatnonzero(mask&~np.r_[mask[1:],False])
eps=[]
for x,y in zip(start,end):
 i=x+np.argmin(th[x:y+1]);eps.append(dict(start=rows[x]['wall'],end=rows[y]['wall'],duration_s=float(dt[x:y+1].sum()),min_timegap_s=float(th[i]),at=rows[i]['wall'],gap_m=float(dist[i]),ego_kph=float(v[i]*3.6),lead_kph=float(a('l1vLead')[i]*3.6),closing_mps=float(-a('l1vRel')[i]),target_gap_m=float(a('desiredDistance')[i]),a_target=float(a('aTarget')[i]),a_ego=float(a('aEgo')[i])))
raw=[];meta=[]
for l in (D/'raw.jsonl').read_text().splitlines():
 try:r=json.loads(l)
 except json.JSONDecodeError:continue
 (meta if r['kind']=='segment' else raw).append(r)
cases=[]
for lo,hi in [('15:43:12','15:43:26'),('15:45:42','15:45:59'),('15:46:05','15:46:16'),('15:49:02','15:49:17')]:
 x=[r for r in raw if lo<=r['wall'][11:19]<=hi and all(k in r for k in ('car','control','leads','scc'))]
 c=dict(start=lo,end=hi,samples=len(x),lead_ids=dict(Counter(str(r['leads'][0]['radarTrackId']) for r in x)),lead_radar_all=all(r['leads'][0]['radar'] and r['leads'][0]['status'] for r in x),lead2_present=sum(r['leads'][1]['status'] for r in x),max_age_s={k:max(r['age'][k] for r in x) for k in ('car','control','leads','scc')},forward_warning_count=sum(r['plan']['fcw'] for r in x),brake_disabled_count=sum(not r['plan']['allowBrake'] for r in x),stop_requests=sum(r['scc']['StopReq']!=0 for r in x),blinkers=sum(r['car']['leftBlinker'] or r['car']['rightBlinker'] for r in x),pedals=sum(r['car']['gasPressed'] or r['car']['brakePressed'] for r in x))
 for metric,fn in [('minimum_distance',lambda r:r['leads'][0]['dRel']),('minimum_time_gap',lambda r:r['leads'][0]['dRel']/r['car']['vEgo']),('strongest_deceleration',lambda r:r['car']['aEgo'])]:
  q=min(x,key=fn);c[metric]={'wall':q['wall'],'ego_kph':q['car']['vEgo']*3.6,'lead_kph':q['leads'][0]['vLead']*3.6,'gap_m':q['leads'][0]['dRel'],'vrel':q['leads'][0]['vRel'],'target_gap_m':q['plan']['desiredDistance'],'aEgo':q['car']['aEgo'],'aTarget':q['plan']['aTarget']}
 cases.append(c)
summary=dict(short_time_gap_episodes=eps,total_short_time_gap_s=float(dt[mask].sum()),eligible_time_s=float(dt[valid&(v>3)].sum()),distance_under7m_and_speed_over20kph_seconds=float(dt[valid&(dist<7)&(v>20/3.6)].sum()),raw_segments=meta,cases=cases)
# Representative, sorted raw-log observations nearest to requested wall seconds.
snap=[]
for wall in ['15:45:44','15:45:46','15:45:48','15:45:50','15:45:52','15:45:53','15:45:54','15:46:08','15:46:09','15:46:10','15:46:11','15:46:12']:
 q=next(r for r in raw if r['wall'][11:19]==wall and 'leads' in r)
 snap.append(q)
summary['snapshots']=snap
(D/'findings.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print('SHORT HEADWAY EPISODES');print(json.dumps(eps,indent=2));print('total',summary['total_short_time_gap_s'],'under7m and >20kph',summary['distance_under7m_and_speed_over20kph_seconds'])
print('RAW SNAPSHOTS wall gap target ve vl vr aLead base target actual preview req')
for r in snap:
 print(r['wall'][11:23],*[round(z,3) for z in [r['leads'][0]['dRel'],r['plan']['desiredDistance'],r['car']['vEgo']*3.6,r['leads'][0]['vLead']*3.6,r['leads'][0]['vRel'],r['leads'][0]['aLeadK'],r['plan']['aTargetBase'],r['plan']['aTarget'],r['car']['aEgo'],r['plan']['leadPreviewSeconds'],r['scc']['aReqValue']]])
