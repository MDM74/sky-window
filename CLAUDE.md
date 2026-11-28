# Sky Window — project notes for Claude

Paragliding forecast dashboard for South-East Queensland and New South Wales, built for a group of
free-flight pilots (Felix and friends). Live at https://mdm74.github.io/sky-window/ (`#qld` / `#nsw`
open a state directly). Owner: Mark (repo MDM74/sky-window). Mark is not a developer: explain changes
in plain language, and keep the public page free of internal notes or "ask Claude" wording.

## How it works

- `refresh.py` (Python stdlib only) fetches data and writes `forecast.json`. Scoring is NOT done here.
- `index.html` is the whole site: one self-contained page (inline CSS/JS, Google Fonts only) that
  reads `forecast.json` and does all scoring in the browser, so thresholds can change without a refresh.
- `.github/workflows/refresh.yml` chains itself: each run refreshes, waits ~2 h 45 min, then dispatches the
  next run (GitHub dropped ~90% of scheduled runs in Nov 2026, leaving data 6–12 h old). The hourly cron is
  only a safety net that restarts the chain; the concurrency group keeps one run active and one waiting.
  Dispatched runs set `SKYWINDOW_FORCE=1`; cron runs skip when data is under `MIN_REFRESH_H` (2.4 h).
  Manual run: Actions tab, or `gh api -X POST repos/MDM74/sky-window/actions/workflows/refresh.yml/dispatches -f ref=main`.
  The page flags data older than 4.5 h.
- GitHub Pages serves the `main` branch root. Repo must stay public (Pages is free only for public repos).
- `refresh.py` runs `quality_check()` before writing. Fatal problems (fewer than 2 models, >10% missing
  hours, impossible values) exit non-zero so the previous forecast stays live. Warnings go into
  `forecast.json` → `qa.warnings` and appear as "data notes" on the page.

## Data sources (all free)

- **Open-Meteo** forecast API, 7 days hourly, four global models: ECMWF IFS 9 km (`ec`), NOAA GFS
  (`gfs`), DWD ICON (`icon`), UK Met Office 10 km (`uk`, ends ~1 day early). Consensus = mean (vector mean
  for directions); per-model winds kept for the agreement/confidence check.
- ECMWF 9 km has **no pressure-level data** on Open-Meteo, so ECMWF upper-air fields (850/700 hPa wind,
  temperature, heights, humidity, and the launch-band profile) come from `ecmwf_ifs025` (`UPPER_SOURCE`).
- ICON has no boundary-layer height; consensus uses the other models.
- **Open-Meteo Marine** sea level for tide highs/lows at beach sites (modelled, not official tables).
- **BOM station observations** JSON (`IDQ60901`/`IDN60901`, falling back to `x60801` for country
  stations). Each site has a primary station, optional `bom_alt` backups used when the primary is over
  3 h stale, and `bom_rep=False` where the station is not representative (Kempsey for Crescent Head).
- Not used, by design: BOM's own forecast API (terms forbid reuse), SkySight/XC Skies (subscription,
  no API), Holfuy launch stations (API needs station-owner permission), Windy API (paid). Linked only.
- Open-Meteo free tier has a daily request budget. Current use is well within it, but many more sites
  or more frequent refreshes could hit it. Heavy testing from a shared IP can also hit it.

## Sites

27 sites in `SITES` / `NSW_SITES` (16 QLD, 11 NSW), mostly from the SAFA National Site Guide and club
pages. Each has launch arcs (`dirs`, degrees clockwise), `wind` = [min, ideal low, ideal high, max] km/h
(starting estimates unless the guide gives limits), `mode` (ridge / thermal / both), height, rating,
club, BOM station, optional tide point, radar, CTA ceiling and notes. Mt Barney is not a listed SAFA site
(launch and directions unknown, height from terrain model). NSW times use Australia/Sydney.

## Scoring (index.html → hourCalc / dayCalc)

- Score 0–100: Good ≥60, Marginal 35–59, Unlikely <35. Day score = best 3-hour average; the window is
  the run of hours ≥70% of the peak. Confidence from per-model agreement; 4+ days out capped at Medium.
- **Wind used for scoring:** coastal sites (<200 m) use the models' **80 m wind**; hill launches (≥200 m)
  use the wind averaged over **launch height to +300 m** from pressure-level profiles. Gusts add the 10 m
  gust spread. The 10 m wind is shown alongside but not scored.
- **Direction:** full marks inside a launch arc, then a smooth fall-off (22.5° outside = half, 45° = zero).
  Thermal sites accept wind under 8 km/h from most directions.
- **Thermals (09:00–17:00):** strength = Deardorff convective velocity w* from sunshine, boundary-layer
  depth and ground dryness (dry air → stronger). 1.2 m/s workable, 1.8 good, 2.5+ strong. Also usable
  lift height (lower of BL top and cloudbase), sunshine reduced by low/mid/high cloud, wind at ~1,500 m,
  rain, storm risk (CAPE + rain chance). Cumulus vs blue day, cu spread-out risk (850 hPa RH ≥80%) and
  overdevelopment risk (700 hPa RH ≥60% with CAPE ≥500) are shown and trim the score.
- The 850–700 hPa lapse rate is displayed but deliberately **not** scored (it sits above the boundary layer
  and is normally stable on good days — this was the cause of the Tamborine under-scoring below).

## Lessons from real flying (calibration history)

- **1 Nov 2026, Rainbow Beach:** pilots flew from the Carlo Sand Blow in a northerly; dashboard said 8.
  Double Island Point (96 m) recorded N 28–35 km/h vs 11–13 forecast. Checks at six exposed coastal BOM
  stations showed model 10 m wind 1.2–2× too light and 80 m wind close to observed → coastal sites now use
  80 m wind. Rainbow's arc widened to N–ENE (guide says NNE–ENE).
- **9 Nov 2026, Mt Tamborine:** SkySight showed excellent conditions; dashboard said 30. Cause was the
  lapse-rate factor flooring thermal scores → replaced with w*. Re-scored 90.
- Verification (3–7 Nov): 80 m coastal forecasts within ~10% of exposed-station winds on average,
  direction errors ~15–22°. Rainbow is the noisiest site (headland station).

## Link and site audit (15 Nov 2026)

All page links and all 27 sites were re-checked against the SAFA site guide (KML export at
siteguide.org.au/Kml/Open and /Kml/Closed) and club pages; all sites were open. Each site can carry
`live` (FreeFlight Wx launch station link), `holfuy`, `radar` and `note` (access/safety rules shown as
"Site notes"). Repeat this audit every few months: sites close and rules change. Re-checked 28 Nov 2026: all links fine,
all sites still open; Mt Borah now uses Tamworth Airport (Barraba only reports at 9 am).

## Open items

- Mt Barney real launch location and facing direction.
- Pilots' sanity check of wind ranges, especially inland sites and Rainbow's maximum.
- Compare thermal strength and cloudbase with what pilots report after flights, and tune thresholds.
- Possible additions: Open-Meteo ensemble (chance-of-flyable), Victoria/ACT sites, regional (not
  single-point) view like SkySight maps.

## Working on it

- Test scoring changes against real data: download the live `forecast.json`, load the `<script>` from
  `index.html` in Node with stubbed `document`/`localStorage`, and call `dayCalc` / `hourCalc`. Older
  forecasts are in git history (`git log -- forecast.json`) for backtesting.
- Check page changes at phone width (~400 px) and in dark mode; the page must not scroll sideways.
- The units switch (ft/m, km/h/knots) is per viewer: format every displayed wind with `W()`/`WU()`,
  heights with `Hft()`/`Hm()`, thermal strength with `TH()`.
- Commit with a clear message explaining the why; changes go live about a minute after pushing.
