# Alishan Shizhuo Terrain Preprocessing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a validated 500 m by 500 m EPSG:3826 GeoTIFF terrain crop and preview from the official 2025 Chiayi County DTM archive.

**Architecture:** Small command-line modules load the canonical YAML site definition, derive metric geometry, inspect the raw ZIP before parsing, and create a standard GeoTIFF. A standalone validator checks output georeferencing and elevation data without simulation-specific conversion.

**Tech Stack:** Python 3, PyYAML, pyproj, rasterio, NumPy, Matplotlib, standard-library unittest.

**Spec:** `docs/superpowers/specs/2026-09-10-alishan-shizhuo-terrain-preprocessing-design.md`

## Global Constraints

- Use EPSG:3826 for every metric extent and GeoTIFF horizontal CRS.
- Preserve the source ZIP unchanged under `data/raw/` and ignore it from Git.
- Read all site parameters from `configs/site.yaml`; do not hard-code Shizhuo coordinates.
- Never smooth, interpolate large missing regions, or create Gazebo/PX4/Blender assets.
- Reject unsupported archive formats, CRS mismatches, missing target coverage, and excessive NoData.

---

### Task 1: Geometry and configuration foundation

**Files:**
- Create: `tests/test_site_geometry.py`
- Create: `scripts/site_geometry.py`
- Create: `requirements.txt`

**Interfaces:**
- Produces: `load_site_config(path: Path) -> SiteConfig`, `project_site(site: SiteConfig) -> ProjectedSite`, and `ProjectedBounds` values in metres.

- [ ] **Step 1: Write failing geometry tests**

```python
site = load_site_config(SITE_CONFIG)
projected = project_site(site)
self.assertAlmostEqual(projected.easting_m, 219213.909, places=3)
self.assertAlmostEqual(projected.northing_m, 2597401.261, places=3)
self.assertEqual(projected.bounds.east_m - projected.bounds.west_m, 500.0)
```

- [ ] **Step 2: Run the test and verify it fails because the module is absent**

Run: `python -m unittest discover -s tests -v`

- [ ] **Step 3: Implement validated YAML loading and EPSG:4326 to EPSG:3826 projection**

```python
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)
easting_m, northing_m = transformer.transform(site.longitude, site.latitude)
```

- [ ] **Step 4: Run geometry tests and verify they pass**

Run: `python -m unittest discover -s tests -v`

### Task 2: Safe official-source handling and inspection

**Files:**
- Create: `data/raw/.gitignore`
- Create: `scripts/inspect_dtm.py`

**Interfaces:**
- Consumes: a ZIP path and `ProjectedBounds`.
- Produces: a JSON/text report listing discovered members, supported grid members, declared metadata, and coverage result.

- [ ] **Step 1: Download the exact official Chiayi County ZIP once with curl and save a SHA-256 checksum in command output**

```bash
curl --fail --location --output data/raw/chiayi_20m_dtm_2025.zip '<official URL>'
sha256sum data/raw/chiayi_20m_dtm_2025.zip
```

- [ ] **Step 2: Inspect ZIP members through `zipfile.ZipFile` and reject non-ZIP or empty archives**

```python
with ZipFile(path) as archive:
    members = [info for info in archive.infolist() if not info.is_dir()]
if not members:
    raise SourceFormatError("DTM archive contains no files")
```

- [ ] **Step 3: Parse discovered metadata before accepting source grids; emit an actionable error for an unknown layout**

Run: `python scripts/inspect_dtm.py --input data/raw/chiayi_20m_dtm_2025.zip --site-config configs/site.yaml`

### Task 3: GeoTIFF crop and preview

**Files:**
- Create: `scripts/crop_dtm.py`

**Interfaces:**
- Consumes: inspected source tiles, `ProjectedBounds`, and a NoData threshold.
- Produces: `data/processed/alishan_shizhuo_terrain_20m.tif` and `data/processed/alishan_shizhuo_terrain_preview.png`.

- [ ] **Step 1: Implement source-grid discovery without filename assumptions**

```python
if declared_horizontal_crs != "TWD97":
    raise CrsMismatchError(f"Expected TWD97, got {declared_horizontal_crs}")
```

- [ ] **Step 2: Select all overlapping grids and reject absent site coverage**

```python
if not overlapping_tiles:
    raise CoverageError("No DTM grid overlaps the requested EPSG:3826 site bounds")
```

- [ ] **Step 3: Write north-up single-band GeoTIFF with EPSG:3826 and TWVD2001/source tags**

```python
profile = {"driver": "GTiff", "crs": "EPSG:3826", "count": 1, "dtype": "float32"}
```

- [ ] **Step 4: Generate a non-interactive PNG from valid source cells only and do not alter elevations**

Run: `python scripts/crop_dtm.py --input data/raw/chiayi_20m_dtm_2025.zip --site-config configs/site.yaml`

### Task 4: Validation, documentation, and end-to-end verification

**Files:**
- Create: `scripts/validate_terrain.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: GeoTIFF and site configuration.
- Produces: a concise report containing dimensions, pixel size, bounds, CRS, elevation statistics, NoData percentage, and center containment/elevation.

- [ ] **Step 1: Validate raster CRS, exact physical extent, and center containment**

```python
if dataset.crs != CRS.from_epsg(3826):
    raise ValidationError("Expected output CRS EPSG:3826")
```

- [ ] **Step 2: Compute min, max, range, NoData percentage, and center elevation without filling missing values**

```python
valid = np.ma.masked_equal(data, nodata).compressed()
nodata_percent = 100.0 * (data.size - valid.size) / data.size
```

- [ ] **Step 3: Document source, dependencies, download/crop/validate commands, and no-smoothing policy in README**

- [ ] **Step 4: Run unit tests and the three command-line stages**

Run: `python -m unittest discover -s tests -v && python scripts/inspect_dtm.py ... && python scripts/crop_dtm.py ... && python scripts/validate_terrain.py ...`
