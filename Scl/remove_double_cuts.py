from ewd.beam import get_feature_property, get_features_list, set_current_beam
from ewd.mach import get_pieces_list
from sclcore import execute_command_bool as exec_bool


def remove_double_cuts():
    for piece in get_pieces_list(only_curr_group = False):
        set_current_beam(piece, update_ui=True)
        for feature in get_features_list():
            if get_feature_property(feature, 'TYP') == "DoubleCut":
                exec_bool("SetNotes", piece + "\\" + feature, "NOTW", "1")

if __name__ == "__main__":
    remove_double_cuts()

remove_double_cuts()