from ewd.beam import *
from ewd.mach import get_pieces_list


from sclcore import execute_command_bool as exec_bool
from sclcore import execute_command_num as exec_num
from sclcore import execute_command_string as exec_string
from sclcore import Ref
from bcfcore import do_debug


def parse_double_cut(piece, up = True):
    dc = get_double_cut(piece)
    if dc:
        rotate_double_cut(piece, dc, up)

def get_double_cut(piece):
    for feature in get_features_list(piece):
        if get_feature_property(feature, 'TYP') == "DoubleCut":
            return feature
    return None

def rotate_double_cut(piece, feature, up = True):
    face = (exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'FAC'))
    rotations = int(face) - 1
    if not up:
        rotations += 2
    if rotations:
        rotate_beam(piece, num_step = rotations)


'''script begins here'''
do_debug()


for piece in get_pieces_list(only_curr_group = False):
    set_current_beam(piece, update_ui = True)
    parse_double_cut(piece, up = True)
