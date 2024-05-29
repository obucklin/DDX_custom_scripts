#########################################################################
# Component for avoid Outline sqauring on side with inclined face
# The component will delete entities with note 'ewx_outline_angle' different by 0
# That note is automatically created by Easywood during the ewx importation and it takes value different by 0 (equal to its angle) if the relative face is inclined

# First version 24.08.2021 MM
#########################################################################

import ewd
import gzip
import os
import math
from ddx import gdb
from ewd import mach, groups
from ewd.msg import get_compo_msg as get_msg
from ddx.autoexec import BaseOperation, ParamType
from sclcore import do_debug
from ddx.confdlg import ConfigHelperDict, ConfigParamType

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

if __name__ == "__main__":
    lay_id_list = []
    #I get the piece in the group
    #group_name = groups.get_current()
    #part_name = groups.get_parts(group_name)[0]
    part_name = mach.get_current_piece()

    for lay in gdb.get_entities(part_name):
        #I get ID of the layers need to be verified
        if lay.find(get_layer_by_importer("LAYER_CONTORNA")) > 0:
            #I get the ID note for identify the layer
            lay_id_list.append(int(gdb.get_note(lay, "ID=")))

    #I get the list of entities from %%MACH
    for mach_name in gdb.get_names(part_name + "\\%%MACH"):
        #I get the applied machinings
        for geom in gdb.get_names(mach_name):
            #I verify the entities of the machining
            if "GEOM_ORIGINAL(1)" in geom:
                for ent in gdb.get_names(geom):
                    #I get the label in which I reach the info about relative layer
                    label = gdb.get_label(ent).split(",")

                    #I get the machining relative layer and compare with the OUTLINE layer ID
                    for label_info in label:
                        if "LAY=" in label_info:
                            mach_lay_id = int(label_info[label_info.find("=")+1:])

                            #if they are matched it means the layer of the machining is a OUTLINE
                            if mach_lay_id in lay_id_list:
                                #if the note 'ewx_outline_angle' is different by it means there is an inclined face
                                if float(gdb.get_note(ent, "ewx_outline_angle")) != 0:
                                    gdb.delete(ent)

                                    #I update the machining
                                    mach.update_machining(mach_name.split("\\")[2], only_modified=False, update_geo=True)