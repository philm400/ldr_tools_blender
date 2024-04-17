import os
import json
import bpy
import numpy
from bpy.props import StringProperty, EnumProperty, BoolProperty, FloatVectorProperty
from bpy_extras.io_utils import ImportHelper
from typing import Any
import platform

from .importldr import import_ldraw

custom_mesh_dir = os.path.dirname(os.path.abspath(__file__))+"/meshes"

def find_ldraw_library() -> str:
    # Get list of possible ldraw installation directories for the platform
    if platform.system() == 'Windows':
        # Windows
        directories = [
            "C:\\LDraw",
            "C:\\Program Files\\LDraw",
            "C:\\Program Files (x86)\\LDraw",
            "C:\\Program Files\\Studio 2.0\\ldraw",
            "~\\Documents\\LDraw",
            "~\\Documents\\ldraw",
            "C:\\Users\\Public\\Documents\\LDraw",
            "C:\\Users\\Public\\Documents\\ldraw"
        ]
    elif platform.system() == 'Darwin':
        # MacOS
        directories = [
            "~/ldraw/",
            "/Applications/LDraw/",
            "/Applications/ldraw/",
            "/usr/local/share/ldraw",
            "/Applications/Studio 2.0/ldraw",
            "~/Documents/ldraw",
        ]
    else:
        # Linux
        directories = [
            "~/LDraw",
            "~/ldraw",
            "~/.LDraw",
            "~/.ldraw",
            "/usr/local/share/ldraw",
        ]

    # Find a directory that looks like an LDraw library.
    for dir in directories:
        dir = os.path.expanduser(dir)
        if os.path.isfile(os.path.join(dir, "LDConfig.ldr")):
            return dir

    return ''


class Preferences():
    preferences_path = os.path.join(
        os.path.dirname(__file__), 'preferences.json')

    def __init__(self):
        self.ldraw_path = find_ldraw_library()
        self.instance_type = 'LinkedDuplicates'
        self.additional_paths = []
        self.unofficial_parts = True
        self.add_gap_between_parts = True
        self.ground_object = True
        self.resolution = 'Normal'
        self.stud_logo = 'Normal'
        self.unofficial_parts = True
        self.add_camera = False
        self.add_env_lighting = False
        self.remove_lights = False
        self.add_ground_plane = False
        self.solid_floor_bg = False
        self.transparent_bg = False
        self.bg_color = [1,1,1,1]

    def from_dict(self, dict: dict[str, Any]):
        # Fill in defaults for any missing values.
        defaults = Preferences()
        self.ldraw_path = dict.get('ldraw_path', defaults.ldraw_path)
        self.instance_type = dict.get(
            'instance_type', defaults.instance_type)
        self.additional_paths = dict.get(
            'additional_paths', defaults.additional_paths)
        self.unofficial_parts = dict.get(
            'unofficial_parts', defaults.unofficial_parts)
        self.add_gap_between_parts = dict.get(
            'add_gap_between_parts', defaults.add_gap_between_parts)
        self.ground_object = dict.get(
            'ground_object', defaults.ground_object)
        self.resolution = dict.get(
            'resolution', defaults.resolution)
        self.stud_logo = dict.get(
            'stud_logo', defaults.stud_logo)
        self.add_camera = dict.get(
            'add_camera', defaults.add_camera)
        self.add_env_lighting = dict.get(
            'add_env_lighting', defaults.add_env_lighting)
        self.remove_lights = dict.get(
            'remove_lights', defaults.remove_lights)
        self.add_ground_plane = dict.get(
            'add_ground_plane', defaults.add_ground_plane)
        self.solid_floor_bg = dict.get(
            'solid_floor_bg', defaults.solid_floor_bg)
        self.transparent_bg = dict.get(
            'transparent_bg', defaults.transparent_bg)
        self.bg_color = dict.get(
            'bg_color', defaults.bg_color)

    def save(self):
        with open(Preferences.preferences_path, 'w+') as file:
            json.dump(self, file, default=lambda o: o.__dict__, indent=2)

    @staticmethod
    def load():
        preferences = Preferences()
        try:
            with open(Preferences.preferences_path, 'r') as file:
                preferences.from_dict(json.load(file))
        except Exception:
            # Set defaults if the loading fails.
            preferences = Preferences()

        return preferences
    

class LDRAW_PATH_LIST_ITEM(bpy.types.PropertyGroup): 
    """Group of properties representing an item in the list."""
    name: StringProperty(
        name="File Path",
        description="Local file path for an instance of LDraw or other parts",
        default="/New path/...."
    ) # type: ignore

class LDRAW_PATH_UL_List(bpy.types.UIList):
    """The UIList - Plain and simple, no filtering option"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = False
        layout.label(text=item.name, icon='NONE') 
      
class LDRAW_PATH_LIST_OT_NewItem(bpy.types.Operator): 
    """Add a new item to the list."""     
    bl_idname = "ldraw_path_list.new_item"
    bl_label = "Add new path"
    
    def execute(self, context): 
        context.scene.ldraw_path_list.add()
        len_i = len(context.scene.ldraw_path_list)
        context.scene.ldraw_path_list_index = len_i-1
        return{'FINISHED'}
    
class LDRAW_PATH_LIST_OT_DeleteItem(bpy.types.Operator):
    """Delete the selected item from the list."""    
    bl_idname = "ldraw_path_list.delete_item"
    bl_label = "Delete selected item"
    
    @classmethod
    def poll(cls, context): 
        return context.scene.ldraw_path_list
    
    def execute(self, context): 
        my_list = context.scene.ldraw_path_list
        index = context.scene.ldraw_path_list_index
        my_list.remove(index)
        context.scene.ldraw_path_list_index = min(max(0, index - 1), len(context.scene.ldraw_path_list) - 1)
        return{'FINISHED'}

class LDRAW_PATH_LIST_OT_MoveItem(bpy.types.Operator):
    """Moves an item up or down in the list."""    
    bl_idname = "ldraw_path_list.move_item"
    bl_label = "Move selected item"

    direction: EnumProperty(items=(('UP', 'Up', ""), ('DOWN', 'Down', ""),)) # type: ignore
    
    @classmethod
    def poll(cls, context): 
        return context.scene.ldraw_path_list
    
    def move_index(self):
        """ Move index of an item render queue while clamping it. """  
        index = bpy.context.scene.ldraw_path_list_index
        list_length = len(bpy.context.scene.ldraw_path_list) - 1 # (index starts at 0)
        new_index = index + (-1 if self.direction == 'UP' else 1)
        
        bpy.context.scene.ldraw_path_list_index = max(0, min(new_index, list_length))
        
    def execute(self, context):
        my_list = context.scene.ldraw_path_list
        index = context.scene.ldraw_path_list_index
        neighbor = index + (-1 if self.direction == 'UP' else 1)
        my_list.move(neighbor, index)
        self.move_index()
        return{'FINISHED'}

class ImportOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.importldr"
    bl_description = "Import LDR (.mpd/.ldr/.dat)"
    bl_label = "Import LDR"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    preferences = Preferences.load()

    # TODO: Consistent usage of "" vs ''
    # File type filter in file browser
    filename_ext = ".ldr"
    filter_glob: StringProperty(
        default="*.mpd;*.ldr;*.dat",
        options={"HIDDEN"}
    ) # type: ignore

    ldraw_path: StringProperty(
        name="",
        default=preferences.ldraw_path
    ) # type: ignore

    instance_type: EnumProperty(
        name="Instance Type",
        items=[
            ("LinkedDuplicates", "Linked Duplicates",
             "Objects with linked mesh data blocks (Alt+D). Easy to edit."),
            ('GeometryNodes', "Geometry Nodes",
             "Geometry node instances on an instancer mesh. Faster imports for large scenes but #harder to edit.")
        ],
        description="The method to use for instancing part meshes",
        # TODO: this doesn't set properly?
        default=preferences.instance_type
    ) # type: ignore

    add_gap_between_parts: BoolProperty(
        name="Gap Between Parts",
        description="Scale to add a small gap horizontally between parts",
        default=preferences.add_gap_between_parts
    ) # type: ignore

    ground_object: BoolProperty(
        name="Place Object on Ground",
        description="Re-calcualtes the position of the object to sit at ground level in the scene",
        default=preferences.ground_object
    ) # type: ignore

    unofficial_parts: BoolProperty(
        name="Use Unofficial Parts",
        description="Includes the 'UnOfficial/' parts folder in the list of folder to look for parts to import",
        default=preferences.unofficial_parts
    ) # type: ignore

    resolution: EnumProperty(
        name="Resolution of primitives",
        description="Resolution of primitive geometry (segments) - 8-Low, 16-Normal, 48-High",
        default=preferences.resolution,
        items=(
            ("Low",     "Low (8-seg)", "Import using low resolution primitives."),
            ("Normal",  "Normal (16-seg)", "Import using standard resolution primitives."),
            ("High",    "High (48-seg)", "High resolution primitives - Added rendering and memory overheads ** Advise against using for complex models **")
        )
    ) # type: ignore

    stud_logo: EnumProperty(
        name="Stud Logo Type",
        description="SHow/Hide stud logo, and determine the resolution/type",
        default=preferences.stud_logo,
        items=(
            ("None",     "None", "Do not show logos on studs"),
            ("Normal",  "Normal", "Basic quality logo"),
            ("High",    "High", "High quality mesh logo - ** increased memory and rendering overheads **"),
            ("Contrast",  "High Contrast",  "Similar style to that used in Lego Instructions with black highlighed studs")
        )
    ) # type: ignore

    add_camera: BoolProperty(
        name="Add a Camera",
        description="Camera will be positioned and targeted towards the imported object",
        default=preferences.add_camera
    ) # type: ignore

    add_env_lighting: BoolProperty(
        name="Add HDRI Environment",
        description="Add HDRI environment lighting",
        default=preferences.add_env_lighting
    ) # type: ignore

    remove_lights: BoolProperty(
        name="Remove Scene Lights",
        description="Remove all existing scene light objects",
        default=preferences.remove_lights
    ) # type: ignore

    add_ground_plane: BoolProperty(
        name="Add Ground Plane",
        description="Adds large scale ground plane",
        default=preferences.add_ground_plane
    ) # type: ignore

    solid_floor_bg: BoolProperty(
        name="Make Floor and background same color",
        description="Makes the ground plane a shadow catcher and scene film transparent",
        default=preferences.solid_floor_bg
    ) # type: ignore

    transparent_bg: BoolProperty(
        name="Transparent Background",
        description="Makes ground plane transparent but a shadow catcher, along with transparent world environment",
        default=preferences.transparent_bg
    ) # type: ignore

    bg_color: FloatVectorProperty(
        name = "Background Color",
        subtype = "COLOR",
        default=preferences.bg_color,
        size = 4,
        min = 0.0,
        max = 1.0
    ) # type: ignore

    def invoke(self, context, event):
        # When modal is triggered rebuild UIList items
        context.scene.ldraw_path_list.clear()
        context.scene.ldraw_path_list_index = 0
        for prop in self.preferences.additional_paths:
            context.scene.ldraw_path_list.add()
            len_i = len(context.scene.ldraw_path_list)
            context.scene.ldraw_path_list_index = len_i-1
            new_item = context.scene.ldraw_path_list[len_i-1]
            new_item.name = prop
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.label(text="LDR Import Options", icon='MESH_DATA')

    def execute(self, context):
        # Update from the UI values to support saving them to disk later.
        ImportOperator.preferences.ldraw_path = self.ldraw_path
        ImportOperator.preferences.instance_type = self.instance_type
        ImportOperator.preferences.add_gap_between_parts = self.add_gap_between_parts
        ImportOperator.preferences.unofficial_parts = self.unofficial_parts
        ImportOperator.preferences.ground_object = self.ground_object
        ImportOperator.preferences.resolution = self.resolution
        ImportOperator.preferences.stud_logo = self.stud_logo
        ImportOperator.preferences.add_camera = self.add_camera
        ImportOperator.preferences.add_env_lighting = self.add_env_lighting
        ImportOperator.preferences.remove_lights = self.remove_lights
        ImportOperator.preferences.add_ground_plane = self.add_ground_plane
        ImportOperator.preferences.solid_floor_bg = self.solid_floor_bg
        ImportOperator.preferences.transparent_bg = self.transparent_bg
        # Cast self.bg_color <bpy_prop_array> to numpy array as a list serialize
        ar = numpy.array(self.bg_color)
        bg_col_array = ar.tolist()
        ImportOperator.preferences.bg_color = bg_col_array

        data = []
        for i, item in enumerate(context.scene.ldraw_path_list, 1):
            data.append(item.name)
        ImportOperator.preferences.additional_paths = data

        env_settings = {
            "add_camera": self.add_camera,
            "add_env_lighting": self.add_env_lighting,
            "remove_lights": self.remove_lights,
            "add_ground_plane": self.add_ground_plane,
            "solid_floor_bg": self.solid_floor_bg,
            "transparent_bg": self.transparent_bg,
            "bg_color": bg_col_array,
        }

        import time
        start = time.time()
        import_ldraw(
            self,
            self.filepath,
            self.ldraw_path,
            ImportOperator.preferences.additional_paths,
            self.instance_type,
            self.add_gap_between_parts,
            self.resolution,
            self.stud_logo,
            self.ground_object,
            self.unofficial_parts,
            custom_mesh_dir,
            env_settings
        )
        end = time.time()
        print(f'Import: {round(end - start, 3)}s')

        # Save preferences to disk for loading next time.
        ImportOperator.preferences.save()
        return {'FINISHED'}

class GEOMETRY_OPTIONS_PT_Panel(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Geometry Options"
    bl_idname = "GEOMETRY_OPTIONS_PT_Panel"

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator
        return operator.bl_idname == "IMPORT_SCENE_OT_importldr"
    
    def draw(self, context):
        sfile = context.space_data
        operator = sfile.active_operator

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        row = layout.row()
        col = row.column(align=True)
        col.prop(operator, "instance_type", expand=True)
        row = layout.row()
        row.prop(operator, "add_gap_between_parts")
        row = layout.row()
        col = row.column(align=True)
        col.prop(operator, "resolution", expand=True)
        row = layout.row()
        col = row.column(align=True)
        col.prop(operator, "stud_logo", expand=True)
        row = layout.row()
        row.prop(operator, "ground_object")


class PARTS_OPTIONS_PT_Panel(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "LDraw Parts Library"
    bl_idname = "PARTS_OPTIONS_PT_Panel"

    @classmethod
    def poll(cls, context): 
        sfile =    context.space_data
        operator = sfile.active_operator
        return operator.bl_idname == "IMPORT_SCENE_OT_importldr"
    
    def draw(self, context):
        sfile = context.space_data
        operator = sfile.active_operator

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        row = layout.row()
        row.label(text="LDraw Directory Path:")
        row = layout.row()
        row.scale_y = 1.5
        row.prop(operator, "ldraw_path")

        layout.use_property_split = False
        row = layout.row()
        row.prop(operator, "unofficial_parts")


class PARTS_SUB_OPTIONS_PT_Panel(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Additional Library Paths"
    bl_idname = "PARTS_SUB_OPTIONS_PT_Panel"
    bl_parent_id = "PARTS_OPTIONS_PT_Panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context): 
        sfile =    context.space_data
        operator = sfile.active_operator
        return operator.bl_idname == "IMPORT_SCENE_OT_importldr"
    
    def draw(self, context):
        scene = context.scene

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        row = layout.row()
        
        col = row.column()
        col.template_list(
            "LDRAW_PATH_UL_List",
            "The_List",
            scene,
            "ldraw_path_list",
            scene,
            "ldraw_path_list_index",
            rows=3
        )        
        col = row.column(align=True)
        col.operator('ldraw_path_list.new_item', text='', icon='ADD')
        col.separator(factor=0.2)
        col.operator('ldraw_path_list.delete_item', text='', icon='REMOVE')
        col.separator(factor=1.5)
        col.operator('ldraw_path_list.move_item', text='', icon='TRIA_UP').direction = 'UP'
        col.separator(factor=0.2)
        col.operator('ldraw_path_list.move_item', text='', icon='TRIA_DOWN').direction = 'DOWN'

        if scene.ldraw_path_list_index >= 0 and scene.ldraw_path_list:
            item = scene.ldraw_path_list[scene.ldraw_path_list_index]
            row = layout.row()
            row.scale_y = 1.5
            row.prop(item, "name")


class ENVIRONMENT_OPTIONS_PT_Panel(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Scene / Environment Setup"
    bl_idname = "ENVIRONMENT_OPTIONS_PT_Panel"

    @classmethod
    def poll(cls, context): 
        sfile =    context.space_data
        operator = sfile.active_operator
        return operator.bl_idname == "IMPORT_SCENE_OT_importldr"
    
    def draw(self, context):
        sfile = context.space_data
        operator = sfile.active_operator

        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        row = layout.row()
        row.prop(operator, "add_camera")

        row = layout.row()
        row.prop(operator, "add_env_lighting")

        row = layout.row()
        row.separator(factor=3)
        col = row.column()
        subrow = col.row()
        subrow.prop(operator, "remove_lights")

        row = layout.row()
        row.prop(operator, "add_ground_plane")

        row = layout.row()
        row.separator(factor=3)
        col = row.column()
        subrow = col.row()
        subrow.enabled = operator.add_ground_plane and not operator.solid_floor_bg
        subrow.prop(operator, "transparent_bg")

        subrow = col.row()
        subrow.enabled = operator.add_ground_plane
        subrow.prop(operator, "solid_floor_bg")

        row = layout.row()
        row.enabled = operator.add_ground_plane
        row.prop(operator, "bg_color")