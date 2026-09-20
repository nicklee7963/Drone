"""Pure validation helpers shared by the Villa V3 Blender and Gazebo tools."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


FLOOR_Z = {"B1": -3.2, "1F": 0.0, "2F": 3.2, "3F": 6.4, "Roof": 9.6}
RESOLVED_DECISIONS = {"FIXED", "PRESERVED_REFERENCE_INTENT", "FALSE_POSITIVE"}


def validate_floor_name(name: str) -> str:
    if name not in FLOOR_Z:
        raise ValueError(f"unsupported floor {name!r}; expected one of {tuple(FLOOR_Z)}")
    return name


def floor_z(name: str) -> float:
    return FLOOR_Z[validate_floor_name(name)]


def interval_gap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Return positive separation, zero contact, or negative overlap depth."""
    if a0 > a1 or b0 > b1:
        raise ValueError("interval endpoints must be ordered")
    return max(a0, b0) - min(a1, b1)


def rect_overlap_area(a: tuple[float, float, float, float],
                      b: tuple[float, float, float, float]) -> float:
    width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return width * height


def classify_gap(width_m: float, context: str) -> str:
    if width_m < 0:
        raise ValueError("gap width cannot be negative")
    declared = {
        "declared_door": "INTENTIONAL_DOOR",
        "declared_circulation": "INTENTIONAL_CIRCULATION",
        "declared_stair": "INTENTIONAL_STAIR_OPENING",
        "declared_glass": "INTENTIONAL_GLASS_TRANSITION",
        "declared_terrace": "INTENTIONAL_TERRACE_OPENING",
    }
    if context in declared:
        return declared[context]
    if context == "undeclared_exterior":
        return "ACCIDENTAL_EXTERIOR_GAP"
    if context == "interior_free_space" and width_m < 0.85:
        return "UNWALKABLE_SLIVER"
    if context == "wall_glass":
        return "WALL_GLASS_CRACK"
    if context == "wall_wall":
        return "WALL_WALL_CRACK"
    return "UNKNOWN"


def resolve_audit_candidates(audit: dict, decisions: dict) -> tuple[list[dict], list[dict]]:
    """Overlay reviewed decisions on raw, read-only audit candidates."""
    resolved = []
    unresolved = []
    for raw in audit.get("candidates", []):
        item = dict(raw)
        review = decisions.get(item.get("id"))
        if review:
            item.update(review)
        if (item.get("decision") not in RESOLVED_DECISIONS
                or not item.get("reference_files") or not item.get("rationale")):
            unresolved.append(item)
        resolved.append(item)
    return resolved, unresolved


def _issue(code: str, path: Path, detail: str) -> dict[str, str]:
    return {"code": code, "path": str(path), "detail": detail}


def validate_sdf_tree(root: Path) -> list[dict[str, str]]:
    """Validate visual/collision mesh presence and local mesh resources."""
    root = Path(root)
    sdf_paths = [root] if root.is_file() else sorted(root.glob("*.sdf"))
    if not sdf_paths:
        return [_issue("MISSING_SDF", root, "no SDF file found")]
    issues: list[dict[str, str]] = []
    for sdf_path in sdf_paths:
        try:
            xml_root = ET.parse(sdf_path).getroot()
        except (ET.ParseError, OSError) as exc:
            issues.append(_issue("INVALID_SDF_XML", sdf_path, str(exc)))
            continue
        for link in xml_root.findall(".//link"):
            visuals = link.findall("./visual")
            collisions = link.findall("./collision")
            if not visuals:
                issues.append(_issue("MISSING_VISUAL", sdf_path, link.get("name", "")))
            if not collisions:
                issues.append(_issue("MISSING_COLLISION", sdf_path, link.get("name", "")))
            for node in visuals + collisions:
                uri = node.findtext("./geometry/mesh/uri")
                if uri and not uri.startswith(("model://", "file://")):
                    mesh_path = sdf_path.parent / uri
                    if not mesh_path.is_file() or mesh_path.stat().st_size == 0:
                        issues.append(_issue("MISSING_MESH", mesh_path, node.tag))
    return issues
