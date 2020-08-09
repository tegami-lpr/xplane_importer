bl_info = {
    "name": "Import: X-Plane OBJ",
    "description": "Importer for X-Plane OBJ8 file.",
    "blender": (2, 82, 0),
    "category": "Import-Export",
    "author": "Tegami",
    "version": (0, 1)
}

if "bpy" in locals():
    import imp
#    if "XPlaneImport" in locals():
    imp.reload(XPlaneImport)
#    if "XPlaneUtils" in locals():
    imp.reload(XPlaneUtils)
    imp.reload(XPObjects)
else:
    import bpy
    from bpy_extras.io_utils import ImportHelper
    from . import XPlaneImport
    from . import XPlaneUtils
    from . import XPObjects

#operators
class ImportXObjFile(bpy.types.Operator, ImportHelper):
    bl_idname = "xplaneimporter.obj"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Import X-Plane OBJ"         # Display name in the interface.
    bl_options = {'UNDO'}  # Enable undo for the operator.
    filename_ext = ".obj"

    filter_glob: bpy.props.StringProperty(
        default="*.obj",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    def execute(self, context):
        if not len(bpy.context.selected_objects) == 0:
            bpy.ops.object.mode_set(mode='OBJECT')

        obj=XPlaneImport.OBJimport(self.filepath)
        resultVal = {'CANCELLED'}
        try:
            obj.doimport()
        except XPlaneImport.ParseError as e:
            if e.type == XPlaneImport.ParseError.HEADER:
                msg='This is not a valid X-Plane v8 OBJ file'
            elif e.type == XPlaneImport.ParseError.PANEL:
                msg='Cannot read cockpit panel texture'
            elif e.type == XPlaneImport.ParseError.NAME:
                msg='Missing dataref or light name at line %s\n' % obj.lineno
            elif e.type == XPlaneImport.ParseError.MISC:
                msg='%s at line %s' % (e.value, obj.lineno)
            else:
                thing=XPlaneImport.ParseError.TEXT[e.type]
                if e.value:
                    msg='Expecting a %s, found "%s" at line %s' % (thing, e.value, obj.lineno)
                else:
                    msg='Missing %s at line %s' % (thing, obj.lineno)
            print("ERROR:\t%s\n" % msg)
        else:
            resultVal = {'FINISHED'}
            self.report({'INFO'}, "Import of X-Plane OBJ finished.")
        obj.file.close()
        
        return resultVal

def menu_function_import(self, context):
    self.layout.operator(ImportXObjFile.bl_idname,
        text="Import X-Plane OBJ (.obj)")


def register():
#    bpy.utils.register_class(OBJimport)
    bpy.utils.register_class(ImportXObjFile)
    bpy.types.TOPBAR_MT_file_import.append(menu_function_import)
#    bpy.utils.register_class(XPlaneUtils)
#    bpy.utils.register_class(ActionOptionPanel)
#    bpy.utils.register_class(EDMMessageBox)
    print("XI: register")

def unregister():
#    bpy.utils.unregister_class(ActionOptionPanel)
#    bpy.utils.unregister_class(EDMObjectPanel)
#    bpy.utils.unregister_class(XPlaneUtils)
    bpy.utils.unregister_class(ImportXObjFile)
#    bpy.utils.unregister_class(OBJimport)
    print("XI: unregister")



# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()
