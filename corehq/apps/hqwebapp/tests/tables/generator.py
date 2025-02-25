import datetime
import uuid

from casexml.apps.case.mock import CaseBlock

from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def get_case_blocks():
    case_blocks = []

    date_opened = datetime.datetime(2022, 2, 17, 12)
    for name, properties in [
        ("Luna Zenzi", {"color": "red", "domain": "user input"}),
        ("Salman Srinivas", {"color": "purple", "domain": "user input"}),
        ("Stella Jonathon", {"color": "red", "domain": "user input"}),
        ("Arundhati Eddy", {"color": "green", "domain": "user input"}),
        ("Katherine Rebecca", {"color": "orange", "domain": "user input"}),
        ("Trish Hartmann", {"color": "blue", "domain": "user input"}),
        ("Karan Jonathon", {"color": "purple", "domain": "user input"}),
        ("Olivia Elicia", {"color": "yellow", "domain": "user input"}),
        ("Stella Coba", {"color": "periwinkle", "domain": "user input"}),
        ("Santiago Edwena", {"color": "salmon", "domain": "user input"}),
        ("Olivia Joeri", {"color": "purple", "domain": "user input"}),
    ]:
        case_blocks.append(CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='person',
            case_name=name,
            owner_id='person_owner',
            date_opened=date_opened,
            create=True,
            update=properties,
        ))
        date_opened += datetime.timedelta(days=1)

    case_blocks[-1].close = True  # close Olivia Joeri
    return case_blocks
