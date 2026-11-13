"""[클코] 코덱 형식 raw를 40초 창(앞 10초 기록값, 뒤 30초 폐회로)으로 자른다. 사용: prepare_windows.py raw.jsonl.gz 출력이름 성향
끊김(0.5초 넘는 표본 간격)이 없는 구간 안에서만 30초 간격으로 창을 만든다. 시각은 각 표본의 wall(맞춰진 시계)로 표시한다."""
import json, gzip, sys, datetime
import numpy as np
src, name, pers = sys.argv[1:4]
KST = datetime.timezone(datetime.timedelta(hours=9))
raw = [json.loads(l) for l in gzip.open(src, 'rt') if l.startswith('{')]
rr = [r for r in raw if r['kind'] == 'sample' and 'car' in r and 'leads' in r and 'control' in r]
ts = np.array([r['mono'] for r in rr]); off = rr[-1]['wall'] - rr[-1]['mono']
breaks = [0] + [i for i in range(1, len(ts)) if ts[i] - ts[i - 1] > 0.5] + [len(ts)]
cases, manifest = [], []
for a, b in zip(breaks, breaks[1:]):
  for w0 in np.arange(ts[a], ts[b - 1] - 40, 30.0):
    grid = w0 + np.arange(0, 40.0001, .05)
    ix = np.clip(np.searchsorted(ts, grid, side='right') - 1, a, b - 1); rows = [rr[i] for i in ix]; samples = []
    for t, r in zip(grid, rows):
      ages = r['age']; car = r['car']; ctrl = r['control']; pl = r['plan']
      eligible = (r['valid'] and r.get('radarValid', False) and ctrl['enabled'] and ctrl['longActive'] and car['canValid'] and not car['gasPressed'] and not car['brakePressed']
                  and not car['leftBlinker'] and not car['rightBlinker'] and r.get('laneChange', 'off') == 'off' and not r['controls']['forceDecel']
                  and not r['selfdrive']['experimentalMode'] and not pl['shouldStop'] and ages['leads'] < .15)
      samples.append({'t': float(t - w0 - 10), 'car': {k: car[k] for k in ('vEgo', 'aEgo')}, 'plan': {k: pl[k] for k in ('tFollow', 'aTarget', 'v0', 'a0')},
                      'vcruise': pl['cruiseTarget'] / 3.6, 'leads': r['leads'], 'eligible': eligible, 'personality': r['selfdrive']['personality'], 'accelCmd': ctrl['accel']})
    v = np.array([r['car']['vEgo'] for r in samples]); x = np.r_[0., np.cumsum(.025 * (v[1:] + v[:-1]))]
    vl = np.array([r['leads'][0]['vLead'] for r in samples]); lp = x + np.array([r['leads'][0]['dRel'] for r in samples])
    li = np.r_[0., np.cumsum(.025 * (vl[1:] + vl[:-1]))]; release = 200; li += lp[release] - li[release]
    for i, r in enumerate(samples): r.update(x=float(x[i]), leadworld=float(lp[i]), leadint=float(li[i]))
    closed = samples[release:]
    ok = (sum(s['eligible'] for s in closed) >= .95 * len(closed) and all(s['personality'] == pers for s in samples)
          and all(s['leads'][0]['status'] for s in closed) and len({s['leads'][0]['radarTrackId'] for s in closed}) == 1)
    tm = datetime.datetime.fromtimestamp(w0 + off, KST)
    ev = {'event': 'W' + tm.strftime('%H%M%S'), 'route': name, 'time': (tm + datetime.timedelta(seconds=10)).strftime('%H:%M:%S'),
          'v_kph_min': float(v[release:].min() * 3.6), 'v_kph_max': float(v[release:].max() * 3.6), 'usable': bool(ok)}
    manifest.append(ev | {'path_discrepancy': float(max(abs(lp[release:] - li[release:])))})
    if ok: cases.append({'event': ev, 'samples': samples, 'path_discrepancy_12s': manifest[-1]['path_discrepancy']})
with gzip.open(f'cases{name}.json.gz', 'wt') as f: json.dump(cases, f)
json.dump(manifest, open(f'cases{name}-manifest.json', 'w'), indent=1, ensure_ascii=False)
print(f"{name}: 창 {len(manifest)}개 중 사용 {len(cases)}개 (같은 앞차 유지, 연결 95% 이상, {pers})")
for m in manifest: print(m['event'], m['time'], f"{m['v_kph_min']:.0f}~{m['v_kph_max']:.0f}km/h", '사용' if m['usable'] else '제외', f"{m['path_discrepancy']:.2f}m")
