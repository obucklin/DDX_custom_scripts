import ewd
import gzip
import os
import math
import csv
import time
from contextlib import contextmanager
from ddx import gdb, math as ewd_math
from ddx.gdb import cad, path, param as parametric, region
from ewd.msg import get_compo_msg as get_msg
from ddx.autoexec import BaseOperation, ParamType
from sclcore import Vec3
from sclcore import do_debug
from ddx.confdlg import ConfigHelperDict, ConfigParamType
from ddx.math import EPSILON_NORM

ROT_GROOVE_X = "X_groove"
ROT_GROOVE_Y = "Y_groove"
NO_ROT = "No_Rot"
ROT_GROOVE_TOP = "Top_groove"
ROT_GROOVE_BOTT = "Down_groove"
ROT_HOLES_TOP = "Top_holes"
ROT_HOLES_BOTT = "Down_holes"
EDGEBAND_RETT = "Edgeband_with_rect"
EDGEBAND_NO_RETT = "Edgeband_no_rect"
COND_TRUE = "TRUE"
COND_FALSE = "FALSE"
ROT_90 = "90"
ROT_180 = "180"
ROT_270 = "270"
RECT_OUTLINE = "Outline_rect"
SLACK_OUTLINE = "Outline_slack"
T_F = [(True, COND_TRUE), (False, COND_FALSE)]
ROT_LIST = [(ROT_90, ROT_90), (ROT_180, ROT_180), (ROT_270, ROT_270)]
N_ERR = 0.001
MAX_NUM_ROWS = 5
_GET = 0
_SET = 1
EPSILON = 1e-3

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

def get_piece_name():
    """
    Function for obtein the current piece name
    """
    if ewd.get_active_module() != ewd.Modules.CAM:
        ewd.set_active_module(ewd.Modules.CAM)
    part_name = ewd.mach.get_current_piece()

    return part_name

def get_real_angle_entity(part, s_ent):
    """
    Function for obtein the entity direction after a piece rotation
    Rotating a piece, layer will be rotated consequentelly, so the local angle will be alwayas the same --> I move the entity in a top fitting layer and I calculated the real angle there
    """

    #Create the fitting layer
    gdb.add_layer(part, "TEMP")
    #move the entity on it
    gdb.change_layer(s_ent, part+"\\TEMP", create_copy=True, keep_pos=True)
    #calculate the real direction
    ent_dir = gdb.get_angle(gdb.get_entities(part + "\\TEMP")[0])
    #delete the fitting layer
    gdb.delete_layer(part+"\\TEMP")

    return ent_dir

def equal(n1: float, n2: float) -> bool:
    """calculates if two passed values are equal based on the passed delta

    :param n1: first value
    :type n1: float
    :param n2: second value
    :type n2: float
    :param delta: delta limit for the floating point, defaults to math.EPSILON
    :type delta: float, optional
    :return: True if the difference is within the delta, else False
    :rtype: bool
    """
    return abs(n1 - n2) <= EPSILON

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


def is_vertical(line: str) -> bool:
    """Checks if the passed line is vertical based on it's extension

    :param line: the line to check
    :type line: str
    :return: True if it's vertical otherwise False
    :rtype: bool
    """
    p_min, p_max = gdb.get_extension(line)

    return True if abs(p_max.y - p_min.y) < ewd_math.EPSILON else False


def is_horizontal(line: str) -> bool:
    """Checks if the passed line is horizontal based on it's extension

    :param line: the line to check
    :type line: str
    :return: True if it's vertical otherwise False
    :rtype: bool
    """
    p_min, p_max = gdb.get_extension(line)

    return True if abs(p_max.x - p_min.x) < ewd_math.EPSILON else False


def is_on_contour(entity: str, cont_path: str) -> bool:
    """Checks if the passed entity is positioned along the contour in the passed path

    :param entity: the entity to check whether it is on contour
    :type entity: str
    :param cont_path: path containing the contour
    :type cont_path: str
    :return: True if at least two intersections have been found, otherwise False
    :rtype: bool
    """
    if not is_horizontal(entity) and not is_vertical(entity):
        return False

    for side in gdb.get_entities(cont_path):
        with temp_layer(hint="TEMP", new_part=True) as temp_path_outline:
            gdb.change_layer(side, temp_path_outline, True, True)
            with temp_layer(hint="TEMP", new_part=True) as temp_path:
                gdb.change_layer(entity, temp_path, True, True)
                n_int = len(path.get_intersections(temp_path, temp_path_outline))
                if n_int >= 2:
                    return True
    return False


def get_outline_path(part_name: str) -> str:
    outline_path = gdb.join_path(part_name, get_layer_by_importer("LAYER_CONTORNA"))
    if not gdb.exist(outline_path):
        outline_path = gdb.join_path(part_name, get_layer_by_importer("LAYER_CONTORNA_NO_OVERDIM"))
        if not gdb.exist(outline_path):
            return ""
    return outline_path


class SetInfolabelNote(BaseOperation):
    """
    Class for set a new value to a specific InfoLabel
    """
    def __init__(self):
        super().__init__(get_msg(2244), "", get_msg(2049))
        self.register_param("piece_name", ParamType.INPUT, get_msg(2166), "")
        self.register_param("infolabel_name", ParamType.INPUT, get_msg(2246), "")
        self.register_param("infolabel_value", ParamType.INPUT, get_msg(2247), "")

    def execute(self):
        piece_name = self.get_param("piece_name")
        if not piece_name:
            piece_name = get_piece_name()
        infolabel_name = self.get_param("infolabel_name")
        infolabel_value = self.get_param("infolabel_value")
        infolabels_path = gdb.join_path(piece_name, "Infolabels")
        if gdb.exist(piece_name):
            if not gdb.exist(infolabels_path):
                gdb.add_layer(piece_name, "Infolabels")
            gdb.set_note(infolabels_path, infolabel_name, infolabel_value)


class GetInfolabelNote(BaseOperation):
    """
    Class for get the actualvalue to a specific InfoLabel
    """
    def __init__(self):
        super().__init__(get_msg(2245), "", get_msg(2049))
        self.register_param("piece_name", ParamType.INPUT, get_msg(2166), "")
        self.register_param("infolabel_name", ParamType.INPUT, get_msg(2246), "")
        self.register_param("infolabel_value", ParamType.OUTPUT, get_msg(2247), "")

    def execute(self):
        piece_name = self.get_param("piece_name")
        if not piece_name:
            piece_name = get_piece_name()
        infolabel_name = self.get_param("infolabel_name").strip()
        infolabels_path = gdb.join_path(piece_name, "Infolabels")
        infolabel_value = ""

        if gdb.exist(infolabels_path):
            infolabel_value = gdb.get_note(infolabels_path, infolabel_name)
        self.set_param("infolabel_value", infolabel_value)

class PythaGetPieceName(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2248), "", get_msg(2049))
        
        self.register_param("piece_name", ParamType.INPUT, get_msg(2206), "")
        self.register_param("curr_piece_name", ParamType.OUTPUT, "", "")

    def execute(self):
        piece_name = self.get_param("piece_name")
        if piece_name == "EWX":
            piece_name = ewd.groups.get_current()
        elif piece_name == "PIECE":
            piece_name = get_piece_name()
        if not piece_name:
            piece_name = get_piece_name()

        self.set_param("curr_piece_name", piece_name)

class EntityInfo():
    """
    Class entity info
    """
    def __init__(self, path):
        self.path = path
        self.width = 0
        self.height = 0
        self.heidepthght = 0

        self.get_dimensions()

    def get_dimensions(self):
        """
        Fucntion that calculates entity dimensions
        """
        points = gdb.get_extension(self.path)
        self.pt_min = points[0]
        self.pt_max = points[1]
        self.width = abs(self.pt_max.x - self.pt_min.x)
        self.height = abs(self.pt_max.y - self.pt_min.y)
        self.depth = abs(self.pt_max.z - self.pt_min.z)


class GetPieceDimensions(BaseOperation):
    """
    Class for calculate pieces dimensions
    """
    def __init__(self):
        super().__init__(get_msg(2185), "", get_msg(2000))
        self.register_param("part_name", ParamType.INPUT, get_msg(2064), "")
        self.register_param("width", ParamType.OUTPUT, "", 0)
        self.register_param("height", ParamType.OUTPUT, "", 0)
        self.register_param("depth", ParamType.OUTPUT, "", 0)

    def execute(self):
        """[summary]
        """
        part_name = self.get_param("part_name")

        if not part_name:
            part_name = get_piece_name()

        # path to box solid group
        path = part_name + "\\%%MACH\\%%BOX\\SOLID"
        #Took dimensions
        loc = EntityInfo(path)

        self.set_param("width", loc.width)
        self.set_param("height", loc.height)
        self.set_param("depth", loc.depth)

class ManageGeometries(BaseOperation):
    """
    Class for manage and rename imported geometries
    """
    tool_names_on_driller = []     #by tools.tool
    tool_diams_on_driller = []     #by tools.tool
    cont_tools = 0              #by tools.tool
    zp_drill = []            #list of vertical drillsby drillgroup.dru
    yp_drill = []            #list of vertical drillsby drillgroup.dru
    ym_drill = []            #list of vertical drillsby drillgroup.dru
    xp_drill = []            #list of vertical drillsby drillgroup.dru
    xm_drill = []            #list of vertical drillsby drillgroup.dru
    drills_info = {}

    def __init__(self):
        super().__init__(get_msg(2186), "", get_msg(2000))

        self.config = None

    def init_operation(self, config):
        self.register_param("layer_drills_NoMultipleDrillHead", ParamType.INPUT, get_msg(2158), "-")
        self.register_param("layer_drills_inclined", ParamType.INPUT, get_msg(2159), "-")

        self.register_param("Name_groove_on_x", ParamType.INPUT, get_msg(2160), "-")
        self.register_param("Name_groove_on_y", ParamType.INPUT, get_msg(2161), "-")

        outline_slacks_options = [(RECT_OUTLINE, get_msg(2240)), (SLACK_OUTLINE, get_msg(2241))]
        self.register_param("outline_slacks_on_board", ParamType.INPUT, get_msg(2239), RECT_OUTLINE, outline_slacks_options)

        self.register_param("through_drill_became_open", ParamType.INPUT, get_msg(2277), False)

        self.register_param("part_name", ParamType.INPUT, get_msg(2166), "")

        #I save the threshold list
        self.config = config

    def manage_tools_file(self):
        """
        function for read the number of tools loaded on multiple driller head (by tools.tol I check for Head 61)
        """

        tool_diam = 0
        is_tool = False
        tool_code = ""
        self.tool_names_on_driller = []
        self.tool_diams_on_driller = []

        #I unzip+open tools file
        with gzip.open(ewd.explode_file_path("%MACHPATH%\\tools.tol")) as file_name:
            for line in file_name:
                #delet beginning/ending spaces
                line = line.decode("utf-8").strip()
                if line.find("[UTE") == 0:
                    #I set main info about tool (name and diameter) in the relatves arrays
                    #from the second (I got info about first and wrote from the second)
                    if self.cont_tools > 0 and is_tool:
                        self.tool_names_on_driller.append(tool_code)
                        self.tool_diams_on_driller.append(tool_diam)

                    is_tool = True
                #I set main info about tool (name and diameter) in the relatves arrays
                elif line.find("[HOLD") == 0:
                    if self.cont_tools > 0 and is_tool:
                        self.tool_names_on_driller.append(tool_code)
                        self.tool_diams_on_driller.append(tool_diam)

                    is_tool = False
                #I get tool name
                elif line.find("Code=") == 0 and is_tool:
                    tool_code = line.replace("Code=", "")
                #I get head type
                elif line.find("TypeInc=") == 0 and is_tool:
                    assembly = line.replace("TypeInc=", "")
                    #it's loaded on multiple driller head?
                    if assembly == "61":
                        is_tool = True
                        self.cont_tools = self.cont_tools + 1
                    else:
                        is_tool = False
                #I get tool diameter
                elif line.find("DiamMax=") == 0 and is_tool:
                    tool_diam = float(line.replace("DiamMax=", ""))

            #I set main info about tool (name and diameter) in the relatves arrays
            if self.cont_tools > 0 and is_tool:
                self.tool_names_on_driller.append(tool_code)
                self.tool_diams_on_driller.append(tool_diam)

    def manage_dru_file(self):
        """
        function for read the tools loaded on multiple driller head (by drillgroup.dru) saving their relative diameters
        """
        tools_on_dru = []

        #I unzip+open dru file
        with gzip.open(ewd.explode_file_path("%MACHPATH%\\DrillGroups.dru")) as file_name:
            for line in file_name:
                #delet beginning/ending spaces
                line = line.decode("utf-8").strip()
                if line.find("List") == 0:
                    tools_on_dru = line.replace("List=", "").split(",")
                    for tool in tools_on_dru:
                        if tool[0:2].upper() == "ZP":
                            n_split = tool.find("=")
                            #array of vertical drills
                            self.zp_drill.append(self.get_drill_diam_from_tool_name(tool[n_split+1:]))
                        elif tool[0:2].upper() == "YP":
                            n_split = tool.find("=")
                            #array of YP drills
                            self.yp_drill.append(self.get_drill_diam_from_tool_name(tool[n_split+1:]))
                        elif tool[0:2].upper() == "YM":
                            n_split = tool.find("=")
                            #array of YM drills
                            self.ym_drill.append(self.get_drill_diam_from_tool_name(tool[n_split+1:]))
                        elif tool[0:2].upper() == "XP":
                            n_split = tool.find("=")
                            #array of XP drills
                            self.xp_drill.append(self.get_drill_diam_from_tool_name(tool[n_split+1:]))
                        elif tool[0:2].upper() == "XM":
                            n_split = tool.find("=")
                            #array of XM drills
                            self.xm_drill.append(self.get_drill_diam_from_tool_name(tool[n_split+1:]))

            #Set dictionary about drills diameters, divided by direction
            self.drills_info["ZP"] = self.zp_drill
            self.drills_info["YP"] = self.yp_drill
            self.drills_info["YM"] = self.ym_drill
            self.drills_info["XP"] = self.xp_drill
            self.drills_info["XM"] = self.xm_drill


    def get_drill_diam_from_tool_name(self, compare):
        """
        function for export the drill diameter taken by tool name (mathcing data from drillgroup.dru and tools.tol)
        """

        for num in range(self.cont_tools):
            if compare == self.tool_names_on_driller[num]:
                return self.tool_diams_on_driller[num]
    def match_drill_on_driller_head(self, key, diam):
        """
        function that matches drill diameter entity with dictionaries of loaded diameter tools on driller head
        """

        find = False
        #I get the list of drill diamaters in this direction (ZP/YP/YM/XP/XM)
        for drill in self.drills_info[key]:
            #if the diameter compairs in the list, it is in the driller head
            if str(drill) == str(diam):
                find = True
                return find

        return find

    def manage_back_groove(self, path):
        """[summary]

        :param path: layer to manage
        :type path: str
        """
        threshold_list = []
        groove_num = 1

        part = path.split("\\")[0]
        layer = path.split("\\")[1]

        try:
            # I get threshold list
            for elem in self.config["back_threshold"]:
                # if the threshold column has valid values, I add them in a list of valid thresholds
                if len(elem.values()) != 0 and elem["var_name"] != "":
                    threshold_list.append(float(elem["var_name"]))
            # I order the list
            threshold_list.sort()
        except KeyError:
            pass

        if gdb.get_reference(part + "\\" + layer)[2].z != -1:
            #if list is empty I don't manage any threshold
            if len(threshold_list) != 0:
                #I chain closed entities and cycle them
                while groove_num <= gdb.path.chain(path):
                    min_val = 0

                    if not gdb.exist(path.replace(path.split("\\")[1], "TEMP")):
                        gdb.add_layer(part, "TEMP")

                    extract_layer = path.replace(path.split("\\")[1], "TEMP")
                    gdb.path.extract(path, groove_num, extract_layer)

                    #I calculate groove dimensions using the smallest one
                    groove_length = abs(gdb.get_extension(extract_layer)[1].x - gdb.get_extension(extract_layer)[0].x)
                    groove_width = abs(gdb.get_extension(extract_layer)[1].y - gdb.get_extension(extract_layer)[0].y)
                    dim_to_compare = min(groove_length, groove_width)

                    #just one threshold
                    if len(threshold_list) == 1:
                        if dim_to_compare <= threshold_list[0]:
                            if not gdb.exist(part + "\\" + layer + "_SGL1"):
                                gdb.add_layer(part, layer + "_SGL1")

                            gdb.change_layer(gdb.get_entities(extract_layer), part + "\\" + layer + "_SGL1", create_copy=False, keep_pos=True)
                        else:
                            if not gdb.exist(part + "\\" + layer + "_SGL2"):
                                gdb.add_layer(part, layer + "_SGL2")

                            gdb.change_layer(gdb.get_entities(extract_layer), part + "\\" + layer + "_SGL2", create_copy=False, keep_pos=True)
                    #several thresholds
                    elif len(threshold_list) > 1:
                        n_list_elem = 1

                        while n_list_elem <= len(threshold_list):
                            max_val = threshold_list[n_list_elem-1]

                            if dim_to_compare > min_val and dim_to_compare <= max_val:
                                if not gdb.exist(part + "\\" + layer + "_SGL" + str(n_list_elem)):
                                    gdb.add_layer(part, layer + "_SGL" + str(n_list_elem))

                                gdb.change_layer(gdb.get_entities(extract_layer), part + "\\" + layer + "_SGL" + str(n_list_elem), create_copy=False, keep_pos=True)
                                #return
                            if dim_to_compare > max_val and n_list_elem == len(threshold_list):
                                if not gdb.exist(part + "\\" + layer + "_SGL" + str(n_list_elem+1)):
                                    gdb.add_layer(part, layer + "_SGL" + str(n_list_elem+1))

                                gdb.change_layer(gdb.get_entities(extract_layer), part + "\\" + layer + "_SGL" + str(n_list_elem+1), create_copy=False, keep_pos=True)
                                #return

                            min_val = max_val
                            n_list_elem += 1
                    groove_num += 1

                #I delete unusefull layers
                gdb.delete_layer(path)
                gdb.delete_layer(part + "\\TEMP")

    def manage_holes(self, path, n_cont):
        """
        function that verifies holes if they can be worked by driller head, otherwise renamed for be worked by the main head

        :param path: entity path
        :type path: str
        :param n_cont: number for renomination of the layer
        :type n_cont: num
        """
        b_is_hole_top = False
        b_is_hole_bott = False
        b_is_hole_front = False
        b_is_hole_back = False
        b_is_hole_left = False
        b_is_hole_rigth = False
        b_is_hole_incl = False
        is_horiz = False
        is_ok = True

        layer_drills_no_multiple_drill_head = self.get_param("layer_drills_NoMultipleDrillHead")
        layer_drills_inclined = self.get_param("layer_drills_inclined")
        through_drill_became_open = self.get_param("through_drill_became_open")

        #I get info from path
        part = path.split("\\")[0]
        lay = path.split("\\")[1]
        ent = path
        #I get the original thickness of the piece
        part_points = gdb.get_extension(part + "\\%%SOLID")
        part_thickness = abs(part_points[0].z - part_points[1].z)

        #I get the ref
        hole_z_ref = gdb.get_reference(ent)[2]
        #I get the diameter and depth
        hole_diam = round(gdb.get_radius(ent) * 2, 2)
        hole_depth = gdb.get_depth(ent)

        #I get round the diameter to the prev. integer diameter, changing the color of the geometry
        b_modified_diam = self.round_and_color_hole(hole_diam, hole_depth, ent)

        #I get the hole direction
        if hole_z_ref.z == 1:
            b_is_hole_top = True
        elif hole_z_ref.z == -1:
            b_is_hole_bott = True
        elif hole_z_ref.y == 1:    #dir.Y+
            b_is_hole_front = True
        elif hole_z_ref.y == -1:    #dir.Y-
            b_is_hole_back = True
        elif hole_z_ref.x == 1:    #dir.X+
            b_is_hole_left = True
        elif hole_z_ref.x == -1:   #dir.X-
            b_is_hole_rigth = True
        else:
            b_is_hole_incl = True

        #I make the hole open, is it is passing (only on vertical drills)
        if b_is_hole_top and through_drill_became_open:
            if hole_depth >= part_thickness:
                cad.modify_hole(ent, hole_diam, hole_depth, True, None, None, None, None)
                black_mat = gdb.cad.StandardColors.BLACK
                gdb.cad.set_material(ent, color=black_mat)

        #I rename if the hole diam is not in the multiple driller head
        if layer_drills_no_multiple_drill_head != "-":
            #vertical drill
            if b_is_hole_top:
                is_ok = self.match_drill_on_driller_head("ZP", hole_diam)
            #vertical drill
            elif b_is_hole_bott:
                #drill from bottom will be managed in second phase
                is_ok = True
            #horizontal drills
            elif b_is_hole_front:   #dir.Y+
                is_ok = self.match_drill_on_driller_head("YP", hole_diam)
                is_horiz = True
            elif b_is_hole_back:   #dir.Y-
                is_ok = self.match_drill_on_driller_head("YM", hole_diam)
                is_horiz = True
            elif b_is_hole_left:    #dir.X+
                is_ok = self.match_drill_on_driller_head("XP", hole_diam)
                is_horiz = True
            elif b_is_hole_rigth:   #dir.X-
                is_ok = self.match_drill_on_driller_head("XM", hole_diam)
                is_horiz = True

            #I change layer if the drill diameter is not matched on driller head
            if not is_ok and not b_modified_diam:
                #I create the new vertical layer
                if not is_horiz:
                    if not gdb.exist(part + "\\" + layer_drills_no_multiple_drill_head + "_vert"):
                        gdb.add_layer(part, layer_drills_no_multiple_drill_head + "_vert")

                    #I change the layer
                    gdb.change_layer(ent, part + "\\" + layer_drills_no_multiple_drill_head + "_vert", create_copy=False, keep_pos=True)
                #I create the new horiz layer
                else:
                    #I create local layer
                    if hole_z_ref.y == 1:    #dir.Y+
                        if not gdb.exist(part + "\\" + layer_drills_no_multiple_drill_head + "_horizBack"):
                            gdb.add_layer(part, layer_drills_no_multiple_drill_head + "_horizBack", ref_type=gdb.RefType.BACK, x_pos=0, y_pos=0, z_pos=0)

                        #I change the layer
                        gdb.change_layer(ent, part + "\\" + layer_drills_no_multiple_drill_head + "_horizBack", create_copy=False, keep_pos=True)

                    if hole_z_ref.y == -1:    #dir.Y-
                        if not gdb.exist(part + "\\" + layer_drills_no_multiple_drill_head + "_horizFront"):
                            gdb.add_layer(part, layer_drills_no_multiple_drill_head + "_horizFront", ref_type=gdb.RefType.FRONT, x_pos=0, y_pos=0, z_pos=0)

                        #I change the layer
                        gdb.change_layer(ent, part + "\\" + layer_drills_no_multiple_drill_head + "_horizFront", create_copy=False, keep_pos=True)

                    if hole_z_ref.x == 1:    #dir.X+
                        if not gdb.exist(part + "\\" + layer_drills_no_multiple_drill_head + "_horizRight"):
                            gdb.add_layer(part, layer_drills_no_multiple_drill_head + "_horizRight", ref_type=gdb.RefType.RIGHT, x_pos=0, y_pos=0, z_pos=0)

                        #I change the layer
                        gdb.change_layer(ent, part + "\\" + layer_drills_no_multiple_drill_head + "_horizRight", create_copy=False, keep_pos=True)

                    if hole_z_ref.x == -1:    #dir.X-
                        if not gdb.exist(part + "\\" + layer_drills_no_multiple_drill_head + "_horizLeft"):
                            gdb.add_layer(part, layer_drills_no_multiple_drill_head + "_horizLeft", ref_type=gdb.RefType.LEFT, x_pos=0, y_pos=0, z_pos=0)

                        #I change the layer
                        gdb.change_layer(ent, part + "\\" + layer_drills_no_multiple_drill_head + "_horizLeft", create_copy=False, keep_pos=True)


        #I rename inclined drills layer
        if b_is_hole_incl and layer_drills_inclined != "-":
            #If I have more entities
            #for ent in gdb.get_entities(part + "\\" + lay):
            new_layer = layer_drills_inclined + "(" + str(n_cont) + ")"

            #I clone the original layer and its references
            gdb.clonate_layer(part + "\\" + lay, part, new_layer)
            gdb.reset_layer(part + "\\" + new_layer)

            gdb.change_layer(ent, part + "\\" + new_layer)
            n_cont += 1

            #delete the original (now empty) layer
            #gdb.delete_layer(part + "\\" + lay)

    def rename_back_groove(self, part, lay):
        """
        function for rename the back groove by its direction

        :param part: the part to verify
        :type part: string
        :param lay: layer imported
        :type lay: string
        """
        n_groove_cont = 0
        for layer in gdb.get_entities(part):
            s_threshold_info = ""
            if get_layer_by_importer(lay) in layer:
                entities = gdb.get_entities(layer)
                max_length = 0
                max_ent = ""
                for ent in entities:
                    #I take the max length entity
                    if max(max_length, gdb.get_length(ent)) == gdb.get_length(ent):
                        max_length = gdb.get_length(ent)
                        max_ent = ent

                #I get the direction of longest entity
                #before, I am costrict to move on a top layer because the possibile piece rotation rotated also layers, so local angle will be always the same
                ent_dir = get_real_angle_entity(part, max_ent)

                #if the threshold info is set, I save and preserv it
                if layer.find("_SGL") > 0:
                    s_threshold_info = layer[layer.find("_SGL"):]

                #if the direction is on x/y --> I rename the layer
                if abs(ent_dir - 270) <= N_ERR or abs(ent_dir - 90) <= N_ERR or abs(ent_dir + 90) <= N_ERR:
                    n_groove_cont = n_groove_cont + 1
                    gdb.rename_layer(layer, self.get_param("Name_groove_on_y") + "(" + str(n_groove_cont) + ")" + s_threshold_info)
                if abs(ent_dir - 0) <= N_ERR or abs(ent_dir - 180) <= N_ERR or abs(ent_dir - 360) <= N_ERR:
                    n_groove_cont = n_groove_cont + 1
                    gdb.rename_layer(layer, self.get_param("Name_groove_on_x") + "(" + str(n_groove_cont) + ")" + s_threshold_info)


    def GetDiamExcess(self, ndiam):
        """function that calculates the excess of the diam to the prev integer diam value (es.8.2 --> excess = 0.2)

        :param ndiam: hole diam to round
        :type ndiam: float
        """
        param = []

        #I get the excess of the integer diameter (ex.0.2)
        integer_diam = math.floor(ndiam)
        excess = round(ndiam - integer_diam, 2)
        param.append(integer_diam)
        param.append(excess)

        return param


    def round_and_color_hole(self, diam, depth, entity):
        """Function for aproximate the hole diameter to the prev. and color it with a dedicated RGB

        :param diam: hole to verify
        :type diam: float
        :param depth: hole to verify
        :type depth: float
        :param entity: entity to verify
        :type entity: strring
        """
        excess = 0
        b_modified = False

        #I get blind holes info
        if self.config is not None:
            try:
                if "drills_blind_decimal" in self.config:
                    if "dec_blind_drill" in self.config["drills_blind_decimal"]:
                        blind_dec = self.config["drills_blind_decimal"]["dec_blind_drill"]
                        if blind_dec == "":
                            blind_dec = "0.0"

                        integer_diam = self.GetDiamExcess(diam)[0]
                        excess = self.GetDiamExcess(diam)[1]
            except KeyError:
                pass

            #I get passing holes info
            try:
                if "drills_passing_decimal" in self.config:
                    if "dec_passing_drill" in self.config["drills_passing_decimal"]:
                        passing_dec = self.config["drills_passing_decimal"]["dec_passing_drill"]
                        if passing_dec == "":
                            passing_dec = "0.0"

                        integer_diam = self.GetDiamExcess(diam)[0]
                        excess = self.GetDiamExcess(diam)[1]
            except KeyError:
                pass

            #I get sink holes info
            try:
                if "drills_sink_decimal" in self.config:
                    if "dec_sink_drill" in self.config["drills_sink_decimal"]:
                        sink_dec = self.config["drills_sink_decimal"]["dec_sink_drill"]
                        if sink_dec == "":
                            sink_dec = "0.0"

                        integer_diam = self.GetDiamExcess(diam)[0]
                        excess = self.GetDiamExcess(diam)[1]
            except KeyError:
                pass

            #I get recess holes info
            try:
                if "drills_recess_decimal" in self.config:
                    if "dec_recess_drill" in self.config["drills_recess_decimal"]:
                        recess_dec = self.config["drills_recess_decimal"]["dec_recess_drill"]
                        if recess_dec == "":
                            recess_dec = "0.0"

                        integer_diam = self.GetDiamExcess(diam)[0]
                        excess = self.GetDiamExcess(diam)[1]
            except KeyError:
                pass

        if excess != 0 and (excess == float(blind_dec) or excess == float(passing_dec) or excess == float(sink_dec) or excess == float(recess_dec)):
            #I modify the hole setting the integer diam
            gdb.cad.modify_hole(entity, integer_diam, depth)
            b_modified = True

            #I color the entity
            green_mat = gdb.cad.StandardColors.GREEN
            yellow_mat = gdb.cad.StandardColors.YELLOW
            blue_mat = gdb.cad.StandardColors.BLUE
            red_mat = gdb.cad.StandardColors.RED

            try:
                if blind_dec != "" and abs(float(blind_dec) - excess) < 0.01:
                    if self.config["drills_blind_decimal"]["colour_blind_drill"] == "GREEN":
                        gdb.cad.set_material(entity, color=green_mat)
                    if self.config["drills_blind_decimal"]["colour_blind_drill"] == "YELLOW":
                        gdb.cad.set_material(entity, color=yellow_mat)
                    if self.config["drills_blind_decimal"]["colour_blind_drill"] == "BLUE":
                        gdb.cad.set_material(entity, color=blue_mat)
                    if self.config["drills_blind_decimal"]["colour_blind_drill"] == "RED":
                        gdb.cad.set_material(entity, color=red_mat)
                elif passing_dec != "" and abs(float(passing_dec) - excess) < 0.01:
                    if self.config["drills_passing_decimal"]["colour_passing_drill"] == "GREEN":
                        gdb.cad.set_material(entity, color=green_mat)
                    if self.config["drills_passing_decimal"]["colour_passing_drill"] == "YELLOW":
                        gdb.cad.set_material(entity, color=yellow_mat)
                    if self.config["drills_passing_decimal"]["colour_passing_drill"] == "BLUE":
                        gdb.cad.set_material(entity, color=blue_mat)
                    if self.config["drills_passing_decimal"]["colour_passing_drill"] == "RED":
                        gdb.cad.set_material(entity, color=red_mat)
                elif sink_dec != "" and abs(float(sink_dec) - excess) < 0.01:
                    if self.config["drills_sink_decimal"]["colour_sink_drill"] == "GREEN":
                        gdb.cad.set_material(entity, color=green_mat)
                    if self.config["drills_sink_decimal"]["colour_sink_drill"] == "YELLOW":
                        gdb.cad.set_material(entity, color=yellow_mat)
                    if self.config["drills_sink_decimal"]["colour_sink_drill"] == "BLUE":
                        gdb.cad.set_material(entity, color=blue_mat)
                    if self.config["drills_sink_decimal"]["colour_sink_drill"] == "RED":
                        gdb.cad.set_material(entity, color=red_mat)
                elif recess_dec != "" and abs(float(recess_dec) - excess) < 0.01:
                    if self.config["drills_recess_decimal"]["colour_recess_drill"] == "GREEN":
                        gdb.cad.set_material(entity, color=green_mat)
                    if self.config["drills_recess_decimal"]["colour_recess_drill"] == "YELLOW":
                        gdb.cad.set_material(entity, color=yellow_mat)
                    if self.config["drills_recess_decimal"]["colour_recess_drill"] == "BLUE":
                        gdb.cad.set_material(entity, color=blue_mat)
                    if self.config["drills_recess_decimal"]["colour_recess_drill"] == "RED":
                        gdb.cad.set_material(entity, color=red_mat)
            except Exception:
                pass
        else:
            white_mat = gdb.cad.StandardColors.WHITE
            gdb.cad.set_material(entity, color=white_mat)

        return b_modified

    def set_ewx_angle_note(self, outline_path: str, orig_path: list):
        """"""
        # for each side of the new outline
        for side in gdb.get_entities(outline_path):
            # default value for the note
            note_val = "0"
            # for each entity of the original contour
            for original_ent in gdb.get_entities(orig_path):

                # check if there is any intersection (2 or greater, both ext) with the current side of the box rect
                intersect = False
                with temp_layer(hint="TEMP", new_part=True) as temp_side:
                    gdb.change_layer(side, temp_side, create_copy=True, keep_pos=True)
                    with temp_layer(hint="TEMP", new_part=True) as temp_orig:
                        gdb.change_layer(original_ent, temp_orig, create_copy=True, keep_pos=True)
                        if len(path.get_intersections(temp_side, temp_orig)) >= 2:
                            intersect = True

                # if an intersection has been found
                if intersect:
                    # read the angle note
                    angle_val = float(gdb.get_note(original_ent, "ewx_outline_angle"))

                    # if it's different from 0 save the value
                    if angle_val != 0:
                        note_val = str(angle_val)

            # assign the note that could be still 0 or a different value
            gdb.set_note(side, "ewx_outline_angle", note_val)

    def calc_groove_cont(self, groove_pock_lay: str) -> None:
        """Calculate the cont version of the passed inner groove pocket

        :param groove_pock_lay: path of the inner groove pocket that will be copied and transformed
        :type groove_pock_lay: str
        """
        part_name = gdb.split_name_group(groove_pock_lay)[1]

        # create new layer
        inner_groove_cont_path = gdb.add_layer(part_name, get_layer_by_importer("LAYER_INNER_GROOVE_CONT"), new_name=True)
        gdb.change_layer(gdb.get_entities(groove_pock_lay), inner_groove_cont_path, True, True)

        # delete open side line
        to_del = [x for x in gdb.get_entities(inner_groove_cont_path) if gdb.get_note(x, "OPN") == "1"]
        for line in to_del:
            gdb.delete_entity(line)

    def calc_groove_pocket(self, outline_path: str) -> int:
        """Calculates and draws the missing lines to close the inner groove found to create an INNER GROOVE pocket

        :param groove_path: path to the layer of the extracted inner groove
        :type groove_path: str
        """
        part_name = gdb.split_name_group(outline_path)[1]

        outline_thick = gdb.get_thickness(gdb.get_entities(outline_path)[0])

        with temp_layer(part_name, "REG_OUTLINE") as region_outline:
            region.create(outline_path, region_outline)
            with temp_layer(part_name, "TEMP_RECT_BOX") as temp_rect_box:
                rect_dim = gdb.get_extension(outline_path)[1] - gdb.get_extension(outline_path)[0]
                rect_orig = gdb.get_extension(outline_path)[0]
                cad.add_rectangle(temp_rect_box, rect_orig, rect_dim.x, rect_dim.y)
                with temp_layer(part_name, "REG_RECT_BOX") as region_rect_box:
                    region.create(temp_rect_box, region_rect_box)

                    try:
                        # calculate loops
                        region.difference(region_rect_box, region_outline, True)
                    except RuntimeError:
                        return 0

                    try:
                        loop_count = region.get_shell_count(region_rect_box)
                    except RuntimeError:
                        loop_count = 0

                    for loop_id in range(1, loop_count + 1):
                        # create groove pocket layer
                        inner_groove_pock_path = gdb.add_layer(part_name, get_layer_by_importer("LAYER_INNER_GROOVE_POCK"), new_name=True)
                        region.extract_region_paths(region_rect_box, inner_groove_pock_path, [loop_id], exclude_internal=True)

                        # set thickness
                        cad.modify_curves(gdb.get_entities(inner_groove_pock_path), thickness=outline_thick)
                        # set material
                        cad.set_material(gdb.get_entities(inner_groove_pock_path), cad.StandardColors.YELLOW)

                        for side in gdb.get_entities(inner_groove_pock_path):
                            if is_on_contour(side, temp_rect_box):
                                gdb.set_note(side, "OPN", "1")

                        path.chain(inner_groove_pock_path)
                        area = path.area([inner_groove_pock_path])

                        if area <= 0:
                            path.invert(inner_groove_pock_path)

                        cad.modify_curves(gdb.get_entities(inner_groove_pock_path), work_side=1)
        return loop_count

    def extract_inner_grooves(self, part):
        """Extracts inner grooves inside new layers and recreates the outline

        :param part: part name
        :type part: str
        """
        param_active = parametric.is_active()
        if param_active:
            parametric.deactivate()


        outline_path = get_outline_path(part)
        if not outline_path:
                return

        self.calc_groove_pocket(outline_path)
        for groove_pock_lay in gdb.get_entities(part):
            if groove_pock_lay.startswith(gdb.join_path(part, get_layer_by_importer("LAYER_INNER_GROOVE_POCK"))):
                self.calc_groove_cont(groove_pock_lay)

        keep_orig = True if self.get_param("outline_slacks_on_board") == SLACK_OUTLINE else False
        if not keep_orig:

            with temp_layer(part, "TEMP_RECT_BOX") as temp_rect_box:
                # creating the rectangular box
                rect_dim = gdb.get_extension(outline_path)[1] - gdb.get_extension(outline_path)[0]
                rect_orig = gdb.get_extension(outline_path)[0]
                cad.add_rectangle(temp_rect_box, rect_orig, rect_dim.x, rect_dim.y)

                self.set_ewx_angle_note(temp_rect_box, outline_path)
                # remove original outline and rename new one
                gdb.delete(outline_path)
                gdb.rename_layer(temp_rect_box, gdb.split_name_group(outline_path)[0])

        if param_active:
            parametric.activate()

    def set_pocket_open_side(self, part) -> bool:
        """Set the open side note on all the sides of the scasso outside the outline region

        :param part: part's name
        :type part: str
        :return: True if at least one side is found open and has been managed, otherwise False
        :rtype: bool
        """
        outline_path = get_outline_path(part)
        if not outline_path:
            return

        for lay in gdb.get_entities(part):
            if lay.startswith(get_layer_by_importer("LAYER_SVUOTA_PERCORSO")):
                part_name = gdb.split_name_group(lay)[1]
                with temp_layer(part_name, "TEMP_CONTOUR") as temp_cont_path:

                    gdb.merge_layer(outline_path, temp_cont_path, keep_original=True)
                    cad.offset(gdb.get_entities(temp_cont_path), 0.005, offset_type=cad.OffsetType.EXTEND, side=cad.OffsetSide.LEFT, keep_original=False)

                    with temp_layer(part_name, "TEMP_REGION") as temp_reg_path:
                        # create region to check position
                        region.create(temp_cont_path, temp_reg_path)

                        open_sides = []
                        for scasso_side in gdb.get_entities(lay):
                            p_min, p_max = gdb.get_extension(scasso_side)
                            p_middle = gdb.get_middle_point(scasso_side)

                            min_ok = region.get_shell_in_point(temp_reg_path, p_min) is not None
                            middle_ok = region.get_shell_in_point(temp_reg_path, p_middle) is not None
                            max_ok = region.get_shell_in_point(temp_reg_path, p_max) is not None

                            if not min_ok and not middle_ok and not max_ok:
                                open_sides.append(scasso_side)

                if open_sides:
                    # set open sides notes
                    for line in open_sides:
                        gdb.set_note(line, "OPN=", "1")
                    return True
                else:
                    return False
    def configure(self, config):
        """[summary]

        :param config: [description]
        :type config: [type]
        :return: [description]
        :rtype: [type]
        """

        colors = [("GREEN", get_msg(2148)), ("YELLOW", get_msg(2149)), ("BLUE", get_msg(2150)), ("RED", get_msg(2151))]

        if config is None:
            config = {}

        #I prepare dialogue ConfigHelper from dict
        cfg = ConfigHelperDict(filter_visible=False)

        cfg.add_folder_grid(get_msg(2130), [get_msg(2131)], [20, 20])
        for row in range(1, MAX_NUM_ROWS):
            cfg.add_parameter_grid(get_msg(2130), row, 1, "back_threshold[%d]\\var_name" % (row), ConfigParamType.STRING, "")

        # blind drills
        cfg.add_parameter(get_msg(2138), "drills_blind_decimal\\dec_blind_drill", get_msg(2140), ConfigParamType.NUMERIC_CONV, 0)
        cfg.add_parameter(get_msg(2138), "drills_blind_decimal\\colour_blind_drill", get_msg(2141), ConfigParamType.LIST, default_value=get_msg(2148), options=colors)

        # passing drills
        cfg.add_parameter(get_msg(2138), "drills_passing_decimal\\dec_passing_drill", get_msg(2142), ConfigParamType.NUMERIC_CONV, 0)
        cfg.add_parameter(get_msg(2138), "drills_passing_decimal\\colour_passing_drill", get_msg(2143), ConfigParamType.LIST, default_value=get_msg(2149), options=colors)

        # sink drills
        cfg.add_parameter(get_msg(2138), "drills_sink_decimal\\dec_sink_drill", get_msg(2144), ConfigParamType.NUMERIC_CONV, 0)
        cfg.add_parameter(get_msg(2138), "drills_sink_decimal\\colour_sink_drill", get_msg(2145), ConfigParamType.LIST, default_value=get_msg(2150), options=colors)

        # recess drills
        cfg.add_parameter(get_msg(2138), "drills_recess_decimal\\dec_recess_drill", get_msg(2146), ConfigParamType.NUMERIC_CONV, 0)
        cfg.add_parameter(get_msg(2138), "drills_recess_decimal\\colour_recess_drill", get_msg(2147), ConfigParamType.LIST, default_value=get_msg(2151), options=colors)

        #I run the dialogue
        cfg.run(config)

        #I get the new dict
        config = cfg.to_dict()

        #I return the new configuration
        return config

    def has_the_piece_overmaterial(self, part):
        """function if the piece has overmaterial

        :param part: part
        :type part: string
        """
        #I ge the minimal extensions of the layer (so if there are pockets on the boards I get the minmal rectangled area)
        #with temp_layer(part, "TEMP_CONT") as temp_cont_path:
        
        gdb.add_layer(part, "TEMP_CONT")

        outline_path = gdb.join_path(part, get_layer_by_importer("LAYER_CONTORNA"))
        if not gdb.exist(outline_path):
            outline_path = gdb.join_path(part, get_layer_by_importer("LAYER_CONTORNA_NO_OVERDIM"))
        rect_dim = gdb.get_extension(outline_path)[1] - gdb.get_extension(outline_path)[0]
        rect_orig = gdb.get_extension(outline_path)[0]
        cad.add_rectangle(part + "\\TEMP_CONT", rect_orig, rect_dim.x, rect_dim.y)


        #I get original layer minimal area
        path.chain(part + "\\TEMP_CONT")
        part_dim = abs(path.area(part + "\\TEMP_CONT"))

        #I get area of overdimensioned layer
        path.chain(part + "\\" + get_layer_by_importer("LAYER_OVERDIM"))
        part_overdim = abs(path.area(part + "\\" + get_layer_by_importer("LAYER_OVERDIM")))

        #If dimension of finished\overmaterial are different, the piece has overmaterial, if not I dont make the squaring
        if abs(part_dim - part_overdim) <= 0.01:
            #I rename original layer
            gdb.rename_layer(part + "\\" + get_layer_by_importer("LAYER_CONTORNA"), get_layer_by_importer("LAYER_CONTORNA_NO_OVERDIM"))
            bNoOverdim = False
        else:
            bNoOverdim = True

        gdb.delete_layer(part+"\\TEMP_CONT")

        return bNoOverdim

    def setshapenote(self,b_has_overdim,part):

        is_rect = True

        if(b_has_overdim):
            length = len(gdb.get_entities(part + "\\" + get_layer_by_importer("LAYER_CONTORNA")))
            lay = part + "\\" + get_layer_by_importer("LAYER_CONTORNA")
        else:
            length = len(gdb.get_entities(part + "\\" + get_layer_by_importer("LAYER_CONTORNA_NO_OVERDIM")))
            lay = part + "\\" + get_layer_by_importer("LAYER_CONTORNA_NO_OVERDIM")

        if length == 4:
            for line in gdb.get_entities(lay):
                line_min, line_max = gdb.get_extension(line)
                if not equal(line_max.x, line_min.x) and not equal(line_max.y, line_min.y):
                    is_rect = False
                    break
        else: 
            is_rect = False
        
        if is_rect:
            gdb.set_note(lay, "Shape", "Rect")
        else:
            gdb.set_note(lay, "Shape", "No_Rect")

    def execute(self):
        """[summary]
        """
        n_rename = 0

        self.cont_tools = 0
        if self.get_param("layer_drills_NoMultipleDrillHead") != "-":
            #I get info about declared tools
            self.manage_tools_file()
            #I get info about driller head declaration
            self.manage_dru_file()

        #for each piece cycle
        if self.get_param("part_name") != "":
            part_name = self.get_param("part_name")
        #for each group cycle
        else:
            group = ewd.groups.get_current()
            part_name = ewd.groups.get_parts(group)[0]

        # set contour layer (from top global 0.0.0.) before doing anything to the geometries
        cad.set_current_layer(part_name, get_layer_by_importer("LAYER_CONTORNA"))

        #I verify if the piece has overmaterial
        bNoOverdim = self.has_the_piece_overmaterial(part_name)

        #I verify all the enitites
        for layer in gdb.get_entities(part_name):
            #back groove thresholds management
            if get_layer_by_importer("LAYER_SCASSO_SCHIENALE") in layer:
                self.manage_back_groove(layer)
            for entity in gdb.get_entities(layer):
                #holes management
                if gdb.get_type(entity) == gdb.EntityType.HOLE:
                    n_rename += 1
                    self.manage_holes(entity, n_rename)

        #if the back groove parameter has been renamed
        if self.get_param("Name_groove_on_x") != "-" or self.get_param("Name_groove_on_y") != "-":
            self.rename_back_groove(part_name, "LAYER_SCASSO_SCHIENALE")

        p_active = parametric.is_active()
        if p_active:
            parametric.deactivate()
        self.extract_inner_grooves(part_name)
        if p_active:
            parametric.activate()

        self.set_pocket_open_side(part_name)

        self.setshapenote(bNoOverdim,part_name)

class PieceRotations(BaseOperation):
    """
    class that calculates piece rotation possibilities
    """
    def __init__(self):
        super().__init__(get_msg(2187), "", get_msg(2000))

        rotations_for_back_dir = [(NO_ROT, get_msg(2163)), (ROT_GROOVE_X, get_msg(2156)), (ROT_GROOVE_Y, get_msg(2157))]
        rotations_for_back_pos = [(NO_ROT, get_msg(2163)), (ROT_GROOVE_TOP, get_msg(2164)), (ROT_GROOVE_BOTT, get_msg(2165))]
        rotations_for_hole_pos = [(NO_ROT, get_msg(2163)), (ROT_HOLES_TOP, get_msg(2284)), (ROT_HOLES_BOTT, get_msg(2283))]

        self.register_param("rotate_if_greater_height", ParamType.INPUT, get_msg(2152), False, T_F)
        self.register_param("rotate_min_length", ParamType.INPUT, get_msg(2153), 0)
        self.register_param("kind_rotation_by_backgroove", ParamType.INPUT, get_msg(2155), NO_ROT, rotations_for_back_dir)
        self.register_param("kind_rotation_by_backgroove_pos", ParamType.INPUT, get_msg(2162), NO_ROT, rotations_for_back_pos)

        self.register_param("separator", ParamType.INPUT, get_msg(2278), 0)

        self.register_param("kind_rotation_by_holes_pos", ParamType.INPUT, get_msg(2279), NO_ROT, rotations_for_hole_pos)
        self.register_param("diam_rotation_by_holes_pos", ParamType.INPUT, get_msg(2280), "")
        self.register_param("angle_rotation_by_holes_pos", ParamType.INPUT, get_msg(2281), ROT_180, ROT_LIST)
        self.register_param("distance_rotation_by_holes_pos", ParamType.INPUT, get_msg(2282), 0)

    def get_max_groove(self, part):
        """function that search the greatest groove and in which direction is orienteted (height/length)

        :param part: the part in which to search for
        :type part: str
        :return: dictionary with groove dimension and orientation
        :rtype: dict
        """
        max_groove = {"MAX_GROOVE": 0}
        max_dim_groove = -9999

        for layer in gdb.get_entities(part):
            if get_layer_by_importer("LAYER_SCASSO_SCHIENALE") in layer:
                #Tookdimensions
                loc = EntityInfo(layer)
                #I get the max dimension of the groove
                max_dim = max(loc.width, loc.height)

                #I set necessaries info in the dict
                if max_dim > max_dim_groove:
                    max_groove["MAX_GROOVE"] = loc.width if loc.width > loc.height else loc.height
                    max_groove["MAX_GROOVE_DIR"] = "On width" if loc.width > loc.height else "On height"
                    max_groove["MAX_GROOVE_MAXPT"] = loc.pt_max
                    max_groove["MAX_GROOVE_MINPT"] = loc.pt_min
                    max_dim_groove = max_dim

        return max_groove


    def rotate_by_holes_pos(self, part, layer):
        """function that verified if a piece needs to be rotated by the holes position
        If a certain hole (searching for the diameter) is closed to top or bottom edge, the piece will be rotated

        :param part: the part in which to search for
        :type part: str
        """
        diam_rotation_holes_pos = self.get_param("diam_rotation_by_holes_pos")
        distance_rotation_holes_pos = self.get_param("distance_rotation_by_holes_pos")
        kind_rotation_holes_pos = self.get_param("kind_rotation_by_holes_pos")

        piece_ext = gdb.get_extension(part + "\\%%SOLID")

        ref_layer = gdb.get_reference(layer)[2]
        #I verify vertical drills
        if ref_layer.z > 1 - EPSILON_NORM:
            for ent in gdb.get_entities(layer):
                if self.hole_diam_in_list(gdb.get_radius(ent)*2, diam_rotation_holes_pos):
                    #I rotate the piece if holes are closed to top border
                    if kind_rotation_holes_pos == ROT_HOLES_TOP:
                        #if the holes position is around the border - a certain distance
                        if gdb.get_center_point(ent).y >= piece_ext[1].y - distance_rotation_holes_pos:
                            return True

                    #I rotate the piece if holes are closed to top border
                    elif kind_rotation_holes_pos == ROT_HOLES_BOTT:
                        #if the holes position is around the border + a certain distance
                        if gdb.get_center_point(ent).y <= piece_ext[0].y + distance_rotation_holes_pos:
                            return True
        
        #In case for the conditions is not necessary to rotate the piece, I return a False value
        return False
                            

    def hole_diam_in_list(self, diameter, list):
        """function for verify in a diameter is in the list of diameters to verify
        """
        for diam_check in list.split(","):
            if diameter == float(diam_check):
                return True
        
        return False
    

    def execute(self):
        """[summary]
        """
        rotate_for_height = self.get_param("rotate_if_greater_height")
        min_piece_width = self.get_param("rotate_min_length")
        kind_rotation_back_groove = self.get_param("kind_rotation_by_backgroove")
        kind_rotation_back_groove_pos = self.get_param("kind_rotation_by_backgroove_pos")

        angle_rotation_holes_pos = self.get_param("angle_rotation_by_holes_pos")
        kind_rotation_holes_pos = self.get_param("kind_rotation_by_holes_pos")

        b_is_rotated_by_back_pos = False

        part_name = get_piece_name()
        # path to box solid group
        path = part_name + "\\%%MACH\\%%BOX\\SOLID"
        #Took dimensions
        loc = EntityInfo(path)

        #if the width is smaller then the min value, I rotate
        if min_piece_width > 0:
            if loc.width < min_piece_width:
                gdb.cad.rotate_piece(part_name, 0, 0, 90, create_copy=False)

        loc = EntityInfo(path)  
        #if the height is greater then the width, I rotate
        if rotate_for_height:
            if loc.width < loc.height:
                gdb.cad.rotate_piece(part_name, 0, 0, 90, create_copy=False)

        #at the end, I force by the greatest back groove direction
        for layer in gdb.get_entities(part_name):
            #if back groove is in list
            if get_layer_by_importer("LAYER_SCASSO_SCHIENALE") in layer:
                #I took  newest piece dimesions after rotation
                loc = EntityInfo(path)
                #I get the max groove and its info
                max_groove = self.get_max_groove(part_name)

                #I force by the greatest back groove direction
                if kind_rotation_back_groove != NO_ROT:
                    if kind_rotation_back_groove == ROT_GROOVE_X:
                        #I rotate only if the max groove is on Y direction
                        if max_groove["MAX_GROOVE_DIR"] == "On height" and max_groove["MAX_GROOVE"] != 0:
                            gdb.cad.rotate_piece(part_name, 0, 0, 90, create_copy=False)
                            #I disable the nesting rotation piece
                            gdb.set_note(part_name, "NART", 0)
                        #if there is a backgroove, I disable the nesting rotation piece too
                        elif max_groove["MAX_GROOVE"] != 0:
                            gdb.set_note(part_name, "NART", 0)
                    elif kind_rotation_back_groove == ROT_GROOVE_Y:
                        #I rotate only if the max groove is on X direction
                        if max_groove["MAX_GROOVE_DIR"] == "On width" and max_groove["MAX_GROOVE"] != 0:
                            gdb.cad.rotate_piece(part_name, 0, 0, 90, create_copy=False)
                            #I disable the nesting rotation piece
                            gdb.set_note(part_name, "NART", 0)
                        #if there is a backgroove, I disable the nesting rotation piece too
                        elif max_groove["MAX_GROOVE"] != 0:
                            gdb.set_note(part_name, "NART", 0)
                    else:
                        raise Exception("Error: no valid dimensions on groove")

                #I took  newest piece dimesions after rotation
                loc = EntityInfo(path)
                #I force by the greatest back groove position
                if kind_rotation_back_groove_pos != NO_ROT:
                    #I get the newest max groove and its info after the first rotations
                    max_groove = self.get_max_groove(part_name)

                    #I verify horizontal grooves
                    if max_groove["MAX_GROOVE_DIR"] == "On width":
                        if kind_rotation_back_groove_pos == ROT_GROOVE_TOP:
                            #min point is over half piece
                            if  max_groove["MAX_GROOVE_MINPT"].y >= loc.height / 2:
                                if not b_is_rotated_by_back_pos:
                                    gdb.cad.rotate_piece(part_name, 0, 0, 180, create_copy=False)
                                    b_is_rotated_by_back_pos = True
                        elif kind_rotation_back_groove_pos == ROT_GROOVE_BOTT:
                            #mAX point is over half piece
                            if  max_groove["MAX_GROOVE_MAXPT"].y <= loc.height / 2:
                                if not b_is_rotated_by_back_pos:
                                    gdb.cad.rotate_piece(part_name, 0, 0, 180, create_copy=False)
                                    b_is_rotated_by_back_pos = True


        #I took  newest piece dimesions after rotation
        loc = EntityInfo(path)
        #at the end, I rotate the piece by holes position
        for layer in gdb.get_entities(part_name):
            #drill in list
            if get_layer_by_importer("LAYER_DRILL") in layer:
                #I force by the holes position
                if kind_rotation_holes_pos != NO_ROT:
                    #I get the newest max groove and its info after the first rotations
                    if self.rotate_by_holes_pos(part_name, layer):
                        gdb.cad.rotate_piece(part_name, 0, 0, float(angle_rotation_holes_pos), create_copy=False)


class DeleteUnderMachinings(BaseOperation):
    """[summary]
    """
    def __init__(self):
        super().__init__(get_msg(2188), "", get_msg(2000))

    def execute(self):

        curr_piece = ewd.mach.get_current_piece()

        pieces = gdb.cad.get_parts()

        for piece in pieces:
            ewd.mach.set_current_piece(piece)
            machinings = ewd.mach.get_machining_list(piece)

            piece_ext = gdb.get_extension(piece+"\\%%MACH\\%%BOX\\SOLID")

            for machining in machinings:
                mach_ext = gdb.get_extension(piece+"\\%%MACH\\"+machining)

                pt_avg_z = (mach_ext[0].z + mach_ext[1].z)/2

                if pt_avg_z < piece_ext[0].z:
                    ewd.mach.delete_machining(machining)

        ewd.mach.set_current_piece(curr_piece)


class Edgebander(BaseOperation):
    """Class for manage edgebander with or without trimmer
    First case I set the solid on EDGE_BANDING
    """

    def __init__(self):
        super().__init__(get_msg(2136), "", get_msg(2133))

        edge_bander_list = [(EDGEBAND_RETT, get_msg(2134)), (EDGEBAND_NO_RETT, get_msg(2135))]
        self.register_param("edge_bander_type", ParamType.INPUT, get_msg(2133), EDGEBAND_NO_RETT, edge_bander_list)

    def execute(self):
        group = ewd.groups.get_current()
        part_name = ewd.groups.get_parts(group)[0]

        edge_bander_type = self.get_param("edge_bander_type")

        if edge_bander_type == EDGEBAND_RETT:
            #I get the original thickness of the piece
            part_points = gdb.get_extension(part_name + "\\%%SOLID")
            part_thickness = abs(part_points[0].z - part_points[1].z)
            #I delete original solid
            gdb.delete(part_name + "\\%%SOLID")

            #I create solid again on EDGEBANDING entities
            try:
                gdb.solid.insert(group=part_name, thickness=part_thickness, entities=gdb.get_entities(part_name + "\\EDGE_BANDING"))
            except RuntimeError:
                self.error(message=get_msg(2137), fatal=True)


class Press(BaseOperation):
    """Class for manage press machine (I set the solid on overmaterial layer)
    """

    def __init__(self):
        super().__init__("Press", "", get_msg(2133))

    def execute(self):
        group = ewd.groups.get_current()
        part_name = ewd.groups.get_parts(group)[0]

        #I get the original thickness of the piece
        part_points = gdb.get_extension(part_name + "\\%%SOLID")
        part_thickness = abs(part_points[0].z - part_points[1].z)
        #I delete original solid
        gdb.delete(part_name + "\\%%SOLID")

        #I create solid again on overmaterial layer entities
        try:
            gdb.solid.insert(group=part_name, thickness=part_thickness, entities=gdb.get_entities(part_name + "\\" + get_layer_by_importer("LAYER_OVERDIM")))
        except RuntimeError:
            self.error(message=get_msg(2137), fatal=True)

class Add2ndPhaseColumnOnCSV(BaseOperation):
    """Class for add column if a piece has a second phase
    This function add the Cam File Name 2phase name as [...] column of csv (column set by interface)
    """

    def __init__(self):
        super().__init__(get_msg(2224), "", get_msg(2022))

        self.register_param("csv_path", ParamType.INPUT, get_msg(2026), "")
        self.register_param("rev_csv_path", ParamType.INPUT, get_msg(2037), "")
        self.register_param("second_phase_list", ParamType.INPUT, get_msg(2223), "")
        self.register_param("add_end_info", ParamType.INPUT, get_msg(2230), "")
        self.register_param("add_begin_info", ParamType.INPUT, get_msg(2236), "")
        self.register_param("column_to_copy_position", ParamType.INPUT, get_msg(2232), 1)
        self.register_param("new_column_position", ParamType.INPUT, get_msg(2227), 1)
        self.register_param("first_mod_csv", ParamType.INPUT, get_msg(2266), False)


    def is_second_phase_piece(self, line_to_verify, column):
        #I get the list of pieces that have the second phase
        list_second_phase_pieces = self.get_param("second_phase_list").split(",")
        #the piece to verify is the column..
        piece_to_verify = line_to_verify[int(column)]

        b_find = False
        #if the piece is in the list of pieces with 2 phases
        for piece in list_second_phase_pieces:
            if piece == piece_to_verify:
                b_find = True

        return b_find

    def execute(self):
        csv_path = self.get_param("csv_path")
        column_to_copy_position = self.get_param("column_to_copy_position")
        new_column_position = self.get_param("new_column_position")
        add_end_info = self.get_param("add_end_info")
        add_begin_info = self.get_param("add_begin_info")
        rev_csv_file_path = self.get_param("rev_csv_path")
        first_mod_csv = self.get_param("first_mod_csv")

        csv_file_path = csv_path

        #I read the csv file
        lines = []

        try:
            with open(csv_file_path, "r", newline="") as csv_file:
                reader = csv.reader(csv_file, delimiter=";")

                for row in reader:
                    lines.append(row)
        except Exception:
            self.error(message=get_msg(2102), fatal=True)

        #Headers
        headers = lines.pop(0)

        #I add the column if the condition is respected
        for i, line in enumerate(lines):
            if self.is_second_phase_piece(lines[i], column_to_copy_position):
                # First modification csv: I add the column
                if first_mod_csv:
                    lines[i].insert(int(new_column_position), add_begin_info + lines[i][int(column_to_copy_position)]+"_2F" + add_end_info)
                # Else I just modify the relative value without to add any new column
                else:
                    lines[i][int(new_column_position)] = add_begin_info + lines[i][int(column_to_copy_position)]+"_2F" + add_end_info
            else:
                # First modification csv: I add an empty column
                if first_mod_csv:
                    lines[i].insert(int(new_column_position), "")

        #I add the new header
        headers.insert(int(new_column_position), "CN File 2Phase")
        lines.insert(0, headers)

        #I get the file name without the path
        file_name = gdb.split_name_group(csv_file_path)[0]

        #I write the new modified csv removing evectual already modified csv
        if first_mod_csv:
            if os.path.exists(rev_csv_file_path+file_name):
                os.remove(rev_csv_file_path+file_name)

            #I create the folder if doesn't exist at the moment
            if not os.path.exists(rev_csv_file_path):
                os.mkdir(rev_csv_file_path)

        with open(rev_csv_file_path+file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            for line in lines:
                writer.writerow(line)


class AddGenericColumnOnCSV(BaseOperation):
    """Class for a generic column on a csv file
    """

    def __init__(self):
        super().__init__(get_msg(2226), "", get_msg(2022))

        self.register_param("csv_path", ParamType.INPUT, get_msg(2026), "")
        self.register_param("rev_csv_path", ParamType.INPUT, get_msg(2037), "")

        self.register_param("new_column_position", ParamType.INPUT, get_msg(2227), 1)
        self.register_param("new_column_title", ParamType.INPUT, get_msg(2228), "")
        self.register_param("new_column_value", ParamType.INPUT, get_msg(2229), "")
        self.register_param("first_mod_csv", ParamType.INPUT, get_msg(2266), False)


    def execute(self):
        csv_path = self.get_param("csv_path")
        new_column_position = self.get_param("new_column_position")
        new_column_title = self.get_param("new_column_title")
        new_column_value = self.get_param("new_column_value")
        rev_csv_file_path = self.get_param("rev_csv_path")
        first_mod_csv = self.get_param("first_mod_csv")

        #for file in lista:
        csv_file_path = csv_path

        #I read the csv file
        lines = []

        try:
            with open(csv_file_path, "r", newline="") as csv_file:
                reader = csv.reader(csv_file, delimiter=";")

                for row in reader:
                    lines.append(row)
        except Exception:
            self.error(message=get_msg(2102), fatal=True)

        #Headers
        headers = lines.pop(0)

        #I add the column in the selected position witrh the same value
        for i, line in enumerate(lines):
            lines[i].insert(int(new_column_position), new_column_value)

        #I add the new header
        headers.insert(int(new_column_position), new_column_title)
        lines.insert(0, headers)

        #I get the file name without the path
        file_name = gdb.split_name_group(csv_file_path)[0]

        #I write the new modified csv removing evectual already modified csv
        if first_mod_csv:
            if os.path.exists(rev_csv_file_path+file_name):
                os.remove(rev_csv_file_path+file_name)

            #I create the folder if doesn't exist at the moment
            if not os.path.exists(rev_csv_file_path):
                os.mkdir(rev_csv_file_path)

        with open(rev_csv_file_path+file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";", quoting=csv.QUOTE_MINIMAL)

            for line in lines:
                writer.writerow(line)


class CopyColumnOnCSV(BaseOperation):
    """Class for copy a column in a csv file
    """

    def __init__(self):
        super().__init__(get_msg(2231), "", get_msg(2022))

        self.register_param("csv_path", ParamType.INPUT, get_msg(2026), "")
        self.register_param("rev_csv_path", ParamType.INPUT, get_msg(2037), "")
        self.register_param("add_end_info", ParamType.INPUT, get_msg(2230), "")
        self.register_param("add_begin_info", ParamType.INPUT, get_msg(2236), "")
        self.register_param("column_to_copy_position", ParamType.INPUT, get_msg(2232), 1)
        self.register_param("new_column_position", ParamType.INPUT, get_msg(2227), 1)
        self.register_param("first_mod_csv", ParamType.INPUT, get_msg(2266), False)

    def execute(self):
        csv_path = self.get_param("csv_path")
        new_column_position = self.get_param("new_column_position")
        column_to_copy_position = self.get_param("column_to_copy_position")
        add_end_info = self.get_param("add_end_info")
        add_begin_info = self.get_param("add_begin_info")
        rev_csv_file_path = self.get_param("rev_csv_path")
        first_mod_csv = self.get_param("first_mod_csv")

        #for file in lista:
        csv_file_path = csv_path

        #I read the csv file
        lines = []

        try:
            with open(csv_file_path, "r", newline="") as csv_file:
                reader = csv.reader(csv_file, delimiter=";")

                for row in reader:
                    lines.append(row)
        except Exception:
            self.error(message=get_msg(2102), fatal=True)

        #Headers
        headers = lines.pop(0)

        #I copy the column adding an info if necessary
        for i, line in enumerate(lines):
            lines[i].insert(int(new_column_position), add_begin_info + lines[i][int(column_to_copy_position)] + add_end_info)

        #I add the new header
        headers.insert(int(new_column_position), "CAM file name")
        lines.insert(0, headers)

        #I get the file name without the path
        file_name = gdb.split_name_group(csv_file_path)[0]
        #I write the new modified csv removing evectual already modified csv
        if first_mod_csv:
            if os.path.exists(rev_csv_file_path+file_name):
                os.remove(rev_csv_file_path+file_name)

            #I create the folder if doesn't exist at the moment
            if not os.path.exists(rev_csv_file_path):
                os.mkdir(rev_csv_file_path)

        with open(rev_csv_file_path+file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";", quoting=csv.QUOTE_MINIMAL)

            for line in lines:
                writer.writerow(line)


class GetCSVPath(BaseOperation):
    """Class for get the imported csv path
    """

    def __init__(self):
        super().__init__(get_msg(2235), "", get_msg(2022))

        self.register_param("csv_input_path", ParamType.INPUT, get_msg(2026), "")
        self.register_param("from_upped_dir", ParamType.INPUT, get_msg(2267), False)

        self.register_param("csv_file", ParamType.OUTPUT, "", "")
        self.register_param("csv_upper_path", ParamType.OUTPUT, "", "")
        self.register_param("csv_upper_folder_name", ParamType.OUTPUT, "", "")

    def execute(self):
        csv_dir = self.get_param("csv_input_path")
        get_from_upped_dir = self.get_param("from_upped_dir")

        #do_debug()
        # I get the csv from the upper folder (used for multiple folders exported by Pytha)
        if get_from_upped_dir:
            #last char is a slash
            if csv_dir[-1] == "\\":
                csv_dir = os.path.dirname(os.path.dirname(csv_dir))
            else:
                csv_dir = os.path.realpath(csv_dir)
            
            csv_folder = os.path.basename(csv_dir)

        fileExt = r".csv"
        lista = [x for x in os.listdir(csv_dir) if x.endswith(fileExt)]

        for file in lista:
            csv_file = file

        #I return the csv file name
        self.set_param("csv_file", csv_file)
        #I return the new upped folder path
        if get_from_upped_dir:
            self.set_param("csv_upper_path", csv_dir)
            self.set_param("csv_upper_folder_name", csv_folder)


class EndCSVMod(BaseOperation):
    """Class for get the imported csv path
    """

    def __init__(self):
        super().__init__(get_msg(2265), "", get_msg(2022))

        self.register_param("file_to_verify", ParamType.INPUT, get_msg(2026), "")

    def execute(self):
        file_to_verify = self.get_param("file_to_verify")

        if not os.path.exists(file_to_verify):
            documento = open(file_to_verify, "w")
            documento.close()


class GetGetDailyContPiece(BaseOperation):
    """Class for obtein the daily pieces cont taken from Machine.ppd and update that value after some operations
    """

    def __init__(self):
        super().__init__(get_msg(2249), "", get_msg(2049))

        phases = [(_GET, get_msg(2250)), (_SET, get_msg(2251))]
        self.register_param("type", ParamType.INPUT, get_msg(2202), _GET, phases)
        self.register_param("actual_pieces_count", ParamType.INPUT, get_msg(2252), 0)
        self.register_param("pieces_count", ParamType.OUTPUT, "", "")
        self.register_param("actual_data", ParamType.OUTPUT, "", "")

    def execute(self):
        phase = self.get_param("type")

        #first phase: I get and manage the values
        if phase == _GET:
            #I open Machine.PPD
            saved_data = ewd.read_string_param("Data","Date",ewd.explode_file_path("%MACHPATH%\\Machine.ppd"))
            saved_pieces_cont = str(ewd.read_string_param("Data","CountPiecesDaily",ewd.explode_file_path("%MACHPATH%\\Machine.ppd")))

            actual_data = time.strftime('%Y%m%d')

            #if the day has changed
            if actual_data != saved_data:
                #I set the last data
                ewd.write_string_param("Data","Date",actual_data,ewd.explode_file_path("%MACHPATH%\\Machine.ppd"))
                #new day, I reset the piece counter
                saved_pieces_cont = str(0)
                ewd.write_string_param("Data","CountPiecesDaily",saved_pieces_cont,ewd.explode_file_path("%MACHPATH%\\Machine.ppd"))

                #saved_data = ewd.read_string_param("Data","Date",ewd.explode_file_path("%MACHPATH%\\Machine.ppd"))
                #saved_pieces_cont = ewd.read_string_param("Data","CountPiecesDaily",ewd.explode_file_path("%MACHPATH%\\Machine.ppd"))

            self.set_param("pieces_count", int(saved_pieces_cont))
            self.set_param("actual_data", actual_data)

        #second phase: I write the new values in the Machine.ppd
        else:
            #I get the actual pieces count updated by the automatic execution
            actual_pieces_count = str(self.get_param("actual_pieces_count"))
            #I delete decimals not necessary
            if actual_pieces_count.find(".") > 0:
                actual_pieces_count = actual_pieces_count[0:actual_pieces_count.find(".")]

            ewd.write_string_param("Data","CountPiecesDaily",actual_pieces_count,ewd.explode_file_path("%MACHPATH%\\Machine.ppd"))


class IncreaseCounter(BaseOperation):
    """Class for increase a counter (to be used in a FOR cycle)
    """

    def __init__(self):
        super().__init__(get_msg(2253), "", get_msg(2049))

        self.register_param("actual_count", ParamType.INPUT, get_msg(2252), 0)
        self.register_param("increased_count", ParamType.OUTPUT, "", 0)

    def execute(self):
        cont = self.get_param("actual_count")

        cont = cont + 1

        self.set_param("increased_count", cont)

class DecreaseCounter(BaseOperation):
    """Class for decrease a counter (to be used in a FOR cycle)
    """

    def __init__(self):
        super().__init__(get_msg(2254), "", get_msg(2049))

        self.register_param("actual_count", ParamType.INPUT, get_msg(2252), 0)
        self.register_param("decreased_count", ParamType.OUTPUT, "", 0)

    def execute(self):
        cont = self.get_param("actual_count")

        cont = cont - 1

        self.set_param("decreased_count", cont)

class GetInfoByEwx(BaseOperation):
    """Class for obtein the value of a note directly in opening a ewx file (because not imported yet, to be used in a cycle for each group)
    """

    def __init__(self):
        super().__init__(get_msg(2261), "", get_msg(2049))

        self.register_param("file_to_read", ParamType.INPUT, get_msg(2022), "")
        self.register_param("info_to_read", ParamType.INPUT, get_msg(2080), "")
        self.register_param("output_info", ParamType.OUTPUT, "", "")

    def execute(self):
        file = self.get_param("file_to_read")
        info = self.get_param("info_to_read")

        with open(ewd.explode_file_path(file)) as file_name:
            #I take the part attribute with precision between ''
            info = "\'" + info + "\'"
            for line in file_name:
                #I search the info and clean it
                if info in line:
                    info_line = line.replace(info,"")
                    info_line = info_line.replace("'","")
                    info_line = info_line.replace(":","")
                    info_line = info_line.replace(",","")
                    info_line = info_line.strip()

        self.set_param("output_info", info_line)
