from custom.icds.data_management.es import ResetMissingCaseName
from custom.icds.data_management.sql import (
    PopulateMissingMotherName,
    SanitizePhoneNumber,
    SanitizeFemaleDeathType
)

DATA_MANAGEMENT_TASKS = {
    PopulateMissingMotherName.slug: PopulateMissingMotherName,
    ResetMissingCaseName.slug: ResetMissingCaseName,
    SanitizePhoneNumber.slug: SanitizePhoneNumber,
    SanitizeFemaleDeathType.slug: SanitizeFemaleDeathType,
}
