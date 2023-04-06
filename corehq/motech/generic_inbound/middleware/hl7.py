from hl7apy.parser import parse_message


def hl7_str_to_dict(raw_hl7: str, use_long_name: bool = True) -> dict:
    """Convert an HL7 string to a dictionary
    :param raw_hl7: The input HL7 string
    :param use_long_name: Whether to use the long names
                          (e.g. "patient_name" instead of "pid_5")
    :returns: A dictionary representation of the HL7 message
    """
    raw_hl7 = raw_hl7.replace("\n", "\r")
    message = parse_message(raw_hl7)
    return hl7_message_to_dict(message, use_long_name=use_long_name)


def hl7_message_to_dict(message_part, use_long_name: bool = True) -> dict:
    """Convert an HL7 message to a dictionary
    :param message_part: The HL7 message as returned by :func:`hl7apy.parser.parse_message`
    :param use_long_name: Whether to use the long names (e.g. "patient_name" instead of "pid_5")
    :returns: A dictionary representation of the HL7 message
    """
    if message_part.children:
        data = {}
        for child in message_part.children:
            name = str(child.name)
            if use_long_name:
                name = str(child.long_name).lower() if child.long_name else name

            dictified = hl7_message_to_dict(child, use_long_name=use_long_name)
            if name in data:
                if not isinstance(data[name], list):
                    data[name] = [data[name]]
                data[name].append(dictified)
            else:
                data[name] = dictified
        return data
    else:
        return message_part.to_er7()
