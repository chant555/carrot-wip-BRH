from pathlib import Path
import json
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib import font_manager
D=Path(__file__).resolve().parent
r=[]
for l in (D/'raw.jsonl').read_text().splitlines():
 try:x=json.loads(l)
 except:continue
 if x.get('kind')=='sample' and all(k in x for k in ('car','leads','scc')):r.append(x)
font=Path('/home/jooheon/C4_500/analysis/2026-10-26-rebase/repo/openpilot/selfdrive/assets/fonts/KaiGenGothicKR-Bold.ttf');font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name();plt.rcParams['axes.unicode_minus']=False
fig,axs=plt.subplots(3,2,figsize=(13,8),layout='constrained')
for col,(lo,hi,title) in enumerate([('15:45:43','15:45:58','비슷한 감속으로 접근 속도가 오래 남는 경우'),('15:46:06','15:46:16','앞차 감속 전환 뒤 자차 가속이 남는 경우')]):
 x=[a for a in r if lo<=a['wall'][11:19]<=hi];t=[datetime.fromisoformat(a['wall']).replace(tzinfo=None) for a in x]
 axs[0,col].plot(t,[a['car']['vEgo']*3.6 for a in x],label='자차',color='#1677bd');axs[0,col].plot(t,[a['leads'][0]['vLead']*3.6 for a in x],label='앞차',color='#e07a16')
 axs[0,col].set_title(title,fontsize=11)
 axs[1,col].plot(t,[a['leads'][0]['dRel'] for a in x],label='실제 기록 거리',color='#1677bd');axs[1,col].plot(t,[a['plan']['desiredDistance'] for a in x],label='계획기 목표 거리',color='#e07a16');axs[1,col].axhline(5.8,label='정지 거리 설정 5.8m',ls=':',color='grey')
 axs[2,col].plot(t,[a['car']['aEgo'] for a in x],label='자차 실제',color='#1677bd');axs[2,col].plot(t,[a['plan']['aTarget'] for a in x],label='자차 목표',color='#bd3232');axs[2,col].plot(t,[a['leads'][0]['aLeadK'] for a in x],label='앞차 추정',color='#e07a16',alpha=.8);axs[2,col].axhline(0,lw=.7,color='grey')
 for ax in axs[:,col]:ax.grid(alpha=.2);ax.xaxis.set_major_locator(md.SecondLocator(interval=3));ax.xaxis.set_major_formatter(md.DateFormatter('%H:%M:%S'));ax.legend(fontsize=8,loc='upper right')
for ax,label in zip(axs[:,0],['속도 (km/h)','거리 (m)','가속도 (m/s²)']):ax.set_ylabel(label)
fig.suptitle('주행 128 · 감속 중 차간이 가까워지는 과정 (2026-11-07, 한국시간)',fontsize=14)
fig.savefig(D/'closing-patterns.png',dpi=150)
print(D/'closing-patterns.png')
