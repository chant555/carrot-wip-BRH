"""감속·재가속 주기 분석: 자차 속도 골(trough)마다 앞차 대비 감속·재가속 시점, 차간, 가속도를 계산한다."""
import json
from load import load
rows = [r for r in load() if r['sccReq'] is not None]
n = len(rows)
def sm(key, w=10):  # 0.5 s 이동평균
  out, acc = [], 0.
  vals = [r[key] or 0. for r in rows]
  for i, v in enumerate(vals):
    acc += v
    if i >= w: acc -= vals[i - w]
    out.append(acc / min(i + 1, w))
  return out
v = [x * 3.6 for x in sm('vEgo')]; vl = [x * 3.6 for x in sm('l1vLead')]
# 골: 앞 피크보다 5km/h 이상 낮고 뒤에서 5km/h 이상 다시 오르는 최저점
troughs, i = [], 1
peak_i = 0
while i < n:
  if v[i] > v[peak_i]: peak_i = i
  if v[peak_i] - v[i] >= 5:
    j = i; lo = i
    while j < n and v[j] < v[lo] + 5:
      if v[j] < v[lo]: lo = j
      j += 1
    if j >= n: break
    troughs.append((peak_i, lo)); peak_i = lo; i = lo + 1
    continue
  i += 1
cyc = []
for k, (p, lo) in enumerate(troughs):
  nxt = troughs[k + 1][0] if k + 1 < len(troughs) else n - 1
  # 다음 피크: lo 이후 nxt까지 최대
  pk = max(range(lo, nxt + 1), key=lambda x: v[x])
  # 앞차 골: 자차 골 전후 ±6초 안의 앞차 최저 속도
  win = range(max(p, lo - 120), min(n, lo + 60))
  llo = min(win, key=lambda x: vl[x])
  # 감속 시작: p 이후 aEgo가 처음 -0.3 미만
  dstart = next((x for x in range(p, lo + 1) if rows[x]['aEgo'] < -0.3), lo)
  lead_dstart = next((x for x in range(max(0, p - 60), llo + 1) if (rows[x]['l1aLead'] or 0) < -0.3), llo)
  # 재가속: 앞차 최저 이후 앞차가 2km/h 오른 시점, 자차가 최저+2km/h, aEgo>0.2 첫 시점
  lead_go = next((x for x in range(llo, n) if vl[x] >= vl[llo] + 2), None)
  ego_go = next((x for x in range(lo, n) if v[x] >= v[lo] + 2), None)
  ego_acc = next((x for x in range(lo, n) if rows[x]['aEgo'] > 0.2), None)
  seg = rows[lo:pk + 1]
  src_reaccel = sum(r['source'] == 'cruise' for r in seg) / max(1, len(seg))
  # 재가속 중 과접근: 재가속 시작 후 다음 피크까지 최소 차간과 그때 상대속도
  after = range(ego_go or lo, pk + 1)
  dmin_after = min(after, key=lambda x: rows[x]['l1dRel'] or 99) if len(after) else lo
  T = lambda x: round(rows[x]['t'], 2) if x is not None else None
  cyc.append(dict(
    wall=rows[lo]['wall'][:8], v_peak=round(v[p], 1), v_min=round(v[lo], 1), v_next_peak=round(v[pk], 1),
    lead_v_min=round(vl[llo], 1), ego_trough_after_lead_trough_s=round(rows[lo]['t'] - rows[llo]['t'], 2),
    decel_onset_after_lead_s=round(rows[dstart]['t'] - rows[lead_dstart]['t'], 2),
    a_min=round(min(r['aEgo'] for r in rows[p:lo + 1]), 2), aT_min=round(min(r['aTarget'] for r in rows[p:lo + 1]), 2),
    gap_at_decel_onset=rows[dstart]['l1dRel'], gap_min_decel=round(min(r['l1dRel'] for r in rows[p:lo + 1] if r['l1dRel'] is not None), 1),
    gap_at_trough=rows[lo]['l1dRel'], desired_at_trough=rows[lo]['desiredDistance'],
    go_delay_s=round(rows[ego_go]['t'] - rows[lead_go]['t'], 2) if lead_go and ego_go else None,
    accel_start_after_lead_go_s=round(rows[ego_acc]['t'] - rows[lead_go]['t'], 2) if lead_go and ego_acc else None,
    gap_at_lead_go=rows[lead_go]['l1dRel'] if lead_go else None, gap_at_ego_go=rows[ego_go]['l1dRel'] if ego_go else None,
    a_max_reaccel=round(max(r['aEgo'] for r in seg), 2), aT_max_reaccel=round(max(r['aTarget'] for r in seg), 2),
    reaccel_cruise_source=round(src_reaccel, 2), gap_min_reaccel=rows[dmin_after]['l1dRel'], vrel_at_gap_min=rows[dmin_after]['l1vRel'],
  ))
json.dump(cyc, open('cycles.json', 'w'), indent=1, ensure_ascii=False)
hdr = ['wall','v_peak','v_min','v_next_peak','lead_v_min','ego_trough_after_lead_trough_s','decel_onset_after_lead_s','a_min','aT_min','gap_at_decel_onset','gap_min_decel','gap_at_trough','desired_at_trough','go_delay_s','accel_start_after_lead_go_s','gap_at_lead_go','gap_at_ego_go','a_max_reaccel','reaccel_cruise_source','gap_min_reaccel','vrel_at_gap_min']
short = ['시각','피크','최저','다음피크','앞차최저','골지연','감속개시지연','a최저','aT최저','감속시작차간','감속중최소차간','골차간','골목표','출발지연','가속개시지연','앞차출발차간','자차출발차간','재가속a최대','재가속cruise비율','재가속최소차간','그때vRel']
print(' | '.join(short))
for c in cyc: print(' | '.join(str(c[h]) for h in hdr))
print('cycles', len(cyc))
