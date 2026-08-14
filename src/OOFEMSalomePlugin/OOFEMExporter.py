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
    def __init__(self, mesh, elem_map, mat_map, bc_map, bc_templates, analysis_data):
        self.mesh = mesh
        self.elem_map = elem_map
        self.mat_map = mat_map
        self.bc_map = bc_map
        self.bc_templates = {t['oofem_name']: t for t in bc_templates}
        self.analysis_data = analysis_data
        self.debug_console = None
        self.SALOME_TYPE_NAMES = self._build_salome_type_map()

        module = getModule()
        if module and hasattr(module, 'debug_console'):
            self.debug_console = module.debug_console

        self._log("Initializing exporter...")
        self.group_to_mat = {mat['assigned_group']: mat for mat in self.mat_map if mat.get('assigned_group')}
        self._log(f"Found {len(self.group_to_mat)} materials assigned to groups.")

        self.elem_to_groups = self._build_element_to_group_map()

        # Maps for tracking exported entities
        self.group_name_to_set_id = {}
        self.mat_internal_id_to_oofem_id = {}
        # A map from a canonical node tuple of a face to (element_id, local_face_index)
        self.face_to_parent_map = self._build_face_to_parent_map()

        self.group_to_cs_id = {}

    def _log(self, msg):
        """Helper to log to the OOFEM debug console if available."""
        if self.debug_console:
            self.debug_console.log(msg)
        else:
            print(f"OOFEMExporter log: {msg}")

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
            if group_name in self.group_to_mat and group.GetType() != SMESH.NODE:
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
        self._log(f"Mapped {len(elem_to_groups)} elements to material groups.")
        return elem_to_groups

    def _build_face_to_parent_map(self):
        """
        Builds a map from a canonical representation of a face (a sorted tuple of its node IDs)
        to a list of parent elements and local face indices: { (n1, n2, ...): [(elem_id, local_face_idx), ...], ... }
        OOFEM local face indices are 1-based.
        """
        self._log("Building face-to-parent-element map...")
        face_map = {}
        all_element_ids = self.mesh.GetElementsId()

        for eid in all_element_ids:
            try:
                elem = self.mesh.FindElement(eid)
                num_faces = elem.GetNumberOfFaces()
                for i in range(num_faces):
                    # GetFaceNodes returns a list of node IDs for the i-th face of the element.
                    face_nodes = elem.GetFaceNodes(i)
                    if not face_nodes: continue
                    
                    key = tuple(sorted(face_nodes))
                    face_map.setdefault(key, []).append((eid, i + 1)) # OOFEM uses 1-based indexing
            except Exception:
                # This can fail for 1D elements which don't have faces. We can ignore this.
                pass
        self._log(f"Built map for {len(face_map)} unique faces.")
        return face_map
    def _get_oofem_element_type(self, eid):
        """
        Determines the OOFEM element type for a given Salome element ID.
        Priority:
        1. Group-specific override from a material assignment.
        2. Global element mapping.
        3. Fallback to "SalomeCell##".
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


        # 1. Check for group-specific overrides
        element_groups = self.elem_to_groups.get(eid, [])
        overrides = {}
        if element_groups:
            for group_name in element_groups:
                mat = self.group_to_mat.get(group_name)
                if mat and mat.get("element_mapping_override"):
                    override_map = mat["element_mapping_override"]
                    if salome_type_name in override_map and override_map[salome_type_name]:
                        oofem_type = override_map[salome_type_name]
                        if oofem_type not in overrides:
                            overrides[oofem_type] = []
                        overrides[oofem_type].append(group_name)

        if len(overrides) > 1:
            conflicting_types = ", ".join([f"'{t}' from group(s) {g}" for t, g in overrides.items()])
            self._log(f"Warning: Element {eid} (type {salome_type_name}) has conflicting element type mappings: {conflicting_types}.")
            self._log(f"Using the first one found: '{list(overrides.keys())[0]}'.")
            return list(overrides.keys())[0]
        
        if len(overrides) == 1:
            return list(overrides.keys())[0]

        # 2. No overrides, check global mapping
        global_mapping = self.elem_map.get(salome_type_name)
        if global_mapping:
            self._log(f"Cell {eid} of salome type {salome_type_id} salome type name {salome_type_name} mapped to OOFEM type {global_mapping}.")
            return global_mapping

        # 3. Fallback
        # This fallback is hit if a Salome type (e.g., "Polygon") is recognized but has no
        # corresponding entry in the global element mapping.
        self._log(f"Warning: No OOFEM mapping for Salome type '{salome_type_name}' (element {eid}). Using fallback name.")
        return f"Unmapped-{salome_type_name}"

    def _export_materials(self, f):
        """Exports all defined materials."""
        if not self.mat_map:
            return
        self._log(f"Exporting {len(self.mat_map)} materials.")
        f.write("\n# === MATERIALS ===\n")
        self.mat_internal_id_to_oofem_id.clear()
        for i, mat_data in enumerate(self.mat_map):
            mat_id = i + 1  # OOFEM uses 1-based indexing
            self.mat_internal_id_to_oofem_id[mat_data['id']] = mat_id

            oofem_type = mat_data['oofem_type']
            params = mat_data.get('params', {})

            param_list = []
            for key, value in params.items():
                param_list.append(str(key))
                param_list.append(str(value))

            params_str = " ".join(param_list)
            n_params = len(param_list)

            f.write(f"material {mat_id} type {oofem_type} n_params {n_params} params {params_str}\n")

    def _export_sets(self, f):
        """Exports all mesh groups as OOFEM sets."""
        mesh_groups = self.mesh.GetGroups()
        if not mesh_groups:
            return
        self._log(f"Exporting {len(mesh_groups)} groups as sets.")
        f.write(f"\n# === SETS ===\n")
        set_id_counter = 1
        self.group_name_to_set_id.clear()
        for group in mesh_groups:
            group_name = group.GetName()
            group_type = group.GetType()

            try:
                entity_ids = group.GetIDs()
            except Exception as e:
                self._log(f"Warning: Could not get IDs for group '{group_name}'. Skipping. Reason: {e}")
                continue

            if not entity_ids:
                self._log(f"Skipping empty group '{group_name}'.")
                continue

            if group_type == SMESH.NODE:
                keyword = "nodes"
            else:  # EDGE, FACE, VOLUME are all element groups
                keyword = "elements"

            ids_str = " ".join(map(str, sorted(entity_ids)))
            f.write(f"set {set_id_counter} name \"{group_name}\" {keyword} {ids_str}\n")
            self.group_name_to_set_id[group_name] = set_id_counter
            set_id_counter += 1

    def _export_cross_sections(self, f):
        """Exports cross sections to link materials to element sets."""
        self._log("Exporting cross sections.")
        f.write("\n# === CROSS SECTIONS ===\n")
        cs_id_counter = 1
        self.group_to_cs_id.clear()

        for mat_data in self.mat_map:
            group_name = mat_data.get('assigned_group')
            if not group_name:
                continue

            oofem_mat_id = self.mat_internal_id_to_oofem_id.get(mat_data['id'])
            set_id = self.group_name_to_set_id.get(group_name)

            if not (oofem_mat_id and set_id):
                self._log(f"Warning: Could not create cross section for material '{mat_data['name']}' on group '{group_name}'. Material or Set ID not found.")
                continue

            # Infer cross-section type from a representative element in the group
            oofem_elem_type = "unknown"
            for eid, groups in self.elem_to_groups.items():
                if group_name in groups:
                    oofem_elem_type = self._get_oofem_element_type(eid)
                    break

            cs_type, n_dofs, params = "unknown", 0, ""
            if "planestress" in oofem_elem_type.lower():
                cs_type, n_dofs, params = "PlaneStress", 2, "t 1.0"  # Default thickness
            elif "truss" in oofem_elem_type.lower():
                cs_type, n_dofs, params = "Truss", 3, "A 1.0"  # Default area
            elif "3d" in oofem_elem_type.lower():
                cs_type, n_dofs = "3d", 3

            if cs_type != "unknown":
                f.write(f"crossSect {cs_id_counter} type {cs_type} n_dofs {n_dofs} mat {oofem_mat_id} set {set_id}")
                if params: f.write(f" {params}")
                f.write("\n")
                self.group_to_cs_id[group_name] = cs_id_counter
                cs_id_counter += 1
            else:
                self._log(f"Warning: Could not determine cross section type for element type '{oofem_elem_type}' in group '{group_name}'.")

    def _export_boundary_conditions(self, f):
        """Exports all defined boundary conditions."""
        if not self.bc_map:
            return
        self._log(f"Exporting {len(self.bc_map)} boundary conditions.")
        f.write("\n# === BOUNDARY CONDITIONS ===\n")
        bc_id_counter = 1

        # We need a copy of the set counter because we might create new sets for boundary loads
        max_set_id = max(self.group_name_to_set_id.values()) if self.group_name_to_set_id else 0
        side_set_counter = max_set_id + 1

        for bc_data in self.bc_map:
            group_name = bc_data.get('assigned_group')
            if not group_name:
                self._log(f"Skipping BC '{bc_data['name']}' because it is not assigned to a group.")
                continue

            template = self.bc_templates.get(bc_data['oofem_type'])
            if not template:
                self._log(f"Warning: Could not find template for BC type '{bc_data['oofem_type']}'. Skipping.")
                continue

            apply_to = template.get('apply_to')
            set_id = self.group_name_to_set_id.get(group_name)

            if apply_to in ['nodes', 'elements']:
                if not set_id:
                    self._log(f"Warning: Group '{group_name}' for BC '{bc_data['name']}' not found. Skipping.")
                    continue
                f.write(f"BoundaryCondition {bc_id_counter} type {bc_data['oofem_type']} set {set_id}")

            elif apply_to == 'element_boundary':
                # This is the complex case. We need to create a new 'sidesofelements' set.
                all_groups = self.mesh.GetGroups()
                group = next((g for g in all_groups if g.GetName() == group_name), None)
                if not group:
                    self._log(f"Warning: Group '{group_name}' for BC '{bc_data['name']}' not found. Skipping.")
                    continue
                
                boundary_elem_ids = group.GetIDs()
                side_list = []
                for beid in boundary_elem_ids:
                    try:
                        # Get the node IDs for the boundary element, which is itself an element.
                        b_nodes_list = self.mesh.GetElemNodes(beid)
                    except TypeError:
                        b_nodes_list = self.mesh.GetElemNodes(beid, False)

                    b_nodes = tuple(sorted(b_nodes_list))
                    parent_info = self.face_to_parent_map.get(b_nodes)

                    if parent_info:
                        side_list.extend(parent_info)
                    else:
                        self._log(f"Warning: Could not find parent element for boundary element {beid} in group '{group_name}'.")

                if not side_list:
                    self._log(f"Warning: Could not identify any element sides for BC '{bc_data['name']}' on group '{group_name}'. Skipping.")
                    continue

                # Create the new set for OOFEM
                side_str = " ".join([f"{eid} {lidx}" for eid, lidx in side_list])
                f.write(f"set {side_set_counter} name \"{bc_data['name']}_sides\" sidesofelements {side_str}\n")
                f.write(f"BoundaryCondition {bc_id_counter} type {bc_data['oofem_type']} set {side_set_counter}")
                side_set_counter += 1

            params = " ".join([f"{k} {v}" for k, v in bc_data.get('params', {}).items()])
            if params:
                f.write(f" {params}")
            f.write("\n")
            bc_id_counter += 1
    def _export_nodes(self, f):
        """Exports all nodes to the given file object."""
        nodes = self.mesh.GetNodesId()
        self._log(f"Exporting {len(nodes)} nodes.")
        f.write(f"nodes {len(nodes)}\n")
        for nid in sorted(nodes):
            x, y, z = self.mesh.GetNodeXYZ(nid)
            f.write(f"node {nid} coords 3 {x:g} {y:g} {z:g}\n")

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
        f.write(f"elements {len(elems_to_export)}\n")

        for eid in sorted(elems_to_export):
            try:
                # GetElemNodes has different signatures across Salome versions.
                conn = self.mesh.GetElemNodes(eid)
            except TypeError:
                # Fallback for other versions that require the second argument.
                conn = self.mesh.GetElemNodes(eid, False)

            oofem_type = self._get_oofem_element_type(eid)

            conn_str = " ".join(map(str, conn))
            nnodes = len(conn)
            f.write(f"{oofem_type} {eid} nodes {nnodes} {conn_str}\n")

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

        params_str = " ".join([f"{key} {value}" for key, value in params.items()])
        f.write(f"{analysis_type} {params_str}\n")

    def export(self, filename):
        self._log(f"--- Starting OOFEM Export to {filename} ---")
        try:
            with open(filename, "w") as f:
                f.write("problem.out\n");
                f.write("Problem description; created by OOFEM Salome Plugin\n")
                self._export_analysis(f)
                f.write("domain 3d\n")
                self._export_nodes(f)
                self._export_elements(f)
                self._export_cross_sections(f)
                self._export_materials(f)
                self._export_boundary_conditions(f)
                self._export_sets(f)
                
            self._log(f"--- Export to {filename} finished successfully. ---")
        except Exception as e:
            self._log(f"!!! EXPORT FAILED: {e} !!!")
            raise
