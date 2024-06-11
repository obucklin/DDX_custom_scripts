import ewd
from ewd import beam
from ewd.beam import *
from ewd.mach import get_pieces_list, get_machining_list, get_machining_tool_list, modify_machining_order, get_machining_type
from ddx.logger import debug
from ddx.gdb import get_note
from sclcore import execute_command_bool as exec_bool
from sclcore import execute_command_num as exec_num
from sclcore import execute_command_string as exec_string
from sclcore import Ref
import bcfcore
from ewd import error

bcfcore.do_debug()

machining_order = [
    "Folding",
    "Drill 3mm",
    "Castor D61",
    "Saw blade D350",
]


# for piece in get_pieces_list(only_curr_group = False):
#     set_current_beam(piece, update_ui=True)
#exec_bool("BeamMach", True, False)
machinings = get_machining_list()

machining_dict = {}
for machining in machinings:
    name = get_machining_type(machining)
    tool = get_machining_tool_list(machining)[0]
    if not machining_dict.get(tool, None):
        machining_dict[tool] = []
    machining_dict[tool].append(machining)

order = []
for tool in machining_order:
    order.extend(machining_dict.get(tool, []))

for i, machining in enumerate(order):
    if i < len(order) - 1:
        modify_machining_order(machining, order[-1])



    


