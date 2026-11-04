"""Pegeldaten der WSV (PEGELONLINE, Lizenz DL-DE->Zero-2.0) archivieren und für die App aufbereiten.
Ablage im Repository: daten/<Pegelnummer>-<Größe>/<Jahr>.csv mit Zeilen „Zeitstempel (UTC);Wert“ im 15-Minuten-Raster.
Befehle (aus dem Repository-Ordner):
  python pegel.py update                      letzte 31 Tage aller Pegel nachladen und anhängen
  python pegel.py wsa                         WSA-Abgabeplan der Edertalsperre (PDF) in daten/wsa/abgabe.csv eintragen
  python pegel.py build                       tageswerte.json für die App erzeugen
  python pegel.py seed <csv> <Pegelnummer> <W|Q>   Download von pegelonline.wsv.de (Ortszeit, „;“, Komma) einlesen
  python pegel.py seed-json <json> <Pegelnummer> <W|Q>   JSON-Download (ISO-Zeitstempel mit Offset) einlesen"""
import os, sys, re, csv, json, io, datetime as dt, urllib.request, urllib.parse
from zoneinfo import ZoneInfo

API = 'https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations'
WSA_PDF = 'https://pss.wsv.de/wsahmue/VorhersageOberweser.pdf'
BERLIN, UTC = ZoneInfo('Europe/Berlin'), dt.timezone.utc
ROOT = os.path.dirname(os.path.abspath(__file__))
DATEN = os.path.join(ROOT, 'daten')

# (Pegelnummer oder Kurzname, Größe, Bezeichnung)
PEGEL = [
    ('42800310', 'W', 'Edertalsperre (Stauhöhe, m + PNP)'),
    ('42800309', 'Q', 'Schmittlotheim (Zufluss, m³/s)'),
    ('42800309', 'W', 'Schmittlotheim (cm)'),
    ('42800502', 'W', 'Affoldern (cm)'),
    ('BONAFORTH', 'Q', 'Bonaforth (Werra, m³/s)'),
    ('LETZTER HELLER', 'Q', 'Letzter Heller (Fulda, m³/s)'),
    ('43100109', 'W', 'Hann. Münden (Weser, cm)'),
    ('43900105', 'W', 'Wahmbeck (Weser, cm)'),
    ('45100100', 'W', 'Karlshafen (Weser, cm)'),
    ('45300109', 'W', 'Höxter (Weser, cm)'),
    ('45700207', 'W', 'Hameln Wehrbergen (Weser, cm)'),
    ('45900208', 'W', 'Vlotho (Weser, cm)'),
    ('47100100', 'W', 'Porta (Weser, cm)'),
    ('49100101', 'W', 'Intschede (Weser, cm)'),
]


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'MeinRVED-Pegelarchiv'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def folder(nr, param):
    return os.path.join(DATEN, f"{re.sub(r'[^A-Za-z0-9]+', '_', nr)}-{param}")


def read_year(path):
    d = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            t, _, v = line.strip().partition(';')
            if v: d[t] = v
    return d


def write_year(path, d):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for t in sorted(d): f.write(f'{t};{d[t]}\n')


def add(nr, param, points):
    """points: Liste (datetime mit Zeitzone, Wert). Hängt an die Jahresdateien an; gibt die Zahl neuer Werte zurück."""
    by_year = {}
    for t, v in points:
        t = t.astimezone(UTC)
        by_year.setdefault(t.year, {})[t.strftime('%Y-%m-%dT%H:%MZ')] = v
    new = 0
    for y, vals in by_year.items():
        path = os.path.join(folder(nr, param), f'{y}.csv')
        cur = read_year(path)
        for t, v in vals.items():
            if t not in cur or cur[t] != v: new += 1
            cur[t] = v
        write_year(path, cur)
    return new


def fmt(v):
    return ('%.3f' % v).rstrip('0').rstrip('.')


def update():
    for nr, param, name in PEGEL:
        try:
            url = f"{API}/{urllib.parse.quote(nr)}/{param}/measurements.json?start=P31D"
            raw = json.loads(fetch(url))
            pts = [(dt.datetime.fromisoformat(m['timestamp']), fmt(m['value'])) for m in raw if m.get('value') is not None]
            print(f'{name}: {len(pts)} Werte, {add(nr, param, pts)} neu')
        except Exception as e:
            print(f'{name}: FEHLER {e}', file=sys.stderr)


def seed(path, nr, param):
    """Download der Seite pegelonline.wsv.de (Kopfzeilen mit #, danach „Zeit;Wert“ in Ortszeit)."""
    pts, prev, fold = [], None, 0
    for line in open(path, encoding='utf-8-sig'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('timestamp'): continue
        t, _, v = line.partition(';')
        if not v: continue
        local = dt.datetime.strptime(t, '%Y-%m-%d %H:%M')
        # doppelte Stunde beim Wechsel von MESZ auf MEZ: zweiter Durchlauf (Zeit springt zurück) gehört zur Winterzeit
        fold = 1 if (prev is not None and local < prev) or (fold and prev is not None and local - prev < dt.timedelta(hours=1)) else 0
        prev = local
        pts.append((local.replace(tzinfo=BERLIN, fold=fold), fmt(float(v.replace(',', '.')))))
    print(f'{len(pts)} Werte, {add(nr, param, pts)} neu')


def seed_json(path, nr, param):
    raw = json.load(open(path, encoding='utf-8'))
    pts = [(dt.datetime.fromisoformat(m['timestamp']), fmt(m['value'])) for m in raw if m.get('value') is not None]
    print(f'{len(pts)} Werte, {add(nr, param, pts)} neu')


def series(nr, param):
    out = {}
    d = folder(nr, param)
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            for t, v in read_year(os.path.join(d, fn)).items():
                out[dt.datetime.strptime(t, '%Y-%m-%dT%H:%MZ').replace(tzinfo=UTC)] = float(v)
    return out


def at7(s, day):
    """Wert um 07:00 Ortszeit (oder innerhalb von 30 Minuten davor)."""
    t = dt.datetime(day.year, day.month, day.day, 7, 0, tzinfo=BERLIN).astimezone(UTC)
    for k in range(0, 3):
        v = s.get(t - dt.timedelta(minutes=15 * k))
        if v is not None: return v
    return None


def wsa():
    import tempfile
    try:
        import pypdf
    except ImportError:
        raise SystemExit('pip install pypdf')
    data = fetch(WSA_PDF)
    txt = '\n'.join(p.extract_text(extraction_mode='layout') for p in pypdf.PdfReader(io.BytesIO(data)).pages)
    stand = re.search(r'Stand:\s*\w\w\.? (\d\d\.\d\d\.\d{4} \d\d:\d\d)', txt)
    block = txt.split('Abgabenplanung Edertalsperre', 1)[-1].split('Abgabenplanung Diemeltalsperre', 1)[0]
    plan = re.findall(r'(\d\d)\.(\d\d)\.(\d{4})\s+\d\d:\d\d\s+([\d,]+)\s*m³/s', block)
    if not plan or not stand: raise SystemExit('Abgabeplan nicht gefunden')
    path = os.path.join(DATEN, 'wsa', 'abgabe.csv')      # Tag;Abgabe m³/s;Stand der Vorhersage; später gewinnt der aktuellere Stand
    cur = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            p = line.strip().split(';')
            if len(p) == 3: cur[p[0]] = (p[1], p[2])
    st = dt.datetime.strptime(stand.group(1), '%d.%m.%Y %H:%M').strftime('%Y-%m-%dT%H:%M')
    today = dt.datetime.now(BERLIN).date()
    n = 0
    for d, m, y, v in plan:
        day = dt.date(int(y), int(m), int(d))
        if day < today: continue                       # nur heute und die Planung voraus
        key = day.isoformat()
        if key not in cur or cur[key][1] <= st:
            cur[key] = (v.replace(',', '.'), st); n += 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for k in sorted(cur): f.write(f'{k};{cur[k][0]};{cur[k][1]}\n')
    print(f'Abgabeplan Stand {stand.group(1)}: {n} Tage eingetragen')


def build():
    lvl, q, aff = series('42800310', 'W'), series('42800309', 'Q'), series('42800502', 'W')
    first = min(lvl)
    start = first.astimezone(BERLIN).date()
    end = max(lvl).astimezone(BERLIN).date()
    days = [start + dt.timedelta(i) for i in range((end - start).days + 1)]
    level = [at7(lvl, d) for d in days]
    qs = {d: at7(q, d) for d in days if q}
    qd = [d for d in days if qs.get(d) is not None]
    ws = {d: at7(aff, d) for d in days if aff}
    wd = [d for d in days if ws.get(d) is not None]
    ab = {}
    p = os.path.join(DATEN, 'wsa', 'abgabe.csv')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            x = line.strip().split(';')
            if len(x) == 3: ab[dt.date.fromisoformat(x[0])] = float(x[1])
    out = dict(stand=end.isoformat(), quelle='WSV PEGELONLINE (DL-DE->Zero-2.0), Abgabe: WSA Weser',
               level=dict(start=start.isoformat(), werte=level))
    if qd:
        out['inflow'] = dict(start=qd[0].isoformat(), werte=[qs.get(qd[0] + dt.timedelta(i)) for i in range((qd[-1] - qd[0]).days + 1)])
    if wd:
        out['affoldern'] = dict(start=wd[0].isoformat(), werte=[ws.get(wd[0] + dt.timedelta(i)) for i in range((wd[-1] - wd[0]).days + 1)])
    if ab:
        a0, a1 = min(ab), max(d for d in ab if d <= end) if any(d <= end for d in ab) else min(ab)
        out['outflow'] = dict(start=a0.isoformat(), werte=[ab.get(a0 + dt.timedelta(i)) for i in range((a1 - a0).days + 1)])
    os.makedirs(os.path.join(ROOT, 'site'), exist_ok=True)
    with open(os.path.join(ROOT, 'site', 'tageswerte.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'))
    print(f"tageswerte.json: {len(days)} Tage seit {start}, Zufluss {len(qd)} Tage, Affoldern {len(wd)} Tage, Abgabe {len(ab)} Tage")


if __name__ == '__main__':
    c = sys.argv[1] if len(sys.argv) > 1 else ''
    if c == 'update': update()
    elif c == 'wsa': wsa()
    elif c == 'build': build()
    elif c == 'seed' and len(sys.argv) == 5: seed(*sys.argv[2:5])
    elif c == 'seed-json' and len(sys.argv) == 5: seed_json(*sys.argv[2:5])
    else: print(__doc__)
