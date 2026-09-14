#!/usr/bin/env python3
"""Download the small OSM highway-way dataset needed by Alishan Shizhuo V1."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from pyproj import Transformer

from site_geometry import PROCESSING_CRS, WGS84_CRS, load_site_config, project_site, site_bounds


OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
OSM_API_MAP_ENDPOINT = "https://api.openstreetmap.org/api/0.6/map"


class OsmDownloadError(RuntimeError):
    """Raised when an OSM road download cannot safely produce a raw artifact."""


def overpass_bbox_for_site(site_config: Path) -> tuple[float, float, float, float]:
    """Return south, west, north, east from the exact metric site rectangle."""
    site = load_site_config(site_config)
    bounds = site_bounds(site, project_site(site))
    inverse = Transformer.from_crs(PROCESSING_CRS, WGS84_CRS, always_xy=True)
    corners = (
        (bounds.west_m, bounds.south_m),
        (bounds.west_m, bounds.north_m),
        (bounds.east_m, bounds.south_m),
        (bounds.east_m, bounds.north_m),
    )
    longitude_latitude = [inverse.transform(easting, northing) for easting, northing in corners]
    longitudes = [longitude for longitude, _ in longitude_latitude]
    latitudes = [latitude for _, latitude in longitude_latitude]
    return min(latitudes), min(longitudes), max(latitudes), max(longitudes)


def build_overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """Build the narrow, geometry-complete Overpass query used by V1."""
    south, west, north, east = bbox
    if not south < north or not west < east:
        raise OsmDownloadError(f"Invalid Overpass bounding box: {bbox}")
    return (
        "[out:json][timeout:30];\n"
        f'way["highway"]({south:.9f},{west:.9f},{north:.9f},{east:.9f});\n'
        "out tags geom;\n"
    )


def osm_api_map_url_for_site(site_config: Path, endpoint: str = OSM_API_MAP_ENDPOINT) -> str:
    """Build the official OSM API map URL for the same inverse-projected site bbox."""
    south, west, north, east = overpass_bbox_for_site(site_config)
    bbox = f"{west:.9f},{south:.9f},{east:.9f},{north:.9f}"
    return endpoint + "?" + urllib.parse.urlencode({"bbox": bbox})


def write_raw_bytes_without_overwrite(output: Path, payload: bytes) -> None:
    """Persist an externally sourced raw response exactly once."""
    if output.exists():
        raise OsmDownloadError(f"Refusing to overwrite existing raw OSM data: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as raw_file:
            raw_file.write(payload)
    except FileExistsError as error:
        raise OsmDownloadError(f"Refusing to overwrite existing raw OSM data: {output}") from error


def download_osm_roads(
    site_config: Path,
    output: Path,
    endpoint: str = OVERPASS_ENDPOINT,
    timeout_seconds: float = 60.0,
) -> tuple[str, int]:
    """Fetch and preserve a raw Overpass JSON response without overwriting it."""
    if output.exists():
        raise OsmDownloadError(f"Refusing to overwrite existing raw OSM data: {output}")
    query = build_overpass_query(overpass_bbox_for_site(site_config))
    request_data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=request_data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "alishan-shizhuo-v1-road-pipeline/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload_bytes = response.read()
    except urllib.error.URLError as error:
        raise OsmDownloadError(f"Unable to reach Overpass endpoint {endpoint}: {error.reason}") from error
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OsmDownloadError("Overpass response is not valid UTF-8 JSON") from error
    elements = payload.get("elements") if isinstance(payload, dict) else None
    if not isinstance(elements, list):
        raise OsmDownloadError("Overpass JSON does not contain an elements list")

    write_raw_bytes_without_overwrite(output, payload_bytes)
    return query, len(elements)


def download_osm_api_map(site_config: Path, output: Path, timeout_seconds: float = 60.0) -> tuple[str, int]:
    """Download unmodified OSM XML from OSM's own small-area map API."""
    url = osm_api_map_url_for_site(site_config)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/xml", "User-Agent": "alishan-shizhuo-v1-road-pipeline/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload_bytes = response.read()
    except urllib.error.URLError as error:
        raise OsmDownloadError(f"Unable to reach official OSM API endpoint: {error.reason}") from error
    try:
        root = ET.fromstring(payload_bytes)
    except ET.ParseError as error:
        raise OsmDownloadError("Official OSM API response is not valid XML") from error
    if root.tag != "osm":
        raise OsmDownloadError("Official OSM API XML root is not <osm>")
    write_raw_bytes_without_overwrite(output, payload_bytes)
    return url, len(root.findall("way"))


def main() -> int:
    """Run the explicit command-line download step."""
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-config", type=Path, default=project_root / "configs/site.yaml")
    parser.add_argument("--source", choices=("overpass", "osm-api"), default="overpass")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--endpoint", default=OVERPASS_ENDPOINT)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    arguments = parser.parse_args()
    output = arguments.output
    if output is None:
        extension = "json" if arguments.source == "overpass" else "osm"
        output = project_root / f"data/raw/osm/alishan_shizhuo_roads_{arguments.source}.{extension}"
    try:
        if arguments.source == "overpass":
            source_description, element_count = download_osm_roads(
                site_config=arguments.site_config,
                output=output,
                endpoint=arguments.endpoint,
                timeout_seconds=arguments.timeout_seconds,
            )
        else:
            source_description, element_count = download_osm_api_map(
                site_config=arguments.site_config,
                output=output,
                timeout_seconds=arguments.timeout_seconds,
            )
    except (OsmDownloadError, ValueError) as error:
        print(f"OSM download error: {error}", file=sys.stderr)
        return 1
    print(f"saved_raw_osm: {output}")
    print(f"source: {arguments.source}")
    if arguments.source == "overpass":
        print(f"overpass_endpoint: {arguments.endpoint}")
        print("overpass_query:")
        print(source_description, end="")
    else:
        print(f"official_osm_api_url: {source_description}")
    print(f"way_count: {element_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
