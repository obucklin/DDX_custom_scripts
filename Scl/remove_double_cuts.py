from ewd.beam import get_feature_property, get_features_list, delete_feature, set_current_beam
from ewd.mach import get_pieces_list
from bcfcore import do_debug

for piece in get_pieces_list(only_curr_group = False):
    set_current_beam(piece, update_ui=True)
    for feature in get_features_list():
        if get_feature_property(feature, 'TYP') == "DoubleCut":
            delete_feature(feature)