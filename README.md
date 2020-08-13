
## Introduction

This is plugin for Blender 2.82+. This plugin allow to import
X-Plane objects in OBJ8 format include animation.

Based on import part of XPlane2Blender v3.10 by Jonathan Harris

## Installing

Just as any Blender plugin.

## Gotchas and Limitations
First of all, this plugin is not covered all aspects of OBJ8 format.
It's really not possible to cover all cases and combination that produced by export plugins.
OBJ8 is not strictly format w/o good docs and exporters sometime add additional chaos to
output file.

This plugin was written to import a specific object and does not pretend to be universal tool.

What this plugin can do:
- Import static geometry.
- Import translate and rotate animations.
- Import default texture.
- Can add dref values to mesh if XPlane2Blender 4.0 installed.

What plugin can't do:
- Import normals.
- Handle keyed animations properly. By default plugin just take first and last values.
But you can change handleKeyAnim to True in XPlaneUtils.py to import by keys. But some time Xplane2Blender export keyed animations with errors. 
- Handle ANIM_show and ANIM_hide.
- Handle any material properties.
- Handle lights.
- Handle manipulator properties.

### Warning:
All imported triangles have their own set of dots (faces just separated from each other). And after importing
there necessary select mesh and merge vertices (Mesh->Merge->By Distance).  It will be fixed in future...

## License

This software is licensed under a Creative Commons License Attribution-Noncommercial-Share Alike 3.0
http://creativecommons.org/licenses/by-nc-sa/3.0/
