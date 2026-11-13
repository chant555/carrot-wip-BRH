import csv, glob
def f(x):
  try: return float(x)
  except (TypeError, ValueError): return None
def load(t0='15:39:00', t1='15:50:00'):
  rows = [r for p in sorted(glob.glob('data/l128_p*.csv')) for r in csv.DictReader(open(p))]
  rows.sort(key=lambda r: int(r['mono']))
  rows = [r for r in rows if r['wall'] and t0 <= r['wall'] < t1]
  m0 = int(rows[0]['mono'])
  for r in rows:
    r['t'] = (int(r['mono']) - m0) / 1e9
    for k in ('vEgo','aEgo','accelCmd','aTarget','aTargetBase','tFollow','desiredDistance','l1dRel','l1vRel','l1vLead','l1aLead','sccReq','sccRaw','sccJL','sccJU','vTargetNow','jTargetNow','leadPreviewAccel','aChangeCost'):
      r[k] = f(r[k])
  return rows
