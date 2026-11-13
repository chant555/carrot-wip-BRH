import json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent
raw=[json.loads(x)for x in (R/'raw.jsonl').read_text().splitlines()if x.startswith('{')];samples=[r for r in raw if r['kind']=='sample' and 'car'in r and 'leads'in r]
def ts(s):return int(s[11:13])*3600+int(s[14:16])*60+float(s[17:].split('+')[0])-56640
rt=np.array([ts(r['wall'])for r in samples]);grid=np.arange(np.ceil(rt[0]/.05)*.05,180.,.05);ix=np.clip(np.searchsorted(rt,grid,side='right')-1,0,len(samples)-1);rows=[samples[i]for i in ix]
obs=[dict(t=float(t),v=r['car']['vEgo'],a=r['car']['aEgo'],d=r['leads'][0]['dRel'],closing=-r['leads'][0]['vRel'],target=r['plan']['aTarget'],desired=r['plan']['desiredDistance'],tf=r['plan']['tFollow']) for t,r in zip(grid,rows)]
(R/'observed.json').write_text(json.dumps(obs))
windows={'full':(60,180),'45_brake':(102,118),'46_brake':(125,136)}
def metric(data,lo,hi):
 r=[s for s in data if lo<=s['t']<hi];t=np.array([s['t']for s in r]);d=np.array([s['d']for s in r]);v=np.array([s['v']for s in r]);a=np.array([s['a']for s in r]);c=np.array([s['closing']for s in r]);cmd=np.array([s['target']for s in r]);k=int(np.argmin(d))
 return {'min_distance_m':float(min(d)),'min_distance_t':float(t[k]),'speed_at_min_kph':float(v[k]*3.6),'max_closing_mps':float(max(c)),'min_accel_mps2':float(min(a)),'min_target_mps2':float(min(cmd)),'min_timegap_s':float(min(d[np.maximum(v,0)>3]/v[v>3])),'under1s_time':float(np.sum((v>3)&(d/v<1))*.05),'peak_target_jerk':float(max(abs(np.diff(cmd)/.05)))}
all={'recorded':{w:metric(obs,*b)for w,b in windows.items()}}
for p in sorted(R.glob('*_closed_*.json')):
 data=json.loads(p.read_text());all[p.stem]={w:metric(data,*b)for w,b in windows.items()}
 if p.stem=='before_aggressive_closed_lag0.05_tau0.15_observed':
  keep=np.array([s['t']>=60 for s in data]);all['baseline_error']={k:{'rmse':float(np.sqrt(np.mean((np.array([s[k]for s in data])[keep]-np.array([s[k]for s in obs])[keep])**2))),'max_abs':float(max(abs(np.array([s[k]for s in data])[keep]-np.array([s[k]for s in obs])[keep])))}for k in ['d','v','a']}
(R/'metrics.json').write_text(json.dumps(all,indent=2))
for k,r in all.items():
 print(k)
 if k=='baseline_error':print(r);continue
 for win,s in r.items():print(win,*(f'{q}={s[q]:.3f}'for q in ['min_distance_m','max_closing_mps','min_accel_mps2','min_timegap_s','under1s_time']))
