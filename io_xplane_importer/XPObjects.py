# This software is licensed under a Creative Commons License
#   Attribution-Noncommercial-Share Alike 3.0
#   http://creativecommons.org/licenses/by-nc-sa/3.0/

import bpy
import mathutils
from os.path import basename
from .XPlaneUtils import Vertex, UV, Face, PanelRegionHandler, getDatarefs


def checkDrefName(drefName: str):
    if drefName is None:
        return False
    if drefName.find("/") >= 0:
        return True
    return False


# ------------------------------------------------------------------------
# -- XPObject --
# ------------------------------------------------------------------------

class XPObject(object):
    def __init__(self):
        self.type = 'None'
        self.children = []
        self.child_offset = Vertex(0, 0, 0)

    def addChild(self, child):
        self.children.append(child)

    def doImport(self, parent):
        raise Exception('Call XPObject abstract method')

    def printLadder(self, level):
        print(" " * (level * 2) + self.type)
        for ch in self.children:
            ch.printLadder(level+1)


# ------------------------------------------------------------------------
# -- XPRootObject --
# ------------------------------------------------------------------------

class XPRootObject(XPObject):
    def __init__(self, objImport):
        super().__init__()
        self.type = 'RootObject'
        self.objImport = objImport
        self.blenderObject = None

    def doImport(self, parent):
        # Create root object
        self.blenderObject = bpy.data.objects.new(basename(self.objImport.filename), None)
        self.blenderObject.location = (0, 0, 0)
        self.blenderObject.empty_display_size = 0.45
        self.blenderObject.empty_display_type = 'PLAIN_AXES'
        bpy.context.scene.collection.objects.link(self.blenderObject)

        if self.objImport.hasXplane2Blender:
            self.blenderObject.xplane.isExportableRoot = True
            self.blenderObject.xplane.layer.name = basename(self.objImport.filename)
            if self.objImport.image:
                self.blenderObject.xplane.layer.texture = self.objImport.imageName
            if self.objImport.litTex:
                self.blenderObject.xplane.layer.texture_lit = self.objImport.litTexName
            if self.objImport.normalTex:
                self.blenderObject.xplane.layer.texture_normal = self.objImport.normalTexName

        for ch in self.children:
            ch.doImport(self)

# ------------------------------------------------------------------------
# -- XPAnimation --
# ------------------------------------------------------------------------


class XPAnimation(XPObject):
    def __init__(self, name: str):
        super().__init__()
        self.type = 'Animation'
        self.name = name

    def doImport(self, parent):
        lastMesh = None
        for ch in self.children:
            if ch.type == 'Mesh':
                lastMesh = ch
                ch.doImport(parent)
            elif ch.type == 'Animation':
                ch.doImport(lastMesh)
            else:
                raise Exception('Unknown XPObject type')

    def printLadder(self, level):
        print(" " * (level * 2) + self.name)
        for ch in self.children:
            ch.printLadder(level+1)

# ------------------------------------------------------------------------
# -- XPMesh --
# ------------------------------------------------------------------------


class XPMesh(XPObject):
    def __init__(self, name: str, objdef, objImport):
        super().__init__()
        self.type = 'Mesh'
        self.objImport = objImport  # Link to ObjImport class
        self.blenderObject = None  # Link to created Blender object from our data
        self.faces = []  # Faces defs from OBJ data
        self.params = []  # List of params for this mesh
        self.animParams = []  # List of animation params for object
        self.name = name

        # objdef is array of next params:
        # [0] - name of geometry: TRIS or LINE
        # [1] - offset in global table
        # [2] - count of elements
        self.objdef = objdef

        self.material = objImport.defaultMat

        if objImport.verbose > 0:
            print("Create XPMesh with def: {} and name {}".format(objdef, self.name))

    # ------------------------------------------------------------------------

    def printLadder(self, level):
        print(" " * (level * 2) + "{} - {}".format(self.type, self.objdef, level))
        for ch in self.children:
            ch.printLadder(level+1)

    # ------------------------------------------------------------------------

    def addParam(self, param):
        if param[0] in ('ANIM_trans', 'ANIM_rotate'):
            self.animParams.append(param)
        else:
            self.params.append(param)

    # ------------------------------------------------------------------------

    def _prepareFaces(self):
        self.faces = []
        if self.objdef[0].find("Empty") >= 0:
            return
        for i in range(self.objdef[1], self.objdef[1] + self.objdef[2], 3):
            face = Face()
            # points are reversed
            (vj, uvj, n2) = self.objImport.vt[self.objImport.idx[i + 2]]
            v = [vj.totuple()]
            face.addVertex(vj)
            face.addUV(uvj)
            (vj, uvj, n1) = self.objImport.vt[self.objImport.idx[i + 1]]
            v.append(vj.totuple())
            face.addVertex(vj)
            face.addUV(uvj)
            (vj, uvj, n0) = self.objImport.vt[self.objImport.idx[i]]
            v.append(vj.totuple())
            face.addVertex(vj)
            face.addUV(uvj)

            self.faces.append(face)
        pass

    # ------------------------------------------------------------------------
    def _addDrefValues(self, drefName: str, drefValues):
        # Adding drefs values to animation
        dataref = self.blenderObject.xplane.datarefs.add()
        dataref.path = drefName
        dataref.anim_type = 'transform'
        if "XPlane Datarefs" not in self.blenderObject.animation_data.action.groups:
            self.blenderObject.animation_data.action.groups.new('XPlane Datarefs')
        for (i, value) in enumerate(drefValues):
            dataref.value = value
            dataref.keyframe_insert(
                data_path="value", frame=i + 1, group="XPlane Datarefs")

    # ------------------------------------------------------------------------

    def _createEmptyObject(self, parent):
        ob = bpy.data.objects.new(self.name, None)
        ob.empty_display_size = 0.45
        ob.empty_display_type = 'PLAIN_AXES'
        print("Create empty object: {}, parent type: {}, parent name: {}".format(ob.name, parent.type, parent.blenderObject.name))
        return ob

    # ------------------------------------------------------------------------

    def _createMeshObject(self, parent):
        self.mesh = bpy.data.meshes.new(self.name)
        # print("create mesh: {}".format(meshName))
        self.mesh.use_auto_smooth = True

        # Create Blender object for Mesh
        ob = bpy.data.objects.new(self.name, self.mesh)
        print("Create mesh object: {}, parent: {}".format(ob.name, parent.type))
        return ob

    # ------------------------------------------------------------------------
    def doImport(self, parent):
        self._prepareFaces()

        centre = Vertex(0, 0, 0)
        ob = None
        if len(self.faces):
            ob = self._createMeshObject(parent)
        else:
            ob = self._createEmptyObject(parent)

        if self.objImport.verbose > 0:
            print("Import Mesh {} with def: {}".format(ob.name, self.objdef))

        self.blenderObject = ob

        ob.parent = parent.blenderObject

        # Reset parenting offset
        #ob.matrix_parent_inverse = mathutils.Matrix(ob.parent.matrix_world).inverted()
        # Adding object to current scene
        bpy.context.scene.collection.objects.link(ob)

        ob.location = (parent.child_offset.x, parent.child_offset.y, parent.child_offset.z)

        if len(self.animParams):
            print('Mesh has animation')
            anim_data = ob.animation_data_create()
            anim_data.action = bpy.data.actions.new(name=ob.name)

            hasRotation = False
            off = None

            needPosReFix = False
            reFixDone = False  # Ignore second position fix. 

            for animParam in self.animParams:
                print("Current anim: {}, dref: {}".format(animParam[0], animParam[3]))
                if animParam[0] == 'ANIM_trans':
                    (_, positions, values, drefName) = animParam

                    if not positions[0].equals(positions[1]):
                        for n in range(0, 3):
                            fcu_z = anim_data.action.fcurves.new(data_path="location", index=n)
                            fcu_z.keyframe_points.add(len(positions))
                            for i in range(len(positions)):
                                fcu_z.keyframe_points[i].co = i + 1, positions[i].toVector(3)[n] + ob.location[n]
                        if checkDrefName(drefName):
                            self._addDrefValues(drefName, values)
                    else:
                        # Some time AC3D create dummy translate animation to move object to right place

                        if needPosReFix == False:
                            if reFixDone == False:
                                # Fix for object position by dummy ANIM_trans
                                off = positions[0]
                                ob.location = (off.x + ob.location[0], off.y + ob.location[1], off.z + ob.location[2])
                                print("Fix object position to {}".format(off))
                                self.child_offset = Vertex(-off.x, -off.y, -off.z)
                                needPosReFix = True

                        else:
                            if reFixDone == False:
                                #centre = Vertex(positions[1].x, positions[1].y, positions[1].z)
                                centre = off
                                needPosReFix = False
                                reFixDone = True

                elif animParam[0] == 'ANIM_rotate':
                    if hasRotation:
                        # TODO: fix many rotate animations
                        continue
                    hasRotation = True
                    # (_, matrix, values, drefName) = animParam
                    # for n in range(0, 4):
                    #     fcu_z = anim_data.action.fcurves.new(data_path="rotation_quaternion", index=n)
                    #     fcu_z.keyframe_points.add(len(matrix))
                    #     for i in range(len(matrix)):
                    #         fcu_z.keyframe_points[i].co = i + 1, matrix[i].to_quaternion()[n]
                    # self._addDrefValues(drefName, values)

                    # for n in range(0, 3):
                    #     fcu_z = ob.animation_data.action.fcurves.new(data_path="rotation_euler", index=n)
                    #     fcu_z.keyframe_points.add(len(matrix))
                    #     for i in range(len(matrix)):
                    #         fcu_z.keyframe_points[i].co = i + 1, matrix[i].to_euler()[n]

                    (_, p, matrix, values, drefName) = animParam
                    ob.rotation_mode = "AXIS_ANGLE"
                    for n in range(0, 4):
                        fcu_z = ob.animation_data.action.fcurves.new(data_path="rotation_axis_angle", index=n)
                        fcu_z.keyframe_points.add(len(matrix))
                        for i in range(len(matrix)):
                            if n == 0:
                                fcu_z.keyframe_points[i].co = i + 1, matrix[i]  # W - value
                            else:
                                fcu_z.keyframe_points[i].co = i + 1, p[n-1]

                    if checkDrefName(drefName):
                        self._addDrefValues(drefName, values)

        if len(self.faces):
            _faces = []
            _verts = []
            for f in self.faces:
                face = []
                for v in f.v:
                    face.append(len(_verts))
                    if centre.x == 0:
                        pass
                    _verts.append([v.x - centre.x, v.y - centre.y, v.z - centre.z])
                _faces.append(face)

            # Adding varticles and faces to mesh
            self.mesh.from_pydata(_verts, [], _faces)
            # Validate mesh after data assigment
            self.mesh.validate()

            # Adding UV map for mesh
            self.mesh.uv_layers.new(name="UVMap", do_init=False)
            uvs = []
            for face in self.faces:
                for uv in face.uv:
                    uvs.append((uv.s, uv.t))

            i = 0
            for uvdata in self.mesh.uv_layers.active.data:
                uvdata.uv = uvs[i]
                i += 1

            # Adding material for Mesh
            self.mesh.materials.append(self.material.getBlenderMat(True))

            self.mesh.calc_normals()
            self.mesh.update(calc_edges=True)

        for ch in self.children:
            ch.doImport(self)

        pass
