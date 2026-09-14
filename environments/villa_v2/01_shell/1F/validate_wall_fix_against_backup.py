"""Prove unchanged shell features against the pre-wall-fix Blender backup.

Run with the corrected scene open in Blender. This script only mutates the
in-memory validation process; it never saves either file.
"""
import bpy
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
BACKUP = OUT / '1F_shell_before_wall_fix.blend'
RESULT = OUT / '1F_wall_fix_comparison.json'
REMOVED = {
    '1F_Column_007_GreatRoom_W1', '1F_Column_008_GreatRoom_E1',
    '1F_Column_009_GreatRoom_W2', '1F_Column_010_GreatRoom_E2',
}


def signature(obj):
    # matrix_basis is valid for both linked scene objects and unlinked objects
    # freshly appended from the backup library. matrix_world for the latter is
    # identity until dependency-graph evaluation.
    vertices = sorted(tuple(round(c, 6) for c in (obj.matrix_basis @ v.co))
                      for v in obj.data.vertices)
    faces = sorted(tuple(sorted(tuple(round(c, 6) for c in
                      (obj.matrix_basis @ obj.data.vertices[i].co)) for i in p.vertices))
                   for p in obj.data.polygons)
    return hashlib.sha256(repr((vertices, faces)).encode()).hexdigest()


def main():
    assert BACKUP.exists(), f'Missing required backup: {BACKUP}'
    current_scene = bpy.context.scene
    current = {o.name:o for o in current_scene.objects}
    # Free the original names before appending the backup scene. The corrected
    # file is never saved by this script, so this is a read-only disk audit.
    for name, obj in current.items():
        obj.name = 'CURRENT__' + name
    with bpy.data.libraries.load(str(BACKUP), link=False) as (source, target):
        target.scenes = list(source.scenes)
    backup_scene = target.scenes[0]
    backup = {o.name:o for o in backup_scene.objects}

    invariant = ['1F_Floor_Main','1F_Terrace_Main','1F_Terrace_Left',
                 '1F_Terrace_Dining','1F_Entry_Porch',
                 '1F_StairA_DownToB1','1F_StairB_UpTo2F']
    invariant += sorted(name for name,o in backup.items()
                        if o.get('element_type') == 'glass')
    invariant += sorted(name for name,o in backup.items()
                        if o.get('element_type') == 'column' and name not in REMOVED)
    changed = []
    missing = []
    for name in invariant:
        if name not in current or name not in backup:
            missing.append(name)
        elif signature(current[name]) != signature(backup[name]):
            changed.append(name)
    removed_state = {name:{'present_before':name in backup,
                           'absent_after':name not in current} for name in sorted(REMOVED)}
    doors_unchanged = current_scene.get('door_paths_json') == backup_scene.get('door_paths_json')
    result = {
        'backup': str(BACKUP),
        'backup_sha256': hashlib.sha256(BACKUP.read_bytes()).hexdigest(),
        'invariant_objects_checked': len(invariant),
        'invariant_objects_changed': changed,
        'invariant_objects_missing': missing,
        'door_paths_unchanged': doors_unchanged,
        'great_room_columns_removed': removed_state,
        'passed': not changed and not missing and doors_unchanged and
                  all(v['present_before'] and v['absent_after'] for v in removed_state.values()),
    }
    if changed:
        name = changed[0]
        result['diagnostic_first_difference'] = {
            'name': name,
            'current_location': list(current[name].location),
            'backup_location': list(backup[name].location),
            'current_matrix_translation': list(current[name].matrix_world.translation),
            'backup_matrix_translation': list(backup[name].matrix_world.translation),
            'current_first_local_vertex': list(current[name].data.vertices[0].co),
            'backup_first_local_vertex': list(backup[name].data.vertices[0].co),
            'current_counts': [len(current[name].data.vertices), len(current[name].data.polygons)],
            'backup_counts': [len(backup[name].data.vertices), len(backup[name].data.polygons)],
        }
    RESULT.write_text(json.dumps(result, indent=2))
    print('WALL FIX BACKUP COMPARISON', json.dumps(result, indent=2))
    if not result['passed']:
        raise AssertionError(f'Wall-fix backup comparison failed: {RESULT}')


if __name__ == '__main__':
    main()
