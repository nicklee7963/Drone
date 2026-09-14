# Summit Estate 1km — first version design

The supplied reference is the primary composition source, not a surveyed site. Units are metres; x east, y north/uphill, z up. The physical domain is [-500,500] in both horizontal axes. The estate is a deliberately oversized 96 × 48 m luxury residence, supporting generous indoor drone clearance.

The gated entry is southwest at (-185,-390). A 9 m winding road ascends from z≈24 to an arrival loop centred at (78,58,80). The lake is west at (-190,135), approximately 330 × 250 m, water at z=49. The villa spans x=30..126, y=115..163; main floor z=80.2, basement 74.8, upper floor 85.8, roof 91.4. A fountain fronts it; a pool and basketball court lie east, with a fire lounge southeast. Peripheral mountains/forest enclose the estate while the central plateau stays open.

Use deterministic Python/Numpy generation and local COLLADA visual meshes, primitive and triangle collision assets, SDFormat 1.9 and Gazebo Harmonic. Group meshes by material/model to keep scene entities modest. All URIs are local model:// paths. No downloaded assets, PX4, ROS, shell profile edits or changes to sibling projects.

Basement excavation must remove terrain from the building volume. Glass remains collidable, explicit open portals provide entry, floor slabs leave an atrium/stairwell void. Furnishing and landscaping have simplified collision geometry. Water has a basin floor collision but no artificial solid surface. This version is dry physics, with no hydrodynamics.

Generate a semantic scene manifest with rooms, openings, flight routes and geometry inventory. Tests cover resources, required spaces, grade and terrain contact, collision clearance along proposed routes, and actual Gazebo loading. Capture actual Gazebo renders for visible feature verification. Provide optional Blender scene import for later editing.
