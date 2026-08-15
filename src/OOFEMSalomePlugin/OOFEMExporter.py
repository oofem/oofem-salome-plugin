import salome
try:
    # In Salome, the SMESH module is available globally.
    import SMESH
except ImportError:
    # Provide a fallback for environments where Salome is not fully loaded,
    # though the exporter will likely fail later without it.
    print("Warning: SMESH module not found. OOFEMExporter may not function correctly.")
    SMESH = None

from OOFEMSalomePlugin.OOFEMModule import getModule


class OOFEMExporter:
    def __init__(self, mesh, elem_map, mat_map, cs_map, bc_map, tf_map, mat_templates, bc_templates, analysis_data, study_name, study_path):
        self.mesh = mesh
        self.elem_map = elem_map
        self.mat_map = mat_map
        self.bc_map = bc_map
        self.cs_map = cs_map
        self.tf_map = tf_map
        self.mat_templates = {t['oofem_name']: t for t in mat_templates}
        self.bc_templates = {t['oofem_name']: t for t in bc_templates}
        self.analysis_data = analysis_data
        self.study_name = study_name
        self.study_path = study_path
        self.debug_console = None
        self.SALOME_TYPE_NAMES = self._build_salome_type_map()

        module = getModule()
        if module and hasattr(module, 'debug_console'):
            self.debug_console = module.debug_console

        self._log("Initializing exporter...")
        # Build a map from group name to the cross section assigned to it.
        self.group_to_cs = {cs['assigned_group']: cs for cs in self.cs_map if cs.get('assigned_group')}
        self._log(f"Found {len(self.group_to_cs)} cross sections assigned to groups.")
        # Build a map from material ID to the material data for quick lookups.
        self.mat_id_to_data = {mat['id']: mat for mat in self.mat_map}
        # Build a map from time function ID to the TF data for quick lookups.
        self.tf_id_to_data = {tf['id']: tf for tf in self.tf_map}

        self.elem_to_groups = self._build_element_to_group_map()

        # Maps for tracking exported entities
        self.group_name_to_set_id = {}
        self.set_map = []
        # A map from a canonical node tuple of a boundary (face/edge) to (element_id, local_side_index)
        self.boundary_to_parent_map = self._build_boundary_to_parent_map()

    def _log(self, msg, level=0):
        """Helper to log to the OOFEM debug console if available."""
        if self.debug_console:
            self.debug_console.log(msg, level)
        else:
            print(f"OOFEMExporter log: {msg}")

    def _assign_material_ids(self):
        """Assigns a 1-based 'oofem_id' to each material in the material map."""
        self._log("Assigning OOFEM IDs to materials...")
        for i, mat_data in enumerate(self.mat_map):
            mat_data['oofem_id'] = i + 1

    def _assign_time_function_ids(self):
        """Assigns a 1-based 'oofem_id' to each time function in the map."""
        self._log("Assigning OOFEM IDs to time functions...")
        for i, tf_data in enumerate(self.tf_map):
            tf_data['oofem_id'] = i + 1

    def _build_set_map(self):
        """
        Builds a list of set data dictionaries from mesh groups, assigns OOFEM IDs,
        and populates the group_name_to_set_id map for quick lookups.
        """
        self._log("Building set data from mesh groups...")
        self.set_map = []
        self.group_name_to_set_id.clear()
        set_id_counter = 1
        mesh_groups = self.mesh.GetGroups()
        for group in mesh_groups:
            group_name = group.GetName()
            try:
                entity_ids = group.GetIDs()
                if not entity_ids:
                    self._log(f"Skipping empty group '{group_name}' during set creation.", level=1)
                    continue

                group_type = group.GetType()
                if group_type == SMESH.NODE:
                    keyword = "nodes"
                else:  # EDGE, FACE, VOLUME are all element groups
                    keyword = "elements"
                    # Check if this group contains any elements that will be exported
                    # (i.e., elements that have a cross-section/material assigned).
                    # The self.elem_to_groups map contains all such elements.
                    has_exported_elements = any(eid in self.elem_to_groups for eid in entity_ids)

                    if not has_exported_elements:
                        self._log(f"Skipping group '{group_name}' for set creation: it contains only elements without an assigned cross-section/material.", level=1)
                        continue

                
                set_data = { 'oofem_id': set_id_counter, 'name': group_name, 'keyword': keyword, 'entity_ids': entity_ids }
                self.set_map.append(set_data)
                self.group_name_to_set_id[group_name] = set_id_counter
                set_id_counter += 1

            except Exception as e:
                self._log(f"Warning: Could not process group '{group_name}' for set creation. Skipping. Reason: {e}")
        self._log(f"Created {len(self.set_map)} sets from mesh groups.")

    def _build_bc_sets(self):
        """
        Creates special sets for boundary conditions applied to element boundaries
        and appends them to the main set_map.
        """
        self._log("Building special sets for boundary conditions...")
        
        # Start numbering BC sets after the last mesh group set
        max_set_id = max([s['oofem_id'] for s in self.set_map]) if self.set_map else 0
        side_set_counter = max_set_id + 1

        for bc_data in self.bc_map:
            group_name = bc_data.get('assigned_group')
            if not group_name:
                continue

            template = self.bc_templates.get(bc_data['oofem_type'])
            if not (template and template.get('apply_to') == 'elementedges'):
                continue

            # This BC needs a 'elementedges' set.
            all_groups = self.mesh.GetGroups()
            group = next((g for g in all_groups if g.GetName() == group_name), None)
            if not group:
                self._log(f"Warning: Group '{group_name}' for BC '{bc_data['name']}' not found during set creation. Skipping.")
                continue
            
            boundary_elem_ids = group.GetIDs()
            side_list = self._find_parent_sides(boundary_elem_ids, group_name)

            if not side_list:
                self._log(f"Warning: Could not identify any element sides for BC '{bc_data['name']}' on group '{group_name}'. Set not created.")
                continue

            # Create the new set data and add it to the set_map
            set_name = f"{bc_data['name']}_sides"
            set_data = {
                'oofem_id': side_set_counter, 'name': set_name, 'keyword': 'elementedges', 'entity_ids': side_list
            }
            self.set_map.append(set_data)
            
            # Store the new set ID in the bc_data for later use during export
            bc_data['oofem_set_id'] = side_set_counter
            self._log(f"Created 'elementedges' set '{set_name}' with ID {side_set_counter} for BC '{bc_data['name']}'.")
            side_set_counter += 1

    def _format_oofem_param(self, value):
        """Formats a parameter value for the OOFEM input file."""
        if isinstance(value, list):
            # Format is: n v1 v2 v3 ...
            return f"{len(value)} {' '.join(map(str, value))}"
        # For other types, just convert to string
        return str(value)

    def _build_salome_type_map(self):
        """
        Builds a mapping from Salome element type integer ID to a UI-friendly string name.
        This is more robust than a static dictionary as it uses the SMESH module's
        own enum definitions at runtime, as revealed by inspecting SMESH.GeometryType.
        """
        if not SMESH:
            return {}

        # This map defines the desired UI string for each canonical SMESH enum name.
        UI_NAME_MAP = {
            "Geom_EDGE": "Segment",
            "Geom_TRIANGLE": "Triangle",
            "Geom_QUADRANGLE": "Quadrangle",
            "Geom_POLYGON": "Polygon",
            "Geom_TETRA": "Tetrahedron",
            "Geom_HEXA": "Hexahedron",
            "Geom_PENTA": "Pentahedron",
            "Geom_PYRAMID": "Pyramid",
            "Geom_POLYHEDRA": "Polyhedron",
        }

        type_map = {}
        for item in SMESH.GeometryType._items:
            if item._n in UI_NAME_MAP:
                type_map[item._v] = UI_NAME_MAP[item._n]
        self._log(f"Built Salome type map: {type_map}")
        return type_map

    def _build_element_to_group_map(self):
        """
        Creates a dictionary mapping each element ID to a list of group names it belongs to.
        This is needed to find group-specific material properties and element type overrides.
        """
        self._log("Building element-to-group map...")
        elem_to_groups = {}
        mesh_groups = self.mesh.GetGroups()
        for group in mesh_groups:
            group_name = group.GetName()
            # We care about any group that has a cross-section assigned to it.
            if group_name in self.group_to_cs and group.GetType() != SMESH.NODE:
                try:
                    # GetIDs() is the correct method to get entity IDs from a group.
                    element_ids = group.GetIDs()
                    for eid in element_ids:
                        if eid not in elem_to_groups:
                            elem_to_groups[eid] = []
                        elem_to_groups[eid].append(group_name)
                except Exception as e:
                    # This can happen if the group is valid but something else goes wrong.
                    self._log(f"Warning: Could not retrieve elements from group '{group_name}'. Skipping. Reason: {e}")
        self._log(f"Mapped {len(elem_to_groups)} elements to cross-section groups.")
        return elem_to_groups

    def _build_boundary_to_parent_map(self):
        """
        Builds a map from a canonical representation of a boundary entity (face or edge)
        to a list of parent elements and local indices: { (n1, n2, ...): [(elem_id, local_idx), ...], ... }
        For 3D elements, boundaries are faces and edges. For 2D, they are edges.
        OOFEM local indices are 1-based. It's assumed faces are numbered first, then edges.
        """
        self._log("Building boundary-to-parent-element map...")
        boundary_map = {}
        all_element_ids = self.mesh.GetElementsId()

        TWOD_TYPES = ["Triangle", "Quadrangle", "Polygon"]
        THREED_TYPES = ["Tetrahedron", "Hexahedron", "Pentahedron", "Pyramid", "Polyhedron"]

        THREED_EDGE_DEFINITIONS = {
            "Hexahedron": [
                (0, 1), (1, 2), (2, 3), (3, 0),  # Bottom face
                (4, 5), (5, 6), (6, 7), (7, 4),  # Top face
                (0, 4), (1, 5), (2, 6), (3, 7)   # Vertical edges
            ],
            "Tetrahedron": [
                (0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)
            ],
            "Pentahedron": [
                (0, 1), (1, 2), (2, 0),  # Bottom face
                (3, 4), (4, 5), (5, 3),  # Top face
                (0, 3), (1, 4), (2, 5)   # Vertical edges
            ],
            "Pyramid": [
                (0, 1), (1, 2), (2, 3), (3, 0),  # Base
                (0, 4), (1, 4), (2, 4), (3, 4)   # Edges to apex
            ]
        }

        for eid in all_element_ids:
            try:
                salome_type_id = self.mesh.GetElementType(eid, True)
                lookup_key = salome_type_id._v - 1
                salome_type_name = self.SALOME_TYPE_NAMES.get(lookup_key)

                if salome_type_name in THREED_TYPES:
                    num_faces = 0
                    try:
                        # Process faces of a 3D element
                        num_faces = self.mesh.ElemNbFaces(eid)
                        for i in range(num_faces):
                            face_nodes = self.mesh.GetElemFaceNodes(eid, i)
                            if face_nodes:
                                key = tuple(sorted(face_nodes))
                                boundary_map.setdefault(key, []).append((eid, i + 1))
                    except Exception:
                        pass  # Some Salome versions might not support this

                    # Process edges of a 3D element
                    if salome_type_name in THREED_EDGE_DEFINITIONS:
                        conn = self.mesh.GetElemNodes(eid)
                        if conn:
                            edge_defs = THREED_EDGE_DEFINITIONS[salome_type_name]
                            for i, edge_node_indices in enumerate(edge_defs):
                                n1_idx, n2_idx = edge_node_indices
                                if n1_idx < len(conn) and n2_idx < len(conn):
                                    n1, n2 = conn[n1_idx], conn[n2_idx]
                                    key = tuple(sorted((n1, n2)))
                                    local_edge_index = num_faces + i + 1
                                    boundary_map.setdefault(key, []).append((eid, local_edge_index))

                elif salome_type_name in TWOD_TYPES:
                    conn = self.mesh.GetElemNodes(eid)
                    if conn:
                        for i in range(len(conn)):
                            n1, n2 = conn[i], conn[(i + 1) % len(conn)]
                            key = tuple(sorted((n1, n2)))
                            boundary_map.setdefault(key, []).append((eid, i + 1))
            except Exception as e:
                self._log(f"Warning: Could not process boundaries for element {eid}. Reason: {e}")
        
        self._log(f"Built map for {len(boundary_map)} unique boundary entities (faces and edges).")
        self._log("Boundary-to-parent-element map sample (first 5 entries):")
        self._log(list(boundary_map.items())[:5])

        return boundary_map

    def _find_parent_sides(self, boundary_elem_ids, group_name):
        """Given a list of boundary element IDs, find their parent elements and local side indices."""
        side_list = []
        for beid in boundary_elem_ids:
            try:
                # Get the node IDs for the boundary element, which is itself an element.
                b_nodes_list = self.mesh.GetElemNodes(beid)
            except TypeError:
                b_nodes_list = self.mesh.GetElemNodes(beid, False)

            b_nodes = tuple(sorted(b_nodes_list))
            parent_info = self.boundary_to_parent_map.get(b_nodes)

            if parent_info:
                side_list.extend(parent_info)
            else:
                self._log(f"Warning: Could not find parent element for boundary element {beid} in group '{group_name}'.")
        return side_list

    def _get_oofem_element_type(self, eid):
        """
        Determines the OOFEM element type for a given Salome element ID.
        Priority:
        1. Cross-section-specific override.
        2. Global element mapping.
        3. Fallback to "Unmapped-SalomeTypeName".
        """
        # The GetElementType method requires a second boolean argument (iselem) in some Salome versions.
        salome_type_id = self.mesh.GetElementType(eid, True)

        # In Salome 9.15, the integer value returned by GetElementType seems to be
        # offset by +1 compared to the internal values of the SMESH.Geom_* enums.
        # For example, for an edge, GetElementType()._v is 2, but SMESH.Geom_EDGE._v is 1.
        # We subtract 1 to align the returned value with the enum values used as keys in SALOME_TYPE_NAMES.
        lookup_key = salome_type_id._v - 1
        salome_type_name = self.SALOME_TYPE_NAMES.get(lookup_key)

        if not salome_type_name:
            self._log(f"Warning: Unknown Salome element type ID '{salome_type_id._v}' (lookup key {lookup_key}) for element {eid}. Using fallback.")
            return f"SalomeCell{salome_type_id._v}"

        # 1. Check for cross-section-specific overrides
        element_groups = self.elem_to_groups.get(eid, [])
        overrides = {}
        if element_groups:
            for group_name in element_groups:
                cs = self.group_to_cs.get(group_name)
                if cs:
                    override_map = cs.get("element_mapping_override")
                    if override_map and salome_type_name in override_map and override_map[salome_type_name]:
                        oofem_type = override_map[salome_type_name]
                        if oofem_type not in overrides:
                            overrides[oofem_type] = []
                        overrides[oofem_type].append(group_name)

        if len(overrides) > 1:
            conflicting_types = ", ".join([f"'{t}' from group(s) {', '.join(g)}" for t, g in overrides.items()])
            self._log(f"Warning: Element {eid} (type {salome_type_name}) has conflicting element type mappings: {conflicting_types}.")
            self._log(f"Using the first one found: '{list(overrides.keys())[0]}'.")
            return list(overrides.keys())[0]
        
        if len(overrides) == 1:
            return list(overrides.keys())[0]

        # 2. No overrides found, check global mapping
        global_mapping = self.elem_map.get(salome_type_name)
        if global_mapping:
            self._log(f"Cell {eid} of salome type {salome_type_id} salome type name {salome_type_name} mapped to OOFEM type {global_mapping}.", level=2)
            return global_mapping

        # 3. Fallback
        self._log(f"Warning: No OOFEM mapping for Salome type '{salome_type_name}' (element {eid}). Using fallback name.")
        return f"Unmapped-{salome_type_name}"

    def _export_time_functions(self, f):
        """Exports all defined time functions."""
        if not self.tf_map:
            return
        self._log(f"Exporting {len(self.tf_map)} time functions.")
        f.write("# === TIME FUNCTIONS ===\n")
        for tf_data in sorted(self.tf_map, key=lambda x: x['oofem_id']):
            tf_id = tf_data['oofem_id']
            oofem_type = tf_data['oofem_type']
            params = tf_data.get('params', {})

            param_list = []
            for key, value in params.items():
                param_list.append(str(key))
                param_list.append(self._format_oofem_param(value))
            params_str = " ".join(param_list)

            f.write(f"{oofem_type} {tf_id} ")
            if params_str:
                f.write(f" {params_str}")
            f.write("\n")

    def _export_materials(self, f):
        """Exports all defined materials."""
        if not self.mat_map:
            return
        self._log(f"Exporting {len(self.mat_map)} materials.")
        f.write("# === MATERIALS ===\n")
        for mat_data in sorted(self.mat_map, key=lambda x: x['oofem_id']):
            mat_id = mat_data['oofem_id']
            oofem_type = mat_data['oofem_type']
            params = mat_data.get('params', {})

            param_list = []
            # Find template to get correct parameter order, if available
            # Note: This part is not fully implemented in the UI side yet.
            # For now, we just iterate over the dictionary keys.
            param_keys = params.keys()

            for key, value in params.items():
                param_list.append(str(key))
                param_list.append(self._format_oofem_param(value))
            params_str = " ".join(param_list)

            f.write(f"{oofem_type} {mat_id} name \"{mat_data['name']}\" {params_str}\n")

    def _export_sets(self, f):
        """Exports all sets defined in the pre-built set_map."""
        if not self.set_map:
            return
        self._log(f"Exporting {len(self.set_map)} sets.")
        f.write(f"# === SETS ===\n")
        # This now includes mesh-group-based sets and special BC sets
        for set_data in sorted(self.set_map, key=lambda x: x['oofem_id']):
            set_id = set_data['oofem_id']
            name = set_data['name']
            keyword = set_data['keyword']
            entity_ids = set_data['entity_ids']

            if keyword == 'elementedges':
                # For sides, entity_ids is a list of (eid, lidx) tuples
                ids_str = " ".join([f"{eid} {lidx}" for eid, lidx in entity_ids])
                ncomp = len(entity_ids)*2  # Each side has two components: element ID and local index
            else:
                # For nodes/elements, it's a list of integers
                ids_str = " ".join(map(str, sorted(entity_ids)))
                ncomp = len(entity_ids)
            f.write(f"set {set_id} name \"{name}\" {keyword} {ncomp} {ids_str}\n")

    def _export_cross_sections(self, f):
        """Exports cross sections to link materials to element sets."""
        self._log("Exporting cross sections.")
        if not self.cs_map:
            return
        f.write("# === CROSS SECTIONS ===\n")
        cs_id_counter = 1

        for cs_data in sorted(self.cs_map, key=lambda x: x.get('name', '')):
            group_name = cs_data.get('assigned_group')
            if not group_name:
                continue

            # Find the oofem_id of the material from the main material map
            mat_id = cs_data.get('material_id')
            mat_info = self.mat_id_to_data.get(mat_id)
            if not mat_info:
                self._log(f"Warning: Could not find material with ID '{mat_id}' for cross section '{cs_data['name']}'. Skipping.")
                continue
            oofem_mat_id = mat_info.get('oofem_id')

            set_id = self.group_name_to_set_id.get(group_name)
            if not set_id:
                self._log(f"Warning: Could not find set for group '{group_name}' for cross section '{cs_data['name']}'. Skipping.")
                continue

            cs_type = cs_data['oofem_type']
            
            param_list = []
            for key, value in cs_data.get('params', {}).items():
                param_list.append(str(key))
                param_list.append(self._format_oofem_param(value))
            params_str = " ".join(param_list)

            f.write(f"{cs_type} {cs_id_counter} name \"{cs_data['name']}\" material {oofem_mat_id} set {set_id}")
            if params_str:
                f.write(f" {params_str}")
            f.write("\n")
            cs_id_counter += 1

    def _export_boundary_conditions(self, f):
        """Exports all defined boundary conditions."""
        if not self.bc_map:
            return
        self._log(f"Exporting {len(self.bc_map)} boundary conditions.")
        f.write("# === BOUNDARY CONDITIONS ===\n")
        bc_id_counter = 1

        for bc_data in sorted(self.bc_map, key=lambda x: x.get('name', '')):
            group_name = bc_data.get('assigned_group')
            if not group_name:
                self._log(f"Skipping BC '{bc_data['name']}' because it is not assigned to a group.")
                continue

            template = self.bc_templates.get(bc_data['oofem_type'])
            if not template:
                self._log(f"Warning: Could not find template for BC type '{bc_data['oofem_type']}'. Skipping.")
                continue

            apply_to = template.get('apply_to')
            
            set_id = None
            if apply_to in ['nodes', 'elements']:
                set_id = self.group_name_to_set_id.get(group_name)
                if not set_id:
                    self._log(f"Warning: Group '{group_name}' for BC '{bc_data['name']}' not found. Skipping.")
                    continue
                f.write(f"{bc_data['oofem_type']} {bc_id_counter} name \"{bc_data['name']}\"  set {set_id}")

            elif apply_to == 'elementedges':
                set_id = bc_data.get('oofem_set_id')
                if not set_id:
                    self._log(f"Warning: Pre-calculated set for BC '{bc_data['name']}' on group '{group_name}' not found. Skipping.")
                    continue
                # The set itself is now written in _export_sets
                f.write(f"{bc_data['oofem_type']} {bc_id_counter} name \"{bc_data['name']}\" set {set_id}")

            if set_id is None:
                self._log(f"Warning: Could not determine set for BC '{bc_data['name']}'. Skipping.")
                continue

            # Add time function if one is assigned
            tf_internal_id = bc_data.get('time_function_id')
            if tf_internal_id:
                tf_info = self.tf_id_to_data.get(tf_internal_id)
                if tf_info:
                    f.write(f" loadTimeFunction {tf_info['oofem_id']}")

            param_list = []
            for k, v in bc_data.get('params', {}).items():
                param_list.append(str(k))
                param_list.append(self._format_oofem_param(v))
            params = " ".join(param_list)
            if params:
                f.write(f" {params}")
            f.write("\n")
            bc_id_counter += 1
    def _export_nodes(self, f):
        """Exports all nodes to the given file object."""
        nodes = self.mesh.GetNodesId()
        self._log(f"Exporting {len(nodes)} nodes.")
        f.write("# === NODES ===\n")
        # f.write(f"nodes {len(nodes)}\n")
        for nid in sorted(nodes):
            x, y, z = self.mesh.GetNodeXYZ(nid)
            f.write(f"node {nid:<10} coords 3 {x:20.10f} {y:20.10f} {z:20.10f}\n")

    def _export_elements(self, f):
        """Exports all elements that have an assigned material."""
        # The elem_to_groups map contains exactly the elements we need to export
        # (i.e., those belonging to a group with an assigned material).
        elems_to_export = self.elem_to_groups.keys()

        if not elems_to_export:
            self._log("No elements to export (no elements found in groups with assigned materials).")
            f.write("elements 0\n")
            return

        self._log(f"Exporting {len(elems_to_export)} elements (out of {self.mesh.NbElements()} total).")
        f.write("# === ELEMENTS ===\n")
        # f.write(f"elements {len(elems_to_export)}\n")

        for eid in sorted(elems_to_export):
            try:
                # GetElemNodes has different signatures across Salome versions.
                conn = self.mesh.GetElemNodes(eid)
            except TypeError:
                # Fallback for other versions that require the second argument.
                conn = self.mesh.GetElemNodes(eid, False)

            oofem_type = self._get_oofem_element_type(eid)

            conn_str = "".join([f"{node_id:10}" for node_id in conn])
            nnodes = len(conn)
            f.write(f"{oofem_type:<20} {eid:<10} nodes {nnodes:4} {conn_str}\n")

    def _export_analysis(self, f):
        if not self.analysis_data:
            self._log("Warning: No analysis data provided. Writing default analysis.")
            f.write("StaticStructural nsteps 1\n")
            return

        analysis_type = self.analysis_data.get('oofem_type')
        params = self.analysis_data.get('params', {})

        if not analysis_type:
            self._log("Warning: Analysis type not specified. Writing default analysis.")
            f.write("StaticStructural nsteps 1\n")
            return

        param_list = []
        for key, value in params.items():
            param_list.append(str(key))
            param_list.append(self._format_oofem_param(value))
        params_str = " ".join(param_list)
        f.write(f"{analysis_type} {params_str}\n")

    def _calculate_component_counts(self):
        """Pre-calculates the number of each component to be exported."""
        counts = {}
        
        counts['ndofman'] = self.mesh.NbNodes()
        counts['nelem'] = len(self.elem_to_groups)
        counts['nmat'] = len(self.mat_map)
        counts['ncrosssect'] = len(self.cs_map)
        counts['nltf'] = len(self.tf_map)
        

        bcs_to_export = [bc for bc in self.bc_map if bc.get('assigned_group')]
        counts['nbc'] = len(bcs_to_export)
        
        # All sets (mesh-based and BC-based) are now in set_map.
        counts['nset'] = len(self.set_map)
        counts['nic'] = 0  # Not implemented in this exporter
        
        self._log(f"Calculated component counts: {counts}")
        return counts

    def _export_component_sizes(self, f, counts):
        """Writes the component size records to the file."""
        f.write("# === COMPONENT SIZES ===\n")
        # OOFEM keywords are case-sensitive and have a typical order.
        order = ['ndofman', 'nelem', 'nmat', 'ncrosssect', 'nset', 'nltf', 'nbc', 'nic']
        for component in order:
            if component in counts:
                f.write(f"{component} {counts[component]} ")
        f.write("\n")


    def export(self, filename):
        self._log(f"--- Starting OOFEM Export to {filename} ---")
        try:
            # Assign IDs and build data structures before any export functions are called.
            self._assign_material_ids()
            self._assign_time_function_ids()
            self._build_set_map()
            self._build_bc_sets()

            # Pre-calculate counts and determine domain type
            counts = self._calculate_component_counts()
            domain_type = '3d'

            with open(filename, "w") as f:
                f.write("# OOFEM input file generated by OOFEM Salome Plugin\n")
                if self.study_path:
                    f.write(f"# Salome Study: {self.study_name} ({self.study_path})\n")
                else:
                    f.write(f"# Salome Study: {self.study_name}\n")

                f.write("problem.out\n")
                f.write("Problem description\n")
                self._export_analysis(f)
                f.write(f"domain {domain_type}\n")
                f.write("OutputManager tstep_all dofman_all element_all\n")
                self._export_component_sizes(f, counts)

                # Correct export order is important for OOFEM
                self._export_nodes(f)
                self._export_elements(f)
                self._export_cross_sections(f)
                self._export_materials(f)
                self._export_boundary_conditions(f)
                self._export_time_functions(f)
                self._export_sets(f)

                
            self._log(f"--- Export to {filename} finished successfully. ---")
        except Exception as e:
            self._log(f"!!! EXPORT FAILED: {e} !!!")
            raise
