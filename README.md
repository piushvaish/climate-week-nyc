# Calcatreu · Land & money

An interactive Climate Week demonstration connecting **2022–2026 satellite observations around Calcatreu, Río Negro**, public project reporting and disclosed corporate financing.

## Explore the demo

- Move through five real Landsat observations and compare each with 2022 using the image slider.
- Switch the vegetation mask on or off and inspect individual 200 m cells.
- Read dated government and company reports beside the image. Additional Tavily results and an AI draft brief retain their source links.
- Explore the public-filings ownership chain and the contractual cash-distribution stages.

**Coverage matters:** only 27.8% of the 25 × 25 km study window is comparable across all five observations. The baseline vegetation screen contains 204 ha; 164 ha remains above the threshold in the August 2026 image. This is vegetation screening, not verified deforestation or evidence that mining caused a change. Sayari authentication is pending; no Sayari records are published.

## Publish with GitHub Pages

In repository **Settings → Pages**, select **GitHub Actions** as the publishing source. The `Publish Calcatreu dashboard` workflow builds and publishes the `site/` directory on pushes to `main` and manual runs.

For news updates, add a repository Actions secret named **`TAVILY_API_KEY`** in **Settings → Secrets and variables → Actions**. Never put its value into a file, commit, issue or browser script. The secret is available only to the retrieval step; deployment artifacts contain source excerpts and data, not credentials.

The workflow requests an update at minute 17 of every hour. GitHub may delay scheduled runs. Each refresh makes three Tavily searches, initially observed to consume six credits; provider limits and billing apply. No satellite reprocessing is scheduled. Without the secret, manual/push builds publish the supplied snapshot, and scheduled runs skip deployment. If retrieval or validation fails, the existing deployment remains available.

The website's **Check for published updates** button reloads published data. It does not call Tavily directly. Live retrieval runs in GitHub Actions. This is a periodically refreshed dashboard, not a continuous stream.

## Build and preview locally

Python 3.12+ is sufficient for the website build, news adapter and tests; no packages are required unless reprocessing satellites.

```sh
python -m unittest -v test_dashboard.py test_pages.py
python build_pages.py
python -m http.server 8767 --directory site --bind 127.0.0.1
```

Open `http://127.0.0.1:8767/`. All asset paths are relative, so the exported site also works at a GitHub repository subpath.

The optional local live server remains available:

```sh
python dashboard_server.py --port 8766 --ask-tavily-key
```

Its terminal prompt is hidden and the key stays in process memory. It refreshes while the server runs; the GitHub Pages deployment does not run this server.

## Data and methodology

`data/calcatreu/satellite.json` contains the satellite images, observation dates, STAC links, QA coverage, encoded NDVI/NBR arrays and summaries. `evidence.json` contains curated public reporting and the ownership snapshot as of 30 June 2025. `news.json` supplies a starting Tavily snapshot; it is not an annual event dataset.

The image dates are 14 August 2022, 1 August 2023, 4 September 2024, 7 September 2025 and 17 August 2026. Processing uses USGS Landsat Collection 2 Level-2 data from Microsoft Planetary Computer, WRS 230/089. QA flags exclude clouds, shadows, snow, water, saturation and fill. Indices are averaged onto a 200 m grid in EPSG:32719, requiring at least 80% valid native support in each observation. All five years use the same 4,343 comparable cells (17,372 ha).

Baseline vegetation is NDVI ≥ 0.20 in 2022. Retention measures how much of that baseline also meets the threshold in the selected image. Lower greenness flags a decline greater than 0.10. These two measures may overlap. Seasonal, weather and other land-use effects remain unresolved, and there is no forest-cover mask or field validation. The study rectangle is not the mine or concession boundary.

To reproduce satellite processing:

```sh
python -m pip install -r requirements.txt
python inspect_calcatreu.py
python prepare_calcatreu.py
```

The retained STAC discovery files preserve source selection. A fresh processing run retrieves verified HTTPS byte ranges and creates cropped caches and a GeoTIFF, which are excluded from Git. The study coordinate comes from the [Argentine government gold-project catalogue](https://www.argentina.gob.ar/sites/default/files/catalogo_de_proyectos_avanzados_de_oro-espanol.pdf).

## Ownership and AI evidence

The ownership view and US$40 million financing link come from [Patagonia Gold's unaudited June 2025 statements, note 19](https://patagoniagold.com/wp-content/uploads/2025/08/Patagonia-Gold-June-30-2025-FS-VF.pdf). Distribution bars illustrate disclosed contractual terms, not actual payments or verified current ownership. Corporate relationships do not establish illicit activity.

The Tavily AI brief is explicitly unverified and links to its retrieved sources. Reported March/April 2026 leaching dates require reconciliation. Publication dates, retrieval dates and satellite dates remain distinct; undated discovery results do not populate the annual timeline.

Sayari MCP is a future authenticated enrichment source. The static builder deliberately omits any private Sayari export. Publishing reviewed Sayari evidence requires a separate change and a review of the applicable sharing rights.

## Open tools and attribution

Original code: MIT (see `LICENSE`). The interface uses HTML, CSS, JavaScript and Canvas. Satellite processing uses Python, NumPy, Rasterio/GDAL, pyproj, Pillow and Requests.

Contains modified public [USGS/NASA Landsat data](https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2). Microsoft hosts the public assets; it does not supply the satellite observations. [USGS quality flags](https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands) support screening. Corporate filings and news retain their publishers' rights. Tavily and Sayari are commercial enrichment services; their content is not represented as open-source data.
