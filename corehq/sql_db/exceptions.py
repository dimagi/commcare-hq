class PartitionValidationError(Exception):
    pass


class NotPowerOf2Error(PartitionValidationError):
    pass


class NonContinuousShardsError(PartitionValidationError):
    pass


class NotZeroStartError(PartitionValidationError):
    pass
