import bpy
import numpy as np
import mathutils
from mathutils import Vector
import math
import os

# TODO: Create a pyi type stub file?
from . import ldr_tools_py

from .ldr_tools_py import LDrawNode, LDrawGeometry, LDrawColor, GeometrySettings

from .material import get_material
from .environment import set_enviroment, selectLDR

# TODO: Add type hints for all functions.

global op

def import_ldraw(
        operator: bpy.types.Operator,
        filepath: str,
        ldraw_path: str,
        additional_paths: list[str],
        instance_type: str,
        add_gap_between_parts: bool,
        primitive_resolution: str,
        stud_type: str,
        ground_object: bool,
        unofficial_parts: bool,
        custom_mesh_path: str,
        environment_settings: bool,
    ):
    global op
    op = operator
    color_by_code = ldr_tools_py.load_color_table(ldraw_path)
    settings = GeometrySettings()
    settings.primitive_resolution = match_primitive(primitive_resolution)
    settings.stud_type = match_stud(stud_type)
    settings.triangulate = False
    settings.add_gap_between_parts = add_gap_between_parts
    settings.scene_scale = 1.0
    settings.unofficial_parts = unofficial_parts
    # Required for calculated normals.
    settings.weld_vertices = True

    obj_name = os.path.split(filepath)

    # TODO: Add an option to make the lowest point have a height of 0 using obj.dimensions?
    if instance_type == 'GeometryNodes' and obj_name[1] != "":
        import_instanced(filepath, ldraw_path, additional_paths, custom_mesh_path, color_by_code, settings, environment_settings, ground_object)
    elif instance_type == 'LinkedDuplicates' and obj_name[1] != "":
        import_objects(filepath, ldraw_path, additional_paths, custom_mesh_path,
                color_by_code, settings, environment_settings, ground_object)
    else:
        set_enviroment(
            environment_settings,
            obj_name[1]
        )

def match_stud(stud_type) -> any:
    match stud_type:
        case 'None': return ldr_tools_py.StudType.Disabled
        case 'Normal': return ldr_tools_py.StudType.Normal
        case 'High': return ldr_tools_py.StudType.Logo4
        case 'Contrast': return ldr_tools_py.StudType.HighContrast
        case _: return ldr_tools_py.StudType.Disabled

def match_primitive(primitive_resolution) -> any:
    match primitive_resolution:
        case 'Low': return ldr_tools_py.PrimitiveResolution.Low
        case 'Normal': return ldr_tools_py.PrimitiveResolution.Normal
        case 'High': return ldr_tools_py.PrimitiveResolution.High
        case _: return ldr_tools_py.PrimitiveResolution.Normal

def import_objects(filepath: str, ldraw_path: str, additional_paths: list[str], custom_mesh_path: str, color_by_code: dict[int, LDrawColor], settings: GeometrySettings, environment_settings: dict, ground_object: bool):
    # Create an object for each part in the scene.
    # This still uses instances the mesh data blocks for reduced memory usage.
    blender_mesh_cache = {}
    scene = ldr_tools_py.load_file(
        filepath, ldraw_path, additional_paths, custom_mesh_path, settings)

    root_obj = add_nodes(scene.root_node, scene.geometry_cache,
                         blender_mesh_cache, color_by_code)
    
    o_name = os.path.split(filepath)
    root_obj.name = o_name[1]

    # Account for Blender having a different coordinate system.
    # Apply a scene scale to match the previous version.
    # TODO: make scene scale configurable.
    root_obj.rotation_euler = mathutils.Euler(
        (math.radians(-90.0), 0.0, 0.0), 'XYZ')
    root_obj.scale = (0.01, 0.01, 0.01)

    if ground_object:
        bpy.context.view_layer.update()
        objectOnGround(root_obj.name)
    
    # Normalise object and child object scales to 1.0
    applyScaleTransform(root_obj.name)

    # check and set any environment properties 
    set_enviroment( environment_settings,  root_obj.name)

def objectOnGround(obj):
    bpy.ops.object.select_all(action='DESELECT')
    try:
        selectLDR(obj)
        bbox_verts = []
        for obj2 in bpy.context.selected_objects:
            m_vert = []
            for v in obj2.bound_box:
                matrix = obj2.matrix_world
                vert = matrix @ Vector(v)
                m_vert.append(vert[2])
            bbox_verts.append(min(m_vert))
        minz = min(bbox_verts)
        bpy.context.scene.objects[obj].matrix_world.translation.z -= minz
    except Exception:
        op.report({"ERROR"}, "An exception occurred - No vertices found")
        print("An exception occurred - No vertices found")

    bpy.ops.object.select_all(action='DESELECT')

def applyScaleTransform(root_obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj = bpy.context.scene.objects[root_obj]
    obj.select_set(True)
    selectLDR(root_obj, ["MESH","EMPTY"])
    # apply Scale transform to Delta - Avoids having to make objects single user
    bpy.ops.object.transforms_to_deltas(mode="SCALE")
    bpy.ops.object.select_all(action='DESELECT')

def add_nodes(node: LDrawNode,
              geometry_cache: dict[str, LDrawGeometry],
              blender_mesh_cache: dict[tuple[str, int], bpy.types.Mesh],
              color_by_code: dict[str, LDrawColor]):

    if node.geometry_name is not None:
        geometry = geometry_cache[node.geometry_name]
        
        # Cache meshes to optimize import times and instance mesh data.
        # Linking an existing mesh data block greatly reduces memory usage.
        mesh_key = (node.geometry_name, node.current_color)

        blender_mesh = blender_mesh_cache.get(mesh_key)
        if blender_mesh is None:
            mesh = create_colored_mesh_from_geometry(
                node.name, node.current_color, color_by_code, geometry)

            blender_mesh_cache[mesh_key] = mesh
            obj = bpy.data.objects.new(node.name, mesh)
        else:
            # Use an existing mesh data block like with linked duplicates (alt+d).
            obj = bpy.data.objects.new(node.name, blender_mesh)

    else:
        # Create an empty by setting the data to None.
        obj = bpy.data.objects.new(node.name, None)

    # Each node is transformed relative to its parent.
    obj.matrix_local = mathutils.Matrix(node.transform).transposed()
    bpy.context.collection.objects.link(obj)

    for child in node.children:
        child_obj = add_nodes(child, geometry_cache,
                              blender_mesh_cache, color_by_code)
        child_obj.parent = obj

    return obj


def import_instanced(filepath: str, ldraw_path: str, additional_paths: list[str], custom_mesh_path: str, color_by_code: dict[int, LDrawColor], settings: GeometrySettings, environment_settings: dict, ground_object: bool):
    # Instance each part on the points of a mesh.
    # This avoids overhead from object creation for large scenes.
    scene = ldr_tools_py.load_file_instanced_points(
        filepath, ldraw_path, additional_paths, custom_mesh_path, settings)

    # First create all the meshes and materials.
    blender_mesh_cache = {}
    for name, color in scene.geometry_point_instances:
        geometry = scene.geometry_cache[name]

        mesh = create_colored_mesh_from_geometry(
            name, color, color_by_code, geometry)

        blender_mesh_cache[(name, color)] = mesh

    root_obj = bpy.data.objects.new(scene.main_model_name, None)
    # Account for Blender having a different coordinate system.
    # TODO: make scene scale configurable.
    root_obj.rotation_euler = mathutils.Euler(
        (math.radians(-90.0), 0.0, 0.0), 'XYZ')
    root_obj.scale = (0.01, 0.01, 0.01)

    bpy.context.collection.objects.link(root_obj)

    # Instant each unique colored part on the faces of a mesh.
    for (name, color), instances in scene.geometry_point_instances.items():
        instancer_mesh = create_instancer_mesh(
            f'{name}_{color}_instancer', instances)

        instancer_object = bpy.data.objects.new(
            f'{name}_{color}_instancer', instancer_mesh)
        instancer_object.parent = root_obj

        bpy.context.collection.objects.link(instancer_object)

        mesh = blender_mesh_cache[(name, color)]
        instance_object = bpy.data.objects.new(
            f'{name}_{color}_instance', mesh)
        instance_object.parent = instancer_object
        bpy.context.collection.objects.link(instance_object)

        # Hide the original instanced object to avoid cluttering the viewport.
        # Make sure the object is in the view layer before hiding.
        instance_object.hide_set(True)
        instance_object.hide_render = True

        # Set up geometry nodes for the actual instancing.
        # Geometry nodes are more reliable than instancing on faces.
        # This also avoids performance overhead from object creation.
        create_geometry_node_instancing(instancer_object, instance_object)

    if ground_object:
        bpy.context.view_layer.update()
        objectOnGround(root_obj.name)
    
    # Normalise object and child object scales to 1.0
    applyScaleTransform(root_obj.name)

    # check and set any environment properties 
    set_enviroment( environment_settings,  root_obj.name)

    # Clean-up: Remove temporary Bounding Box Geometry from instancer object modifiers
    bpy.ops.object.select_all(action='DESELECT')
    selectLDR(root_obj.name)
    for obj in bpy.context.selected_objects:
        geo_nodes = obj.modifiers["GeometryNodes"].node_group
        remove_geometry_instancing_bbox(geo_nodes)
    bpy.ops.object.select_all(action='DESELECT')

def create_geometry_node_instancing(instancer_object: bpy.types.Object, instance_object: bpy.types.Object):
    modifier = instancer_object.modifiers.new(
        name="GeometryNodes", type='NODES')
    node_tree = bpy.data.node_groups.new('GeometryNodes', 'GeometryNodeTree')
    modifier.node_group = node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    group_input = nodes.new('NodeGroupInput')
    node_tree.interface.new_socket(
        in_out='INPUT', socket_type='NodeSocketGeometry', name='Geometry')

    group_output = nodes.new('NodeGroupOutput')
    node_tree.interface.new_socket(
        in_out='OUTPUT', socket_type='NodeSocketGeometry', name='Geometry')
    
    # Instancer bounding box geometry setup.
    bbox_join = nodes.new(type="GeometryNodeJoinGeometry")
    links.new(bbox_join.outputs["Geometry"],
              group_output.inputs["Geometry"])
    bbox_delete = nodes.new(type="GeometryNodeDeleteGeometry")
    bbox_delete.mode = "EDGE_FACE"
    links.new(bbox_delete.outputs["Geometry"],
              bbox_join.inputs["Geometry"])
    bbox_create = nodes.new(type="GeometryNodeBoundBox")
    links.new(bbox_create.outputs["Bounding Box"],
              bbox_delete.inputs["Geometry"])
    bbox_realize = nodes.new(type="GeometryNodeRealizeInstances")
    links.new(bbox_realize.outputs["Geometry"],
              bbox_create.inputs["Geometry"])

    # The instancer mesh's points define the instance translation.
    instance_points = nodes.new(type="GeometryNodeInstanceOnPoints")
    links.new(group_input.outputs["Geometry"],
              instance_points.inputs["Points"])
    links.new(instance_points.outputs["Instances"],
              bbox_realize.inputs["Geometry"])
    links.new(instance_points.outputs["Instances"],
              bbox_join.inputs["Geometry"])

    # Set the instance mesh.
    instance_info = nodes.new(type="GeometryNodeObjectInfo")
    instance_info.inputs[0].default_value = instance_object
    links.new(instance_info.outputs["Geometry"],
              instance_points.inputs["Instance"])

    # Scale instances from the custom attribute.
    scale_attribute = nodes.new(type="GeometryNodeInputNamedAttribute")
    scale_attribute.data_type = 'FLOAT_VECTOR'
    scale_attribute.inputs["Name"].default_value = "instance_scale"
    links.new(scale_attribute.outputs["Attribute"],
              instance_points.inputs["Scale"])

    # Rotate instances from the custom color attributes.
    rotation = nodes.new(type="FunctionNodeRotateEuler")
    rotation.type = 'AXIS_ANGLE'

    rot_axis = nodes.new(type="GeometryNodeInputNamedAttribute")
    rot_axis.data_type = 'FLOAT_VECTOR'
    rot_axis.inputs["Name"].default_value = "instance_rotation_axis"
    links.new(rot_axis.outputs["Attribute"], rotation.inputs["Axis"])

    rot_angle = nodes.new(type="GeometryNodeInputNamedAttribute")
    rot_angle.data_type = 'FLOAT'
    rot_angle.inputs["Name"].default_value = "instance_rotation_angle"

    separate = nodes.new(type="ShaderNodeSeparateXYZ")
    # The second output is the float attribute when selecting a different type.
    links.new(rot_angle.outputs[1], separate.inputs["Vector"])
    links.new(separate.outputs["X"], rotation.inputs["Angle"])

    links.new(rotation.outputs["Rotation"], instance_points.inputs["Rotation"])

def remove_geometry_instancing_bbox(node_grp: bpy.types.NodeGroup):
    if node_grp.type == "GEOMETRY":
        list = ["Bounding Box", "Realize Instances", "Delete Geometry", "Join Geometry"]
        for n in list:
            if n in [node.name for node in node_grp.nodes]:
                node = node_grp.nodes[n]
                node_grp.nodes.remove(node)
        # Re-establish link between IoP as GroupOutput
        instance_points = node_grp.nodes["Instance on Points"]
        group_output = node_grp.nodes["Group Output"]
        node_grp.links.new(instance_points.outputs["Instances"],  group_output.inputs["Geometry"])

def create_instancer_mesh(name: str, instances: ldr_tools_py.PointInstances):
    # Create a vertex at each instance.
    instancer_mesh = bpy.data.meshes.new(name)

    positions = instances.translations
    if positions.shape[0] > 0:
        # Using foreach_set is faster than bmesh or from_pydata.
        # https://devtalk.blender.org/t/alternative-in-2-80-to-create-meshes-from-python-using-the-tessfaces-api/7445/3
        # We can assume the data is already a numpy array.
        instancer_mesh.vertices.add(positions.shape[0])
        instancer_mesh.vertices.foreach_set('co', positions.reshape(-1))

        # Encode rotation and scale into custom attributes.
        # This allows geometry nodes to access the attributes later.
        scale_attribute = instancer_mesh.attributes.new(
            name='instance_scale', type='FLOAT_VECTOR', domain='POINT')
        scale_attribute.data.foreach_set(
            'vector', instances.scales.reshape(-1))

        rot_axis_attribute = instancer_mesh.attributes.new(
            name='instance_rotation_axis', type='FLOAT_VECTOR', domain='POINT')
        rot_axis_attribute.data.foreach_set(
            'vector', instances.rotations_axis.reshape(-1))

        rot_angle_attribute = instancer_mesh.attributes.new(
            name='instance_rotation_angle', type='FLOAT', domain='POINT')
        rot_angle_attribute.data.foreach_set(
            'value', instances.rotations_angle)

    instancer_mesh.validate()
    instancer_mesh.update()
    return instancer_mesh


def create_colored_mesh_from_geometry(name: str, color: int, color_by_code: dict[int, LDrawColor], geometry: LDrawGeometry):
    mesh = create_mesh_from_geometry(name, geometry)

    assign_materials(mesh, color, color_by_code, geometry)

    # TODO: Why does this need to be done here to avoid messing up face colors?
    # TODO: Can blender adjust faces in these calls?
    mesh.validate()
    mesh.update()

    # Add attributes needed to render grainy slopes properly.
    if geometry.has_grainy_slopes:
        # Get custom normals now that everything has been initialized.
        # This won't include any object transforms.
        mesh.calc_normals_split()
        loop_normals = np.zeros(len(mesh.loops) * 3)
        mesh.loops.foreach_get('normal', loop_normals)

        normals = mesh.attributes.new(
            name='ldr_normals', type='FLOAT_VECTOR', domain='CORNER')
        normals.data.foreach_set('vector', loop_normals)

    return mesh


def assign_materials(mesh: bpy.types.Mesh, current_color: int, color_by_code: dict[int, LDrawColor], geometry: LDrawGeometry):
    if len(geometry.face_colors) == 1:
        # Geometry is cached with code 16, so also handle color replacement.
        face_color = geometry.face_colors[0]
        color = current_color if face_color == 16 else face_color

        # Cache materials by name.
        material = get_material(color_by_code, color,
                                geometry.has_grainy_slopes)
        mesh.materials.append(material)
    else:
        # Handle the case where not all faces have the same color.
        # This includes patterned (printed) parts and stickers.
        for face, face_color in zip(mesh.polygons, geometry.face_colors):
            color = current_color if face_color == 16 else face_color

            material = get_material(
                color_by_code, color, geometry.has_grainy_slopes)
            if mesh.materials.get(material.name) is None:
                mesh.materials.append(material)
            face.material_index = mesh.materials.find(material.name)


def create_mesh_from_geometry(name: str, geometry: LDrawGeometry):
    mesh = bpy.data.meshes.new(name)
    if geometry.vertices.shape[0] > 0:
        # Using foreach_set is faster than bmesh or from_pydata.
        # https://devtalk.blender.org/t/alternative-in-2-80-to-create-meshes-from-python-using-the-tessfaces-api/7445/3
        # We can assume the data is already a numpy array.
        mesh.vertices.add(geometry.vertices.shape[0])
        mesh.vertices.foreach_set('co', geometry.vertices.reshape(-1))

        mesh.loops.add(geometry.vertex_indices.size)
        mesh.loops.foreach_set('vertex_index', geometry.vertex_indices)

        mesh.polygons.add(geometry.face_sizes.size)
        mesh.polygons.foreach_set(
            'loop_start', geometry.face_start_indices)
        mesh.polygons.foreach_set('loop_total', geometry.face_sizes)

        # Enable autosmooth to handle some cases where edges aren't split.
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(30.0)
        mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))

        # Add attributes needed to render grainy slopes properly.
        if geometry.has_grainy_slopes:
            is_stud = mesh.attributes.new(
                name='ldr_is_stud', type='FLOAT', domain='FACE')
            is_stud.data.foreach_set('value', geometry.is_face_stud)

    return mesh
