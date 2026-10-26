#!/usr/bin/env python3
"""Codzienny skan BZP + TED pod kątem zakresu Mega-Rem. Tylko biblioteka standardowa.
Użycie: python tenders.py [--offline] [--days N]"""
import json, os, re, sys, math, smtplib, urllib.request, urllib.parse, urllib.error
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(ROOT, "data", "store.json")
KR = (50.0647, 19.9450)
RADIUS_KM = int(os.environ.get("RADIUS_KM", "500"))
OFFLINE = "--offline" in sys.argv
DAYS = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else None

# --- filtry (do strojenia) ---
CORE = ["kotł", "kocio", "młyn", "biomas", "współspal", "elektrofiltr", "odżuż", "żużl", "wentylator",
        "turbin", "suwnic", "dźwignic", "akpia", "nieniszcz", "wymiennikown", "kotłown", "ciepłown"]
WEAK = ["pomp", "generator", "silnik", "rozdzielni", "armatur", "rurociąg", "spawa", "scada"]
CONTEXT = ["elektrowni", "elektrociepłowni", "ciepłowni", "energetyczn", "blok"]
EXCL = ["wiatrow", "fotowolt"]
AREAS = [("Młyn węglowy", ["młyn"]), ("Biomasa / współspalanie", ["biomas", "współspal"]),
         ("Elektrofiltr / odżużlacz", ["elektrofiltr", "odżuż", "żużl"]), ("Wentylatory / kanały", ["wentylator"]),
         ("Obiekty / ciepłownictwo", ["kotłown", "ciepłown", "wymiennikown"]), ("Kocioł", ["kotł", "kocio"]),
         ("Turbina / generator / pompy", ["turbin", "generator", "pomp"]), ("Armatura / rurociągi", ["armatur", "rurociąg"]),
         ("Elektryka / AKPiA", ["akpia", "rozdzielni", "silnik", "scada"]), ("Dźwignice (UDT)", ["suwnic", "dźwignic"]),
         ("Laboratorium spawalnicze / NDT", ["nieniszcz", "spawa"])]
CPV_PREFIXES = ["50530", "50531", "45251", "42160", "42161"]   # do weryfikacji w słowniku CPV
CPV_TED = ["50531100", "50530000", "45251000", "42160000", "42161000"]

CITIES = {"kraków": (50.0647, 19.945), "skawina": (49.975, 19.828), "trzebinia": (50.162, 19.471), "jaworzno": (50.205, 19.275),
 "katowice": (50.2649, 19.0238), "zabrze": (50.3249, 18.7857), "gliwice": (50.2945, 18.6714), "chorzów": (50.297, 18.954),
 "łaziska górne": (50.147, 18.842), "rybnik": (50.0971, 18.5463), "częstochowa": (50.7965, 19.1203), "opole": (50.6751, 17.9213),
 "wrocław": (51.1079, 17.0385), "bełchatów": (51.3689, 19.3566), "łódź": (51.7592, 19.456), "kielce": (50.8661, 20.6286),
 "połaniec": (50.439, 21.286), "kozienice": (51.583, 21.547), "rzeszów": (50.0412, 21.9991), "stalowa wola": (50.582, 22.053),
 "lublin": (51.2465, 22.5684), "warszawa": (52.2297, 21.0122), "ostrołęka": (53.084, 21.574), "bogatynia": (50.904, 14.965),
 "poznań": (52.4064, 16.9252), "bydgoszcz": (53.1235, 18.0084), "toruń": (53.0138, 18.5984), "gdańsk": (54.352, 18.6466),
 "gdynia": (54.5189, 18.5305), "nowe czarnowo": (53.216, 14.465), "szczecin": (53.4285, 14.5528), "tarnów": (50.0121, 20.9858),
 "nowy sącz": (49.6218, 20.697), "bielsko-biała": (49.8224, 19.0584), "radom": (51.4027, 21.1471), "płock": (52.5463, 19.7065),
 "sosnowiec": (50.2863, 19.1041), "dąbrowa górnicza": (50.3217, 19.1949), "tychy": (50.1218, 18.9966),
 "jastrzębie-zdrój": (49.957, 18.575), "zawiercie": (50.486, 19.417), "kędzierzyn-koźle": (50.349, 18.228),
 "ostrowiec świętokrzyski": (50.929, 21.385), "konin": (52.223, 18.2511)}
PROV = {"dolnośląskie": (51.1, 16.9), "kujawsko-pomorskie": (53.1, 18.5), "lubelskie": (51.2, 22.6), "lubuskie": (52.2, 15.3),
 "łódzkie": (51.6, 19.4), "małopolskie": (49.9, 20.2), "mazowieckie": (52.2, 21.0), "opolskie": (50.7, 17.9),
 "podkarpackie": (49.9, 22.1), "podlaskie": (53.1, 23.2), "pomorskie": (54.2, 18.2), "śląskie": (50.3, 19.0),
 "świętokrzyskie": (50.8, 20.7), "warmińsko-mazurskie": (53.8, 20.8), "wielkopolskie": (52.3, 17.3), "zachodniopomorskie": (53.5, 15.6)}

def dist(c):
    r = math.pi / 180; a = (c[0] - KR[0]) * r; b = (c[1] - KR[1]) * r
    h = math.sin(a / 2) ** 2 + math.cos(KR[0] * r) * math.cos(c[0] * r) * math.sin(b / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(h)))

def locate(city, prov=""):
    c = (city or "").strip().lower()
    if c in CITIES: return dist(CITIES[c]), city
    p = (prov or "").strip().lower()
    for k, v in PROV.items():
        if k in p: return dist(v), (city or "") + " (~ " + k + ")"
    return None, city or ""

def classify(title, cpvs):
    t = title.lower()
    if any(x in t for x in EXCL): return None
    core = any(k in t for k in CORE)
    weak = any(k in t for k in WEAK) and any(k in t for k in CONTEXT)
    cpv = any(c.startswith(p) for c in cpvs for p in CPV_PREFIXES)
    if not (core or weak or cpv): return None
    for name, keys in AREAS:
        if any(k in t for k in keys): return name
    return "Inne – do oceny"

def http(url, data=None, tries=3):
    h = {"User-Agent": "mega-rem-tender-bot/1.0", "Accept": "application/json"}
    if data is not None: h["Content-Type"] = "application/json"; data = json.dumps(data).encode()
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:500]
            if e.code < 500 or i == tries - 1: raise RuntimeError("HTTP %s: %s" % (e.code, body))
        except Exception as e:
            if i == tries - 1: raise
    return None

def pick(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""): return d[k]
    return None

def day(s):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(s or "")); return m.group(1) if m else None

# ---------------- BZP ----------------
def fetch_bzp(d_from, d_to):
    out, dbg = [], None
    cur = d_from
    while cur <= d_to:
        for page in range(1, 6):
            q = {"NoticeType": "ContractNotice", "PublicationDateFrom": cur.isoformat(), "PublicationDateTo": cur.isoformat(),
                 "PageSize": 100, "PageNumber": page}
            res = http("https://ezamowienia.gov.pl/mo-board/api/v1/Board/Search?" + urllib.parse.urlencode(q))
            items = res if isinstance(res, list) else (pick(res, "items", "results", "data") or [])
            if dbg is None and items: dbg = items[:3]
            out += items
            if len(items) < 100: break
        cur += timedelta(days=1)
    if dbg:  # surowe próbki do szybkiej diagnozy pól po pierwszym uruchomieniu
        json.dump(dbg, open(os.path.join(ROOT, "data", "debug_bzp.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out

def norm_bzp(x):
    title = pick(x, "orderObject", "title", "name") or ""
    cpv = re.findall(r"\d{8}", str(pick(x, "cpvCode", "cpv") or ""))
    area = classify(title, cpv)
    if not area: return None
    nid = pick(x, "noticeNumber", "bzpNumber", "id") or ""
    km, place = locate(pick(x, "organizationCity", "city"), pick(x, "organizationProvince", "province"))
    link = "https://ezamowienia.gov.pl/mo-client-board/bzp/list?search=" + urllib.parse.quote(str(nid))
    guid = pick(x, "noticeId", "objectId", "guid")
    if guid: link = "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/" + str(guid)
    return {"id": "bzp:" + str(nid), "due": day(pick(x, "submittingOffersDate", "deadline")), "title": title.strip(),
            "buyer": pick(x, "organizationName", "buyerName") or "", "place": place, "km": km, "exec": "wg SWZ",
            "area": area, "url": link, "src": "BZP"}

# ---------------- TED ----------------
def txt(v):
    if isinstance(v, dict):
        for k in ("pol", "POL", "pl", "eng", "ENG"):
            if k in v: return txt(v[k])
        return txt(next(iter(v.values()), ""))
    if isinstance(v, list): return txt(v[0]) if v else ""
    return str(v or "")

def fetch_ted(d_from):
    cpv = " OR ".join("classification-cpv=%s" % c for c in CPV_TED)
    query = "buyer-country=POL AND publication-date>=%s AND (%s)" % (d_from.strftime("%Y%m%d"), cpv)
    body = {"query": query, "page": 1, "limit": 100, "scope": "ACTIVE",
            "fields": ["publication-number", "notice-title", "buyer-name", "deadline-receipt-tender-date-lot",
                       "classification-cpv", "place-of-performance-city-lot", "links"]}
    try:
        res = http("https://api.ted.europa.eu/v3/notices/search", body)
    except RuntimeError as e:
        print("TED: pole/zapytanie odrzucone, ponawiam z minimalnym zestawem:", e)
        body["fields"] = ["publication-number", "notice-title", "buyer-name"]
        body["query"] = "buyer-country=POL AND publication-date>=%s" % d_from.strftime("%Y%m%d")
        res = http("https://api.ted.europa.eu/v3/notices/search", body)
    return res.get("notices", []) if isinstance(res, dict) else []

def norm_ted(x):
    title = txt(x.get("notice-title")); cpv = [str(c) for c in (x.get("classification-cpv") or [])]
    area = classify(title, cpv)
    if not area: return None
    num = txt(x.get("publication-number"))
    city = txt(x.get("place-of-performance-city-lot"))
    km, place = locate(city, "")
    return {"id": "ted:" + num, "due": day(txt(x.get("deadline-receipt-tender-date-lot"))), "title": title.strip(),
            "buyer": txt(x.get("buyer-name")), "place": place, "km": km, "exec": "wg SWZ", "area": area,
            "url": "https://ted.europa.eu/pl/notice/-/detail/" + num, "src": "TED"}

# ---------------- main ----------------
def main():
    today = date.today()
    store = json.load(open(STORE, encoding="utf-8")) if os.path.exists(STORE) else {}
    days = DAYS or (30 if not store else 3)
    status, found = [], []
    if OFFLINE:
        fx = json.load(open(os.path.join(ROOT, "tests", "fixture.json"), encoding="utf-8"))
        found = [n for n in (norm_bzp(x) for x in fx) if n]; status.append("TRYB TESTOWY (dane syntetyczne)")
    else:
        for name, fn in (("BZP", lambda: [norm_bzp(x) for x in fetch_bzp(today - timedelta(days=days), today)]),
                         ("TED", lambda: [norm_ted(x) for x in fetch_ted(today - timedelta(days=days))])):
            try:
                r = [n for n in fn() if n]; found += r; status.append("%s: OK (%d dopasowań)" % (name, len(r)))
            except Exception as e:
                status.append("%s: BŁĄD" % name); print(name, "błąd:", e)
    seen_titles = {re.sub(r"\W+", "", v["title"].lower())[:60] for v in store.values()}
    new = []
    for n in found:
        key = n["id"]; sig = re.sub(r"\W+", "", n["title"].lower())[:60]
        if key in store: continue
        if sig in seen_titles: continue          # to samo ogłoszenie w BZP i TED
        n["first_seen"] = today.isoformat(); store[key] = n; seen_titles.add(sig); new.append(n)
    keep = {}
    for k, v in store.items():                    # usuń pozycje po terminie (> 1 dzień)
        if v.get("due") and v["due"] < (today - timedelta(days=1)).isoformat(): continue
        keep[k] = v
    rows = []
    for v in keep.values():
        if v.get("km") is not None and v["km"] > RADIUS_KM: continue
        v = dict(v); v["new"] = v.get("first_seen") == today.isoformat(); rows.append(v)
    rows = [r for r in rows if r.get("due")]
    rows.sort(key=lambda r: r["due"])
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True); os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    json.dump(keep, open(STORE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(rows, open(os.path.join(ROOT, "docs", "data.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    meta = {"updated": datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M"), "status": "; ".join(status)}
    t = open(os.path.join(ROOT, "template.html"), encoding="utf-8").read()
    t = t.replace("__META__", json.dumps(meta, ensure_ascii=False)).replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/"))
    open(os.path.join(ROOT, "docs", "index.html"), "w", encoding="utf-8").write(t)
    print("Pozycji na stronie:", len(rows), "| nowe:", len(new), "|", meta["status"])
    if new and os.environ.get("SMTP_HOST"): send_mail(new)

def send_mail(new):
    m = EmailMessage(); m["Subject"] = "Nowe przetargi Mega-Rem: %d" % len(new)
    m["From"] = os.environ["MAIL_FROM"]; m["To"] = os.environ["MAIL_TO"]
    lines = ["%s | do %s | %s | %s km\n%s\n%s\n" % (n["src"], n["due"], n["place"], n["km"], n["title"], n["url"]) for n in new]
    base = os.environ.get("PAGE_URL", ""); m.set_content("\n".join(lines) + ("\nZestawienie: " + base if base else ""))
    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465"))) as s:
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"]); s.send_message(m)

if __name__ == "__main__":
    main()
