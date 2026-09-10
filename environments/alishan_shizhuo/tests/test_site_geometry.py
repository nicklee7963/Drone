"""Tests for site configuration and projected geometry."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SITE_CONFIG = PROJECT_ROOT / "configs" / "site.yaml"
sys.path.insert(0, str(SCRIPTS_DIR))

from site_geometry import SiteConfigError, load_site_config, project_site, site_bounds  # noqa: E402


class SiteConfigTests(unittest.TestCase):
    """Configuration behavior used by every terrain command."""

    def test_load_site_config_preserves_canonical_wgs84_values(self) -> None:
        """A loader regression must fail if YAML site values are ignored or altered."""
        site = load_site_config(SITE_CONFIG)

        self.assertEqual(site.name, "alishan_shizhuo")
        self.assertEqual(site.latitude, 23.47939)
        self.assertEqual(site.longitude, 120.69861)
        self.assertEqual(site.width_m, 500.0)
        self.assertEqual(site.height_m, 500.0)

    def test_project_site_converts_wgs84_center_to_twd97_tm2_121(self) -> None:
        """A projection regression must fail if the wrong Taiwan CRS or axis order is used."""
        projected = project_site(load_site_config(SITE_CONFIG))

        self.assertAlmostEqual(projected.easting_m, 219213.909, places=3)
        self.assertAlmostEqual(projected.northing_m, 2597401.261, places=3)

    def test_site_bounds_are_exactly_500_m_by_500_m_in_projected_space(self) -> None:
        """A bounds regression must fail if dimensions are derived in degrees or off-center."""
        site = load_site_config(SITE_CONFIG)
        bounds = site_bounds(site, project_site(site))

        self.assertAlmostEqual(bounds.west_m, 218963.909, places=3)
        self.assertAlmostEqual(bounds.east_m, 219463.909, places=3)
        self.assertAlmostEqual(bounds.south_m, 2597151.261, places=3)
        self.assertAlmostEqual(bounds.north_m, 2597651.261, places=3)
        self.assertEqual(bounds.width_m, 500.0)
        self.assertEqual(bounds.height_m, 500.0)

    def test_load_site_config_reports_missing_required_fields_clearly(self) -> None:
        """Removing a required metric dimension must produce a config error, not a KeyError."""
        temporary_config = PROJECT_ROOT / "tests" / "missing_height_site.yaml"
        self.addCleanup(temporary_config.unlink, missing_ok=True)
        temporary_config.write_text(
            "name: test\nlatitude: 23.0\nlongitude: 120.0\nwidth_m: 500\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(SiteConfigError, "missing required field: height_m"):
            load_site_config(temporary_config)


if __name__ == "__main__":
    unittest.main()
