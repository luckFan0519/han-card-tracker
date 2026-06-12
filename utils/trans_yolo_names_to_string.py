from config.settings import LITTLE_JOKER_SHOWN, BIG_JOKER_SHOWN


def tool_trans(lst : list):
    string = ""
    for item in lst:
        if item == "小":
            string += LITTLE_JOKER_SHOWN
            continue
        if item == "大":
            string += BIG_JOKER_SHOWN
            continue
        string = string + str(item)
    return string

def trans_yolo_names_to_string(lst : list):
    string = ""
    for item in lst:
        string = string + tool_trans(item)
        string += "     "
    return  string