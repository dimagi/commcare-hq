import uuid


class UUIDGeneratorException(Exception):
    pass


class UUIDGeneratorMixin(object):
    """
    Automatically generates uuids on __init__ if not generated yet.

    To use: Add this mixin to your model as the left-most class being inherited from
    and list all field names in UUIDS_TO_GENERATE to generate uuids for.

    NOTE: Where possible, a UUIDField should be used instead of this mixin. But
    this is needed in cases where migrating a char field to a UUIDField is
    not possible because some of the existing uuids don't match the
    UUIDField format constraints.
    """

    def __init__(self, *args, **kwargs):
        super(UUIDGeneratorMixin, self).__init__(*args, **kwargs)

        field_names = getattr(self, 'UUIDS_TO_GENERATE', [])
        if not field_names:
            raise UUIDGeneratorException("Expected UUIDS_TO_GENERATE to not be empty")

        for field_name in field_names:
            value = getattr(self, field_name)
            if not value:
                new_value = uuid.uuid4()
                if getattr(self, 'CONVERT_UUID_TO_HEX', True):
                    new_value = new_value.hex
                setattr(self, field_name, new_value)


# https://gist.github.com/glarrain/5448253
class ValidateModelMixin(object):

    def save(self, *args, **kwargs):
        self.full_clean()
        super(ValidateModelMixin, self).save(*args, **kwargs)
