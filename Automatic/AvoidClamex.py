#########################################################################
# Component for avoid lamello with wrong direction (negative z vers.) 
# First version 26.02.2021 MM
#               18.05.2021 MM  Improved for avoid clamex under the piece
#########################################################################

import ewd
import gzip
import os
import math
from ddx import gdb
from ewd import mach
from ewd.msg import get_compo_msg as get_msg
from ddx.autoexec import BaseOperation, ParamType
from sclcore import do_debug
from ddx.confdlg import ConfigHelperDict, ConfigParamType

def GetMacroList():
    """function for get the macro list to be verified

    :return: 
    :rtype: list
    """

    list = []

    #I get the list of macro has to ve verifier
    with open(ewd.explode_file_path("%MACHPATH%\\Automatic\\AvoidClamex.ini")) as file_name:
        for line in file_name:
            #not a comment
            if line.find("\\") != 0:
                list.append(line)

    return list

def MacroHasToVerified(layer_to_verify, list):
    """I veify if the layer has to be verified

    :param layer_to_verify: layer to verify
    :type layer_to_verify: string
    :param list: list of maco to be checked
    :type list: list
    :return:
    :rtype: bool
    """
    layer_clean = layer_to_verify

    #I get the clean name of the layer
    layer_clean = layer_clean.split("\\")[1]
    if layer_clean.find("(") > 0:
        layer_clean = layer_clean[0:layer_clean.find("(")].strip()
    else:
        layer_clean = layer_clean[0:layer_clean.find("_GROUP_PATH")].strip()

    for elem in list:
        #I verify the subfolder PATH
        if layer_clean == elem.strip() and layer_to_verify.find("PATH") > 0:
            return True

    return False

if __name__ == "__main__":
    #I get the list of macro to be verified
    macro_list = []
    macro_list = GetMacroList()

    part_list = gdb.get_entities()

    
    for part_name in part_list:
        min_pt_piece = gdb.get_extension(part_name+"\\%%SOLID")[0].z
        for lay in gdb.get_entities(part_name):
            if MacroHasToVerified(lay, macro_list):
                #I get the Z reference
                ref = gdb.get_reference(lay)
                vec_z = ref[2]
                #I get min extension
                min_pt_layer = gdb.get_extension(lay)[0].z

                #if the reference is less then 0 or uner the part, I avoid the clamex because from bottom
                if vec_z.z < 0 or (min_pt_layer < min_pt_piece):
                    gdb.rename_layer(lay, "NO"+ lay.split("\\")[1])
                    lay_notes = part_name + "\\NO"+ lay.split("\\")[1]
                    #I set the notes on the renamed layer
                    for entity in gdb.get_entities(lay_notes):
                        gdb.set_note(entity, "Clamex_DIR", "NO")
