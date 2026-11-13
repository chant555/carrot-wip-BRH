import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
R=Path(__file__).resolve().parent
font='/home/jooheon/C4_500/analysis/2026-10-26-rebase/repo/openpilot/selfdrive/assets/fonts/KaiGenGothicKR-Bold.ttf'
from matplotlib import font_manager
font_manager.fontManager.addfont(font);plt.rcParams['font.family']=FontProperties(fname=font).get_name();plt.rcParams['axes.unicode_minus']=False
cases=[('observed','실제 로그','#777777','--'),('before_aggressive_closed_lag0.05_tau0.15_observed','복원 전 aggressive','#db951f','-'),('after_aggressive_closed_lag0.05_tau0.15_observed','복원 후 aggressive','#c93636','-'),('after_standard_closed_lag0.05_tau0.15_observed','복원 후 standard','#2469b5','-')]
fig,axs=plt.subplots(3,2,figsize=(13,9),sharex='col');windows=[(102,118,'15:45:42~58'),(125,136,'15:46:05~16')]
for name,label,col,ls in cases:
 data=json.loads((R/(name+'.json')).read_text())
 for c,(lo,hi,title)in enumerate(windows):
  a=[s for s in data if lo<=s['t']<=hi];x=[s['t']-(60 if c==0 else 120)for s in a]
  for row,(key,ylabel)in enumerate([('d','앞차 거리 (m)'),('closing','접근속도 (m/s)'),('a','자차 가속도 (m/s²)')]):
   axs[row,c].plot(x,[s[key]for s in a],label=label,color=col,linestyle=ls,linewidth=1.6)
for c,(_,_,title) in enumerate(windows):
 axs[0,c].set_title(title);axs[2,c].set_xlabel('해당 분의 초')
 for row,ylabel in enumerate(['앞차 거리 (m)','접근속도 (m/s)','자차 가속도 (m/s²)']):
  axs[row,c].set_ylabel(ylabel);axs[row,c].grid(alpha=.2)
  if row>0:axs[row,c].axhline(0,color='gray',linewidth=.5)
handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=4,bbox_to_anchor=(.5,.965),fontsize=10)
fig.suptitle('주행 128: 동일한 앞차 움직임을 사용한 복원 전후 모의 비교',fontsize=15,y=.995)
fig.text(.5,.012,'실제 로그 외 곡선은 모의 결과입니다. 복원 전 재현의 거리 오차는 평균제곱근 기준 1.16m입니다.',ha='center',fontsize=10)
fig.tight_layout(rect=[0,.035,1,.93]);fig.savefig(R/'comparison.png',dpi=150);plt.close(fig)
