#!/usr/bin/env python3
"""Sky Window data refresh.

Pulls 7-day hourly forecasts from four global weather models (via Open-Meteo),
tide heights (Open-Meteo marine) and the latest Bureau of Meteorology station
observations for each South-East Queensland flying site, then writes
forecast.json for the dashboard page to read.

Run:  python3 refresh.py [output_path]
Stdlib only. Scoring happens in the page, so thresholds can change without
re-running this script.
"""
import json, math, os, ssl, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

TZ = "Australia/Brisbane"
AEST = timezone(timedelta(hours=10))
DAY_START, DAY_END = 5, 19            # local hours kept (inclusive start, exclusive end)
DAYS = 7
ONLY = [m for m in os.environ.get("SKYWINDOW_MODELS", "").split(",") if m]  # testing: limit models

MODELS = [  # (open-meteo id, short key, label)
    ("ecmwf_ifs", "ec", "ECMWF IFS 9 km"),
    ("gfs_global", "gfs", "NOAA GFS"),
    ("icon_global", "icon", "DWD ICON"),
    ("ukmo_global_deterministic_10km", "uk", "UK Met Office 10 km"),
]

# dirs: list of [from_deg, to_deg, label] read clockwise. wind: [min, ideal_lo, ideal_hi, max] km/h
# mode: ridge | thermal | both.  Sources: SAFA National Site Guide (siteguide.org.au) and club pages.
SITES = [
    dict(id="rainbow", name="Rainbow Beach", sub="Carlo Sand Blow", region="Cooloola Coast", lat=-25.9148, lon=153.0996,
         height=90, mode="ridge", dirs=[[22.5, 67.5, "NNE–ENE"]], wind=[12, 15, 26, 32], rating="PG2",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/rainbow-beach/",
         bom=("94584", "Double Island Point"), tide=(-25.905, 153.13), tide_note="Some high tides leave no safe beach landing below launch."),
    dict(id="teewah", name="Teewah Beach", sub="Coloured sands", region="Cooloola Coast", lat=-26.26887, lon=153.06666,
         height=30, mode="ridge", dirs=[[67.5, 112.5, "E"]], wind=[13, 16, 26, 30], rating="PG2",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/teewah-beach/",
         bom=("94570", "Tewantin"), tide=(-26.27, 153.10), tide_note="4WD beach access: check tide before driving."),
    dict(id="sunrise", name="Sunrise Beach", sub="Noosa", region="Sunshine Coast", lat=-26.4152, lon=153.1102,
         height=23, mode="ridge", dirs=[[67.5, 112.5, "E"]], wind=[14, 17, 28, 32], rating="All levels (induction required)",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/sunrise/",
         bom=("94569", "Sunshine Coast Airport"), tide=(-26.415, 153.14)),
    dict(id="cartwright", name="Point Cartwright", sub="Buddina", region="Sunshine Coast", lat=-26.68041, lon=153.13835,
         height=22, mode="ridge", dirs=[[112.5, 157.5, "SSE–ESE"]], wind=[14, 17, 28, 32], rating="PG2 (controlled airspace)",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/carties/",
         bom=("94569", "Sunshine Coast Airport")),
    dict(id="moffats", name="Moffat Beach", sub="Caloundra headland", region="Sunshine Coast", lat=-26.790351, lon=153.144828,
         height=12, mode="ridge", dirs=[[0, 22.5, "N–NNE"]], wind=[16, 19, 28, 32], rating="PG4",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/moffats/",
         bom=("94569", "Sunshine Coast Airport")),
    dict(id="kings", name="Kings Beach", sub="Caloundra", region="Sunshine Coast", lat=-26.802527, lon=153.14456,
         height=15, mode="ridge", dirs=[[157.5, 180, "S–SSE"]], wind=[16, 19, 28, 32], rating="Experienced pilots",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/kings-beach/",
         bom=("94569", "Sunshine Coast Airport"), tide=(-26.805, 153.17), tide_note="Do not fly at high tide: no contingency landing."),
    dict(id="buchys", name="Buchy's", sub="Gerrards Lookout", region="Sunshine Coast Hinterland", lat=-26.731103, lon=152.901987,
         height=375, mode="both", dirs=[[67.5, 112.5, "ENE–ESE"]], wind=[12, 16, 26, 32], rating="PG2",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/buchys/",
         bom=("95572", "Nambour"), holfuy="1622"),
    dict(id="towers", name="Towers", sub="Maleny plateau", region="Sunshine Coast Hinterland", lat=-26.778957, lon=152.915607,
         height=463, mode="thermal", dirs=[[0, 45, "N–NE"]], wind=[3, 6, 20, 28], rating="PG4",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/towers/",
         bom=("95572", "Nambour")),
    dict(id="widgee", name="Mt Widgee", sub="West of Gympie", region="Wide Bay", lat=-26.2476, lon=152.361,
         height=620, mode="both", dirs=[[90, 157.5, "E–SSE"]], wind=[12, 16, 26, 32], rating="PG2",
         club="Sunshine Coast Free Flyers", url="https://freeflyers.com.au/widgee/",
         bom=("94566", "Gympie"), note="Bombout owner needs 24 hours notice."),
    dict(id="tamborine", name="Mt Tamborine", sub="Tambo launch", region="Gold Coast Hinterland", lat=-27.95028, lon=153.18104,
         height=548, mode="thermal", dirs=[[225, 315, "SW–NW"]], wind=[3, 6, 20, 28], rating="PG4", cta=7500,
         club="Canungra Hang Gliding Club", url="https://siteguide.org.au/Sites/Details/Mt.%20Tamborine",
         bom=("95575", "Beaudesert"), holfuy="1312"),
    dict(id="beechmont", name="Beechmont", sub="Rosin's Lookout", region="Gold Coast Hinterland", lat=-28.117819, lon=153.201971,
         height=530, mode="both", dirs=[[45, 157.5, "NE–SSE"]], wind=[12, 16, 26, 32], rating="PG2",
         club="Canungra Hang Gliding Club", url="https://siteguide.org.au/Sites/Details/Beechmont%20-%20Rosin's%20Lookout",
         bom=("95575", "Beaudesert"), holfuy="1342"),
    dict(id="hinchies", name="Hinchcliffe's", sub="Flattop", region="Gold Coast Hinterland", lat=-28.07125, lon=153.14554,
         height=527, mode="thermal", dirs=[[90, 180, "E–S"]], wind=[3, 6, 20, 28], rating="PG3", cta=6500,
         club="Canungra Hang Gliding Club", url="https://siteguide.org.au/Sites/Details/Hinchcliffe's%20(Hart's,%20Flattop)",
         bom=("95575", "Beaudesert")),
    dict(id="barney", name="Mt Barney", sub="Scenic Rim (launch unconfirmed)", region="Scenic Rim", lat=-28.2833, lon=152.7000,
         height=1189, height_note="terrain height at the plotted point; launch unconfirmed", mode="thermal", dirs=[], wind=[0, 4, 20, 28], rating="Not in SAFA site guide",
         club=None, url="https://en.wikipedia.org/wiki/Mount_Barney_(Queensland)",
         bom=("95575", "Beaudesert"), note="Not a listed SAFA site; launch directions unknown, so wind direction is not scored."),
    dict(id="killarney", name="Killarney", sub="Four launches", region="Darling Downs", lat=-28.22152, lon=152.35104,
         height=1078, height_note="N launch, from terrain model", mode="both", dirs=[[337.5, 45, "N launch (NNW–NE)"], [67.5, 112.5, "E launch"], [112.5, 157.5, "SE launch (ESE–SSE)"], [247.5, 292.5, "W launch (WSW–WNW)"]],
         wind=[12, 16, 28, 34], rating="N PG2 · SE PG3 · E/W PG4",
         club=None, url="https://siteguide.org.au/Sites/Details/Killarney%20-%20N%20Launch",
         bom=("94555", "Warwick")),
    dict(id="wilsons", name="Wilson's", sub="Toowoomba Range", region="Darling Downs", lat=-27.69168, lon=151.99881,
         height=718, mode="thermal", dirs=[[22.5, 67.5, "NE"]], wind=[3, 6, 20, 28], rating="PG4",
         club="Wicked Wings", url="https://siteguide.org.au/Sites/Details/Wilson's",
         bom=("95551", "Toowoomba")),
    dict(id="mamacreek", name="Ma Ma Creek", sub="Lockyer Valley", region="Darling Downs", lat=-27.63696, lon=152.14366,
         height=366, height_note="from terrain model", mode="both", dirs=[[22.5, 112.5, "NE–E"]], wind=[12, 16, 26, 30], rating="PG2",
         club="Wicked Wings", url="https://siteguide.org.au/Sites/Details/Ma%20Ma%20Creek",
         bom=("94562", "Gatton"), note="Military airspace limits on weekdays; contact Wicked Wings first."),
]

VARS = ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m", "temperature_2m", "dew_point_2m",
        "cloud_cover_low", "cloud_cover", "precipitation", "precipitation_probability", "cape",
        "boundary_layer_height", "shortwave_radiation", "wind_speed_850hPa", "wind_direction_850hPa",
        "temperature_850hPa", "temperature_700hPa", "geopotential_height_850hPa", "geopotential_height_700hPa"]
SHORT = dict(wind_speed_10m="ws", wind_direction_10m="wd", wind_gusts_10m="wg", temperature_2m="t", dew_point_2m="td",
             cloud_cover_low="lcc", cloud_cover="cc", precipitation="pr", precipitation_probability="pp", cape="cape",
             boundary_layer_height="blh", shortwave_radiation="sw", wind_speed_850hPa="w850", wind_direction_850hPa="d850",
             temperature_850hPa="t850", temperature_700hPa="t700", geopotential_height_850hPa="z850", geopotential_height_700hPa="z700")
DIRVARS = {"wd", "d850"}
MVARS = ("ws", "wd", "wg", "pr", "blh", "cape", "lcc")

# Wind at launch height: for hill launches (>= INLAND_MIN m above sea level) the 10 m model wind
# describes the model's smoothed ground, not an exposed launch. We build a vertical wind profile from
# the 10 m wind plus pressure-level winds (with their heights) and average it over the band pilots fly
# in, from launch height to BAND_TOP m above launch.
INLAND_MIN = 200
BAND_TOP = 300
LEVELS = [1000, 975, 950, 925, 900, 850]
LVARS = [f"{v}_{l}hPa" for l in LEVELS for v in ("wind_speed", "wind_direction", "geopotential_height")] + ["wind_speed_10m", "wind_direction_10m"]


def uv(spd, d):
    return -spd * math.sin(math.radians(d)), -spd * math.cos(math.radians(d))


def band_wind(launch, prof):
    """prof: list of (height_asl, u, v) sorted by height. Returns (speed, dir) averaged over the band."""
    if len(prof) < 2:
        return None, None
    us = vs = 0.0; n = 0
    for dz in range(0, BAND_TOP + 1, 50):
        z = launch + dz
        lo = max((p for p in prof if p[0] <= z), key=lambda p: p[0], default=prof[0])
        hi = min((p for p in prof if p[0] >= z), key=lambda p: p[0], default=prof[-1])
        if hi[0] == lo[0]:
            u, v = lo[1], lo[2]
        else:
            f = (z - lo[0]) / (hi[0] - lo[0]); u = lo[1] + f * (hi[1] - lo[1]); v = lo[2] + f * (hi[2] - lo[2])
        us += u; vs += v; n += 1
    u, v = us / n, vs / n
    spd = math.hypot(u, v)
    d = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    return round(spd, 1), round(d)


def fetch_levels():
    """Pressure-level winds for hill launches only (keeps the API call budget down)."""
    idx = [i for i, s in enumerate(SITES) if (s.get("height") or 0) >= INLAND_MIN]
    out = {}
    if not idx:
        return idx, out
    lats = ",".join(str(SITES[i]["lat"]) for i in idx)
    lons = ",".join(str(SITES[i]["lon"]) for i in idx)
    for mid, key, _ in MODELS:
        if ONLY and key not in ONLY:
            continue
        q = urllib.parse.urlencode(dict(latitude=lats, longitude=lons, hourly=",".join(LVARS), models=mid,
                                        timezone=TZ, forecast_days=DAYS, wind_speed_unit="kmh"))
        try:
            data = get_json("https://api.open-meteo.com/v1/forecast?" + q)
            out[key] = data if isinstance(data, list) else [data]
        except Exception as e:
            print("levels failed", key, e, file=sys.stderr)
    return idx, out


def launch_series(site, d):
    """Band-averaged wind for every hour of one model's response d (or None)."""
    h = d.get("hourly", {}); launch = site["height"]
    n = len(h.get("time", []))
    sp, dr = [], []
    for i in range(n):
        prof = []
        w10, d10 = h.get("wind_speed_10m", [None] * n)[i], h.get("wind_direction_10m", [None] * n)[i]
        if w10 is not None and d10 is not None:
            prof.append((launch + 10, *uv(w10, d10)))  # 10 m wind sits at the bottom of the band
        for l in LEVELS:
            z = h.get(f"geopotential_height_{l}hPa", [None] * n)[i]
            w = h.get(f"wind_speed_{l}hPa", [None] * n)[i]
            dd = h.get(f"wind_direction_{l}hPa", [None] * n)[i]
            if None in (z, w, dd) or z <= launch + 10:
                continue  # levels at or below the launch are skipped (often below ground in the model)
            prof.append((z, *uv(w, dd)))
        prof.sort()
        a, b = band_wind(launch, prof) if len(prof) >= 2 else (None, None)
        sp.append(a); dr.append(b)
    return sp, dr


def ssl_ctx():
    for p in (os.environ.get("SSL_CERT_FILE"), "/root/.ccr/ca-bundle.crt"):
        if p and os.path.exists(p):
            return ssl.create_default_context(cafile=p)
    return ssl.create_default_context()


CTX = ssl_ctx()


def get_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SkyWindow/1.0 (paragliding dashboard)"})
            with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa
            err = e
            time.sleep(2 + 3 * i)
    raise RuntimeError(f"fetch failed: {url[:120]}… {err}")


def r1(x, nd=1):
    return None if x is None else round(x, nd)


def vec_mean(dirs, speeds):
    u = v = 0.0; n = 0
    for d, s in zip(dirs, speeds):
        if d is None:
            continue
        w = s if s else 1.0
        u += w * math.sin(math.radians(d)); v += w * math.cos(math.radians(d)); n += 1
    if not n:
        return None
    return round((math.degrees(math.atan2(u, v)) + 360) % 360)


def fetch_models():
    lats = ",".join(str(s["lat"]) for s in SITES)
    lons = ",".join(str(s["lon"]) for s in SITES)
    out = {}
    for mid, key, _ in MODELS:
        if ONLY and key not in ONLY:
            continue
        q = urllib.parse.urlencode(dict(latitude=lats, longitude=lons, hourly=",".join(VARS), models=mid,
                                        timezone=TZ, forecast_days=DAYS, wind_speed_unit="kmh"))
        try:
            data = get_json("https://api.open-meteo.com/v1/forecast?" + q)
            if isinstance(data, dict):
                data = [data]
            out[key] = data
        except Exception as e:
            print("model failed", key, e, file=sys.stderr)
    return out


def fetch_tides():
    res = {}
    pts = [s for s in SITES if s.get("tide")]
    q = urllib.parse.urlencode(dict(latitude=",".join(str(s["tide"][0]) for s in pts),
                                    longitude=",".join(str(s["tide"][1]) for s in pts),
                                    hourly="sea_level_height_msl", timezone=TZ, forecast_days=DAYS))
    try:
        data = get_json("https://marine-api.open-meteo.com/v1/marine?" + q)
        if isinstance(data, dict):
            data = [data]
        for s, d in zip(pts, data):
            t, h = d["hourly"]["time"], d["hourly"]["sea_level_height_msl"]
            ext = []
            for i in range(1, len(h) - 1):
                if None in (h[i - 1], h[i], h[i + 1]):
                    continue
                if h[i] >= h[i - 1] and h[i] > h[i + 1]:
                    ext.append([t[i], "H", round(h[i], 2)])
                elif h[i] <= h[i - 1] and h[i] < h[i + 1]:
                    ext.append([t[i], "L", round(h[i], 2)])
            res[s["id"]] = dict(ext=ext, series=[[t[i], r1(h[i], 2)] for i in range(len(t))
                                                 if DAY_START <= int(t[i][11:13]) < DAY_END])
    except Exception as e:
        print("tides failed", e, file=sys.stderr)
    return res


def fetch_obs():
    res = {}
    for wmo in sorted({s["bom"][0] for s in SITES}):
        url = f"https://www.bom.gov.au/fwo/IDQ60901/IDQ60901.{wmo}.json"
        try:
            d = get_json(url)["observations"]["data"][:8]
            res[wmo] = [dict(t=o.get("local_date_time_full"), dir=o.get("wind_dir"), ws=o.get("wind_spd_kmh"),
                             wg=o.get("gust_kmh"), temp=o.get("air_temp"), rh=o.get("rel_hum")) for o in d]
        except Exception as e:
            print("obs failed", wmo, e, file=sys.stderr)
    return res


def build():
    models = fetch_models()
    lidx, levels = fetch_levels()
    tides = fetch_tides()
    obs = fetch_obs()
    keys = [k for _, k, _ in MODELS if k in models]
    sites_out = []
    for idx, s in enumerate(SITES):
        per = {k: models[k][idx] for k in keys}
        ref = per[keys[0]]
        times = ref["hourly"]["time"]
        elev = ref.get("elevation")
        times_out, cons, mod = [], {SHORT[v]: [] for v in VARS}, {k: {sk: [] for sk in MVARS} for k in keys}
        for i, t in enumerate(times):
            if not (DAY_START <= int(t[11:13]) < DAY_END):
                continue
            times_out.append(t)
            for v in VARS:
                sk = SHORT[v]
                vals = [(k, per[k]["hourly"].get(v, [None] * len(times))[i]) for k in keys]
                good = [(k, x) for k, x in vals if x is not None]
                if sk in DIRVARS:
                    spv = "wind_speed_10m" if sk == "wd" else "wind_speed_850hPa"
                    sp = {k: per[k]["hourly"].get(spv, [None] * len(times))[i] for k in keys}
                    cons[sk].append(vec_mean([x for _, x in good], [sp[k] for k, _ in good]))
                else:
                    cons[sk].append(r1(sum(x for _, x in good) / len(good), 0 if sk in ("cape", "blh", "sw", "z850", "z700", "lcc", "cc", "pp") else 1) if good else None)
                if sk in MVARS:
                    for k, x in vals:
                        mod[k][sk].append(None if x is None else (round(x) if sk in ("wd", "blh", "cape", "lcc") else r1(x)))
        # wind in the flying band above a hill launch, per model and as a consensus
        if idx in lidx and levels:
            j = lidx.index(idx)
            ls = {}
            for k in keys:
                if k in levels and j < len(levels[k]):
                    a, b = launch_series(s, levels[k][j])
                    lt = levels[k][j].get("hourly", {}).get("time", [])
                    pos = {t: n for n, t in enumerate(lt)}
                    ls[k] = ([a[pos[t]] if t in pos else None for t in times_out], [b[pos[t]] if t in pos else None for t in times_out])
            if ls:
                for k in keys:
                    mod[k]["wsl"], mod[k]["wdl"] = ls.get(k, ([None] * len(times_out), [None] * len(times_out)))
                cons["wsl"], cons["wdl"] = [], []
                for i in range(len(times_out)):
                    good = [(ls[k][0][i], ls[k][1][i]) for k in ls if ls[k][0][i] is not None and ls[k][1][i] is not None]
                    cons["wsl"].append(r1(sum(g[0] for g in good) / len(good)) if good else None)
                    cons["wdl"].append(vec_mean([g[1] for g in good], [g[0] for g in good]) if good else None)
        o = dict(id=s["id"], name=s["name"], sub=s["sub"], region=s["region"], lat=s["lat"], lon=s["lon"],
                 height=s["height"], height_note=s.get("height_note"), band=BAND_TOP if "wsl" in cons else None, elev=elev, mode=s["mode"], dirs=s["dirs"], wind=s["wind"], rating=s["rating"],
                 club=s["club"], url=s["url"], cta=s.get("cta"), note=s.get("note"), holfuy=s.get("holfuy"),
                 bom=dict(id=s["bom"][0], name=s["bom"][1], obs=obs.get(s["bom"][0], [])),
                 tide=tides.get(s["id"]), tide_note=s.get("tide_note"), t=times_out, c=cons, m=mod)
        sites_out.append(o)
    return dict(generated=datetime.now(AEST).isoformat(timespec="minutes"),
                models=[dict(key=k, id=m, label=l, ok=k in models) for m, k, l in MODELS],
                sites=sites_out)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "forecast.json"
    data = build()
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    ok = [m["key"] for m in data["models"] if m["ok"]]
    print(f"wrote {out}: {len(data['sites'])} sites, models {ok}, {os.path.getsize(out)//1024} KB")
