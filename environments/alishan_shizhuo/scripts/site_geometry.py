"""Load canonical site configuration for terrain preprocessing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pyproj import Transformer


WGS84_CRS = "EPSG:4326"
PROCESSING_CRS = "EPSG:3826"


class SiteConfigError(ValueError):
    """Raised when the canonical site YAML cannot define valid terrain geometry."""


@dataclass(frozen=True)
class SiteConfig:
    """Canonical WGS84 site location and metric target dimensions."""

    name: str
    latitude: float
    longitude: float
    width_m: float
    height_m: float


@dataclass(frozen=True)
class ProjectedSite:
    """Site center in the metre-based terrain-processing CRS."""

    easting_m: float
    northing_m: float


@dataclass(frozen=True)
class ProjectedBounds:
    """Axis-aligned terrain extent in EPSG:3826 metres."""

    west_m: float
    south_m: float
    east_m: float
    north_m: float

    @property
    def width_m(self) -> float:
        """Return the east-west extent in metres."""
        return self.east_m - self.west_m

    @property
    def height_m(self) -> float:
        """Return the north-south extent in metres."""
        return self.north_m - self.south_m


def load_site_config(path: Path) -> SiteConfig:
    """Load the environment site definition from YAML."""
    try:
        with path.open(encoding="utf-8") as config_file:
            data = yaml.safe_load(config_file)
    except OSError as error:
        raise SiteConfigError(f"Unable to read site configuration: {path}") from error
    except yaml.YAMLError as error:
        raise SiteConfigError(f"Invalid YAML in site configuration: {path}") from error
    if not isinstance(data, dict):
        raise SiteConfigError("site configuration must be a YAML mapping")
    for field_name in ("name", "latitude", "longitude", "width_m", "height_m"):
        if field_name not in data:
            raise SiteConfigError(f"missing required field: {field_name}")
    try:
        site = SiteConfig(
            name=str(data["name"]),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            width_m=float(data["width_m"]),
            height_m=float(data["height_m"]),
        )
    except (TypeError, ValueError) as error:
        raise SiteConfigError("site latitude, longitude, width_m, and height_m must be numeric") from error
    if not site.name.strip():
        raise SiteConfigError("site name must not be empty")
    if not -90.0 <= site.latitude <= 90.0:
        raise SiteConfigError("site latitude must be between -90 and 90 degrees")
    if not -180.0 <= site.longitude <= 180.0:
        raise SiteConfigError("site longitude must be between -180 and 180 degrees")
    if site.width_m <= 0.0 or site.height_m <= 0.0:
        raise SiteConfigError("site width_m and height_m must be positive")

    return site


def project_site(site: SiteConfig) -> ProjectedSite:
    """Transform the canonical WGS84 center into EPSG:3826 metres."""
    transformer = Transformer.from_crs(WGS84_CRS, PROCESSING_CRS, always_xy=True)
    easting_m, northing_m = transformer.transform(site.longitude, site.latitude)
    return ProjectedSite(easting_m=easting_m, northing_m=northing_m)


def site_bounds(site: SiteConfig, projected: ProjectedSite) -> ProjectedBounds:
    """Return the centered metric crop bounds defined by the site dimensions."""
    half_width_m = site.width_m / 2.0
    half_height_m = site.height_m / 2.0
    return ProjectedBounds(
        west_m=projected.easting_m - half_width_m,
        south_m=projected.northing_m - half_height_m,
        east_m=projected.easting_m + half_width_m,
        north_m=projected.northing_m + half_height_m,
    )
