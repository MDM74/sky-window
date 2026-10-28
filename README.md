# Sky Window SEQ

Paragliding forecast dashboard for South-East Queensland sites. `index.html` is the page,
`forecast.json` is the data, and `refresh.py` rebuilds the data from Open-Meteo (ECMWF, GFS,
ICON, UK Met Office), Open-Meteo Marine tides and Bureau of Meteorology observations.
A GitHub Action runs `refresh.py` every 3 hours and commits the new `forecast.json`.

## One-time setup (about 10 minutes)
1. Sign up at https://github.com (free).
2. Click **+ → New repository**. Name it `sky-window`, set it **Public**, click **Create repository**.
3. On the new repo page click **uploading an existing file**. Unzip this package on a computer and
   drag in everything, including the hidden `.github` folder (on a Mac press Cmd+Shift+. to show it).
   Click **Commit changes**. Check that `.github/workflows/refresh.yml` appears in the repo.
4. **Settings → Pages**: Source = *Deploy from a branch*, Branch = `main`, folder `/ (root)`, **Save**.
5. **Settings → Actions → General → Workflow permissions**: choose *Read and write permissions*, **Save**.
6. **Actions** tab → *Refresh forecast* → **Run workflow** to do the first refresh now.
7. After a minute or two the site is live at `https://YOUR-USERNAME.github.io/sky-window/`.

## Changing sites or wind ranges
Edit the `SITES` list near the top of `refresh.py` (launch arcs in degrees, wind range in km/h:
`[min, ideal low, ideal high, max]`), commit, then run the workflow again.

## Notes
- If the BOM blocks requests from GitHub's servers, the observation panel shows "No recent
  observation" and everything else keeps working.
- GitHub pauses scheduled workflows in repos with no activity for 60 days; the 3-hourly data
  commits count as activity, but if refreshes ever stop, re-enable it from the Actions tab.
- Data: Open-Meteo (CC BY 4.0), Bureau of Meteorology, SAFA National Site Guide.
