from custom.icds.data_management.sql import (
    PopulateMissingMotherName,
    SanitizePhoneNumber,
)

DATA_MANAGEMENT_TASKS = {
    PopulateMissingMotherName.slug: PopulateMissingMotherName,
    SanitizePhoneNumber.slug: SanitizePhoneNumber,
}
