"""Inspect native Taiwan 20 m DTM archives before terrain conversion."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from site_geometry import ProjectedBounds, SiteConfigError, load_site_config, project_site, site_bounds


EXPECTED_CRS = "EPSG:3826"
EXPECTED_HORIZONTAL_DATUM = "TWD97"
EXPECTED_VERTICAL_DATUM = "TWVD2001"


class SourceFormatError(RuntimeError):
    """Raised when a supplied archive is not a supported native DTM source."""


class CrsMismatchError(SourceFormatError):
    """Raised when source metadata does not declare the required processing CRS."""


class CoverageError(SourceFormatError):
    """Raised when no valid source tile covers the requested metric bounds."""


@dataclass(frozen=True)
class GridHeader:
    """Verified grid header values required to locate and parse a native tile."""

    tile_name: str
    tile_id: str
    horizontal_datum: str
    vertical_datum: str
    easting_spacing_m: float
    northing_spacing_m: float
    point_count: int
    easting_count: int
    northing_count: int
    southwest_easting_m: float
    southwest_northing_m: float

    @property
    def east_m(self) -> float:
        """Return the easternmost source-grid point coordinate."""
        return self.southwest_easting_m + (self.easting_count - 1) * self.easting_spacing_m

    @property
    def north_m(self) -> float:
        """Return the northernmost source-grid point coordinate."""
        return self.southwest_northing_m + (self.northing_count - 1) * self.northing_spacing_m

    def contains_bounds(self, bounds: ProjectedBounds) -> bool:
        """Return whether a requested crop lies within this grid's point extent."""
        return (
            self.southwest_easting_m <= bounds.west_m
            and self.east_m >= bounds.east_m
            and self.southwest_northing_m <= bounds.south_m
            and self.north_m >= bounds.north_m
        )


@dataclass(frozen=True)
class GridTile:
    """A discovered native grid member and its verified header."""

    grid_member: str
    header_member: str
    header: GridHeader


@dataclass(frozen=True)
class DtmArchive:
    """A supported DTM archive with all valid, paired native tiles."""

    path: Path
    metadata_crs: str
    tiles: tuple[GridTile, ...]
    ignored_headers: tuple[str, ...]

    def tile_covering(self, bounds: ProjectedBounds) -> GridTile:
        """Return exactly one valid source grid covering the requested bounds."""
        covering_tiles = [tile for tile in self.tiles if tile.header.contains_bounds(bounds)]
        if not covering_tiles:
            raise CoverageError(
                "No verified DTM grid fully covers the requested EPSG:3826 bounds: "
                f"{bounds.west_m:.3f}, {bounds.south_m:.3f}, "
                f"{bounds.east_m:.3f}, {bounds.north_m:.3f}"
            )
        if len(covering_tiles) > 1:
            covering_tiles.sort(key=lambda tile: tile.header.point_count)
        return covering_tiles[0]


def _decode_header(raw_header: bytes) -> list[str]:
    """Decode official header text while retaining non-ASCII tile names."""
    for encoding in ("utf-8-sig", "cp950"):
        try:
            return raw_header.decode(encoding).splitlines()
        except UnicodeDecodeError:
            continue
    raise SourceFormatError("DTM header is neither UTF-8 nor CP950 encoded")


def _parse_header(raw_header: bytes, header_member: str) -> GridHeader:
    """Validate the documented DTM header structure and return its geometry."""
    lines = _decode_header(raw_header)
    if len(lines) < 12:
        raise SourceFormatError(f"Header {header_member} has {len(lines)} fields; expected at least 12")
    try:
        header = GridHeader(
            tile_name=lines[0].strip(),
            tile_id=lines[1].strip(),
            horizontal_datum=lines[2].strip(),
            vertical_datum=lines[3].strip(),
            easting_spacing_m=float(lines[5]),
            northing_spacing_m=float(lines[6]),
            point_count=int(lines[7]),
            easting_count=int(lines[8]),
            northing_count=int(lines[9]),
            southwest_easting_m=float(lines[10]),
            southwest_northing_m=float(lines[11]),
        )
    except ValueError as error:
        raise SourceFormatError(f"Header {header_member} has non-numeric grid geometry") from error

    if not header.horizontal_datum.startswith(EXPECTED_HORIZONTAL_DATUM):
        raise CrsMismatchError(
            f"Header {header_member} declares {header.horizontal_datum!r}; expected {EXPECTED_HORIZONTAL_DATUM}"
        )
    if header.vertical_datum != EXPECTED_VERTICAL_DATUM:
        raise CrsMismatchError(
            f"Header {header_member} declares vertical datum {header.vertical_datum!r}; "
            f"expected {EXPECTED_VERTICAL_DATUM}"
        )
    if header.easting_spacing_m <= 0 or header.northing_spacing_m <= 0:
        raise SourceFormatError(f"Header {header_member} has non-positive grid spacing")
    if header.point_count <= 0 or header.easting_count <= 1 or header.northing_count <= 1:
        raise SourceFormatError(f"Header {header_member} has invalid grid dimensions")
    if header.easting_count * header.northing_count != header.point_count:
        raise SourceFormatError(
            f"Header {header_member} grid dimensions do not match its declared point count"
        )
    return header


def _member_stems(archive: ZipFile, suffix: str) -> dict[str, str]:
    """Map case-insensitive member stems to archive paths for one file type."""
    return {
        Path(member).stem.lower(): member
        for member in archive.namelist()
        if not member.endswith("/") and member.lower().endswith(suffix)
    }


def inspect_archive(path: Path) -> DtmArchive:
    """Discover and validate a native official DTM ZIP without extracting it."""
    try:
        with ZipFile(path) as archive:
            metadata_members = [
                member for member in archive.namelist() if Path(member).name.lower() == "metadata.xml"
            ]
            if len(metadata_members) != 1:
                raise SourceFormatError("DTM archive must contain exactly one Metadata.xml member")
            metadata_text = archive.read(metadata_members[0]).decode("utf-8-sig", errors="replace")
            if EXPECTED_CRS not in metadata_text:
                raise CrsMismatchError(f"Archive metadata does not declare {EXPECTED_CRS}")

            grid_members = _member_stems(archive, ".grd")
            header_members = _member_stems(archive, ".hdr")
            if not grid_members or not header_members:
                raise SourceFormatError("DTM archive must contain paired .grd and .hdr members")

            tiles: list[GridTile] = []
            ignored_headers: list[str] = []
            for stem, header_member in sorted(header_members.items()):
                grid_member = grid_members.get(stem)
                if grid_member is None:
                    ignored_headers.append(f"{header_member}: no matching .grd member")
                    continue
                try:
                    header = _parse_header(archive.read(header_member), header_member)
                except SourceFormatError as error:
                    ignored_headers.append(str(error))
                    continue
                tiles.append(GridTile(grid_member=grid_member, header_member=header_member, header=header))
    except FileNotFoundError as error:
        raise SourceFormatError(f"DTM archive does not exist: {path}") from error
    except BadZipFile as error:
        raise SourceFormatError(f"DTM archive is not a readable ZIP: {path}") from error

    if not tiles:
        raise SourceFormatError("DTM archive contains no valid grid/header pairs")
    return DtmArchive(
        path=path,
        metadata_crs=EXPECTED_CRS,
        tiles=tuple(tiles),
        ignored_headers=tuple(ignored_headers),
    )


def main() -> None:
    """Print a concise source-inspection report for a site and native DTM archive."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Official native DTM ZIP archive")
    parser.add_argument(
        "--site-config", type=Path, default=Path("configs/site.yaml"), help="Canonical site YAML path"
    )
    arguments = parser.parse_args()

    site = load_site_config(arguments.site_config)
    bounds = site_bounds(site, project_site(site))
    source = inspect_archive(arguments.input)
    tile = source.tile_covering(bounds)
    print(f"archive: {source.path}")
    print(f"metadata_crs: {source.metadata_crs}")
    print(f"valid_tiles: {len(source.tiles)}")
    print(f"ignored_headers: {len(source.ignored_headers)}")
    print(f"covering_tile: {tile.grid_member}")
    print(
        "tile_grid: "
        f"{tile.header.easting_count} x {tile.header.northing_count} at "
        f"{tile.header.easting_spacing_m:g} m x {tile.header.northing_spacing_m:g} m"
    )
    print(
        "site_bounds_epsg3826: "
        f"{bounds.west_m:.3f}, {bounds.south_m:.3f}, {bounds.east_m:.3f}, {bounds.north_m:.3f}"
    )


if __name__ == "__main__":
    try:
        main()
    except (SourceFormatError, SiteConfigError) as error:
        raise SystemExit(f"error: {error}")
