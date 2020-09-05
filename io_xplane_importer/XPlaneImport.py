# ------------------------------------------------------------------------
# X-Plane importer for blender 2.82 and XPlane2Blender 4.0
# Based on XPlaneImport from XPlane2Blender 3.10 by Jonathan Harris

# This software is licensed under a Creative Commons License
#   Attribution-Noncommercial-Share Alike 3.0
#   http://creativecommons.org/licenses/by-nc-sa/3.0/

import sys
import bpy
import mathutils
# import bmesh
from .XPlaneUtils import Vertex, UV, Face, PanelRegionHandler, getDatarefs, CurrentRotate, CurrentTranslate
from .XPObjects import XPObject, XPMesh, XPAnimation, XPRootObject

from math import radians
from os import listdir
from os.path import abspath, basename, curdir, dirname, join, normpath, sep, splitdrive, splitext, split, exists


# import time

# ------------------------------------------------------------------------
# -- ParseError --
# ------------------------------------------------------------------------

class ParseError(Exception):
    def __init__(self, type, value=""):
        self.type = type
        self.value = value

    HEADER = 0
    TOKEN = 1
    INTEGER = 2
    FLOAT = 3
    NAME = 4
    MISC = 5
    PANEL = 6
    TEXT = ["Header", "Command", "Integer", "Number", "Name", "Misc", "Panel"]


# ------------------------------------------------------------------------
# -- Mat --
# ------------------------------------------------------------------------

class Mat:
    def __init__(self, objimport, e=[0, 0, 0], s=0):
        self.e = e
        self.s = s
        self.blenderMat = None
        self.objimport = objimport

    def equals(self, other):
        return (self.e == other.e and self.s == other.s)

    def clone(self):
        return Mat(self.objimport, self.e, self.s)

    def getBlenderMat(self, force=False):
        if not self.blenderMat and (force or self.e != [0, 0, 0] or self.s):
            self.blenderMat = bpy.data.materials.new(
                basename(self.objimport.filename))

            self.blenderMat.use_nodes = True
            bsdf = self.blenderMat.node_tree.nodes[bpy.app.translations.pgettext(
                'Principled BSDF')]

            if self.objimport.image:
                texImage = self.blenderMat.node_tree.nodes.new(
                    'ShaderNodeTexImage')
                texImage.image = self.objimport.image
                self.blenderMat.node_tree.links.new(
                    bsdf.inputs['Base Color'], texImage.outputs['Color'])

            if self.objimport.normalTexName:
                normalImage = self.blenderMat.node_tree.nodes.new(
                    'ShaderNodeTexImage')
                normalImage.image = self.objimport.normalTex

                normalMap = self.blenderMat.node_tree.nodes.new(
                    'ShaderNodeNormalMap')
                self.blenderMat.node_tree.links.new(
                    normalMap.inputs['Color'], normalImage.outputs['Color'])

                self.blenderMat.node_tree.links.new(
                    bsdf.inputs['Normal'], normalMap.outputs['Normal'])

            '''
            #TODO: need fix Material params
            self.blenderMat.mirCol=self.e
            if self.e==[0,0,0]:
                self.blenderMat.emit=0
            else:
                self.blenderMat.emit=1
            '''
            self.blenderMat.specular_intensity = self.s
        return self.blenderMat


# ------------------------------------------------------------------------
# -- OBJimport --
# ------------------------------------------------------------------------
class OBJimport:
    LAYER = [0, 1, 2, 4]

    # ------------------------------------------------------------------------
    def __init__(self, filename, subroutine=None):

        # Check if Xplane2Blender is installed
        self.hasXplane2Blender = False

        try:
            print("We have XPlane2Blender version {}".format(
                bpy.context.scene.xplane.xplane2blender_ver_history[-1].addon_version_clean_str()))
            addon_ver = bpy.context.scene.xplane.xplane2blender_ver_history[-1].addon_version
            if addon_ver[0] == 4 and addon_ver[1] == 0:
                print("Mark it as compatible")
                self.hasXplane2Blender = True
        except:
            pass

        # Merging rules:
        # self.merge=1 - v7: merge if primitives have same flags
        #                v8: every TRIS statement is a new object
        # self.merge=2 - merge all triangles into one object
        # self.merge = 1

        # verbose - level of verbosity in console: 1-normal,2-chat,3-debug
        self.verbose = 2

        # self.meshname = 'Mesh'
        self.globalmatrix = bpy.context.scene.cursor.matrix

        # if filename[0:2] in ['//', '\\\\']:
        #     # relative to .blend file
        #     self.filename = normpath(join(dirname(Blender.Get('filename')),
        #                                   filename[2:]))
        # else:
        #     self.filename = abspath(filename)

        self.filename = abspath(filename)
        # if sep == '\\':
        #     if self.filename[0] in ['/', '\\']:
        #         # Add Windows drive letter
        #         (drive, foo) = splitdrive(Blender.sys.progname)
        #         self.filename = drive.lower()+self.filename
        #     else:
        #         # Lowercase Windows drive lettter
        #         self.filename = filename[0].lower()+self.filename[1:]
        self.filename = filename[0].lower() + self.filename[1:]

        self.linesemi = 0.025
        self.file = None  # file handle
        self.filelen = 0  # for progress reports
        self.line = None  # current input line
        self.lineno = 0  # for error reporting
        self.progress = -1
        self.fileformat = 0  # 6, 7 or 8

        self.panelimage = None
        self.regions = []  # cockpit regions
        self.curmesh = []  # unoutputted meshes
        self.nprim = 0  # Number of X-Plane objects imported
        self.log = []

        # flags controlling import
        self.layer = 0
        self.lod = None  # list of lod limits
        self.fusecount = 0

        # v8 structures
        self.vt = []
        self.vline = []
        self.vlight = []
        self.idx = []

        # attributes
        self.hard = False
        self.deck = None
        self.surface = None
        self.twoside = False
        self.flat = False  # >=7.30 defaults to smoothed
        self.alpha = False
        self.panel = False
        self.curregion = None
        self.poly = False
        self.drawgroup = None
        self.slung = 0
        self.armob = None  # armature Object
        self.arm = None  # Armature
        self.action = None  # armature Action
        self.pendingbone = None  # current bone
        self.off = []  # offset from current bone
        self.bones = []  # Latest children

        self.mat = Mat(objimport=self)
        self.mats = [self.mat]  # Cache of mats to prevent duplicates

        ##########################

        self.image = None  # texture image, if object has texture
        self.imageName = None  # texture image name, if there is one

        self.litTex = None  # Lit texture
        self.litTexName = None  # Lit texture filename

        self.normalTex = None  # NormalMap texture
        self.normalTexName = None  # NormalMap texture filename

        self.xpRootObject = XPRootObject(self)  # Root object for imported objects
        self.animationChain = []  # List of ANIM parents

        self.defaultMat = Mat(objimport=self)  # Material by default
        self.materialsList = [self.defaultMat]  # Cache of mats to prevent duplicates

        self.animParamStack = []  # Stack of anim params for mesh
        #self.meshAnimParams = []  # List of current params

        self.emptyCount = 0  # Count of empty objects for animations
        self.animationCount = 0  # Count of animation objects
        self.meshCount = 0  # Count of mesh objects

        self.currentrot = None  # current rotate_key axis, key and angles
        self.currenttrans = None  # current trans_key, key and postions

    # ------------------------------------------------------------------------

    def info(self, message):
        if self.verbose > 0:
            print("INFO: {}".format(message))

    # ------------------------------------------------------------------------

    def _creatingBlenderObjects(self):
        self.info("----------------------------------------------")
        self.info("Starting creation object from imported data...")

        if self.verbose > 1:
            self.xpRootObject.printLadder(0)

        self.xpRootObject.doImport(None)

    # ------------------------------------------------------------------------
    def doimport(self):
        # clock=time.clock()	# Processor time
        self.info("Starting OBJ reading from " + self.filename)

        self.file = open(self.filename, 'rU')
        self.file.seek(0, 2)
        self.filelen = self.file.tell()
        self.file.seek(0)
        bpy.context.window_manager.progress_begin(0, 1)
        self._readHeader()
        scene = bpy.context.scene
        try:
            self._readObjects(scene)
            self._creatingBlenderObjects()
            bpy.context.scene.frame_set(1)
        finally:
            bpy.context.window_manager.progress_end()

        if self.verbose:
            print("Finished - imported %s primitives\n" % self.nprim)
            if not self.log:
                self.log = ['OK']

    #            Draw.PupMenu(("Imported %s primitives%%t|" % self.nprim)+'|'.join(self.log))

    # ------------ Helper functions -------------------------------------------

    def _getCR(self, optional=False):
        while True:
            line = self.file.readline()
            self.lineno += 1
            if not line:
                if optional:
                    return False
                else:
                    raise ParseError(ParseError.MISC, 'Unexpected <EOF>')
            self.line = line.split('#')[0].split('//')[0].split()
            if self.line:
                if self.verbose > 2:
                    print('Input:\t%s' % self.line)
                return True
            elif line.startswith('####_'):
                # check for special comments
                self.line = [line.strip()]
                if self.verbose > 2:
                    print('Input:\t%s' % self.line)
                return True
            elif not optional:
                raise ParseError(ParseError.MISC, 'Unexpected <EOL>')

    # ------------------------------------------------------------------------
    def _getInput(self, optional=False):
        try:
            return self.line.pop(0)
        except IndexError:
            if optional:
                return None
            else:
                raise ParseError(ParseError.MISC, "getInput: IndexError")

    # ------------------------------------------------------------------------
    def _getVertex(self):
        v = [self._getFloat() for i in range(3)]
        # Rotate to Blender format
        return Vertex(round(v[0], Vertex.ROUND),
                      round(-v[2], Vertex.ROUND),
                      round(v[1], Vertex.ROUND))

    # ------------------------------------------------------------------------
    def _getUV(self):
        u = self._getFloat()
        v = self._getFloat()
        return UV(u, v)

    # ------------------------------------------------------------------------
    def _getFloat(self, optional=False):
        try:
            return float(self.line.pop(0))
        except IndexError as e:
            if optional:
                return 0
            raise ParseError(ParseError.FLOAT, str(e))
        except ValueError as e:
            if optional:
                return 0
            raise ParseError(ParseError.FLOAT, str(e))

    # ------------------------------------------------------------------------
    def _getInt(self):
        try:
            return int(self.line.pop(0))
        except IndexError as e:
            raise ParseError(ParseError.INTEGER, str(e))
        except ValueError as e:
            raise ParseError(ParseError.INTEGER, str(e))

    # ------------------------------------------------------------------------
    def _getCol(self):
        if self.fileformat < 8:
            return [self._getFloat() / 10.0 for i in range(3)]
        else:
            return [self._getFloat() for i in range(3)]

    # ------------------------------------------------------------------------

    def _addXPObject(self, xpObject):
        if len(self.animationChain):
            parent = self.animationChain[-1]
        else:
            parent = self.xpRootObject

        parent.addChild(xpObject)

        # if xpObject.type == "Animation":
        #     self.parentChain.append(xpObject)

        # if parent.type == "Animation":
        #     if len(parent.children):
        #         if parent.children[-1].type ==
        #     self.parentChain.append(xpObject)

    # ------------------------------------------------------------------------

    def _createMesh(self, t, a, b):
        objdef = (t, a, b)

        if t.find("Empty") >= 0:
            name = t
        else:
            name = "Mesh_{}".format(self.meshCount)
            self.meshCount += 1

        mesh = XPMesh(name, objdef, self)
        # Adding params to mesh
        if len(self.animParamStack):
            for param in self.animParamStack[-1]:
                mesh.addParam(param)
            self.animParamStack[-1] = []

        return mesh

    # ------------------------------------------------------------------------
    def _createAnimGroup(self):

        mesh = None

        if len(self.animationChain):
            if len(self.animationChain[-1].children) == 0:
                if self.verbose > 1:
                    print("Prev Animation w/o mesh. Creating Empty object for it.")
                mesh = self._createMesh("Empty_{}".format(self.emptyCount), 0, 0)
                self.emptyCount += 1
                self._addXPObject(mesh)
            else:
                mesh = self.animationChain[-1].children[-1]

        xpAnim = XPAnimation("Animation_{}".format(self.animationCount))
        self.animationCount += 1
        if mesh is None:
            self._addXPObject(xpAnim)
        else:
            mesh.addChild(xpAnim)

        self.animationChain.append(xpAnim)

        if self.verbose > 1:
            print('Append animation group. Chain len={}'.format(len(self.animationChain)))

    # ------------------------------------------------------------------------
    def _closeAnimGroup(self):
        del self.animationChain[-1]

        if self.verbose > 1:
            print('Remove animation group. Chain len={}'.format(len(self.animationChain)))

    # ------------ Reading header of OBJ file ---------------------------------
    def _readHeader(self):
        c = self.file.readline().strip()
        if self.verbose > 2:
            print('Input:\t"%s"' % c)
        if not c in ['A', 'I']:
            raise ParseError(ParseError.HEADER)

        c = self.file.readline().split()
        self.lineno = 2
        if not c:
            raise ParseError(ParseError.HEADER)
        if self.verbose > 2:
            print('Input:\t"%s"' % c[0])
        if c[0] == "800":
            if self.file.readline().split('#')[0].split('//')[0].split()[0] != "OBJ":
                raise ParseError(ParseError.HEADER)
            self.fileformat = 8
            self.lineno = 3
            if self.verbose > 1:
                print("Info:\tThis is an X-Plane v8 format file")
        else:
            raise ParseError(ParseError.HEADER)

    # ------------ Reading objects --------------------------------------------
    def _readObjects(self, scene):
        while True:
            pos = self.file.tell()
            progress = pos * 50 / self.filelen
            # only update progress bar if need to
            if self.progress != progress:
                bpy.context.window_manager.progress_update(float(pos) * 0.5 / self.filelen)
                self.progress = progress

            if not self._getCR(True):
                break

            t = self.line.pop(0)
            if t in ['end', 99]:
                break

            elif t in ['TEXTURE', 'TEXTURE_LIT', 'TEXTURE_NORMAL']:
                # TODO: check if that _cockpit object, then TEXTURE has predefined filename Panel.png
                texName = self._getInput(optional=True)
                if texName:
                    tmpImage = None
                    print('Info:\tLoading texture file "%s"' % texName)
                    fullTexPath = normpath(dirname(self.filename) + '/' + texName)
                    try:
                        tmpImage = bpy.context.blend_data.images.load(
                            fullTexPath, check_existing=True)
                    except:
                        print('WARN:\tCannot read texture file "%s"' % texName)
                        self.log.append(
                            'Cannot read texture file "%s"' % texName)
                    else:
                        if t == "TEXTURE":
                            if tmpImage is None:
                                print('CRIT:\tTexture file must exists.')
                                raise ParseError(ParseError.HEADER)

                            self.image = tmpImage
                            self.imageName = texName
                        if t == "TEXTURE_LIT":
                            self.litTex = tmpImage
                            self.litTexName = texName
                        if t == "TEXTURE_NORMAL":
                            self.normalTex = tmpImage
                            self.normalTexName = texName
                else:
                    print("Info:\tNo texture defined for " + t)

            elif t == 'VT':
                v = self._getVertex()
                n = self._getVertex()  # normal
                uv = self._getUV()
                self.vt.append((v, uv, n))

            elif t == 'VLINE':
                v = self._getVertex()
                c = self._getCol()
                self.vline.append((v, c))

            elif t == 'IDX10':
                self.idx.extend([self._getInt() for i in range(10)])

            elif t == 'IDX':
                self.idx.append(self._getInt())

            elif t == 'TRIS':
                a = self._getInt()
                b = self._getInt()
                mesh = self._createMesh(t, a, b)
                self._addXPObject(mesh)

            elif t == 'ANIM_begin':
                self._createAnimGroup()
                self.animParamStack.append([])
                pass

            elif t == 'ANIM_end':
                # Clear params list
                del self.animParamStack[-1]
                #self.meshAnimParams.clear()

                self._closeAnimGroup()
                pass

            elif t == 'ANIM_trans':
                p1 = self._getVertex()
                p2 = self._getVertex()
                v1 = self._getFloat(optional=True)
                v2 = self._getFloat(optional=True)
                datarefName = self._getInput(optional=True)

                # Adding trans params to the list:
                # [0] - param name (ANIM_trans)
                # [1] - List of positions
                # [2] - List of values
                # [4] - DataRef name
                self.animParamStack[-1].append([t, [p1, p2], [v1, v2], datarefName])
                #self.meshAnimParams.append([t, [p1, p2], [v1, v2], datarefName])

            elif t == 'ANIM_rotate':
                p = self._getVertex()
                r1 = self._getFloat()  # start angle
                r2 = self._getFloat()  # stop angle
                v1 = self._getFloat(optional=True)  # start value
                v2 = self._getFloat(optional=True)  # stop value
                datarefName = self._getInput(optional=True)

                while r2 >= 360 or r2 <= -360:
                    # hack from old code
                    r2 /= 2
                    v2 /= 2

                m1 = mathutils.Matrix.Rotation(radians(r1), 4, p.toVector(3))
                m2 = mathutils.Matrix.Rotation(radians(r2), 4, p.toVector(3))
                # print(m1)
                # print(m2)
                # self.animParamStack[-1].append([t, [m1, m2], [v1, v2], datarefName])
                self.animParamStack[-1].append([t, p.toVector(3), [radians(r1), radians(r2)], [v1, v2], datarefName])


            elif t == 'ANIM_rotate_begin':
                p = self._getVertex()
                datarefName = self._getInput()
                self.currentrot = CurrentRotate(p, datarefName)
                print('DEBUG:\t Found ANIM_rotate_begin for dref {}.'.format(datarefName))

            elif t == 'ANIM_rotate_key':
                v = self._getFloat()
                r = self._getFloat()
                self.currentrot.addKey(v, radians(r))

            elif t == 'ANIM_rotate_end':
                print('DEBUG:\t Found ANIM_rotate_end for dref {}.'.format(self.currentrot.dataRef))
                self.animParamStack[-1].append(self.currentrot.toMeshParam())
                #self.meshAnimParams.append(self.currentrot.toMeshParam())
                self.currentrot = None

            elif t == 'ANIM_trans_begin':
                datarefName = self._getInput()
                self.currenttrans = CurrentTranslate(datarefName)
                print('DEBUG:\t Found ANIM_trans_begin for dref {}.'.format(datarefName))

            elif t == 'ANIM_trans_key':
                v = self._getFloat()  # Value
                p = self._getVertex()  # Position
                self.currenttrans.addKey(v, p)

            elif t == 'ANIM_trans_end':
                print('DEBUG:\t Found ANIM_trans_end for dref {}.'.format(self.currenttrans.dataRef))
                self.animParamStack[-1].append(self.currenttrans.toMeshParam())
                #self.meshAnimParams.append(self.currenttrans.toMeshParam())
                self.currenttrans = None


            else:
                if self.verbose > 1:
                    print('WARNING: Unrecognised Command "%s"' % t)

            pass
        # end of while

        pass
