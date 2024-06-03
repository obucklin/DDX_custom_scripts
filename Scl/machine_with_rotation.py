import ewd
from ewd import beam
from ewd.beam import *
from ewd.mach import get_pieces_list
from ddx.logger import debug
from ddx.gdb import get_note
from sclcore import execute_command_bool as exec_bool
from sclcore import execute_command_num as exec_num
from sclcore import execute_command_string as exec_string
from sclcore import Ref
import bcfcore
from ewd import error

bcfcore.do_debug()


def feature_executed(piece, feature):
    notw = exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'NOTW')
    return notw == '0'

def remove_features_from_beam(piece, features):
    if isinstance(features, str):
        features = [features]
    current = get_current_beam()
    set_current_beam(piece, update_ui=False)
    for feature in features:
        delete_feature(feature)
    set_current_beam(current, update_ui=False)


parts_to_rotate = []
for piece in get_pieces_list(only_curr_group = False):
    set_current_beam(piece, update_ui=True)

    exec_bool("BeamMach", True, False)

    remove_from_copy = []   
    remove_from_piece = []
    for feature in get_features_list():
        if feature_executed(piece, feature):
            remove_from_copy.append(feature)
        else:
            remove_from_piece.append(feature)
    if len(remove_from_piece)>0:
        copy = copy_beam(piece)
        rename_beam(piece + "_", copy)
        copy = piece + "_"
        parts_to_rotate.append(str(piece + "_"))
        remove_features_from_beam(piece, remove_from_piece)
        remove_features_from_beam(copy, remove_from_copy)


# for piece in parts_to_rotate:
#     set_current_beam(piece, update_ui=True)
#     i = 0    
#     for rotations in [2,1,2]:
#         i += rotations
#         rotate_beam(num_step = rotations)
#         for feature in get_features_list():
#             on = exec_bool("SetNotes", piece + "\\" + feature, "NOTW", "0")
#         exec_bool("BeamMach", True, False)
#         for feature in get_features_list():
#             if not feature_executed(piece, feature):
#                 break
#         else:
#             rename_beam(piece + "rot:_" + str(i % 4))
#             debug(r"C:\ProgramData\Ddx\EasyWood\Machines\Epicon7235_ETH_Zürich\Scl\test.py", "SUCCESS on piece: " + piece)
#             break      


