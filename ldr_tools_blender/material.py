from typing import Callable

from .ldr_tools_py import LDrawColor
from .colors import rgb_peeron_by_code, rgb_ldr_tools_by_code

import bpy

# Materials are based on the techniques described in the following blog posts.
# This covers how to create lego shaders with realistic surface detailing.
# https://stefanmuller.com/exploring-lego-material-part-1/
# https://stefanmuller.com/exploring-lego-material-part-2/
# https://stefanmuller.com/exploring-lego-material-part-3/


def get_material(color_by_code: dict[int, LDrawColor], code: int, is_slope: bool) -> bpy.types.Material:
    # Cache materials by name.
    # This loads materials lazily to avoid creating unused colors.
    ldraw_color = color_by_code.get(code)

    name = str(code)
    if ldraw_color is not None:
        name = f'{code} {ldraw_color.name}'
        if is_slope:
            name += ' slope'

    material = bpy.data.materials.get(name)

    # TODO: Report warnings if a part contains an invalid color code.
    if material is None:
        material = bpy.data.materials.new(name)
        material.use_nodes = True

        # TODO: Error if color is missing?
        if ldraw_color is not None:
            bsdf = material.node_tree.nodes["Principled BSDF"]

            # Alpha is specified using transmission instead.
            r, g, b, a = ldraw_color.rgba_linear

            # Set the color in the viewport.
            # This can use the default LDraw color for familiarity.
            material.diffuse_color = [r, g, b, a]

            # Partially complete alternatives to LDraw colors for better realism.
            if code in rgb_ldr_tools_by_code:
                r, g, b = rgb_ldr_tools_by_code[code]
            elif code in rgb_peeron_by_code:
                r, g, b = rgb_peeron_by_code[code]

            bsdf.inputs['Base Color'].default_value = [r, g, b, 1.0]

            # Transparent colors specify an alpha of 128 / 255.
            is_transmissive = a <= 0.6

            # RANDOM_WALK is more accurate but has discoloration around thin corners.
            # TODO: This is in Blender units and should depend on scene scale
            bsdf.subsurface_method = 'BURLEY'
            # Use a less accurate SSS method instead.
            bsdf.inputs['Subsurface Radius'].default_value = [r, g, b]
            bsdf.inputs['Subsurface Weight'].default_value = 1.0
            bsdf.inputs['Subsurface Scale'].default_value = 0.025

            # Procedural roughness.
            roughness_node = create_node_group(
                material, 'ldr_tools_roughness', create_roughness_node_group)

            material.node_tree.links.new(
                roughness_node.outputs['Roughness'], bsdf.inputs['Roughness'])

            # Normal opaque materials.
            roughness_node.inputs['Min'].default_value = 0.075
            roughness_node.inputs['Max'].default_value = 0.2

            # TODO: Have a case for each finish type?
            if ldraw_color.finish_name == 'MatteMetallic':
                bsdf.inputs['Metallic'].default_value = 1.0
            if ldraw_color.finish_name == 'Chrome':
                # Glossy metal coating.
                bsdf.inputs['Metallic'].default_value = 1.0
                roughness_node.inputs['Min'].default_value = 0.075
                roughness_node.inputs['Max'].default_value = 0.1
            if ldraw_color.finish_name == 'Metal':
                # Rougher metals.
                bsdf.inputs['Metallic'].default_value = 1.0
                roughness_node.inputs['Min'].default_value = 0.15
                roughness_node.inputs['Max'].default_value = 0.3
            elif ldraw_color.finish_name == 'Pearlescent':
                bsdf.inputs['Metallic'].default_value = 0.35
                roughness_node.inputs['Min'].default_value = 0.3
                roughness_node.inputs['Max'].default_value = 0.5
            elif ldraw_color.finish_name == 'Speckle':
                # TODO: Are all speckled colors metals?
                bsdf.inputs['Metallic'].default_value = 1.0

                speckle_node = create_node_group(
                    material, 'ldr_tools_speckle', create_speckle_node_group)

                # Adjust the thresholds to control speckle size and density.
                speckle_node.inputs['Min'].default_value = 0.5
                speckle_node.inputs['Max'].default_value = 0.6

                # Blend between the two speckle colors.
                mix_rgb = material.node_tree.nodes.new('ShaderNodeMixRGB')

                material.node_tree.links.new(
                    speckle_node.outputs['Fac'], mix_rgb.inputs['Fac'])
                mix_rgb.inputs[1].default_value = [r, g, b, 1.0]
                speckle_r, speckle_g, speckle_b, _ = ldraw_color.speckle_rgba_linear
                mix_rgb.inputs[2].default_value = [
                    speckle_r, speckle_g, speckle_b, 1.0]

                material.node_tree.links.new(
                    mix_rgb.outputs['Color'], bsdf.inputs['Base Color'])

            if is_transmissive:
                bsdf.inputs['Transmission Weight'].default_value = 1.0
                bsdf.inputs['IOR'].default_value = 1.55

                if ldraw_color.finish_name == 'Rubber':
                    # Make the transparent rubber appear cloudy.
                    roughness_node.inputs['Min'].default_value = 0.1
                    roughness_node.inputs['Max'].default_value = 0.35
                else:
                    roughness_node.inputs['Min'].default_value = 0.01
                    roughness_node.inputs['Max'].default_value = 0.15

                # Disable shadow casting for transparent materials.
                # This avoids making transparent parts too dark.
                make_shadows_transparent(material, bsdf)

            # Procedural normals.
            normals = create_node_group(
                material, 'ldr_tools_normal', create_normals_node_group)

            if is_slope:
                # Apply grainy normals to faces that aren't vertical or horizontal.
                # Use non transformed normals to not consider object rotation.
                ldr_normals = material.node_tree.nodes.new(
                    'ShaderNodeAttribute')
                ldr_normals.attribute_name = 'ldr_normals'

                separate = material.node_tree.nodes.new(
                    'ShaderNodeSeparateXYZ')
                material.node_tree.links.new(
                    ldr_normals.outputs['Vector'], separate.inputs['Vector'])

                # Use normal.y to check if the face is horizontal (-1.0 or 1.0) or vertical (0.0).
                # Any values in between are considered "slopes" and use grainy normals.
                absolute = material.node_tree.nodes.new('ShaderNodeMath')
                absolute.operation = 'ABSOLUTE'
                material.node_tree.links.new(
                    separate.outputs['Y'], absolute.inputs['Value'])

                compare = material.node_tree.nodes.new('ShaderNodeMath')
                compare.operation = 'COMPARE'
                compare.inputs[1].default_value = 0.5
                compare.inputs[2].default_value = 0.45
                material.node_tree.links.new(
                    absolute.outputs['Value'], compare.inputs['Value'])

                slope_normals = create_node_group(
                    material, 'ldr_tools_slope_normal', create_slope_normals_node_group)

                is_stud = material.node_tree.nodes.new('ShaderNodeAttribute')
                is_stud.attribute_name = 'ldr_is_stud'

                # Don't apply the grainy slopes to any faces marked as studs.
                # We use an attribute here to avoid per face material assignment.
                subtract_studs = material.node_tree.nodes.new('ShaderNodeMath')
                subtract_studs.operation = 'SUBTRACT'
                material.node_tree.links.new(
                    compare.outputs['Value'], subtract_studs.inputs[0])
                material.node_tree.links.new(
                    is_stud.outputs[2], subtract_studs.inputs[1])

                # Choose between grainy and smooth normals depending on the face.
                mix_normals = material.node_tree.nodes.new('ShaderNodeMix')
                mix_normals.data_type = 'VECTOR'
                material.node_tree.links.new(
                    subtract_studs.outputs['Value'], mix_normals.inputs['Factor'])
                material.node_tree.links.new(
                    normals.outputs['Normal'], mix_normals.inputs[4])
                material.node_tree.links.new(
                    slope_normals.outputs['Normal'], mix_normals.inputs[5])

                # The second output is the vector output.
                material.node_tree.links.new(
                    mix_normals.outputs[1], bsdf.inputs['Normal'])
            else:
                material.node_tree.links.new(
                    normals.outputs['Normal'], bsdf.inputs['Normal'])

    return material


def create_node_group(material: bpy.types.Material, name: str, create_group: Callable[[str], bpy.types.NodeTree]):
    node_tree = bpy.data.node_groups.get(name)
    if node_tree is None:
        node_tree = create_group(name)

    node = material.node_tree.nodes.new(type='ShaderNodeGroup')
    node.node_tree = node_tree
    return node


def make_shadows_transparent(material, bsdf):
    mix_shader = material.node_tree.nodes.new('ShaderNodeMixShader')
    light_path = material.node_tree.nodes.new('ShaderNodeLightPath')
    transparent_bsdf = material.node_tree.nodes.new(
        'ShaderNodeBsdfTransparent')
    output_node = material.node_tree.nodes.get('Material Output')

    material.node_tree.links.new(
        light_path.outputs['Is Shadow Ray'], mix_shader.inputs['Fac'])
    material.node_tree.links.new(
        bsdf.outputs['BSDF'], mix_shader.inputs[1])
    material.node_tree.links.new(
        transparent_bsdf.outputs['BSDF'], mix_shader.inputs[2])

    material.node_tree.links.new(
        mix_shader.outputs['Shader'], output_node.inputs['Surface'])


def create_roughness_node_group(name: str) -> bpy.types.NodeTree:
    node_group_node_tree = bpy.data.node_groups.new(
        name, 'ShaderNodeTree')

    node_group_node_tree.interface.new_socket(
        in_out='OUTPUT', socket_type='NodeSocketFloat', name='Roughness')

    inner_nodes = node_group_node_tree.nodes
    inner_links = node_group_node_tree.links

    input_node = inner_nodes.new('NodeGroupInput')
    node_group_node_tree.interface.new_socket(
        in_out='INPUT', socket_type='NodeSocketFloat', name='Min')
    node_group_node_tree.interface.new_socket(
        in_out='INPUT', socket_type='NodeSocketFloat', name='Max')

    # TODO: Create frame called "smudges" or at least name the nodes.
    noise = inner_nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 4.0
    noise.inputs['Detail'].default_value = 2.0
    noise.inputs['Roughness'].default_value = 0.5
    noise.inputs['Distortion'].default_value = 0.0

    # Easier to configure than a color ramp since the input is 1D.
    map_range = inner_nodes.new('ShaderNodeMapRange')
    inner_links.new(noise.outputs['Fac'], map_range.inputs['Value'])
    inner_links.new(input_node.outputs['Min'], map_range.inputs['To Min'])
    inner_links.new(input_node.outputs['Max'], map_range.inputs['To Max'])

    output_node = inner_nodes.new('NodeGroupOutput')

    inner_links.new(map_range.outputs['Result'],
                    output_node.inputs['Roughness'])

    return node_group_node_tree


def create_speckle_node_group(name: str) -> bpy.types.NodeTree:
    node_group_node_tree = bpy.data.node_groups.new(
        name, 'ShaderNodeTree')

    node_group_node_tree.interface.new_socket(
        in_out='OUTPUT', socket_type='NodeSocketFloat', name='Fac')

    inner_nodes = node_group_node_tree.nodes
    inner_links = node_group_node_tree.links

    input_node = inner_nodes.new('NodeGroupInput')
    node_group_node_tree.interface.new_socket(
        in_out='INPUT', socket_type='NodeSocketFloat', name='Min')
    node_group_node_tree.interface.new_socket(
        in_out='INPUT', socket_type='NodeSocketFloat', name='Max')

    noise = inner_nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 15.0
    noise.inputs['Detail'].default_value = 6.0
    noise.inputs['Roughness'].default_value = 1.0
    noise.inputs['Distortion'].default_value = 0.0

    # Easier to configure than a color ramp since the input is 1D.
    map_range = inner_nodes.new('ShaderNodeMapRange')
    inner_links.new(noise.outputs['Fac'], map_range.inputs['Value'])
    inner_links.new(input_node.outputs['Min'], map_range.inputs['From Min'])
    inner_links.new(input_node.outputs['Max'], map_range.inputs['From Max'])

    output_node = inner_nodes.new('NodeGroupOutput')

    inner_links.new(map_range.outputs['Result'], output_node.inputs['Fac'])

    return node_group_node_tree


def create_normals_node_group(name: str) -> bpy.types.NodeTree:
    node_group_node_tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')

    node_group_node_tree.interface.new_socket(
        in_out='OUTPUT', socket_type='NodeSocketVector', name='Normal')

    nodes = node_group_node_tree.nodes
    links = node_group_node_tree.links

    output_node = nodes.new('NodeGroupOutput')

    bevel = nodes.new('ShaderNodeBevel')
    bevel.inputs['Radius'].default_value = 0.01

    # TODO: Set node positions.
    # Faces of bricks are never perfectly flat.
    # Create a very low frequency noise to break up highlights
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 0.01  # TODO: scene scale?
    noise.inputs['Detail'].default_value = 1.0
    noise.inputs['Roughness'].default_value = 1.0
    noise.inputs['Distortion'].default_value = 0.0

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = 0.01

    tex_coord = nodes.new('ShaderNodeTexCoord')
    
    links.new(bevel.outputs['Normal'], bump.inputs['Normal'])

    links.new(tex_coord.outputs['Object'],
              noise.inputs['Vector'])
    links.new(
        noise.outputs['Fac'], bump.inputs['Height'])
    links.new(
        bump.outputs['Normal'], output_node.inputs['Normal'])

    return node_group_node_tree


def create_slope_normals_node_group(name: str) -> bpy.types.NodeTree:
    node_group_node_tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')

    node_group_node_tree.interface.new_socket(
        in_out='OUTPUT', socket_type='NodeSocketVector', name='Normal')

    nodes = node_group_node_tree.nodes
    links = node_group_node_tree.links

    output_node = nodes.new('NodeGroupOutput')

    bevel = nodes.new('ShaderNodeBevel')
    bevel.inputs['Radius'].default_value = 0.01

    # TODO: Set node positions.
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 125.0
    noise.inputs['Detail'].default_value = 3.0
    noise.inputs['Roughness'].default_value = 0.5
    noise.inputs['Lacunarity'].default_value = 2.0

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.5
    bump.inputs['Distance'].default_value = 0.005

    tex_coord = nodes.new('ShaderNodeTexCoord')

    links.new(bevel.outputs['Normal'], bump.inputs['Normal'])

    links.new(tex_coord.outputs['Object'],
              noise.inputs['Vector'])
    links.new(
        noise.outputs['Fac'], bump.inputs['Height'])
    links.new(
        bump.outputs['Normal'], output_node.inputs['Normal'])

    return node_group_node_tree
