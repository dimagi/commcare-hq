from custom.icds.data_management.base import SQLBasedDataManagement
from custom.icds.data_management.doc_processors import (
    PopulateMissingMotherNameDocProcessor,
)


class PopulateMissingMotherName(SQLBasedDataManagement):
    slug = "populate_missing_mother_name"
    name = "Populate missing mother name"
    case_type = "person"
    doc_processor = PopulateMissingMotherNameDocProcessor
