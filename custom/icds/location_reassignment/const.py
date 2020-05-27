# column names
# Download
CURRENT_LGD_CODE = "Current LGD Code"
CURRENT_NAME = "Current Location Name*"
CURRENT_PARENT_NAME = "Current Parent Name"
CURRENT_PARENT_SITE_CODE = "Current Parent Location Code*"
CURRENT_PARENT_TYPE = "Current Parent Type"
CURRENT_SITE_CODE_COLUMN = 'Current Location Code*'
CURRENT_SUB_DISTRICT_NAME = 'Current Sub-District Name'
NEW_LGD_CODE = "New LGD Code"
NEW_NAME = "New Location Name*"
NEW_SITE_CODE_COLUMN = 'New Location Code*'
NEW_PARENT_SITE_CODE = "New Parent Location Code*"
NEW_SUB_DISTRICT_NAME = 'New Sub-District Name'
OPERATION_COLUMN = 'Operation*'
USERNAME_COLUMN = "Username*"
NEW_USERNAME_COLUMN = "New User Name*"
MERGE_OPERATION = 'Merge'
SPLIT_OPERATION = 'Split'
MOVE_OPERATION = 'Move'
EXTRACT_OPERATION = 'Extract'
RENAME_OPERATION = 'Rename'
VALID_OPERATIONS = [MERGE_OPERATION, SPLIT_OPERATION, MOVE_OPERATION, EXTRACT_OPERATION]
OPERATIONS_TO_IGNORE = [RENAME_OPERATION]

AWC_NAME_COLUMN = 'Name of AWC'
AWC_CODE_COLUMN = 'AWC Code (11 digits)*'
HOUSEHOLD_MEMBER_DETAILS_COLUMN = 'Names of HH Members with Age and Gender'
HOUSEHOLD_ID_COLUMN = 'Household ID in ICDS-CAS (Do Not Modify)'

CASE_NAME = 'Name'
CASE_ID_COLUMN = 'Case ID in ICDS-CAS (Do Not Modify)'

# Dumper
OLD_LOCATION_CODE_COLUMN = "Old location code"
TRANSITION_COLUMN = "Transition"
NEW_LOCATION_CODE_COLUMN = "New location code"
MISSING_COLUMN = "Missing"
ARCHIVED_COLUMN = "Archived"
CASE_COUNT_COLUMN = "Number of Cases"
DUMPER_COLUMNS = [
    OLD_LOCATION_CODE_COLUMN,
    TRANSITION_COLUMN,
    NEW_LOCATION_CODE_COLUMN,
    MISSING_COLUMN,
    ARCHIVED_COLUMN,
    CASE_COUNT_COLUMN
]

# metadata fields on locations
DEPRECATED_TO = "deprecated_to"  # destination location this location was deprecated to
DEPRECATED_VIA = "deprecated_via"  # operation via this location was deprecated
DEPRECATED_AT = "deprecated_at"  # datetime when this location was deprecated
DEPRECATES = "deprecates"  # source location that this location deprecated
DEPRECATES_VIA = "deprecates_via"  # operation via which this location deprecated the source location
DEPRECATES_AT = "deprecates_at"  # datetime when this location deprecated the other location
LGD_CODE = "lgd_code"
MAP_LOCATION_NAME = "map_location_name"

AWC_CODE = "awc"
SUPERVISOR_CODE = "supervisor"  # also called "Sector" at times
BLOCK_CODE = "block"  # also called "Project" at times
# location types that append raw name and site code together as the final location name
HAVE_APPENDED_LOCATION_NAMES = [AWC_CODE, SUPERVISOR_CODE]

HOUSEHOLD_CASE_TYPE = "household"
PERSON_CASE_TYPE = "person"
WORKER_CASE_TYPE = "worker"

CASE_TYPES_TO_IGNORE = [
    WORKER_CASE_TYPE
]

# title mapped to headers for the sheet
SHEETS_TO_IGNORE = {
    "User Deletion Requests": ["Username to be deleted"]
}
