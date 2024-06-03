import ewd
from ewd import beam
from ewd.beam import *
from ewd.mach import get_pieces_list, PieceRotation, set_current_piece
from ddx.logger import debug
from ddx.gdb import get_note
from sclcore import execute_command_bool as exec_bool
from sclcore import execute_command_num as exec_num
from sclcore import execute_command_string as exec_string
from sclcore import Ref
from bcfcore import do_debug
from ewd import error

do_debug()
import_btl(r"C:\Users\obucklin\Desktop\TestOutput\Module_44_test.btlx", "36")


def parse_double_cut(piece, up = True):
    dc = get_double_cut()
    if dc:
        flip_double_cut()
        rotate_double_cut(up)
        delete_feature(dc)
      
            
def get_double_cut():
    for feature in get_features_list():
        type = get_feature_property(feature, 'TYP')
        if type == "DoubleCut":
            return feature
    return None

def flip_double_cut():
    piece = get_current_beam()
    feature = get_double_cut()
    x_pos = (exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'Orientation'))
    if x_pos == "start":
        flip_beam()

def rotate_double_cut(up = True):
    piece = get_current_beam()
    feature = get_double_cut() 
    face = (exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'FAC'))
    for i in range(4):
        if (face == '3' and not up) or (face == '1' and up):
            break
        rotate_beam(fix_start_modality=1)
        beam = get_current_beam()
        set_current_beam(beam, update_ui=True)

def finished_leftovers(piece, leftover_features):
    for feature in leftover_features:
        if exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'NOTW') == '1':
            return False
    return True        
    
def machining_complete(piece, feature):                                             #returns false for example when drilling can't go to full depth
    mf = exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'MF')
    return mf == '1'

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


# def generate_predrill(piece):
#     for feature in get_features_list(piece):
#         type = get_feature_property(feature, 'TYP')
#         if type == "Drilling":
#             group = get_feature_property(feature, 'GRP')
#             id_feature = get_feature_property(feature, 'TYP')
#             face = get_feature_property(feature, 'FAC')

#             params = feature_notes(piece, feature)

#             predrill_feature = add_feature(group, id_feature, face, params)


def feature_notes(piece, feature):
    list = []
     
    note_names = ["TYP","FAC","StartX","StartY","DepthLimited","Angle","Inclination","Depth","Diameter","HoleType","DeclineDiameter","DeclineDepth","NOTW","HFS","HFE"]
    for name in note_names:
        list.append(exec_string("GetNotes", '{}\\{}'.format(piece, feature), name))
    return list




parts_to_rotate = []
for piece in get_pieces_list(only_curr_group = False):
    # set_current_beam(piece, update_ui=True)

    # for i in range(4):
    #     rotate_beam()
         



    # debug(r"C:\ProgramData\Ddx\EasyWood\Machines\Epicon7235_ETH_Zürich\Scl\test.py", "Processing piece: " + piece)

    start_face = parse_double_cut(piece)

    if start_face and start_face != "1":
        steps = int(start_face) - 1
        rotate_beam(fix_start_modality = 2)

    # generate_predrill(piece)

    if exec_bool("BeamMach", False, False):
        pass

    copy_piece = False
    remove_from_copy = []   
    remove_from_piece = []
    for feature in get_features_list():
        if feature_executed(piece, feature):
            remove_from_copy.append(feature)
        else:
            remove_from_piece.append(feature)
            copy_piece = True
    if copy_piece:
        copy = copy_beam(piece)
        rename_beam(piece + "_", copy)
        copy = piece + "_"
        parts_to_rotate.append(str(piece + "_"))
        remove_features_from_beam(piece, remove_from_piece)
        remove_features_from_beam(copy, remove_from_copy)


for piece in parts_to_rotate:
    set_current_beam(piece, update_ui=True)
    i = 0    
    for rotations in [2,1,2]:
        i += rotations
        rotate_beam(num_step = rotations)
        for feature in get_features_list():
            on = exec_bool("SetNotes", piece + "\\" + feature, "NOTW", "0")
        exec_bool("BeamMach", True, False)
        for feature in get_features_list():
            if not feature_executed(piece, feature):
                break
        else:
            rename_beam(piece + "rot:_" + str(i % 4))
            debug(r"C:\ProgramData\Ddx\EasyWood\Machines\Epicon7235_ETH_Zürich\Scl\test.py", "SUCCESS on piece: " + piece)
            break      

