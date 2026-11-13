from pathlib import Path
import csv, json, hashlib
from collections import Counter
from datetime import datetime, timedelta
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
BASE=Path(__file__).resolve().parents[1]; OUT=Path(__file__).resolve().parent
paths=sorted((BASE/'data').glob('l128_p*.csv'))
rows=[r for p in paths for r in csv.DictReader(p.open()) if '15:39:00' <= r['wall'] < '15:50:00']
rows.sort(key=lambda r:int(r['mono']))
def arr(k):return np.array([float(r[k]) if r[k] else np.nan for r in rows])
t=arr('mono')/1e9; dt=np.diff(t,append=t[-1]+.05)
valid=(arr('l1Status')==1)&np.isfinite(arr('l1dRel'))
q=lambda a:dict(zip(['min','p05','median','p95','max'],map(float,np.nanpercentile(a,[0,5,50,95,100]))))
cycles=json.loads((BASE/'cycles.json').read_text())
prior=[c for c in cycles if c['ego_trough_after_lead_trough_s']>=0]
future=[c['wall'] for c in cycles if c['ego_trough_after_lead_trough_s']<0]
metrics={
 'window':'2026-11-07 15:39:00 <= KST < 15:50:00', 'route':'00000128--996b87d9ef',
 'samples':len(rows),'span_seconds':float(t[-1]-t[0]),'max_sample_gap_seconds':float(np.diff(t).max()),
 'duplicate_monotonic_timestamps':int(sum(np.diff(t)==0)),
 'commit_counts':dict(Counter(r['git'] for r in rows)),
 'enabled_counts':dict(Counter(r['enabled'] for r in rows)),
 'long_active_counts':dict(Counter(r['longActive'] for r in rows)),
 'gas_counts':dict(Counter(r['gas'] for r in rows)), 'brake_counts':dict(Counter(r['brake'] for r in rows)),
 'standstill_counts':dict(Counter(r['standstill'] for r in rows)),
 'speed_kph':q(arr('vEgo')*3.6),'acceleration_mps2':q(arr('aEgo')),
 'gap_m':q(arr('l1dRel')[valid]),'desired_gap_m':q(arr('desiredDistance')[valid]),
 'gap_minus_desired_m':q((arr('l1dRel')-arr('desiredDistance'))[valid]),
 'plan_source_counts':dict(Counter(r['source'] for r in rows)),
 'automatic_speed_setting_kph':q(arr('vCruise')),
 'valid_lead_samples':int(valid.sum()),'lead_gap_under_1s_denominator_speed_gt3mps':int(sum(valid&(arr('vEgo')>3))),
 'cycles_total':len(cycles),'cycles_with_prior_lead_trough':len(prior),'ambiguous_future_lead_trough_times':future,
 'prior_subset_trough_delay_s':q(np.array([c['ego_trough_after_lead_trough_s'] for c in prior])),
 'prior_subset_plus2kph_recovery_delay_s':q(np.array([c['go_delay_s'] for c in prior])),
 'prior_subset_gap_growth_m':q(np.array([c['gap_at_ego_go']-c['gap_at_lead_go'] for c in prior])),
 'prior_subset_cruise_source_fraction_median':float(np.median([c['reaccel_cruise_source'] for c in prior])),
 'input_sha256':{str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
 'cautions':['CSV uses last-observed messages without freshness or radar track IDs.',
 '18-cycle delay statistics condition on a prior lead minimum; not an unbiased all-cycle delay.',
 'cruise source is selected from the first prediction point, not proof of no lead constraint over the full horizon.',
 'No raw-log reread or vehicle contact in this review. Route date anchored by saved clocks inventory.']}
mask=valid&(arr('vEgo')>3);short=mask&(arr('l1dRel')/arr('vEgo')<1)
metrics['time_gap_seconds']=q((arr('l1dRel')/arr('vEgo'))[mask])
metrics['time_gap_under1_fraction']=float(dt[short].sum()/dt[mask].sum())
hard=arr('aEgo') < -2
starts=np.flatnonzero(hard&~np.r_[False,hard[:-1]])
metrics['deceleration_below_minus2_events']=[rows[i]['wall'] for i in starts]
metrics['deceleration_below_minus2_seconds']=float(dt[hard].sum())
# Cross-correlation is a descriptive offset on last-observed message samples.
a=arr('aTarget');b=arr('aEgo');corr=[]
for lag in range(21):
 x=a[:-lag] if lag else a;y=b[lag:] if lag else b
 ok=np.isfinite(x)&np.isfinite(y);corr.append(float(np.corrcoef(x[ok],y[ok])[0,1]))
lag=int(np.argmax(corr));metrics['target_to_measured_best_offset_s']=lag*float(np.median(np.diff(t)));metrics['target_to_measured_correlation']=corr[lag]
errors=[]
for c in prior:
 lo=next(i for i,r in enumerate(rows) if r['wall'][:8]==c['wall'])
 win=(t>=t[lo]-6)&(t<=t[lo])&valid
 errors.append(float(np.min((arr('l1dRel')-arr('desiredDistance'))[win])))
metrics['prior_subset_ego_min_at_least_2kph_below_lead_count']=sum(c['v_min']<=c['lead_v_min']-2 for c in prior)
(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False)+'\n')
font=Path('/home/jooheon/C4_500/analysis/2026-10-26-rebase/repo/openpilot/selfdrive/assets/fonts/KaiGenGothicKR-Bold.ttf')
font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
plt.rcParams['axes.unicode_minus']=False
wall=np.array([datetime.strptime('2026-11-07 '+r['wall'],'%Y-%m-%d %H:%M:%S.%f') for r in rows])
lead=arr('l1vLead')*3.6;lead[~valid]=np.nan
fig,axs=plt.subplots(3,1,figsize=(13,8),sharex=True,layout='constrained')
axs[0].plot(wall,lead,label='앞차 추정 속도',color='#e07a16',lw=1.2);axs[0].plot(wall,arr('vEgo')*3.6,label='자차 속도',color='#1677bd',lw=1.2);axs[0].set_ylabel('속도 (km/h)')
axs[1].plot(wall,arr('aTarget'),label='목표 가속도',color='#e07a16',lw=1.1);axs[1].plot(wall,arr('aEgo'),label='실제 가속도',color='#1677bd',lw=.9);axs[1].axhline(0,color='grey',lw=.6);axs[1].set_ylabel('가속도 (m/s²)')
axs[2].plot(wall,np.where(valid,arr('l1dRel'),np.nan),label='앞차 거리',color='#1677bd',lw=1.1);axs[2].plot(wall,arr('desiredDistance'),label='계획기 목표 거리',color='#e07a16',lw=1.1);axs[2].set_ylabel('거리 (m)');axs[2].set_xlabel('한국시간 — 2026년 11월 7일')
for ax in axs:ax.grid(alpha=.2);ax.legend(loc='upper right',ncols=2)
axs[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
fig.suptitle('주행 128 · 15:39–15:50 감속과 재가속 (상류 복원 전 3791b956)',fontsize=15)
fig.savefig(OUT/'drive128-overview.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(3,2,figsize=(13,8),layout='constrained')
for col,(start,end,title) in enumerate([('15:41:39','15:41:53','완만한 감속 뒤 회복'),('15:44:59','15:45:12','앞차보다 더 감속한 뒤 회복')]):
 mask=np.array([start<=r['wall']<end for r in rows]);x=wall[mask]
 axs[0,col].plot(x,lead[mask],label='앞차',color='#e07a16');axs[0,col].plot(x,(arr('vEgo')*3.6)[mask],label='자차',color='#1677bd');axs[0,col].set_title(title)
 axs[1,col].plot(x,arr('aTarget')[mask],label='목표',color='#e07a16');axs[1,col].plot(x,arr('aEgo')[mask],label='실제',color='#1677bd');axs[1,col].axhline(0,color='grey',lw=.7)
 axs[2,col].plot(x,arr('l1dRel')[mask],label='앞차 거리',color='#1677bd');axs[2,col].plot(x,arr('desiredDistance')[mask],label='목표 거리',color='#e07a16')
 for ax in axs[:,col]:ax.grid(alpha=.2);ax.legend(loc='upper left');ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'));ax.xaxis.set_major_locator(mdates.SecondLocator(interval=4))
for ax,label in zip(axs[:,0],['속도 (km/h)','가속도 (m/s²)','거리 (m)']):ax.set_ylabel(label)
fig.suptitle('앞차가 속도를 회복해도 자차의 감속이 잠시 이어지는 사례',fontsize=15)
fig.savefig(OUT/'drive128-examples.png',dpi=150);plt.close(fig)
print(json.dumps({k:v for k,v in metrics.items() if k not in ('input_sha256','cautions')},indent=2,ensure_ascii=False))
