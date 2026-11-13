"""앞차 제동 시작 대비 자차 제동 시작 지연과 그동안의 접근(차간·TTC)을 감속 사건마다 계산한다."""
import statistics as st
from load import load
rows = [r for r in load() if r['sccReq'] is not None and r['l1dRel'] is not None]
n = len(rows)
ev, i = [], 0
while i < n:
  r = rows[i]
  # 앞차 제동 시작: aLead가 -0.5 아래로 내려가는 첫 프레임(직전 1초는 -0.5 이상)
  if r['l1Status'] == '1' and r['l1aLead'] < -0.5 and all(x['l1aLead'] >= -0.5 for x in rows[max(0, i - 20):i]):
    j0 = i
    ego = next((k for k in range(j0 - 20, min(n, j0 + 80)) if k >= 0 and rows[k]['aTarget'] < -0.5), None)
    end = min(n, j0 + 120)
    win = rows[j0:end]
    close = [x for x in win if x['l1vRel'] < -0.1]
    ttc = min((x['l1dRel'] / -x['l1vRel'] for x in close), default=99)
    dmin = min(x['l1dRel'] for x in win)
    k = min(range(j0, end), key=lambda q: rows[q]['l1dRel'])
    ev.append(dict(wall=r['wall'][:10], v=round(r['vEgo'] * 3.6, 1), d0=round(r['l1dRel'], 1), des0=round(r['desiredDistance'], 1),
                   err0=round(r['l1dRel'] - r['desiredDistance'], 1), vrel0=round(r['l1vRel'], 2),
                   lead_amin=round(min(x['l1aLead'] for x in win), 2),
                   ego_delay=round(rows[ego]['t'] - r['t'], 2) if ego is not None else None,
                   ego_amin=round(min(x['aEgo'] for x in win), 2), dmin=round(dmin, 1),
                   err_min=round(rows[k]['l1dRel'] - rows[k]['desiredDistance'], 1), tg_min=round(rows[k]['l1dRel'] / max(rows[k]['vEgo'], .1), 2),
                   ttc=round(ttc, 1), preview=round(r['leadPreviewAccel'], 2)))
    i = j0 + 40
    continue
  i += 1
print('앞차제동시작 | 시속 | 차간 | 목표 | 차간-목표 | vRel | 앞차a최저 | 자차제동지연s | 자차a최저 | 최소차간 | 그때 차간-목표 | 그때 차간시간 | TTC최소 | preview')
for e in ev: print(' | '.join(str(e[k]) for k in ('wall','v','d0','des0','err0','vrel0','lead_amin','ego_delay','ego_amin','dmin','err_min','tg_min','ttc','preview')))
d = [e['ego_delay'] for e in ev if e['ego_delay'] is not None]
print(f"\n사건 {len(ev)}개, 자차 제동 지연 중앙 {st.median(d):.2f}s (범위 {min(d):.2f}~{max(d):.2f}), 1초 이상 {sum(x>=1 for x in d)}개")
print(f"최소 차간 중앙 {st.median(e['dmin'] for e in ev):.1f}m, 목표보다 3m 이상 가까워진 사건 {sum(e['err_min']<=-3 for e in ev)}개, 차간시간 1초 미만 {sum(e['tg_min']<1 for e in ev)}개, TTC 5초 미만 {sum(e['ttc']<5 for e in ev)}개")
near = [e for e in ev if e['err_min'] <= -3]
far = [e for e in ev if e['err_min'] > -3]
if near and far:
  print(f"가까워진 사건: 시작 차간-목표 중앙 {st.median(e['err0'] for e in near):+.1f}m, 앞차a최저 중앙 {st.median(e['lead_amin'] for e in near):.2f}, 제동지연 중앙 {st.median(e['ego_delay'] for e in near if e['ego_delay'] is not None):.2f}s")
  print(f"그 외 사건   : 시작 차간-목표 중앙 {st.median(e['err0'] for e in far):+.1f}m, 앞차a최저 중앙 {st.median(e['lead_amin'] for e in far):.2f}, 제동지연 중앙 {st.median(e['ego_delay'] for e in far if e['ego_delay'] is not None):.2f}s")
