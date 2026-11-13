"""앞차 제동 시작 순간의 차간을 기본 목표(여분 제외)와 표시 목표(여분 포함)로 나눠 비교한다.
기본 목표 = v²/(2·2.4) + tFollow·v + 5.8 - vLead²/(2·2.4)  (3791b956의 desired_follow_distance, StopDistanceCarrot=580, comfortBrake 2.4)"""
import statistics as st
from load import load
rows = [r for r in load() if r['sccReq'] is not None and r['l1dRel'] is not None and r['l1Status'] == '1']
CB, SD = 2.4, 5.8
for r in rows:
  v, vl = r['vEgo'], max(0.0, r['l1vLead'])
  r['base'] = v * v / (2 * CB) + r['tFollow'] * v + SD - vl * vl / (2 * CB)
  r['margin'] = r['desiredDistance'] - r['base']
print('전체 여분(표시 목표 - 기본 목표) 분포 m:', ' '.join(f"p{p}={sorted(x['margin'] for x in rows)[int(len(rows)*p/100)]:.2f}" for p in (5,25,50,75,95)))
print('여분 0.5m 미만 비율:', round(sum(x['margin'] < 0.5 for x in rows) / len(rows), 2))
ons = []
for i, r in enumerate(rows):
  if r['l1aLead'] < -0.5 and all(x['l1aLead'] >= -0.5 for x in rows[max(0, i - 20):i]) and (not ons or r['t'] - ons[-1]['t'] > 2):
    ons.append(r)
print(f"\n앞차 제동 시작 {len(ons)}건")
print(' 시각       시속  차간  기본목표 여분  차간-기본  차간-표시목표')
for r in ons:
  print(f" {r['wall'][:10]} {r['vEgo']*3.6:5.1f} {r['l1dRel']:5.1f} {r['base']:7.1f} {r['margin']:5.1f} {r['l1dRel']-r['base']:+8.1f} {r['l1dRel']-r['desiredDistance']:+10.1f}")
print(f"\n차간-기본목표 중앙 {st.median(r['l1dRel']-r['base'] for r in ons):+.1f}m, 기본목표보다 가까움 {sum(r['l1dRel']<r['base'] for r in ons)}/{len(ons)}")
print(f"차간-표시목표 중앙 {st.median(r['l1dRel']-r['desiredDistance'] for r in ons):+.1f}m, 표시목표보다 가까움 {sum(r['l1dRel']<r['desiredDistance'] for r in ons)}/{len(ons)}")
print(f"제동 시작 순간 여분 중앙 {st.median(r['margin'] for r in ons):.1f}m")
