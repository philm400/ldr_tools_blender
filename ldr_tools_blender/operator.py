import os
import json
import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from typing import Any
import platform

from .importldr import import_ldraw

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

    def save(self):
        with open(Preferences.preferences_path, 'w+') as file:
            json.dump(self, file, default=lambda o: o.__dict__)

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


class LIST_OT_NewItem(bpy.types.Operator):
    """Add a new item to the list."""

    bl_idname = "additional_paths.new_item"
    bl_label = "Add a new item"

    def execute(self, context):
        # TODO: Don't store the preferences in the operator itself?
        # TODO: singleton pattern?
        p = context.scene.ldr_path_to_add
        ImportOperator.preferences.additional_paths.append(p)
        return {'FINISHED'}


class LIST_OT_DeleteItem(bpy.types.Operator):
    """Delete the selected item from the list."""

    bl_idname = "additional_paths.delete_item"
    bl_label = "Deletes an item"

    @classmethod
    def poll(cls, context):
        return ImportOperator.preferences.additional_paths

    def execute(self, context):
        ImportOperator.preferences.additional_paths.pop()
        return {'FINISHED'}


class ImportOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.importldr"
    bl_description = "Import LDR (.mpd/.ldr/.dat)"
    bl_label = "Import LDR"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    preferences = Preferences.load()

    # TODO: Consistent usage of "" vs ''
    # File type filter in file browser
    filename_ext = ".ldr"
    filter_glob: StringProperty(
        default="*.mpd;*.ldr;*.dat",
        options={'HIDDEN'}
    ) # type: ignore

    ldraw_path: StringProperty(
        name="",
        default=preferences.ldraw_path
    ) # type: ignore

    instance_type: EnumProperty(
        name="Instance Type",
        items=[
            ('LinkedDuplicates', "Linked Duplicates",
             "Objects with linked mesh data blocks (Alt+D). Easy to edit."),
            ('GeometryNodes', "Geometry Nodes",
             "Geometry node instances on an instancer mesh. Faster imports for large scenes but harder to edit.")
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

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        row = layout.row()
        col = row.column(align=True)
        col.prop(self, "instance_type", expand=True)
        row = layout.row()
        row.prop(self, "add_gap_between_parts")
        row = layout.row()
        col = row.column(align=True)
        col.prop(self, "resolution", expand=True)
        row = layout.row()
        col = row.column(align=True)
        col.prop(self, "stud_logo", expand=True)
        row = layout.row()
        row.prop(self, "ground_object")

        # TODO: File selector?
        # TODO: Come up with better UI for this?

        layout.separator(factor=1.5)
        layout.use_property_split = False
        row = layout.row()
        row.label(text="LDraw Directory Path:")
        row = layout.row()
        row.scale_y = 1.2
        row.prop(self, "ldraw_path")
        row = layout.row()
        row.prop(self, "unofficial_parts")

        row = layout.row()
        row.label(text="Additional Library Paths:")

        row = layout.row()
        row.scale_y = 1.2
        row.prop(context.scene, "ldr_path_to_add")
        row = layout.row()
        row.operator("additional_paths.new_item", text="Add Path")
        row = layout.row()
        col = row.column()

        for path in ImportOperator.preferences.additional_paths:
            col.label(text="\"" + path + "\"")
        
        row = layout.row()
        row.operator("additional_paths.delete_item", text="Remove Path")

    def execute(self, context):
        # Update from the UI values to support saving them to disk later.
        ImportOperator.preferences.ldraw_path = self.ldraw_path
        ImportOperator.preferences.instance_type = self.instance_type
        ImportOperator.preferences.add_gap_between_parts = self.add_gap_between_parts
        ImportOperator.preferences.unofficial_parts = self.unofficial_parts
        ImportOperator.preferences.ground_object = self.ground_object
        ImportOperator.preferences.resolution = self.resolution
        ImportOperator.preferences.stud_logo = self.stud_logo

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
        )
        end = time.time()
        print(f'Import: {end - start}')

        # Save preferences to disk for loading next time.
        ImportOperator.preferences.save()
        return {'FINISHED'}
