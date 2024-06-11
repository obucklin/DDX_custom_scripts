from ewd.beam import get_feature_property, get_features_list, set_current_beam, get_current_beam, start_modify_feature, end_modify_feature, change_dimension_beam
from ewd.mach import get_pieces_list
from sclcore import execute_command_bool as exec_bool
from sclcore import execute_command_string as exec_string
import bcfcore

# bcfcore.do_debug()


def redraw():
    piece = get_current_beam()
    dims = []
    for key in ["LUN", "LAR", "ALT"]:
        dims.append(float(exec_string("GetNotes", piece, key)+"0"))
    change_dimension_beam(dims[1], dims[2], dims[0])
    


piece = get_current_beam()
for feature in get_features_list(piece):
    if feature[0:4] == "Text" or feature[0:6] == "Marker":
        face = (exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'FAC'))
        if face == '1':
            exec_bool("SetNotes", piece + "\\" + feature, "FAC", "3")
        elif face == '2':
            exec_bool("SetNotes", piece + "\\" + feature, "FAC", "4")
        elif face == '3':
            exec_bool("SetNotes", piece + "\\" + feature, "FAC", "1")
        elif face == '4':
            exec_bool("SetNotes", piece + "\\" + feature, "FAC", "2")
        new_face = (exec_string("GetNotes", '{}\\{}'.format(piece, feature), 'FAC'))
        pass
redraw()        

