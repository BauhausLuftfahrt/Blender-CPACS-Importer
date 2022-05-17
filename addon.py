"""
    Created by Marc Engelmann
    Date: 08.07.2019
    © Bauhaus Luftfahrt e.V.

    (c) 2019 - 2021 Bauhaus Luftfahrt e.V.. All rights reserved. This program and the accompanying
    materials are made available under the terms of the GNU General Public License v3.0 which accompanies
    this distribution, and is available at https://www.gnu.org/licenses/gpl-3.0.html.en

"""

bl_info = {"name": "CPACS Import",
           "author": "Marc Engelmann, Bauhaus Luftfahrt e.V.",
           "location": "File > Import > CPACS (.xml)",
           "version": (1, 0),
           "category": "Import-Export",
           "warning": "Addon is not functional yet!",
           "support": "COMMUNITY",
           "wiki_url": "https://github.com/BauhausLuftfahrt/Blender-CPACS-Importer",
           "blender": (2, 80, 0)}

########################################################################################################################
###                                           This is the Blender addon part.                                        ###
########################################################################################################################

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

import logging
import math
import os
import sys
import xml.etree.cElementTree as ETree
import xml.etree.ElementTree as XMLTree

import bpy
import bmesh


class ImportCPACSActionMenu(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "blender_cpacs_importer.load_cpacs"
    bl_label = "Import CPACS"

    # ImportHelper mixin class uses this
    filename_ext = ".xml"

    filter_glob: StringProperty(
        default="*.xml",
        options={'HIDDEN'},
        maxlen=255,
    )

    """
    option_select_business_seat: EnumProperty(
        name="BC Seat Type",
        description="Choose between the business class type models",
        items=(
            ('OPT_A', "Economy Style", "Default economy class style seat. Use in short range configurations"),
            ('OPT_B', "Enhanced Style", "Enhanced single economy class style seat"),
            ('OPT_C', "Long Range Premium Style",
             "Separated premium seat for long range business class configurations"),
        ),
        default='OPT_C',
    )

    """

    option_select_business_seat = "OPT_A"

    def execute(self, context):
        return run_main_parser(self.filepath, self.option_select_business_seat)


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportCPACSActionMenu.bl_idname, text="CPACS (.xml)")


def register():
    bpy.utils.register_class(ImportCPACSActionMenu)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportCPACSActionMenu)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


########################################################################################################################
###                                        This is the CPACS literal collection                                      ###
########################################################################################################################

class CPACS:
    """
    CPACS literals used in this script
    """

    # -----------
    # Official literals

    fuselage_profile_path: str = 'vehicles/profiles/fuselageProfiles/fuselageProfile'
    fuselage_profile_pointlist_x: str = 'pointList/x'
    fuselage_profile_pointlist_y: str = 'pointList/y'
    fuselage_profile_pointlist_z: str = 'pointList/z'

    fuselage_element_scaling_y: str = 'elements/element/transformation/scaling/y'
    fuselage_element_scaling_z: str = 'elements/element/transformation/scaling/z'
    fuselage_element_translation_z: str = 'elements/element/transformation/translation/z'

    fuselage_positioning_length: str = 'length'

    fuselage_section_path: str = 'vehicles/aircraft/model/fuselages/fuselage/sections/section'
    fuselage_positioning_path: str = 'vehicles/aircraft/model/fuselages/fuselage/positionings/positioning'

    deck_path: str = 'vehicles/aircraft/model/fuselages/fuselage/decks/deck'
    object_name: str = 'name'

    cabin_geometry_x: str = 'cabGeometry/x'
    cabin_geometry_yZ: str = 'cabGeometry/yZ'
    cabin_geometry_z: str = 'cabGeometry/z'
    cabin_z0: str = 'z0'
    cabin_x0: str = 'x0'

    floor_element_sub_path: str = 'floorElements/floorElement'
    floor_element_type: str = 'type'
    floor_element_type_kitchen: str = 'kitchen'
    floor_element_type_toilet: str = 'toilet'

    object_x: str = 'x'
    object_y: str = 'y'
    object_z: str = 'z'

    aisle_sub_path: str = 'aisles/aisle'
    seat_element_sub_path: str = 'seatElements/seatElement'
    seats_per_group: str = 'nSeats'

    object_length: str = 'length'
    object_width: str = 'width'
    object_height: str = 'height'

    seat_element_type: str = 'type'
    seat_element_type_business: str = 'business'
    seat_element_type_economy: str = 'economy'
    seat_element_type_first: str = 'first'

    # -----------
    # Custom CPACS with default values

    custom_overhead_bin_height: str = 'overheadBinHeight'
    custom_overhead_bin_height_default: str = '0.4'
    custom_overhead_bin_indent: str = 'overheadBinIndent'
    custom_overhead_bin_indent_default: str = '0.35'
    custom_floor_element_type_curtain: str = 'curtain'
    custom_floor_element_type_bar: str = 'bar'
    custom_floor_element_type_staircase: str = 'staircase'
    custom_floor_element_type_table: str = 'table'
    custom_floor_element_type_divider: str = 'divider'
    custom_object_rotation: str = 'rotation'
    custom_object_rotation_default: str = '0.0'
    custom_seat_element_type_premium_economy: str = 'premiumEconomy'

    def getStringArray(parsed_element: XMLTree.Element, literal: str) -> [str]:
        """
        Try split the vectors for aisle and cabin geometry using different delimiters.
        This issue is caused by different CPACS versions.
        :param literal:
        :return:
        """

        # Parse the string
        initial_string: str = parsed_element.find(literal).text

        # Remove last character if it is a delimiter
        if initial_string.endswith(';') or initial_string.endswith(' '):
            initial_string = initial_string[:-1]

        # Split the string
        string_array: [str] = initial_string.split(';')

        # Split it with another delimiter if the first attempt failed
        if len(string_array) == 1:
            string_array = initial_string.split(' ')

        return string_array

    def getCustomOrElse(parsed_element: XMLTree.Element, literal: str, default_value: str) -> str:

        """
        As it can not be expected that custom CPACS literals are existent in the file, set so predefined values instead.
        :param literal:
        :param defaultValue:
        :return:
        """
        if parsed_element.find(literal) is None:

            logging.info(literal + " not found in file. Using default instead.")
            return default_value
        else:

            return parsed_element.find(literal).text


########################################################################################################################
###                                        This is the core part of the script                                       ###
########################################################################################################################

# ------------------------------------------------------------------------------
# Utility Functions

class Vector:
    """
    Three dimensional vector
    """

    def __init__(self, x: float = 0, y: float = 0, z: float = 0) -> None:
        self.x = x
        self.y = y
        self.z = z


def set_smooth(obj) -> None:
    """ Enable smooth shading on an mesh object """

    for face in obj.data.polygons:
        face.use_smooth = True


def recalculate_normals(mesh) -> None:
    bm = bmesh.new()
    bm.from_mesh(mesh)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    bm.to_mesh(mesh)
    bm.free()


def vector_x_distance_to(vec: Vector, x_pos: float):
    return abs(vec.x - x_pos)


# ------------------------------------------------------------------------------
# Main Functions

def create_world():
    """

    :return:
    """

    bpy.data.scenes['Scene'].render.engine = 'CYCLES'
    bpy.data.worlds['World'].node_tree.nodes.new(type='ShaderNodeTexSky')

    material_input: bpy.types.NodeGroupInput = bpy.data.worlds['World'].node_tree.nodes['World Output'].inputs[
        'Surface']
    material_output: bpy.types.NodeGroupOutput = bpy.data.worlds['World'].node_tree.nodes['Background'].outputs[
        'Background']
    bpy.data.worlds['World'].node_tree.links.new(material_input, material_output)

    material_input: bpy.types.NodeGroupInput = bpy.data.worlds['World'].node_tree.nodes['Background'].inputs[
        'Color']
    material_output: bpy.types.NodeGroupOutput = bpy.data.worlds['World'].node_tree.nodes['Sky Texture'].outputs[
        'Color']
    bpy.data.worlds['World'].node_tree.links.new(material_input, material_output)


def create_camera() -> bpy.types.Object:
    """

    :return:
    """
    camera: bpy.types.Object = bpy.ops.object.camera_add()
    'camera. location = (-13.0, -11.0, 3.5)'
    'camera.rotation_euler = (80.0 * math.pi / 180.0, 0.0, 300.0 * math.pi / 180.0)'

    return camera


def create_light(name: str, pos: Vector, collection, color: Vector = None, strength: int = 1000,
                 light_type: str = "POINT", rotation: Vector = None, lamp_size: Vector = None) -> bpy.types.Object:
    """

    :param name:
    :param pos:
    :param collection:
    :param color:
    :param strength:
    :param light_type:
    :param rotation:
    :param lamp_size:
    :return:
    """

    # Lamp data
    __lamp_data: bpy.types.Light = bpy.data.lights.new(name=name, type=light_type)
    __lamp_data.energy = strength

    # Create new object with our lamp data block
    __lamp_object: bpy.types.Object = bpy.data.objects.new(name=name, object_data=__lamp_data)

    if light_type == "AREA" and lamp_size is not None:
        __lamp_data.shape = "RECTANGLE"
        __lamp_data.size = lamp_size.x
        __lamp_data.size_y = lamp_size.y

    # Link lamp object to the scene so it'll appear in this scene
    collection.objects.link(__lamp_object)

    # Place lamp to a specified location
    __lamp_object.location = (pos.x, pos.y, pos.z)

    if rotation is not None:
        __lamp_object.rotation_euler = (
            rotation.x * math.pi / 180.0, rotation.y * math.pi / 180.0, rotation.z * math.pi / 180.0)

    if color is not None:
        __lamp_data.color = (color.x, color.y, color.z)

    return __lamp_object


def create_material(material_name: str, color: Vector = None) -> bpy.types.Material:
    """

    :param material_name:
    :param color:
    :return:
    """
    __material: bpy.types.Material = bpy.data.materials.new(material_name)
    __material.use_nodes = True

    # Remove default node
    __material.node_tree.nodes.remove(__material.node_tree.nodes['Principled BSDF'])

    if "light" in material_name:
        __material.node_tree.nodes.new(type='ShaderNodeEmission')
        node_name = 'Emission'
        output_name = node_name
    else:
        __material.node_tree.nodes.new(type='ShaderNodeBsdfDiffuse')
        node_name = 'Diffuse BSDF'
        output_name = 'BSDF'

    if color is not None:
        __material.node_tree.nodes[node_name].inputs[0].default_value = (color.x, color.y, color.z, 1.0)

    material_input: bpy.types.NodeGroupInput = __material.node_tree.nodes['Material Output'].inputs['Surface']
    material_output: bpy.types.NodeGroupOutput = __material.node_tree.nodes[node_name].outputs[output_name]

    __material.node_tree.links.new(material_input, material_output)

    return __material


def load_obj_file(path: str, template_collection: bpy.types.Collection, material_dict: dict = None) -> bpy.types.Object:
    """

    :param path:
    :param template_collection:
    :param material_dict:
    :return:
    """

    # main_path: str = 'S:\\Visualisation\\Concepts\\AVACON\\CAD_Models\\'
    main_path: str = 'C:\\Users\\marc.engelmann\\Desktop\\Blender_files\\CAD_Models\\'

    bpy.ops.import_scene.obj(filepath=main_path + path + ".obj")

    for element in bpy.context.selected_objects:

        if material_dict == None:
            material: bpy.types.Material = create_material(element.name)

        else:
            try:
                material: bpy.types.Material = material_dict[str(element.name).split('.')[0]]
            # material.name = material.name + str(element.name).split('.')[0]

            except KeyError as e:
                material: bpy.types.Material = create_material(element.name + ' ERROR', Vector(255, 0, 0))

        # Check if object already has a material, then apply it to object
        if element.data.materials:
            element.data.materials[0] = material

        else:
            element.data.materials.append(material)

    if len(bpy.context.selected_objects) > 1:
        bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        bpy.ops.object.join()

    obj_object = bpy.context.selected_objects[0]
    obj_object.select_set(False)

    set_smooth(obj_object)

    bpy.context.scene.collection.objects.unlink(obj_object)
    template_collection.objects.link(obj_object)

    return obj_object


def load_material(material_name: str) -> bpy.types.Material:
    """

    :param name:
    :param file_name:
    :param material_name:
    :return:
    """

    try:
        # material_directory = 'S:/Visualisation/Concepts/AVACON/Textures/Cabin Textures/Texture Samples.blend\\Material\\'
        material_directory = 'C:/Users/marc.engelmann/Desktop/Blender_files/Textures/Cabin Textures/Texture Samples.blend\\Material\\'
        bpy.ops.wm.append(directory=material_directory, filename=material_name)
        mat: bpy.types.Material = bpy.data.materials[material_name]
        mat.name = material_name
    except RuntimeError as e:
        logging.info("Could not load material " + material_name + ".")
        return create_material(material_name + " not found!")

    return mat


def mirror(mirror_object: bpy.types.Object, x: bool = False, y: bool = False, z: bool = False):
    """

    :param mirror_object:
    :param x:
    :param y:
    :param z:
    :return:
    """
    mirror_object.select_set(True)
    bpy.ops.transform.mirror(orient_type='GLOBAL', constraint_axis=(x, y, z))
    mirror_object.select_set(False)


def correct_normals(normals_object: bpy.types.Object) -> None:
    """

    :param normals_object:
    :return:
    """
    bpy.context.view_layer.objects.active = normals_object
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.editmode_toggle()


def connect_shapes(name: str, collection: bpy.types.Collection, shapes: [[Vector]],
                   material: bpy.types.Material = None,
                   check_normals: bool = True) -> bpy.types.Object:
    """
    Define multiple vector shapes of equal vector amount and connect all shapes
    :param name:
    :param collection:
    :param shapes:
    :param material:
    :param check_normals:
    :return:
    """

    if len(shapes[0]) == 0:
        shapes.remove(shapes[0])
        logging.warning("'connect_shapes': array seems to be corrupted!")

    __vertices: [float] = []
    __faces = []

    number_of_shapes: int = len(shapes)

    # Add all vectors to vertices list
    for shape in shapes:
        for vec in shape:
            __vertices.append((vec.x, vec.y, vec.z))

    # Get size of shape
    points_per_shape: int = len(shapes[0])

    # Create front face
    __faces.append([i for i in range(points_per_shape)])

    for shape_index in range(number_of_shapes - 1):

        for _i in range(points_per_shape):

            if _i == (points_per_shape - 1):
                __faces.append((_i + shape_index * points_per_shape, 0 + shape_index * points_per_shape,
                                _i + 1 + shape_index * points_per_shape,
                                2 * points_per_shape - 1 + shape_index * points_per_shape))

            else:
                __faces.append((_i + shape_index * points_per_shape, _i + 1 + shape_index * points_per_shape,
                                _i + points_per_shape + 1 + shape_index * points_per_shape,
                                _i + points_per_shape + shape_index * points_per_shape))

    # Create back face
    __faces.append(
        [i for i in range((number_of_shapes - 1) * points_per_shape, number_of_shapes * points_per_shape)])

    mesh: bpy.types.Mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(__vertices, [], __faces)
    shape_object: bpy.types.Object = bpy.data.objects.new(name, mesh)

    recalculate_normals(shape_object.data)
    set_smooth(shape_object)

    collection.objects.link(shape_object)

    # Check if material is required
    if material is not None:

        # Check if object already has a material, then apply it to object
        if shape_object.data.materials:
            shape_object.data.materials[0] = material

        else:
            shape_object.data.materials.append(material)

    # If the normals orientation should be checked, perform test
    if check_normals:
        # correct the normals!
        correct_normals(shape_object)

    mesh.update()
    return shape_object


def create_from_template(template: bpy.types.Object, collection: bpy.types.Collection, position: Vector,
                         size_x: float = None, size_y: float = None,
                         size_z: float = None) -> bpy.types.Object:
    """

    :param template:
    :param collection:
    :param position:
    :param size_x:
    :param size_y:
    :param size_z:
    :return:
    """

    # Create new object
    new_object: bpy.types.Object = template.copy()
    new_object.data = new_object.data.copy()

    # new_object: bpy.types.Object = bpy.data.objects.new(template.name, template.data)

    # Assign new collection
    collection.objects.link(new_object)

    # Select object
    new_object.select_set(True)

    # Rotate 90 degrees (required for .obj import copy)
    new_object.rotation_euler[0] = 90 * math.pi / 180.0

    # Set position of new object
    new_object.location[0] = position.x
    new_object.location[1] = position.y
    new_object.location[2] = position.z

    # Deselect object
    new_object.select_set(False)

    # Determine size of new object
    set_dimensions(new_object, size_x, size_y, size_z)

    # Return object
    return new_object


def set_dimensions(object: bpy.types.Object, size_x: float = None, size_y: float = None, size_z: float = None):
    """

    :param object:
    :param size_x:
    :param size_y:
    :param size_z:
    :return:
    """

    object.select_set(True)

    # Determine size of new object
    new_dimension_x: float = size_x if size_x is not None else bpy.context.selected_objects[0].dimensions[0]
    new_dimension_y: float = size_y if size_y is not None else bpy.context.selected_objects[0].dimensions[1]
    new_dimension_z: float = size_z if size_z is not None else bpy.context.selected_objects[0].dimensions[2]

    # Set size of new object
    bpy.context.selected_objects[0].dimensions = new_dimension_x, new_dimension_y, new_dimension_z

    object.select_set(False)


def create_from_cpacs(path: str, enum_bc_seat_type=None) -> None:
    """

    :param path:
    :param generate_fuselage:
    :param enum_bc_seat_type:
    :return:
    """
    material_fabric_black: bpy.types.Material = load_material('Fabric_black')
    material_fabric_blue: bpy.types.Material = load_material('Fabric_blue')
    material_fabric_blue_dark: bpy.types.Material = load_material('Fabric_blue_dark')
    material_fabric_green: bpy.types.Material = load_material('Fabric_green')
    material_fabric_orange: bpy.types.Material = load_material('Fabric_orange')
    material_fabric_white: bpy.types.Material = load_material('Fabric_white')
    material_fabric_wite_logo: bpy.types.Material = load_material('Fabric_white with logo')
    material_leather: bpy.types.Material = load_material('Leather_1')
    material_leather_black: bpy.types.Material = load_material('Leather_2_black')
    material_leather_3: bpy.types.Material = load_material('Leather_3')
    material_light: bpy.types.Material = load_material('Light')
    material_metal_bright: bpy.types.Material = load_material('Metal_bright')
    material_metal_dark: bpy.types.Material = load_material('Metal_dark')
    material_plastic_dark: bpy.types.Material = load_material('Plastic_dark')
    material_plastic_grey: bpy.types.Material = load_material('Plastic_grey')
    material_plastic_rough: bpy.types.Material = load_material('Plastic_rough')
    material_plastic_white: bpy.types.Material = load_material('Plastic_white')
    material_wood: bpy.types.Material = load_material('Wood')
    material_black: bpy.types.Material = create_material('Just_Black', Vector(0, 0, 0))

    material_dict: dict = dict([
        ('cushion', material_fabric_blue_dark),
        ('pillow', material_fabric_black),
        ('window', material_light),
        ('light', material_light),
        ('armrest', material_plastic_dark),
        ('rail', material_metal_bright),
        ('tray_table', material_plastic_grey),
        ('housing', material_plastic_grey),
        ('bin', material_plastic_grey),
        ('arch', material_plastic_grey),
        ('base', material_plastic_dark),
        ('ventilation', material_plastic_dark),
        ('locker', material_metal_dark),
        ('table', material_wood),
        ('lamp', material_metal_dark),
        ('cover', material_plastic_grey),
        ('cover_inside', material_wood),
        ('lining', material_plastic_grey),
        ('walls', material_plastic_grey),
        ('divider_wall', material_plastic_grey),
        ('foot', material_plastic_grey),
        ('shelves', material_plastic_dark),
        ('tv_frame', material_plastic_dark),
        ('trolley', material_metal_dark),
        ('tv_display', material_black),
        ('railing', material_metal_dark),
        ('stairs', material_fabric_black)

    ])

    logging.info("Creating aircraft model from '" + path + "'.")

    cpacs = ETree.parse(path).getroot()

    # Clear all exiting collections except the cameras
    for c in bpy.data.collections:
        if c.name != "World":
            bpy.data.collections.remove(c)

    # create new collections for all elements
    seats_col: bpy.types.Collection = bpy.data.collections.new('Seats')
    floor_col: bpy.types.Collection = bpy.data.collections.new('Floor Elements')
    lining_col: bpy.types.Collection = bpy.data.collections.new('Lining')
    ceiling_col: bpy.types.Collection = bpy.data.collections.new('Ceiling')
    temp_col: bpy.types.Collection = bpy.data.collections.new('Templates')
    fuselage_col: bpy.types.Collection = bpy.data.collections.new('Fuselage')

    # link collections to scene
    bpy.context.scene.collection.children.link(ceiling_col)
    bpy.context.scene.collection.children.link(lining_col)
    bpy.context.scene.collection.children.link(temp_col)
    bpy.context.scene.collection.children.link(seats_col)
    bpy.context.scene.collection.children.link(floor_col)
    bpy.context.scene.collection.children.link(fuselage_col)

    # Load all .obj files here.
    lining_obj: bpy.types.Object = load_obj_file('Linings\\side_wall_1', temp_col, material_dict)
    lining_obj_2: bpy.types.Object = load_obj_file('Linings\\side_wall_2', temp_col, material_dict)
    lining_obj_3: bpy.types.Object = load_obj_file('Linings\\side_wall_3', temp_col, material_dict)
    luggage_bin_object: bpy.types.Object = load_obj_file('Overhead_Bins\\bin', temp_col, material_dict)
    ceiling_object: bpy.types.Object = load_obj_file('Overhead_Bins\\aisle_arch', temp_col, material_dict)
    ceiling_middle_object: bpy.types.Object = load_obj_file('Overhead_Bins\\bin_extension_3', temp_col, material_dict)

    galley_object = None
    curtain_object = None
    wall_object = None

    bar_object = None
    table_object = None
    stairs_object = None

    busi_seat_object: bpy.types.Object = load_obj_file('Seats\\bc_1', temp_col, material_dict)
    preco_seat_object: bpy.types.Object = load_obj_file('Seats\\pec_1', temp_col, material_dict)

    seat_object_1 = None
    seat_object_2 = None
    seat_object_3 = None
    seat_object_4 = None
    seat_object_5 = None

    fuselage_profile: XMLTree.Element = cpacs.find(CPACS.fuselage_profile_path)
    fuselage_positioning: [XMLTree.Element] = cpacs.findall(CPACS.fuselage_positioning_path)

    # Only create fuselage shape if model supports it
    if len(fuselage_positioning) > 0:

        # Create the fuselage shape of the aircraft
        circular_x: [float] = [float(x) for x in
                               CPACS.getStringArray(fuselage_profile, CPACS.fuselage_profile_pointlist_x)]
        circular_y: [float] = [float(y) for y in
                               CPACS.getStringArray(fuselage_profile, CPACS.fuselage_profile_pointlist_y)]
        circular_z: [float] = [float(z) for z in
                               CPACS.getStringArray(fuselage_profile, CPACS.fuselage_profile_pointlist_z)]

        fuselage_shapes: [[Vector]] = [[]]

        indexer: int = 0
        total_length: float = 0.0

        for fuselage_section in cpacs.findall(CPACS.fuselage_section_path):
            length: float = float(fuselage_positioning[indexer].find(CPACS.fuselage_positioning_length).text)
            scale_y: float = float(fuselage_section.find(CPACS.fuselage_element_scaling_y).text)
            scale_z: float = float(fuselage_section.find(CPACS.fuselage_element_scaling_z).text)
            delta_z: float = float(fuselage_section.find(CPACS.fuselage_element_translation_z).text)
            fuselage_shapes.append(
                [Vector(total_length + circular_x[i], circular_y[i] * scale_y, circular_z[i] * scale_z + delta_z) for i
                 in
                 range(len(circular_x) - 1)])

            indexer += 1
            total_length += length

        connect_shapes("Outer Fuselage", fuselage_col, fuselage_shapes, None)

    # --------------------
    # Hard coded values
    floor_thickness: float = 0.05
    ceiling_thickness: float = 0.01

    # Loop through all cabin decks of the aircraft
    for deck in cpacs.findall(CPACS.deck_path):

        logging.info("Creating deck " + deck.find(CPACS.object_name).text + ".")

        overhead_bin_height: float = float(
            CPACS.getCustomOrElse(deck, CPACS.custom_overhead_bin_height, CPACS.custom_overhead_bin_height_default))
        luggage_bins_aisle_indent: float = float(
            CPACS.getCustomOrElse(deck, CPACS.custom_overhead_bin_indent, CPACS.custom_overhead_bin_indent_default))

        # Deck floor
        geo_x: [float] = [float(x) for x in CPACS.getStringArray(deck, CPACS.cabin_geometry_x)]
        geo_z: [float] = [float(z) for z in CPACS.getStringArray(deck, CPACS.cabin_geometry_z)]
        geo_y: [[float]] = [
            [float(y) for y in CPACS.getStringArray(deck, CPACS.cabin_geometry_yZ + str(i))] for i in
            range(1, len(geo_z) + 1)]

        # z0 of cabin
        z_0: float = float(deck.find(CPACS.cabin_z0).text)
        x_0: float = float(deck.find(CPACS.cabin_x0).text)

        floor_shape: [Vector] = [Vector(x_0 + geo_x[i], geo_y[0][i], z_0) for i in range(len(geo_x))]
        floor_shape_2: [Vector] = [Vector(x_0 + geo_x[i], geo_y[0][i], z_0 - floor_thickness) for i in
                                   range(len(geo_x))]
        ceiling_shape_2: [Vector] = [
            Vector(x_0 + geo_x[i], geo_y[len(geo_y) - 1][i], z_0 + max(geo_z) + ceiling_thickness)
            for i in range(len(geo_x))]
        ceiling_shape: [Vector] = [Vector(x_0 + geo_x[i], geo_y[len(geo_y) - 1][i], z_0 + max(geo_z)) for i in
                                   range(len(geo_x))]

        deck_size: Vector = Vector(max(geo_x), max(geo_y[0]) * 2.0, max(geo_z))
        deck_size_y_bins: float = max(geo_y[len(geo_y) - 2]) * 2.0
        floor_shape.insert(0, Vector(x_0, 0, z_0))
        floor_shape_2.insert(0, Vector(x_0, 0, z_0 - floor_thickness))

        ceiling_shape_2.insert(0, Vector(x_0, 0, z_0 + max(geo_z) + ceiling_thickness))
        ceiling_shape.insert(0, Vector(x_0, 0, z_0 + max(geo_z)))

        floor_shape.append(Vector(x_0 + deck_size.x, 0, z_0))
        floor_shape_2.append(Vector(x_0 + deck_size.x, 0, z_0 - floor_thickness))
        ceiling_shape_2.append(Vector(x_0 + deck_size.x, 0, z_0 + max(geo_z) + ceiling_thickness))
        ceiling_shape.append(Vector(x_0 + deck_size.x, 0, z_0 + max(geo_z)))

        # Create deck floor
        connect_shapes('Deck Floor R', floor_col, [floor_shape, floor_shape_2], material_fabric_black)
        mirror(connect_shapes('Deck Floor L', floor_col, [floor_shape, floor_shape_2], material_fabric_black), y=True)
        connect_shapes('Deck Ceiling R', floor_col, [ceiling_shape_2, ceiling_shape], None)
        mirror(connect_shapes('Deck Ceiling L', floor_col, [ceiling_shape_2, ceiling_shape], None), y=True)

        logging.info("Creating linings.")

        # Note: Algorithm is currently designed for linings of 1m width!

        sorted_x_values_left = geo_x.copy()
        sorted_x_values_right = geo_x.copy()

        for step in range(0, int(deck_size.x)):
            sorted_x_values_left.sort(key=lambda x: abs(x - step - 1.0))
            sorted_x_values_right.sort(key=lambda x: abs(x - step))

            closest_left: float = sorted_x_values_left[0]
            closest_right: float = sorted_x_values_right[0]

            closest_y_left: float = geo_y[0][geo_x.index(closest_left)]
            closest_y_right: float = geo_y[0][geo_x.index(closest_right)]

            corresponding_y_left_top: float = geo_y[len(geo_y) - 2][geo_x.index(closest_left)]
            corresponding_y_right_top: float = geo_y[len(geo_y) - 2][
                geo_x.index(closest_right)]

            y_middle: float = (closest_y_left + closest_y_right) / 2.0
            deck_width_ceiling: float = (corresponding_y_left_top + corresponding_y_right_top) / 2.0

            if abs(deck_width_ceiling - y_middle) < 0.10:
                selected_lining = lining_obj_3
                lining_pos_port: Vector = Vector(x_0 + step + 0.5, -min(deck_width_ceiling, y_middle), z_0)
                lining_pos_star: Vector = Vector(x_0 + step + 0.5, min(deck_width_ceiling, y_middle), z_0)
                lining_width: float = (y_middle - deck_width_ceiling)

            elif deck_width_ceiling > y_middle:
                selected_lining = lining_obj_2
                lining_pos_port: Vector = Vector(x_0 + step + 0.5, -y_middle, z_0)
                lining_pos_star: Vector = Vector(x_0 + step + 0.5, y_middle, z_0)
                lining_width: float = y_middle - deck_width_ceiling

            else:
                selected_lining = lining_obj
                lining_pos_port: Vector = Vector(x_0 + step + 0.5, -deck_width_ceiling, z_0)
                lining_pos_star: Vector = Vector(x_0 + step + 0.5, deck_width_ceiling, z_0)
                lining_width: float = y_middle - deck_width_ceiling

            lining_obj_port = create_from_template(selected_lining, lining_col, lining_pos_port, size_x=1,
                                                   size_y=deck_size.z - overhead_bin_height, size_z=lining_width)

            lining_obj_star = create_from_template(selected_lining, lining_col, lining_pos_star, size_x=1,
                                                   size_y=deck_size.z - overhead_bin_height, size_z=lining_width)
            mirror(lining_obj_star, y=True)

            if closest_y_left != closest_y_right:
                angle: float = math.atan((closest_y_right - closest_y_left) / (closest_right - closest_left))

                # Determine size of rotated lining
                new_x_dimension: float = abs(closest_y_right - closest_y_left) / math.sin(angle)
                delta_x_position: float = (y_middle - deck_width_ceiling) / math.tan(math.radians(90) - angle)

                # Set properties of port element
                lining_obj_port.rotation_euler[2] = - angle
                lining_obj_port.location[0] = delta_x_position + lining_obj_port.location[0]
                set_dimensions(lining_obj_port, size_x=new_x_dimension)

                # Set properties of starboard element
                lining_obj_star.rotation_euler[2] = angle
                lining_obj_star.location[0] = delta_x_position + lining_obj_star.location[0]
                set_dimensions(lining_obj_star, size_x=new_x_dimension)

        """
        lining_end_gap: float = x_dim_deck - int(x_dim_deck)

        cover_location: Vector = Vector(int(x_dim_deck) + 0.5 * lining_end_gap, -deck_width_ceiling / 2.0, z)
        create_from_template(lining_obj, lining_collection, cover_location, size_x=lining_end_gap, size_y=deck_height,
                             size_z=y_dim_deck / 2.0 - deck_width_ceiling / 2.0)

        cover_location: Vector = Vector(int(x_dim_deck) + 0.5 * lining_end_gap, deck_width_ceiling / 2.0, z)
        mirror(create_from_template(lining_obj, lining_collection, cover_location, size_x=lining_end_gap,
                                    size_y=deck_height,
                                    size_z=y_dim_deck / 2.0 - deck_width_ceiling / 2.0), y=True)
        """
        # Luggage bins

        logging.info("Creating floor elements.")

        # Create floor elements
        for floor_element in deck.findall(CPACS.floor_element_sub_path):

            x_dim = float(floor_element.find(CPACS.object_length).text)
            z_dim = float(floor_element.find(CPACS.object_height).text)
            y_dim = float(floor_element.find(CPACS.object_width).text)

            if floor_element.find(CPACS.floor_element_type).text == CPACS.floor_element_type_kitchen:
                if galley_object is None:
                    galley_object = load_obj_file('Galley\\galley_1', temp_col, material_dict)

                floor_obj: bpy.types.Object = galley_object

            elif floor_element.find(CPACS.floor_element_type).text == CPACS.custom_floor_element_type_curtain:
                if curtain_object is None:
                    curtain_object = load_obj_file('Divider\\curtain_1', temp_col, material_dict)

                floor_obj: bpy.types.Object = curtain_object

            elif floor_element.find(CPACS.floor_element_type).text == CPACS.custom_floor_element_type_bar:
                if bar_object is None:
                    bar_object = load_obj_file('Bar\\bar_1', temp_col, material_dict)

                floor_obj: bpy.types.Object = bar_object

            elif floor_element.find(CPACS.floor_element_type).text == CPACS.custom_floor_element_type_staircase:
                if stairs_object is None:
                    stairs_object = load_obj_file('Stairs\\stairs_1', temp_col, material_dict)

                floor_obj: bpy.types.Object = stairs_object

            elif floor_element.find(CPACS.floor_element_type).text == CPACS.custom_floor_element_type_table:
                if table_object is None:
                    table_object = load_obj_file('Tables\\table_1', temp_col, material_dict)

                floor_obj: bpy.types.Object = table_object

            else:
                if wall_object is None:
                    wall_object = load_obj_file('Divider\\divider_3', temp_col, material_dict)

                floor_obj: bpy.types.Object = wall_object

            """
            elif floor_element.find(CPACS.floor_element_type).text == CPACS.floor_element_type_toilet:
                if lavatory is None:
                    lavatory = load_obj_file('Tables\\table_1', temp_col)

                floor_obj: bpy.types.Object = lavatory
            """

            floor_location: Vector = Vector(x_0 + float(floor_element.find(CPACS.object_x).text) + x_dim / 2.0,
                                            float(floor_element.find(CPACS.object_y).text), z_0)
            bpy_floor_obj: bpy.types.Object = create_from_template(floor_obj, floor_col, floor_location, size_x=x_dim,
                                                                   size_y=z_dim,
                                                                   size_z=y_dim)
            bpy_floor_obj.rotation_euler[2] = math.radians(float(
                CPACS.getCustomOrElse(floor_element, CPACS.custom_object_rotation,
                                      CPACS.custom_object_rotation_default)))

        # Create cabin front and end
        floor_location: Vector = Vector(x_0 - 0.05, 0, z_0)
        create_from_template(wall_object, floor_col, floor_location, size_x=0.1, size_z=geo_y[0][0] * 2.0,
                             size_y=deck_size.z)

        floor_location: Vector = Vector(x_0 + deck_size.x + 0.05, 0, z_0)
        create_from_template(wall_object, floor_col, floor_location, size_x=0.1,
                             size_z=geo_y[0][len(geo_y[0]) - 1] * 2.0, size_y=deck_size.z)

        logging.info("Creating overhead bins.")

        luggage_bin_object.select_set(True)
        bin_width: float = bpy.context.selected_objects[0].dimensions[2]
        luggage_bin_object.select_set(False)

        ceiling_object.select_set(True)
        arch_height: float = bpy.context.selected_objects[0].dimensions[1]
        ceiling_object.select_set(False)

        '''
        ceiling_middle_object.select_set(True)
        arch_width: float = bpy.context.selected_objects[0].dimensions[1]
        ceiling_middle_object.select_set(False)
        '''

        aisles = deck.findall(CPACS.aisle_sub_path)

        for aisle in aisles:
            aisle_x: [float] = [float(x) for x in CPACS.getStringArray(aisle, CPACS.object_x)]
            aisle_y: [float] = [float(y) for y in CPACS.getStringArray(aisle, CPACS.object_y)]

            for i in range(len(aisle_x) - 1):
                aisle_y_pos_start: float = aisle_y[i]
                aisle_y_pos_end: float = aisle_y[i + 1]

                # Lights within aisle step
                aisle_x_pos_start: float = aisle_x[i]
                aisle_x_pos_end: float = aisle_x[i + 1]

                general_x_pos: float = aisle_x_pos_start + (aisle_x_pos_end - aisle_x_pos_start) / 2.0
                general_y_pos: float = aisle_y_pos_start + (aisle_y_pos_end - aisle_y_pos_start) / 2.0

                # Generate bins
                luggage_bin_position: Vector = Vector(x_0 + general_x_pos,
                                                      general_y_pos - luggage_bins_aisle_indent - bin_width / 2.0,
                                                      z_0 + deck_size.z - overhead_bin_height / 2.0)

                create_from_template(luggage_bin_object, ceiling_col, luggage_bin_position,
                                     size_x=aisle_x_pos_end - aisle_x_pos_start, size_y=overhead_bin_height)

                # Determine gap to closest lining
                gap_y_starboard: float = deck_size_y_bins / 2.0 - general_y_pos - luggage_bins_aisle_indent - bin_width
                gap_y_port: float = deck_size_y_bins / 2.0 + general_y_pos - luggage_bins_aisle_indent - bin_width

                if gap_y_starboard > 0 and gap_y_starboard < bin_width:
                    luggage_filler_position: Vector = Vector(x_0 + general_x_pos,
                                                             general_y_pos + luggage_bins_aisle_indent + bin_width + gap_y_starboard / 2.0,
                                                             z_0 + deck_size.z - overhead_bin_height / 2.0)

                    create_from_template(ceiling_middle_object, ceiling_col, luggage_filler_position,
                                         size_x=aisle_x_pos_end - aisle_x_pos_start,
                                         size_y=overhead_bin_height,
                                         size_z=gap_y_starboard)

                # Generate bins
                luggage_bin_position_right: Vector = Vector(x_0 + general_x_pos,
                                                            general_y_pos + luggage_bins_aisle_indent + bin_width / 2.0,
                                                            z_0 + deck_size.z - overhead_bin_height / 2.0)

                mirror(create_from_template(luggage_bin_object, ceiling_col, luggage_bin_position_right,
                                            size_x=aisle_x_pos_end - aisle_x_pos_start, size_y=overhead_bin_height),
                       y=True)

                if 0 < gap_y_port < bin_width:
                    luggage_filler_position: Vector = Vector(x_0 + general_x_pos,
                                                             general_y_pos - luggage_bins_aisle_indent - bin_width - gap_y_port / 2.0,
                                                             z_0 + deck_size.z - overhead_bin_height / 2.0)

                    mirror(create_from_template(ceiling_middle_object, ceiling_col, luggage_filler_position,
                                                size_x=aisle_x_pos_end - aisle_x_pos_start, size_y=overhead_bin_height,
                                                size_z=gap_y_port), y=True)

                # Generate bin arch
                ceiling_arch_pos: Vector = Vector(x_0 + general_x_pos, general_y_pos,
                                                  z_0 + deck_size.z - arch_height * 0.1)

                create_from_template(ceiling_object, ceiling_col, ceiling_arch_pos,
                                     size_x=aisle_x_pos_end - aisle_x_pos_start,
                                     size_z=2 * luggage_bins_aisle_indent + bin_width)

        logging.info("Creating seats.")

        # loop through seat groups
        for seat_group in deck.findall(CPACS.seat_element_sub_path):
            number_of_seats: int = int(seat_group.find(CPACS.seats_per_group).text)

            x_dim: float = float(seat_group.find(CPACS.object_length).text)
            y_dim_total: float = float(seat_group.find(CPACS.object_width).text)
            z_dim: float = float(seat_group.find(CPACS.object_height).text)

            x: float = float(seat_group.find(CPACS.object_x).text)
            y_total: float = float(seat_group.find(CPACS.object_y).text) - y_dim_total / 2.0

            # economy seats are created in groups
            if seat_group.find(CPACS.seat_element_type).text == CPACS.seat_element_type_economy:
                if number_of_seats == 5:
                    if seat_object_5 is None:
                        seat_object_5 = load_obj_file('Seats\\ec_5', temp_col, material_dict)

                    eco_seat: bpy.types.Object = seat_object_5

                elif number_of_seats == 4:
                    if seat_object_4 is None:
                        seat_object_4 = load_obj_file('Seats\\ec_4', temp_col, material_dict)

                    eco_seat: bpy.types.Object = seat_object_4

                elif number_of_seats == 3:
                    if seat_object_3 is None:
                        seat_object_3 = load_obj_file('Seats\\ec_3', temp_col, material_dict)

                    eco_seat: bpy.types.Object = seat_object_3

                elif number_of_seats == 2:
                    if seat_object_2 is None:
                        seat_object_2 = load_obj_file('Seats\\ec_2', temp_col, material_dict)

                    eco_seat: bpy.types.Object = seat_object_2

                else:
                    if seat_object_1 is None:
                        seat_object_1 = load_obj_file('Seats\\ec_1', temp_col, material_dict)

                    eco_seat: bpy.types.Object = seat_object_1

                seat_position: Vector = Vector(x_0 + x + x_dim / 2.0, y_total + y_dim_total / 2.0, z_0)
                new_seat: bpy.types.Object = create_from_template(eco_seat, seats_col, seat_position,
                                                                  size_x=x_dim, size_y=z_dim,
                                                                  size_z=y_dim_total)

                if y_total < 0 and number_of_seats == 2:
                    mirror(new_seat, y=True)

                new_seat.rotation_euler[2] = math.radians(float(
                    CPACS.getCustomOrElse(seat_group, CPACS.custom_object_rotation,
                                          CPACS.custom_object_rotation_default)))

            else:
                # loop through all other seats
                for seatID in range(number_of_seats):
                    y_dim_per_seat: float = y_dim_total / number_of_seats
                    y_pos_per_seat: float = y_total + seatID * y_dim_per_seat

                    seat_position_busi: Vector = Vector(x_0 + x + x_dim / 2.0, y_pos_per_seat + y_dim_per_seat / 2.0,
                                                        z_0)
                    if seat_group.find(CPACS.seat_element_type).text == CPACS.seat_element_type_business:
                        single_seat_obj: bpy.types.Object = busi_seat_object
                    else:
                        single_seat_obj: bpy.types.Object = preco_seat_object

                    new_single_seat: bpy.types.Object = create_from_template(single_seat_obj, seats_col,
                                                                             seat_position_busi, size_x=x_dim,
                                                                             size_y=z_dim, size_z=y_dim_per_seat)
                    new_single_seat.rotation_euler[2] = math.radians(
                        float(CPACS.getCustomOrElse(seat_group, CPACS.custom_object_rotation,
                                                    CPACS.custom_object_rotation_default)))

                    if seatID % 2 == 1:
                        mirror(new_single_seat, y=True)

    logging.info("Creating world objects.")
    create_world()

    bpy.data.collections.remove(temp_col)

    logging.info("Import completed.")


def run_main_parser(file_path: str, business_seat_option) -> [str]:
    """

    :param file_path:
    :param business_seat_option:
    :return:
    """
    # init logger
    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')
    logging.info("Running CPACS import script to Blender.")
    logging.info("Created by Marc Engelmann @ Bauhaus Luftfahrt e.V.")

    create_from_cpacs(file_path, business_seat_option)

    return {'FINISHED'}


def run_as_script() -> None:
    """

    :return:
    """
    # init logger
    logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')

    if "--" not in sys.argv:
        argv = []  # as if no args are passed
    else:
        argv = sys.argv[sys.argv.index("--") + 1:]  # get all args after "--"

    logging.info("####################### Blender output start. #######################")
    logging.info("Running CPACS import script to Blender.")
    logging.info("Created by Marc Engelmann @ Bauhaus Luftfahrt e.V.")

    logging.info("Launch arguments:")
    for arg in argv:
        logging.info("\t " + arg)

    # Run main function
    if len(argv) == 0:
        create_from_cpacs(
            path=os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop') + '/workflow/output/output_file.xml')
    else:
        create_from_cpacs(path=argv[0])

    # create_from_cpacs(file_path, generate_fuselage)

    save_path: str = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop') + '/cabin.blend'
    logging.info("Saving project to " + save_path)
    bpy.ops.wm.save_as_mainfile(filepath=save_path)

    # Kill app if it runs in background mode
    if bpy.app.background:
        bpy.ops.wm.quit_blender()

    logging.info("####################### Blender output end. #######################")


########################################################################################################################
###                                Only this is run if the script is called normally!                                ###
########################################################################################################################

# Main code is run when this is not run as an add-on!
if __name__ == "__main__":
    run_as_script()
