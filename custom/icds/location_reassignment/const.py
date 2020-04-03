OPERATION_COLUMN = 'operation'
OLD_SITE_CODE_COLUMN = 'site_code'
NEW_SITE_CODE_COLUMN = 'new_site_code'
MERGE_OPERATION = 'Merge'
SPLIT_OPERATION = 'Split'
MOVE_OPERATION = 'Move'
EXTRACT_OPERATION = 'Extract'
VALID_OPERATIONS = [MERGE_OPERATION, SPLIT_OPERATION, MOVE_OPERATION, EXTRACT_OPERATION]

# metadata fields on locations
DEPRECATED_TO = "deprecated_to"  # destination location this location was deprecated to
DEPRECATED_VIA = "deprecated_via"  # operation via this location was deprecated
DEPRECATED_AT = "deprecated_at"  # datetime when this location was deprecated
DEPRECATES = "deprecates"  # source location that this location deprecated
DEPRECATES_VIA = "deprecates_via"  # operation via which this location deprecated the source location
DEPRECATES_AT = "deprecates_at"  # datetime when this location deprecated the other location
