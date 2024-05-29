import ewd
import subprocess
import os
from sclcore import do_debug, Vec3
from ddx import gdb
from ddx import math
from ddx.gdb import cad, param as parametric
from ddx.math import EPSILON_NORM
from ewd.msg import get_compo_msg as get_msg
from ddx.autoexec import BaseOperation, ParamType
from contextlib import contextmanager


_FIRST_PHASE = 0
_SECOND_PHASE = 1
X_AXIS = "X_AX"
Y_AXIS = "Y_AX"

@contextmanager
def temp_layer(part_name="", hint="", new_part=False):
    """Create a temp layer, return the layer name.
    At the end destroy the temp layer
    :param part_name: part's name, defaults to ""
    :type part_name: str, optional
    :param hint: hint for the name of the new layer, defaults to ""
    :type hint: str, optional
    :param new_part: True if a temp part needs to be created too, defaults to False
    :type new_part: bool, optional
    :yield: path to the created layer
    :rtype: str
    """
    temp_part = False
    try:
        # if requested
        # or if the passed name is empty
        # I add a new part
        if new_part or (new_part and not part_name):
            part_name = gdb.get_new_name("", part_name)
            gdb.add_part(part_name)
            temp_part = True

        # create a new layer
        lay_path = gdb.add_layer(part_name, hint, new_name=True)

        # return layer path
        yield lay_path
    finally:
        if temp_part:
            gdb.delete_part(part_name)
        else:
            gdb.delete_layer(lay_path)


def get_layer_by_importer(skey):
    """
    Function for get layer name referred to the used CAD software
    """
    #I open CFG layer names file
    with open(ewd.explode_file_path("%MACHPATH%\\Automatic\\Layer_Names.cfg")) as file_name:
        for line in file_name:
            #Search for the key and clean for have the layer
            if skey in line:
                line = line.strip()
                return line[line.find("=")+2:-1]

class PythaFilter(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2222), "", "Pytha")

        phases = [(_FIRST_PHASE, get_msg(2198)), (_SECOND_PHASE, get_msg(2199))]
        rot_axis = [(X_AXIS, get_msg(2200)), (Y_AXIS, get_msg(2201))]
        self.register_param("phase", ParamType.INPUT, get_msg(2202), _FIRST_PHASE, phases)
        self.register_param("side_workings", ParamType.INPUT, get_msg(2203), True)
        self.register_param("clamex_pocket", ParamType.INPUT, get_msg(2262), False)
        self.register_param("clamex_5ax", ParamType.INPUT, get_msg(2285), False)
        self.register_param("rotation_axis", ParamType.INPUT, get_msg(2204), X_AXIS, rot_axis)
        self.register_param("list_piece_force_rebating", ParamType.INPUT, get_msg(2225), "", "")

        self.register_param("cont_to_overturn", ParamType.OUTPUT, "", "")

    def overturn_manage_outline(self, part, rot_ax):
        """[summary]
        :param part: [description]
        :type part: [type]
        """

        gdb.cad.overturn_piece(part, 180, False, rot_ax)

        gdb.add_layer(part, "OUTLINETemp")

        outline_ents = gdb.get_entities(part + "\\" + get_layer_by_importer("LAYER_CONTORNA"))

        for ent in outline_ents:
            #old
            #gdb.copy_object(ent, part + "\\OUTLINETemp", True)
            #modified for Sprea
            new_name = gdb.copy_object(ent, part + "\\OUTLINETemp", True)
            # overturn_piece set inverted work side
            # I invert for corrige it
            work_side = gdb.get_note(ent, "TC")
            if work_side != "":
                work_side = int(work_side)
                if work_side != 0:
                    new_work_side = 1 if work_side == 2 else 2
                cad.modify_curves(part + "\\OUTLINETemp\\" + new_name, work_side=new_work_side)

        gdb.delete_layer(part + "\\" + get_layer_by_importer("LAYER_CONTORNA"))
        gdb.rename_layer(part + "\\OUTLINETemp", get_layer_by_importer("LAYER_CONTORNA"))

        thick = gdb.get_solid_thickness(part)

        gdb.cad.move_entities(outline_ents, to_z=thick)

        #I modify OVERMAT layer
        outline_ents = gdb.get_entities(part + "\\" + get_layer_by_importer("LAYER_OVERDIM"))
        if len(outline_ents) > 0:
            gdb.add_layer(part, "OVERMATTemp")

            for ent in outline_ents:
                #old
                #gdb.copy_object(ent, part + "\\EDGE_BANDINGTemp", True)
                #modified for Sprea
                new_name = gdb.copy_object(ent, part + "\\OVERMATTemp", True)
                # overturn_piece set inverted work side
                # I invert for corrige it
                work_side = gdb.get_note(ent, "TC")
                if work_side != "":
                    work_side = int(work_side)
                    if work_side != 0:
                        new_work_side = 1 if work_side == 2 else 2
                    cad.modify_curves(part + "\\OVERMATTemp\\" + new_name, work_side=new_work_side)

            gdb.delete_layer(part + "\\" + get_layer_by_importer("LAYER_OVERDIM"))
            gdb.rename_layer(part + "\\OVERMATTemp", get_layer_by_importer("LAYER_OVERDIM"))

            gdb.cad.move_entities(outline_ents, to_z=thick)

        #I modify edge banding layer
        outline_ents = gdb.get_entities(part + "\\EDGE_BANDING")
        if len(outline_ents) > 0:
            gdb.add_layer(part, "EDGE_BANDINGTemp")

            for ent in outline_ents:
                #old
                #gdb.copy_object(ent, part + "\\EDGE_BANDINGTemp", True)
                #modified for Sprea
                new_name = gdb.copy_object(ent, part + "\\EDGE_BANDINGTemp", True)
                # overturn_piece set inverted work side
                # I invert for corrige it
                work_side = gdb.get_note(ent, "TC")
                if work_side != "":
                    work_side = int(work_side)
                    if work_side != 0:
                        new_work_side = 1 if work_side == 2 else 2
                    cad.modify_curves(part + "\\EDGE_BANDINGTemp\\" + new_name, work_side=new_work_side)

            gdb.delete_layer(part + "\\EDGE_BANDING")
            gdb.rename_layer(part + "\\EDGE_BANDINGTemp", "EDGE_BANDING")

            gdb.cad.move_entities(outline_ents, to_z=thick)
            

    def create_raw_material(self, part):
        """function for create a layer who contains the raw material dimension

        :param part: part
        :type part: string
        """
        #I get overmaterial applied to the piece
        try: 
            raw_mat = float(gdb.get_note(part + "\\InfoLabels", "part_attribute66"))
        except:
            raise Exception("Error: No OFFSET note in ewx file")

        #I create the layer
        gdb.add_layer(part, get_layer_by_importer("LAYER_OVERDIM"))

        part_dim = gdb.get_extension(part + "\\%%SOLID")

        #I calc the dimension of the overmaterial piece
        raw_part_dimx = abs(part_dim[0].x - part_dim[1].x) + raw_mat*2
        raw_part_dimy = abs(part_dim[0].y - part_dim[1].y) + raw_mat*2

        rectangle_point = Vec3(part_dim[0].x-raw_mat, part_dim[0].y-raw_mat, 0)
        gdb.cad.add_rectangle(part + "\\" + get_layer_by_importer("LAYER_OVERDIM"), rectangle_point, raw_part_dimx, raw_part_dimy, 0, 0, material="BOX_MAT_NAME")

    def verify_passing_entities_direction(self, part):
        """procedure for verify if there are passing entities on bottom reference.
        In this case I invert them for let them worked in first phase

        :param part: the part to verify
        :type part: string
        """

        piece_ref = gdb.get_extension(part + "\\%%SOLID")
        # layers cycle
        layers = cad.get_layers(part)
        layer_to_delete = []

        for layer in layers:
            ent_list_passing = []
            b_hole_to_invert = False
            b_groove_passing = False

            #I get the reference of active layer
            ref = gdb.get_reference(part + "\\" + layer)
            vz = ref[2]

            for ent in gdb.get_entities(part + "\\" + layer):
                #holes cycle
                if gdb.get_type(ent) == gdb.EntityType.HOLE:
                    #I get the hole center
                    hole_center = gdb.get_start_point(ent, get_global=True)
                    #I get the hole reference
                    hole_ref = gdb.get_reference(ent)
                    #I get the hole depth
                    hole_depth = gdb.get_depth(ent)

                    #I set the end point
                    end_point = Vec3(0, 0, -hole_depth)
                    glob_point = math.point_to_glob(end_point, hole_center, hole_ref[2], hole_ref[0])

                    #if the end point of the hole is upper the piece, it means the hole is passing so I have to rebate it
                    if vz.z < 0 + EPSILON_NORM:
                        if glob_point.z >= 0:
                            if abs(glob_point.z - piece_ref[1].z) > EPSILON_NORM:
                                ent_list_passing.append(ent)
                                b_hole_to_invert = True
                    else:
                        #if the end point of the hole is under the piece, it means the hole is passing but is from top so I don't have to rebate it
                        if glob_point.z <= (piece_ref[0].z - EPSILON_NORM):
                            ent_list_passing.append(ent)
                            b_hole_to_invert = False

                #I verify grooves from bottom
                elif layer.find("PYTHA_GROOVE") >= 0 or layer.find("PYTHA_ROUTE") >= 0 or layer.find("PYTHA_POCKET") >= 0:
                    if layer.find("PYTHA_ROUTE_X") < 0 and layer.find("PYTHA_ROUTE_Y"):
                        #I ensure the layer is on a top/bottom layer otherwise don't consider it for passing
                        local_depth = gdb.get_local_vector(Vec3(z=-1), part + "\\" + layer)
                        is_vertical_layer = local_depth.z >= 1 - EPSILON_NORM or local_depth.z <= -1 + EPSILON_NORM
                        if is_vertical_layer:
                            #I get DEPTH note
                            depth = gdb.get_note(part + "\\" + layer, "depth")

                            #if the depth of the groove greater the piece dimension, it means is passing
                            if float(depth) >= abs(piece_ref[0].z - piece_ref[1].z):
                                if vz.z < 0 + EPSILON_NORM:
                                    b_groove_passing = True

                #list of passing holes
                if len(ent_list_passing) > 0:
                    layer_created = False
                    self.passing_entities_to_overturn = True

                    for passing_ent in ent_list_passing:
                        #I invert the hole if necessary
                        if b_hole_to_invert:
                            gdb.cad.modify_hole(passing_ent, gdb.get_radius(passing_ent)*2, gdb.get_depth(passing_ent), through=None, hole_type=None, second_diameter=None, second_depth=None, invert=True)

                        #I create a new layer getting the start point of the hole and its angles
                        if not layer_created:
                            hole_ref_angles = gdb.get_ref_angles(passing_ent)
                            point = gdb.get_start_point(passing_ent, get_global=True)

                            if b_hole_to_invert:
                                gdb.add_layer(part, layer + "_pass", ref_type=gdb.RefType.GENERIC, x_pos=point.x, y_pos=point.y, z_pos=point.z)
                                gdb.modify_layer_ref(part + "\\"  +layer + "_pass", 28, ref_type=gdb.RefType.GENERIC, pos_x=point.x, pos_y=point.y, pos_z=point.z, ang1=hole_ref_angles[0], ang2=hole_ref_angles[1], ang3=hole_ref_angles[2])
                            else:
                                gdb.add_layer(part, layer + "_pass", ref_type=gdb.RefType.TOP, x_pos=point.x, y_pos=point.y, z_pos=point.z)
                            layer_created = True

                        #I move the hole in the new layer
                        gdb.change_layer(passing_ent, part + "\\" + layer + "_pass", create_copy=False, keep_pos=True)

                    #If the original layer is now empty, I will delete it
                    if len(gdb.get_entities(part + "\\" + layer)) == 0:
                        layer_to_delete.append(layer)

                    break

                #grooves to be inverted
                elif b_groove_passing:
                    self.passing_entities_to_overturn = True
                    #I get the start point
                    point = gdb.get_start_point(part + "\\" + layer, get_global=True)

                    #I create a new layer getting the stard point of the hole and its angles
                    gdb.add_layer(part, layer + "_pass", ref_type=gdb.RefType.GENERIC, x_pos=point.x, y_pos=point.y, z_pos=point.z)
                    #I copy notes from original layer
                    notes_to_copy = gdb.get_note_string(part + "\\"+ layer)
                    gdb.set_note_string(part + "\\" + layer + "_pass", notes_to_copy)

                    """param_active = parametric.is_active()
                    if param_active:
                        parametric.deactivate()"""

                    #I move the groove to the new layer
                    gdb.change_layer(gdb.get_entities(part + "\\" + layer), part + "\\" + layer + "_pass", create_copy=False, keep_pos=True)
                    hole_ref_angles = gdb.get_ref_angles(part + "\\" + layer + "_pass")

                    #I modify the layer reference for invert the groove
                    gdb.modify_layer_ref(part + "\\" + layer + "_pass", 15, ref_type=gdb.RefType.GENERIC, pos_x=point.x, pos_y=point.y, pos_z=point.z + abs(piece_ref[0].z - piece_ref[1].z), ang1=hole_ref_angles[0], ang2=hole_ref_angles[1])

                    """if param_active:
                        parametric.activate()"""

                    #If the original layer is now empty, I delete it
                    if len(gdb.get_entities(part + "\\" + layer)) == 0:
                        layer_to_delete.append(layer)

                    break

                ent_list_passing = []
        #list of old layers can be deleted because now empty
        if len(layer_to_delete) != 0:
            for lay in layer_to_delete:
                gdb.delete_layer(part + "\\" + lay)


    def execute(self):
        phase = self.get_param("phase")
        b_do_side_workings = self.get_param("side_workings")
        b_nesting_with_pocket = self.get_param("clamex_pocket")
        b_clamex_5ax = self.get_param("clamex_5ax")
        part_to_overturn = 0
        self.passing_entities_to_overturn = False

        #list of piece for which the rebating in second phase for have Inclined Face cut from top
        list_piece_force_rebate_incl_face_from_top = self.get_param("list_piece_force_rebating")
        rotation_axis = self.get_param("rotation_axis")
        if rotation_axis == X_AXIS:
            rotation_axis = int( rotation_axis.replace(rotation_axis, "0"))
        else:
            rotation_axis = int( rotation_axis.replace(rotation_axis, "1"))

        # pieces cycle
        parts = gdb.get_entities("")

        for part in parts:
            b_has_upper_holes = False
            b_has_under_holes = False
            b_has_upper_pockets = False
            b_has_under_pockets = False
            b_has_upper_cuts = False
            b_has_under_cuts = False
            b_has_upper_grooves = False
            b_has_under_grooves = False
            b_has_upper_routes = False
            b_has_under_routes = False
            b_has_side_workings = False
            b_has_upper_clamex = False
            b_has_under_clamex = False
            b_has_inclined_face = False
            b_already_force_second_phase = False
            b_force_first_program = False

            #I create a layer for the raw material, takef from relative exported note from Pytha
            if phase == _FIRST_PHASE:
                self.create_raw_material(part)

            #I verify if there are passing entities from bottom reference and I invert them for work in the first phase
            self.verify_passing_entities_direction(part)

            # layers cycle
            layers = cad.get_layers(part)
            for layer in layers:
                b_is_top = False
                b_is_bottom = False

                ref = gdb.get_reference(part + "\\" + layer)

                #I get the reference of active layer
                vz = ref[2]

                #I skip the control if is a pocket for holes
                if layer.startswith("ForoTascaForatore") or layer.startswith("ForoTascaAggre"):
                    continue

                if vz.z > 0:   #OLD_CONTROL: 1 - EPSILON_NORM
                    b_is_top = True
                else:
                    if vz.z < 0:   #OLD_CONTROL: -1 + EPSILON_NORM
                        b_is_bottom = True
                    else:
                        if phase == _SECOND_PHASE:
                            #for second phase I don't considerate clamex because they have double path PATH/PATH_RETRO for always work in first phase
                            if b_do_side_workings:
                                #if the first phase has the nesting with pockets, clamex is made in first phase so is not considerated in second phase
                                if b_nesting_with_pocket:
                                    if not layer.startswith("CLF") and not layer.startswith("CLM") and not layer.startswith("Inclined_Face"):
                                        b_has_side_workings = True
                                else:
                                    b_has_side_workings = True
                        else:
                            b_has_side_workings = True

                #I verify if there is the force first program by Pytha for disable overturning rotations by here
                if layer.startswith("PYTHA_POCKET") or layer.startswith("PYTHA_ROUTE"):
                    if gdb.get_note(part + "\\" + layer, "tool_name") == "FORCE":
                        b_force_first_program = True

                # Holes layer (not prevously inverted because passing)
                if layer.startswith("Holes") and not layer.find("_pass") > 0:
                    do_debug()
                    if b_is_top:
                        b_has_upper_holes = True
                    else:
                        if b_is_bottom:
                            b_has_under_holes = True

                # Cut layer
                if layer.startswith("PYTHA_CUT"):
                    if b_is_top:
                        b_has_upper_cuts = True
                    else:
                        if b_is_bottom:
                            b_has_under_cuts = True

                # Pocket layer (not prevously inverted because passing)
                if layer.startswith("PYTHA_POCKET") and not layer.find("_pass") > 0:
                    if b_is_top:
                        b_has_upper_pockets = True
                    else:
                        if b_is_bottom:
                            b_has_under_pockets = True

                # Groove layer (not prevously inverted because passing)
                if layer.startswith("PYTHA_GROOVE") and not layer.find("_pass") > 0:
                    if b_is_top:
                        b_has_upper_grooves = True
                    else:
                        if b_is_bottom:
                            b_has_under_grooves = True

                # Layer (not prevously inverted because passing)
                if layer.startswith("PYTHA_ROUTE") and not layer.find("_pass") > 0:
                    if b_is_top:
                        b_has_upper_routes = True
                    else:
                        if b_is_bottom:
                            b_has_under_routes = True

                # Layer Inclined Face
                if layer.startswith("Inclined_Face"):
                    b_has_inclined_face = True

                # Layer macro
                if layer.startswith("CLF") or layer.startswith("CLM"):
                    #\\GROUP
                    for group in gdb.get_entities(part+"\\"+layer):
                        #sub-layer
                        layer_hole = group + "\\HOLE2"
                        for ent in gdb.get_entities(layer_hole):
                            #I verify holes direction in the macro
                            if gdb.get_type(ent) == gdb.EntityType.HOLE:
                                ref_hole_clamex = gdb.get_reference(ent)

                                if ref_hole_clamex[2].z > 0:   #OLD_CONTROL: 1 - EPSILON_NORM
                                    b_has_upper_holes = True
                                elif ref_hole_clamex[2].z < 0:   #OLD_CONTROL: -1 + EPSILON_NORM
                                    b_has_under_holes = True
                    
                    #I verify the clamex female only if is made with 5asxis finishing
                    if b_clamex_5ax:
                        if layer.startswith("CLF"):
                            if b_is_top:
                                b_has_upper_clamex = True
                            else:
                                if b_is_bottom:
                                    b_has_under_clamex = True

            if b_clamex_5ax:
                b_has_under_workings = b_has_under_cuts or b_has_under_grooves or b_has_under_holes or b_has_under_pockets or b_has_under_routes or b_has_under_clamex
                b_has_upper_workings = b_has_upper_cuts or b_has_upper_grooves or b_has_upper_holes or b_has_upper_pockets or b_has_upper_routes or b_has_upper_clamex
            else:
                b_has_under_workings = b_has_under_cuts or b_has_under_grooves or b_has_under_holes or b_has_under_pockets or b_has_under_routes #or b_has_under_clamex
                b_has_upper_workings = b_has_upper_cuts or b_has_upper_grooves or b_has_upper_holes or b_has_upper_pockets or b_has_upper_routes# or b_has_upper_clamex
            #PYTHA_CUT_BEVEL is always from top, I verify if it is the only one from top
            b_has_only_upper_cuts = b_has_upper_cuts and not b_has_upper_grooves and not b_has_upper_holes and not b_has_upper_pockets and not b_has_upper_routes #and not b_has_upper_clamex
            b_has_only_under_clamex = b_has_under_clamex and not b_has_under_grooves and not b_has_under_holes and not b_has_under_pockets and not b_has_under_routes and not b_has_under_cuts

            b_already_overturned = False

            # Overturning management in first phase
            # X: Overturning skipped if there is the force first program by pyhta
            if b_force_first_program:
                #I keep the same rotation
                b_keep_rotation = True
            # 1.I overturn if I have holes from bottom and not from top
            elif b_has_under_holes and not b_has_upper_holes:
                # If I am in first phase I overturn the piece and then the next one
                if phase == _FIRST_PHASE:
                    self.overturn_manage_outline(part, rotation_axis)
                    #need to verify again the passing entites previously inverted
                    if self.passing_entities_to_overturn:
                        #I verify if there are passing entities from bottom reference and I invert them for work in the first phase
                        self.verify_passing_entities_direction(part)

                # If I am in second phase I save it was overturned in first phase
                b_already_overturned = True
            else:
                #2. If I have no workings from top but something from bottom, I need to overturn the piece
                if not b_has_upper_workings and b_has_under_workings and not (b_has_only_under_clamex and b_has_inclined_face):
                    # If I am in first phase I overturn the piece and then the next one
                    if phase == _FIRST_PHASE:
                        self.overturn_manage_outline(part, rotation_axis)
                        #need to verify again the passing entites previously inverted
                        if self.passing_entities_to_overturn:
                            #I verify if there are passing entities from bottom reference and I invert them for work in the first phase
                            self.verify_passing_entities_direction(part)

                    # If I am in second phase I save it was overturned in first phase
                    b_already_overturned = True

            # Overturning calculation for second phase, made in first phase
            #If is the first phase and need to overturn in second phase, I set has to be overtuned in a dedicated note
            if phase == _FIRST_PHASE:
                # 1. If I have something from bottom and piece wasn't overturned in first phase, I need to overtrurn in second phase
                b_to_overturn = False
                if b_has_under_workings and not b_already_overturned:
                    b_to_overturn = True

                # 2. If I had workings from top and piece was overturned I need to overturn also in second phase (now workings from top are from bottom because piece is overtuned)
                if b_has_upper_workings and b_already_overturned:
                    b_to_overturn = True

                # 3. I have lateral workings but I don't need to work in first phase
                if b_has_side_workings and not b_do_side_workings:
                    b_to_overturn = True

                if b_to_overturn:
                    gdb.set_note(part + "\\InfoLabels", "N_Fasi", "1+2")
                else:
                    gdb.set_note(part + "\\InfoLabels", "N_Fasi", "1")

            # Overturning calculation for second phase, made in first phase
            if phase == _SECOND_PHASE:
                #1. Overturning sure if there is the force first program by pyhta and there are under workings (upper workings maed in first phase)
                if b_force_first_program:
                    if b_has_under_workings:
                        self.overturn_manage_outline(part, rotation_axis)
                        b_already_force_second_phase = True
                #2.I force the rebating if the piece is in the list of pieces to be rebated in second phase (for Inclined Phase from top)
                elif list_piece_force_rebate_incl_face_from_top != "" and part in list_piece_force_rebate_incl_face_from_top.split(","):
                    self.overturn_manage_outline(part, rotation_axis)
                    b_already_force_second_phase = True

                #If the only working from top is an inclined cut, it was made if first phase
                elif b_has_only_upper_cuts and not b_has_under_holes and not b_has_under_routes and not b_has_under_pockets and not(b_clamex_5ax and b_has_under_clamex):
                    gdb.delete_part(part)
                    continue
                #If I have no workings from top and side and the piece was already overturned, I delete it
                elif not (b_has_upper_workings or (b_has_side_workings and b_do_side_workings)) and b_already_overturned:
                    gdb.delete_part(part)
                    continue
                #If the piece wasn't overtuned and I don't have any working from bottom and side, I delete it
                elif not b_already_overturned and not ((b_has_side_workings and b_do_side_workings) or b_has_under_workings):
                    gdb.delete_part(part)
                    continue

                #3. If not overtuned in first phase, I have to overturn it
                if not b_already_overturned and not b_already_force_second_phase:
                    self.overturn_manage_outline(part, rotation_axis)

                part_to_overturn = part_to_overturn + 1
                #continue

                # If the piece just have lateral workings and was overtuned, I need overturn again
                #if b_has_side_workings and b_do_side_workings and not b_has_upper_workings and b_already_overturned:
                    #self.overturn_manage_outline(part, rotation_axis)
                    #continue

        if  phase == _SECOND_PHASE and part_to_overturn > 0:
            self.set_param("cont_to_overturn", str(part_to_overturn))

class PythaGetEWXName(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2207), "", "Pytha")
        
        self.register_param("part_name", ParamType.INPUT, get_msg(2064), "")
        self.register_param("ewx_file_name", ParamType.OUTPUT, "", "")

    def execute(self):
        part_name = self.get_param("part_name")

        ewx_file_name = gdb.get_note(part_name + "\\InfoLabels", "EWX_File_Name")
        # rimuovo estensione
        last_dot_index = ewx_file_name.rfind('.')
        ewx_file_name = ewx_file_name[0 : last_dot_index]
        self.set_param("ewx_file_name", ewx_file_name)

class PythaGetCabinetName(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2208), "", "Pytha")
        
        self.register_param("group_name", ParamType.INPUT, get_msg(2206), "")
        self.register_param("cabinet_name", ParamType.OUTPUT, "", "")

    def execute(self):
        group = self.get_param("group_name")
        if group == "":
            group = ewd.groups.get_current()
        parts = ewd.groups.get_parts(group)
        cabinet_name = gdb.get_note(parts[0] + "\\InfoLabels", "part_attribute74")
        cabinet_name = cabinet_name.strip("/")
        self.set_param("cabinet_name", cabinet_name)
            
class PythaGetMaterialName(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2209), "", "Pytha")
        
        self.register_param("Char_Mat", ParamType.INPUT, get_msg(2210), "")
        self.register_param("Material_name", ParamType.OUTPUT, "", "")

    def execute(self):
        group = ewd.groups.get_current()
        parts = ewd.groups.get_parts(group)

        #With nesting
        if gdb.exist(parts[0] + "\\%%NESTDATA", allow_reserved=True):
            material_name = gdb.get_note(parts[0] + "\\%%NESTDATA", "NMTR")
            material_name = material_name.strip("/")
        else:
            #I get info from core material
            material_name = gdb.get_note(parts[0] + "\\InfoLabels", "core_material")
            material_name = material_name.strip("/")
            #if core material is not set, I get material info
            if len(material_name) == 0:
                material_name = gdb.get_note(parts[0] + "\\InfoLabels", "material")
                material_name = material_name.strip("/")

        #I get separator char
        SepChar = self.get_param("Char_Mat")
        if len(SepChar) > 0:
            if SepChar in material_name:
                #I get material name
                material_name = material_name[0:material_name.index(SepChar)]

        self.set_param("Material_name", material_name)

class PythaGetProjectName(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2211), "", "Pytha")
        
        self.register_param("group_name", ParamType.INPUT, get_msg(2206), "")
        self.register_param("project_name", ParamType.OUTPUT, "", "")
    
    def execute(self):
        group = self.get_param("group_name")
        if group == "":
            group = ewd.groups.get_current()
        parts = ewd.groups.get_parts(group)
        cabinet_name = gdb.get_note(parts[0] + "\\InfoLabels", "Project Title")
        self.set_param("project_name", cabinet_name)

class PythaManageGrain(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2218), "", "Pytha")
        
        self.register_param("material_filter", ParamType.INPUT, get_msg(2213), "ven_")
        self.register_param("Char_Mat", ParamType.INPUT, get_msg(2210), "")
    
    def execute(self):
        material_filter = self.get_param("material_filter")
        
        if not material_filter:
            return

        material_filter = material_filter.lower()

        #I cycle all the pieces and verify by the material name
        #if nesting rotation has to be disabled
        group = ewd.groups.get_current()
        part_name = ewd.groups.get_parts(group)[0]

        #I get info from core material
        material_name = gdb.get_note(part_name + "\\InfoLabels", "core_material")
        material_name = material_name.strip("/")
        #if core material is not set, I get material info
        if len(material_name) == 0:
            material_name = gdb.get_note(part_name + "\\InfoLabels", "material")
            material_name = material_name.strip("/")

        if material_name.lower().startswith(material_filter):
            gdb.set_note(part_name, "NART", 0)
            gdb.set_note(part_name, "NRST", 180)
            gdb.set_note(part_name, "NRAN", "0")
            remove_cnt = len(material_filter)
            material_name = material_name[remove_cnt:]
        else:
            #I don't set the rotation note if already previously set in some other operation
            value = str(gdb.get_note(part_name, "NART"))
            if value == "":
                gdb.set_note(part_name, "NART", 1)

        #I get the separator char
        SepChar = self.get_param("Char_Mat")
        if len(SepChar) > 0:
            if SepChar in material_name:
                #I get the material name
                material_name = material_name[0:material_name.index(SepChar)]

        #I set the material for the nesting
        gdb.set_note(part_name, "NMTR", material_name)
                
class SetEwxPath(BaseOperation):
    # Set the ewx file path, because is the same path in which are saved emf labels exported by Pytha (if they exist)
    def __init__(self):
        super().__init__(get_msg(2219), "", "Pytha")

        self.register_param("part", ParamType.INPUT, get_msg(2064), "")
        self.register_param("directory", ParamType.INPUT, "Ewx_directory", "")

    def execute(self):
        part = self.get_param("part")
        directory = self.get_param("directory")
        gdb.set_note(part + "\\InfoLabels", "Ewx_directory", directory)

    def _get_abs_path(self, path=None):
        if not path:
            return
        
        net_use = subprocess.check_output(['net', 'use']).decode("utf-8").splitlines()
        drive = path[0:2]
        abs_path = None
        for line in net_use:
            if drive in line:
                abs_path = line[line.index('\\'):-1]
                break

        if abs_path:
            path = path.replace(drive, abs_path)
            path = r'%s' % path
            return path
        
        return path

class ForceInclinedCutFromTop(BaseOperation):
    """
    Fucntion for force the second phase if the Inclined Face normal direction is from bottom after rebating in first phase(customer SamArreda who works with a tool, not a blade)
    """
    def __init__(self):
        super().__init__(get_msg(2225), "", "Pytha")

        self.register_param("list_piece_force_rebating", ParamType.OUTPUT, "", "")


    def execute(self):
        piece_list = []

        # parts cycle
        parts = gdb.get_entities("")

        for part in parts:

            # layer cycle
            layers = cad.get_layers(part)
            for layer in layers:
                # Layer Inclined Face
                if layer.startswith("Inclined_Face"):
                    #I copy in a fitting global layer
                    gdb.add_layer(part, "Temp")
                    new_name = gdb.copy_object(gdb.get_entities(part + "\\" + layer)[0], part + "\\Temp", True)

                    surf_norm = gdb.surf.get_normal(part + "\\Temp\\" + new_name)
                    gdb.delete_layer(part + "\\Temp")

                    #if the normal is smaller then 0 it is from bottom
                    if surf_norm.z < 0:
                        piece_list.append(part)
                        #I rename the layer for not work in first phase
                        gdb.rename_layer(part + "\\" + layer, "No_Inclined_Face")

        #I set the list of pieces to force the rebating in second phase
        self.set_param("list_piece_force_rebating", ",".join(piece_list))