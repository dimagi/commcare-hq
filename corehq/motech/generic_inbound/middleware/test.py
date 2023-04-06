from corehq.motech.generic_inbound.middleware.hl7 import hl7_str_to_dict

# https://confluence.hl7.org/display/OO/v2+Sample+Messages
msh = "MSH|^~\\&|ADT1|GOOD HEALTH HOSPITAL|GHH LAB, INC.|GOOD HEALTH HOSPITAL|198808181126|SECURITY|" \
      "ADT^A01^ADT_A01|MSG00001|P|2.8||"

# I'm not 100% sure this will always match the XML
hl7_dict = hl7_str_to_dict(msh, False)
assert hl7_dict == {
    "MSH": {
        "MSH.1": "|",
        "MSH.2": "^~\\&",
        "MSH.3": {
            "HD.1": "ADT1"
        },
        "MSH.4": {
            "HD.1": "GOOD HEALTH HOSPITAL"
        },
        "MSH.5": {
            "HD.1": "GHH LAB, INC."
        },
        "MSH.6": {
            "HD.1": "GOOD HEALTH HOSPITAL"
        },
        "MSH.7": "198808181126",
        "MSH.8": "SECURITY",
        "MSH.9": {
            "MSG.1": "ADT",
            "MSG.2": "A01",
            "MSG.3": "ADT_A01"
        },
        "MSH.10": "MSG00001",
        "MSH.11": {
            "PT.1": "P"
        },
        "MSH.12": {
            "VID.1": "2.8"
        }
    }
}
