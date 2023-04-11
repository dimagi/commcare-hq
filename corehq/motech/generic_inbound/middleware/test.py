import json

from corehq.motech.generic_inbound.middleware.hl7 import hl7_str_to_dict

# https://confluence.hl7.org/display/OO/v2+Sample+Messages
msh = "MSH|^~\\&|ADT1|GOOD HEALTH HOSPITAL|GHH LAB, INC.|GOOD HEALTH HOSPITAL|198808181126|SECURITY|" \
      "ADT^A01^ADT_A01|MSG00001|P|2.8||"

# I'm not 100% sure this will always match the XML
hl7_dict = hl7_str_to_dict(msh, False)
# print(json.dumps(hl7_dict, indent=2))
assert hl7_dict == {
    "MSH": {
        "MSH_1": "|",
        "MSH_2": "^~\\&",
        "MSH_3": {
            "HD_1": "ADT1"
        },
        "MSH_4": {
            "HD_1": "GOOD HEALTH HOSPITAL"
        },
        "MSH_5": {
            "HD_1": "GHH LAB, INC."
        },
        "MSH_6": {
            "HD_1": "GOOD HEALTH HOSPITAL"
        },
        "MSH_7": "198808181126",
        "MSH_8": "SECURITY",
        "MSH_9": {
            "MSG_1": "ADT",
            "MSG_2": "A01",
            "MSG_3": "ADT_A01"
        },
        "MSH_10": "MSG00001",
        "MSH_11": {
            "PT_1": "P"
        },
        "MSH_12": {
            "VID_1": "2.8"
        }
    }
}
