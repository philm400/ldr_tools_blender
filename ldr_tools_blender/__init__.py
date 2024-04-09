import bpy
from . import operator

bl_info = {
    "name": "ldr_tools_blender",
    "description": "Import LDraw models in .mpd .ldr, and .dat formats",
    "author": "Philm400 (forked from ScanMountGoat)",
    "version": (0, 3, 2),
    "blender": (4, 0, 0),
    "location": "File > Import",
    "warning": "",
    "category": "Import-Export"
}

def menuImport(self, context):
    self.layout.operator(operator.ImportOperator.bl_idname,
                         text="LDraw (.mpd/.ldr/.dat)")


classes = [operator.ImportOperator,
           operator.GEOMETRY_OPTIONS_PT_Panel,
           operator.PARTS_OPTIONS_PT_Panel,
           operator.PARTS_SUB_OPTIONS_PT_Panel,
           operator.LDRAW_PATH_LIST_ITEM,
           operator.LDRAW_PATH_UL_List,
           operator.LDRAW_PATH_LIST_OT_NewItem,
           operator.LDRAW_PATH_LIST_OT_DeleteItem,
           operator.LDRAW_PATH_LIST_OT_MoveItem,
           operator.ENVIRONMENT_OPTIONS_PT_Panel,]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.ldraw_path_list = bpy.props.CollectionProperty(type = operator.LDRAW_PATH_LIST_ITEM)
    bpy.types.Scene.ldraw_path_list_index = bpy.props.IntProperty(name = "Index for ldraw_path_list", default = 0)

    bpy.types.TOPBAR_MT_file_import.append(menuImport)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.ldraw_path_list
    del bpy.types.Scene.ldraw_path_list_index

    bpy.types.TOPBAR_MT_file_import.remove(menuImport)

if __name__ == "__main__":
    register()
 