import os
from csv import DictReader, writer
from typing import Iterable, Iterator

from django.conf import settings

import attr

from custom.onse.const import MAPPINGS_FILE


@attr.s(auto_attribs=True)
class CasePropertyMap:
    case_property: str
    data_element_id: str
    data_set_id: str
    dhis2_name: str

    def __str__(self):
        return (f'case property {self.case_property!r} <- '
                f'data element {self.dhis2_name!r} ({self.data_element_id})')


def iter_mappings() -> Iterator[CasePropertyMap]:
    filename = os.path.join(settings.BASE_DIR, MAPPINGS_FILE)
    with open(filename, 'r') as csv_file:
        dict_reader = DictReader(csv_file)
        for dict_ in dict_reader:
            yield CasePropertyMap(**dict_)


def write_mappings(mappings: Iterable[CasePropertyMap]):
    filename = os.path.join(settings.BASE_DIR, MAPPINGS_FILE)
    with open(filename, 'w') as csv_file:
        csv_writer = writer(csv_file)
        header = [f.name for f in attr.fields(CasePropertyMap)]
        csv_writer.writerow(header)
        rows = (attr.astuple(m) for m in mappings)
        csv_writer.writerows(rows)
