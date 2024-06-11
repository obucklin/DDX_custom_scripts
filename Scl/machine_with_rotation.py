import ewd
from ewd import beam
from ewd.beam import *
from ewd.mach import get_pieces_list
from ddx.logger import debug
from ddx.gdb import get_note, delete_part, delete, delete_entity
from sclcore import execute_command_bool as exec_bool
from sclcore import execute_command_num as exec_num
from sclcore import execute_command_string as exec_string
from sclcore import Ref
import bcfcore
from ewd import error


def remove_double_cuts():
    for piece in get_pieces_list(only_curr_group = False):
        set_current_beam(piece, update_ui=True)
        for feature in get_features_list():
            if get_feature_property(feature, 'TYP') == "DoubleCut":
                exec_bool("SetNotes", piece + "\\" + feature, "NOTW", "1")

def feature_executed(piece, feature):
    if exec_str("GetNotes", piece + "\\" + feature, "TYP") == "DoubleCut":
        return True
    result = exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'NOTW') == '0'
    return result

def reset_features(piece, features):
    for feature in features:
        exec_bool("SetNotes", piece + "\\" + feature, "NOTW", "0")
    

def invert_active_features(piece):
    active_features = []
    for feature in get_features_list(piece):
        if exec_str("GetNotes", piece + "\\" + feature, "TYP") == "DoubleCut":
            continue
        if exec_string("GetNotes", piece + "\\" + feature, "NOTW") == '1':
            exec_bool("SetNotes", piece + "\\" + feature, "NOTW", "0")
            active_features.append(feature)
        else:
            exec_bool("SetNotes", piece + "\\" + feature, "NOTW", "1")
    return active_features


bcfcore.do_debug()
remove_double_cuts()


parts_to_rotate = []
for piece in get_pieces_list(only_curr_group = False):
    set_current_beam(piece, update_ui=True)

    exec_bool("BeamMach", True, False)
    copy = copy_beam(piece)
    rename_beam(piece + "_", copy)
    copy = piece + "_"
    for feature in get_features_list():
        if not feature_executed(piece, feature):
            if copy not in parts_to_rotate:
                parts_to_rotate.append(copy)
                piece.rename(piece + "_pt1_")
    if copy not in parts_to_rotate:
        delete_part(copy)    
    

for copy in parts_to_rotate:
    set_current_beam(copy, update_ui=True)
    features_to_try = invert_active_features(copy)
    base_name = copy
    i = 0    
    success = False
    for j in range(2):
        rots = [[2,1,2], [0,2,1,2]]
        for rotations in rots[j]:
            i += rotations
            rename_beam(base_name + "rot:_" + str(i % 4), copy)    
            copy = base_name + "rot:_" + str(i % 4) 
            set_current_beam(copy, update_ui=True)
            rotate_beam(num_step = i)
            success = exec_bool("BeamMach", True, False)
            # for feature in features_to_try:
            # if not feature_executed(copy, feature):
            if not success:
                reset_features(copy, features_to_try)
                break
            else:
                break      
        if success:
            break
        else:
            rotate_beam(num_step = 3)
            flip_beam()        
            base_name +="flip_"

    # import reorder_machinings
