"""Offline actual-acados controller counterfactual; no messages or Params writes."""
import os,sys,json,types,importlib.util,ast,hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
ROOT=Path(__file__).resolve().parent
assert Path('/data/params/d/IsOffroad').read_text().strip()=='1'
from openpilot.cereal import log
from openpilot.common.constants import CV
from openpilot.common.realtime import DT_MDL
from openpilot.selfdrive.carrot.t_follow import get_speed_t_follow_factor,ramp_mode_t_follow_factor,ramp_t_follow,get_t_follow_mode_max
from openpilot.selfdrive.modeld.constants import ModelConstants
from openpilot.selfdrive.controls.lib.drive_helpers import get_accel_from_plan,CONTROL_N
import openpilot.selfdrive.controls.lib.longitudinal_preview as pv

# Reuse exact production TF methods without constructing Params or any planner service.
p=Path('/data/openpilot/openpilot/selfdrive/carrot/carrot_functions.py')
tree=ast.parse(p.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CarrotPlanner')
names={'_get_base_t_follow','_apply_speed_t_follow_scale','_apply_decel_hold_and_boost_t_follow','_clip_t_follow','get_T_FOLLOW'}
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
c=ast.ClassDef(name='Follow',bases=[],keywords=[],body=methods,decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[c],type_ignores=[])),str(p),'exec'))
DT=.05;TIMES=ModelConstants.T_IDXS[:CONTROL_N]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def make_controller(variant,personality,first,experiment):
 gap=load('replay_gap_'+variant,ROOT/'snapshots'/f'{variant}_longitudinal_gap_recovery.py')
 m=load('replay_mpc_'+variant,ROOT/'snapshots'/f'{variant}_long_mpc.py');m.LeadGapState=gap.LeadGapState;m.displayed_follow_distance=gap.displayed_follow_distance
 ctrl=m.LongitudinalMpc();ctrl.failures=[]
 real_solver=ctrl.solver
 class AuditSolver:
  def __getattr__(self,k):return getattr(real_solver,k)
  def solve(self):
   code=real_solver.solve()
   if code:ctrl.failures.append(int(code))
   return code
 ctrl.solver=AuditSolver()
 if experiment=='brake_cost':
  original=ctrl.set_weights
  def weights(*args,**kw):
   if getattr(ctrl,'closing_guard',False):kw['a_change_cost_factor']=min(.5,kw.get('a_change_cost_factor',1.))
   return original(*args,**kw)
  ctrl.set_weights=weights
 f=Follow();f.speedTFFactor=17;f.tFollowGap1=.46;f.tFollowGap2=.65;f.tFollowGap3=.85;f.tFollowGap4=1.10
 f.tFollowDecelBoost=0.;f.myTFollowFactor=1.;f._tf_decel_extra=0.;f._tf_applied=first['plan']['tFollow'];f._tf_decel_base=None;f._tf_mode_factor=None;f._tf_base_last=first['plan']['tFollow'];f.t_follow_last=f._tf_base_last
 f.comfort_brake=2.4;f.stop_distance=5.8;f.v_cruise=100/3.6;f.stop_dist=1000.;f.mode='acc';f.trafficStopDistanceAdjust=-1.;f.lane_change_active=False
 f.leadAccelResponse=4 if personality=='aggressive' else 3
 return NS(m=m,mpc=ctrl,carrot=f,vfilter=first['car']['vEgo'],adesired=first['car']['aEgo'],preview=0.,ids=[-1,-1],counts=[0,0],personality=getattr(log.LongitudinalPersonality,personality),experiment=experiment)

def step(c,v,a,leads,vcruise):
 c.vfilter=max(0.,(1-DT/(2.+DT))*c.vfilter+DT/(2.+DT)*v)
 for i,l in enumerate(leads):
  tid=int(l.radarTrackId) if l.status and l.radar and l.radarTrackId>=0 else -1
  c.counts[i]=c.counts[i]+1 if tid>=0 and tid==c.ids[i] else (1 if tid>=0 else 0);c.ids[i]=tid
 c.carrot.v_cruise=vcruise
 amax=float(np.interp(v,np.array([0,10,40,60,80,110,140])/3.6,[1.5,1.7,1.3,.9,.7,.6,.6]))
 c.mpc.set_accel_limits(min(-2.,c.adesired+.05),amax);c.mpc.set_cur_state(c.vfilter,c.adesired)
 c.mpc.closing_guard=leads[0].status and leads[0].vRel<-.5 and leads[0].aLeadK<-.1
 c.mpc.update(c.carrot,False,NS(leadOne=leads[0],leadTwo=leads[1]),vcruise,*[np.zeros(c.m.N+1) for _ in range(4)],personality=c.personality,prev_accel_constraint=True,lead_accel_response_enabled=True,lead_gap_enabled=True,lead_track_frames=c.counts,measured_a_ego=a,cutout_relief_enabled=True)
 vt=np.interp(TIMES,c.m.T_IDXS,c.mpc.v_solution);at=np.interp(TIMES,c.m.T_IDXS,c.mpc.a_solution)
 old=c.adesired;c.adesired=float(np.interp(DT,TIMES,at));c.vfilter+=DT*(old+c.adesired)/2
 action=.25;base=float(get_accel_from_plan(vt,at,TIMES,action_t=action)[0])
 lead=leads[1] if c.mpc.source=='lead1' else leads[0]
 req=pv.get_lead_preview_request(3,lead_status=lead.status and lead.radar and lead.radarTrackId>=0,a_lead=lead.aLeadK,a_ego=a)
 c.preview=pv.clip_preview_offset(action,pv.rate_limit_preview(req.offset_s,c.preview))
 predicted=float(get_accel_from_plan(vt,at,TIMES,action_t=action+c.preview)[0])
 target=pv.apply_preview_target(base,predicted,3)
 if c.experiment=='preview_030' and base<0:target=min(base,max(predicted,base-.30))
 return dict(target=target,base=base,tf=c.mpc.t_follow,desired=c.mpc.desired_distance,preview=c.preview,cost=c.mpc.a_change_cost,gapmargin=float(c.mpc.lead_gap_margins[0,0]))

raw=[json.loads(x) for x in (ROOT/'raw.jsonl').read_text().splitlines() if x.startswith('{')];samples=[x for x in raw if x['kind']=='sample' and 'car'in x and 'leads'in x]
def secs(s):return int(s[11:13])*3600+int(s[14:16])*60+float(s[17:])
# ISO timezone suffix is stripped explicitly.
t0=15*3600+44*60
rt=np.array([secs(x['wall'].split('+')[0])-t0 for x in samples]);grid=np.arange(np.ceil(rt[0]/DT)*DT,min(180.,rt[-1]),DT)
ix=np.clip(np.searchsorted(rt,grid,side='right')-1,0,len(rt)-1);rows=[samples[i] for i in ix]
vel=np.array([r['car']['vEgo'] for r in rows]);acc=np.array([r['car']['aEgo'] for r in rows]);target=np.array([r['plan']['aTarget'] for r in rows]);dist=np.array([r['leads'][0]['dRel'] for r in rows]);lv=np.array([r['leads'][0]['vLead'] for r in rows])
xobs=np.r_[0.,np.cumsum((vel[1:]+vel[:-1])*.5*DT)];leadworld=xobs+dist
# Using the observed lead world path anchors the measured ranges; recorded lead-speed estimates are retained.
# A second world path integrates recorded lead speed and quantifies sensitivity to this discrepancy.
leadint=np.r_[0.,np.cumsum((lv[1:]+lv[:-1])*.5*DT)]
release=int(np.searchsorted(grid,60.));leadint+=leadworld[release]-leadint[release]
train=(grid>=10)&(grid<60);test=(grid>=60)
def plant_series(lag,tau,command=target):
 out=np.empty_like(acc);out[0]=acc[0];delay=int(round(lag/DT));alpha=1 if tau==0 else 1-np.exp(-DT/tau)
 for i in range(1,len(out)):out[i]=out[i-1]+alpha*(command[max(0,i-1-delay)]-out[i-1])
 return out
fit=[]
for lag in np.arange(0,.451,.05):
 for tau in np.arange(0,.401,.05):
  out=plant_series(lag,tau);fit.append((float(np.mean((out[train]-acc[train])**2)),float(lag),float(tau),float(np.sqrt(np.mean((out[test]-acc[test])**2)))))
fit.sort();best=fit[0]
meta={'fit_mse_training':best[0],'lag':best[1],'tau':best[2],'test_accel_rmse':best[3],'samples':len(rows),'start':grid[0],'end':grid[-1],'lead_path_discrepancy_max_45_47':float(np.max(np.abs(leadint[test]-leadworld[test]))),'segment_metadata':[r for r in raw if r['kind']=='segment'],'fit_top10':fit[:10]}
(ROOT/'fit.json').write_text(json.dumps(meta,indent=2))

def run(variant,personality,closed=True,lag=None,tau=None,experiment='',path='observed'):
 if Path('/data/params/d/IsOffroad').read_text().strip()!='1':raise RuntimeError('Vehicle became onroad; stopping offline work')
 lag=best[1] if lag is None else lag;tau=best[2] if tau is None else tau
 c=make_controller(variant,personality,rows[0],experiment);out=[];commands=[];delay=int(round(lag/DT));alpha=1 if tau==0 else 1-np.exp(-DT/tau)
 v=vel[0];a=acc[0];x=xobs[0];leadpos=leadworld if path=='observed' else leadint
 for i,(t,r) in enumerate(zip(grid,rows)):
  if i%200==0 and Path('/data/params/d/IsOffroad').read_text().strip()!='1':raise RuntimeError('Vehicle became onroad')
  if not closed or i<=release:v=vel[i];a=acc[i];x=xobs[i]
  leads=[NS(**l) for l in r['leads']]
  if closed and i>=release:
   leads[0].dRel=float(leadpos[i]-x);leads[0].vRel=float(lv[i]-v)
  z=step(c,float(v),float(a),leads,r['car']['vCruise']/3.6*r['car']['vCluRatio'])
  out.append(dict(t=float(t),v=float(v),a=float(a),d=float(leads[0].dRel),closing=float(-leads[0].vRel),lead=float(lv[i]),**z));commands.append(z['target'] if i>=release else target[i])
  if closed and i>=release:
   newa=a+alpha*(commands[max(0,i-delay)]-a);newv=max(0.,v+DT*(a+newa)/2);x+=DT*(v+newv)/2;v,a=newv,newa
  if not all(np.isfinite(val) for val in out[-1].values()):raise RuntimeError('Nonfinite result')
 if c.mpc.failures:raise RuntimeError(f'Solver failures {c.mpc.failures}')
 name=f'{variant}_{personality}_{"closed" if closed else "fixed"}_lag{lag:.2f}_tau{tau:.2f}_{path}{"_"+experiment if experiment else ""}'
 (ROOT/(name+'.json')).write_text(json.dumps(out));print(json.dumps({'done':name,'n':len(out),'solver_failures':0}),flush=True)
 return out

if __name__=='__main__':
 mode=sys.argv[1] if len(sys.argv)>1 else 'calibrate'
 if mode=='calibrate':
  out=run('before','aggressive',closed=False)
  for key,orig in [('target',target),('tf',np.array([r['plan']['tFollow']for r in rows])),('desired',np.array([r['plan']['desiredDistance']for r in rows])),('base',np.array([r['plan']['aTargetBase']for r in rows]))]:
   err=np.array([q[key]for q in out])-orig
   print(json.dumps({'validation':key,'rmse':float(np.sqrt(np.mean(err[test]**2))),'mean':float(np.mean(err[test])),'max_abs':float(np.max(np.abs(err[test])))}),flush=True)
 elif mode=='compare':
  for var,person in [('before','aggressive'),('after','aggressive'),('before','standard'),('after','standard')]:run(var,person)
 elif mode=='sensitivity':
  for var in ['before','after']:
   for lag in [max(0.,best[1]-.1),best[1]+.1]:run(var,'aggressive',lag=lag)
   run(var,'aggressive',path='integrated')
 elif mode=='candidates':
  for person in ['aggressive','standard']:
   for exp in ['preview_030','brake_cost']:run('after',person,experiment=exp)
