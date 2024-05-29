import ewd
import sclcore
from ddx import dlg, gdb
from ddx.gdb import param
from ewd.msg import get_compo_msg as get_msg
from ddx.autoexec import BaseOperation, ParamType, context
from ddx.confdlg import ConfigHelperDict, ConfigParamType
from sclcore import do_debug

class HHEasyLabelTransmission(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2189), "", "HolzHer")
        self.file_path = ""
        self.lbl_generation_path = ""

        self.register_param("lbl_generation_path", ParamType.INPUT, get_msg(2190), "")

    def init_operation(self, config):
        if config is None or not "trasm_file_path" in config:
            self.file_path = "%MACHPATH%\\script\\transmission\\src\\transmission.py"
            return

        self.register_param("lbl_generation_path", ParamType.INPUT, get_msg(2190), "")
        self.file_path = config["trasm_file_path"]

    def execute(self):
        transm_py_file = ewd.explode_file_path(self.file_path)
        lbl_generation_path = self.get_param("lbl_generation_path")

        with context(message="HHEasyLabel generation"):
            sclcore.execute_command("RunPyFun", transm_py_file, "main_function", lbl_generation_path)

    def configure(self, config):
        if config is None:
            config = {}

        #I prepare the dialogue ConfigHelper from dict
        cfg = ConfigHelperDict(filter_visible=False, category_visible=False)

        #generic parameters
        cfg.add_parameter(get_msg(2103), "trasm_file_path", get_msg(2116), ConfigParamType.FILE, "%MACHPATH%\\script\\transmission\\src\\transmission.py", file_filter="Python file (*.py)|*.py||")

        #I run the dialogue
        cfg.run(config)

        #I get the new dict
        config = cfg.to_dict()

        #I return the new configuration
        return config


class HHAdjustClamexDir(BaseOperation):
    def __init__(self):
        super().__init__(get_msg(2191), "", "HolzHer")

    def init_operation(self, config):
        dir_choices = [(-1, "X-"), (1, "X+")]
        self.register_param("dir_x", ParamType.INPUT, "Aggre X dir", -1, dir_choices)
        dir_choices = [(-1, "Y-"), (1, "Y+")]
        self.register_param("dir_y", ParamType.INPUT, "Aggre Y dir", -1, dir_choices)
        self.register_param("filter", ParamType.INPUT, get_msg(2192), "")

    def execute(self):
        with context(message="Adjust clamex DIR"):
            self.run()

    def run(self):
        macro_filter = self.get_param("filter")
        dir_x = self.get_param("dir_x")
        dir_y = self.get_param("dir_y")
        # scroll entities
        for part in gdb.get_entities():
            for layer in gdb.get_entities(part):
                # check filter
                if macro_filter == "" or macro_filter in gdb.split_name_group(layer)[0]:
                    for sub_lay_1 in gdb.get_entities(layer):
                        # if the sub layer exist and is called "GROUP"
                        if "GROUP" in gdb.split_name_group(sub_lay_1)[0]:
                            for sub_lay_2 in gdb.get_entities(sub_lay_1):
                                # if the sub-sub layer exist and is the one named "PATH"
                                if "PATH" in gdb.split_name_group(sub_lay_2)[0]:
                                    z_vect = gdb.get_reference(sub_lay_2)[2]

                                    # set label about kind of clamex dir
                                    if abs(z_vect.x) == 1:
                                        note = "X"
                                    elif abs(z_vect.y) == 1:
                                        note = "Y"
                                    elif abs(z_vect.z) == 1:
                                        note = "Z"
                                    else:
                                        note = "GEN"
                                    for entity in gdb.get_entities(sub_lay_2):
                                        gdb.set_note(entity, "Clamex_DIR", note)
                                    # check if the direction is ok or not
                                    if z_vect.x == -dir_x or z_vect.y == -dir_y or z_vect.z == -1:
                                        # change dir
                                        self.rotate_feature(gdb.split_name_group(sub_lay_1)[0], layer, 180)

    def rotate_feature(self, name, path, angle):
        """
        Rotate the passed parametric feature to the given angle
        :param name: layer name of the feature
        :type name: str
        :param path: path to the layer of the feature
        :param path: str
        :param angle: rotation angle
        :param angle: float
        """
        # get the ID of the feature
        action_id = param.get_id_action(name, path, 0)
        param_name = sclcore.Ref("")
        param_value = sclcore.Ref("")
        # get param name and value (the param is the angle)
        sclcore.execute_command_bool("GetActionParamValue", action_id, 0, param_name, param_value)
        # normalize the angle after having added the additional rotation
        temp_value = float(param_value.value)
        temp_value += 180
        while temp_value >= 360:
            temp_value -= 360
        # set the new angle to the feature
        sclcore.execute_command_bool("SetActionParamValue", action_id, 0, str(temp_value))
