import bpy
import numpy as np
import mathutils
from mathutils import Vector
import math
import os
import json
import itertools

def set_enviroment(
        environment_settings: dict,
        file_name: str
        #add_camera
        #add_env_lighting
        #remove_lights
        #add_ground_plane
        #solid_floor_bg
        #transparent_bg
        #bg_color
    ):
    print("environment_settings: "+json.dumps(environment_settings, indent=2))
    if environment_settings["add_ground_plane"]:
        add_plane(environment_settings)

    if environment_settings["add_env_lighting"]:
        add_env_lighting(environment_settings)

    if environment_settings["remove_lights"]:
        remove_lights(environment_settings)

    if environment_settings["add_camera"] and file_name != "":
        add_camera(environment_settings, file_name)

def add_plane(environment_settings):
    bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
    obj = bpy.context.active_object
    # scale big enough to capture shadows for 99% of imports
    obj.scale = (25,25,25)
    if environment_settings["transparent_bg"]:
        make_transparent(obj)
    if environment_settings["solid_floor_bg"]:
        if not environment_settings["transparent_bg"]:
            make_transparent(obj)
        add_solid_bg(environment_settings["bg_color"])


def make_transparent(plane):
    # Set plane as shadow catcher
    plane.is_shadow_catcher = True

    # Render film as transparent & RGBA alpha channel
    bpy.context.scene.render.film_transparent = True
    bpy.context.scene.render.image_settings.color_mode = 'RGBA'

    # Change render engine to Cycles for this to render properly
    # TODO: bpy.context.scene.cycles.device = 'GPU' as a future option
    bpy.context.scene.render.engine = 'CYCLES'

def add_solid_bg(bg_color):
    # switch on nodes and get reference
    bpy.context.scene.use_nodes = True
    tree = bpy.context.scene.node_tree

    layers_node = tree.nodes["Render Layers"]

    comp_node = tree.nodes["Composite"]
    comp_node.location = 500,400

    # Clear out any existing Alpha Over nodes
    for node in tree.nodes:
        if node.type == "ALPHAOVER":
            tree.nodes.remove(node)

    # create Alpha Over Node
    alpha_node = tree.nodes.new(type='CompositorNodeAlphaOver')
    alpha_node.location = 300,400
    alpha_node.premul = 1.0

    # Link up
    # clean-up first link
    if (len(layers_node.outputs[0].links) > 0):
        layer = layers_node.outputs[0].links[0]
        tree.links.remove(layer)

    tree.links.new(layers_node.outputs[0], alpha_node.inputs[2])
    tree.links.new(alpha_node.outputs[0], comp_node.inputs[0])

    # Set color of the Alpha Over node
    alpha_node.inputs[1].default_value = bg_color

def add_env_lighting(environment_settings):
    # switch on nodes and get reference
    bpy.context.scene.world.use_nodes = True
    tree = bpy.context.scene.world.node_tree

    hdri_path = os.path.dirname(os.path.abspath(__file__))+"/hdri/brown_photostudio_02_2k.exr"

    bg_node = tree.nodes["Background"]
    bg_node.inputs["Strength"].default_value = 0.75

    env_node = tree.nodes.new(type='ShaderNodeTexEnvironment')
    env_node.location = -280,300
    # set URL of HDRI image
    env_node.image = bpy.data.images.load(hdri_path)

    map_node = tree.nodes.new(type='ShaderNodeMapping')
    map_node.location = -460,300
    map_node.inputs["Rotation"].default_value[2] = math.radians(200)

    coord_node = tree.nodes.new(type='ShaderNodeTexCoord')
    coord_node.location = -640,300

    tree.links.new(coord_node.outputs[0], map_node.inputs[0])
    tree.links.new(map_node.outputs[0], env_node.inputs[0])
    tree.links.new(env_node.outputs[0], bg_node.inputs[0])
    # switch render engine to Cycles for full effect
    bpy.context.scene.render.engine = 'CYCLES'
    # change Layout screen rendering to full
    for area in bpy.context.screen.areas: 
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            if space.type == 'VIEW_3D':
                space.shading.type = 'RENDERED'

def remove_lights(environment_settings):
    bpy.ops.object.select_all(action='DESELECT')
    #build a list of scene lights
    scene_lights = [ob for ob in bpy.context.scene.objects if ob.type == 'LIGHT']
    #loop and select
    for o in scene_lights:
        o.select_set(True)
    #delete        
    bpy.ops.object.delete()

def add_camera(environment_settings, file_name):
    # create the first camera
    cam1 = bpy.data.cameras.new("Camera - LDR")
    cam1.lens = 53 # 53mm lens > reduce this down to 50mm at the end to create margins

    # create the first camera object
    cam_obj1 = bpy.data.objects.new("Camera - LDR", cam1)
    cam_obj1.location = (-4.327, -5.536, 2.14)
    cam_obj1.rotation_euler = mathutils.Euler((math.radians(77.1), 0, math.radians(-57.0)), 'XYZ')
    bpy.context.scene.collection.children['Collection'].objects.link(cam_obj1)
    bpy.context.scene.camera = cam_obj1

    #switch 3D Viewport view to active camera
    region = next(iter([area.spaces[0].region_3d for area in bpy.context.screen.areas if area.type == 'VIEW_3D']), None)
    if region:
        region.view_perspective = 'CAMERA'
    
    bpy.ops.object.select_all(action='DESELECT')
    # select objects in LDR file
    selectLDR(file_name)

    def get_min(axis):
        return min(v[axis] for v in bbox_verts)
    def get_max(axis):
        return max(v[axis] for v in bbox_verts)

    bbox_verts = []

    for obj2 in bpy.context.selected_objects:
        for v in obj2.bound_box:
            matrix = obj2.matrix_world
            bbox_verts.append(matrix @ Vector(v))

    # Get Min/Max vertices of selected objects
    vert_min = np.array([get_min(0), get_min(1), get_min(2)])
    vert_max = np.array([get_max(0), get_max(1), get_max(2)])
    # Calc bounding box
    G  = np.array((vert_min, vert_max)).T
    # bound box coords ie the 8 combinations of bfl tbr.
    bbc = [i for i in itertools.product(*G)]

    bpy.ops.object.select_all(action='DESELECT')

    # draw cube faces between vertices
    faces = [
        (0, 1, 3, 2),
        (0, 1, 5, 4),
        (1, 3, 7, 5),
        (2, 3, 7, 6),
        (5, 7, 6, 4),
        (0, 2, 6, 4),
    ]
    # create a mesh from the vert, edge, and face data
    mesh_data = bpy.data.meshes.new("cube_data")
    mesh_data.from_pydata(np.array(bbc), [], faces)

    # create a object using the mesh data
    mesh_obj = bpy.data.objects.new("cube_object", mesh_data)
    bpy.context.view_layer.update()
    bpy.context.collection.objects.link(mesh_obj)

    camera = bpy.data.cameras["Camera - LDR"]
    bpy.context.scene.camera = bpy.data.objects["Camera - LDR"]
    mesh_obj.select_set(True)
    bpy.ops.view3d.camera_to_view_selected()
    mesh_obj.hide_set(True)
    camera.lens = 50

    # Clean up - remove mesh_obj from scene
    bpy.ops.object.select_all(action='DESELECT')
    objs = bpy.data.objects
    objs.remove(objs["cube_object"], do_unlink=True)
    mesh = bpy.data.meshes["cube_data"]
    bpy.data.meshes.remove(mesh)


def selectLDR(parent, type=["MESH"]): 
    for obj in bpy.context.scene.objects:
        if obj.parent == bpy.context.scene.objects[parent]:
            obj.select_set(obj.type in type)
            if obj.type == "EMPTY":
                selectLDR(obj.name, type)