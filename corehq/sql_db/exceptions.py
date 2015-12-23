class PartitionValidationError(Exception):
    pass


class PartitionedDatabaseRequiredError(PartitionValidationError):
    pass


class NotPowerOf2Error(PartitionValidationError):
    pass


class NonContinuousShardsError(PartitionValidationError):
    pass


class NotZeroStartError(PartitionValidationError):
    pass
