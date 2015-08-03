from django.utils.translation import ugettext_noop

class LookupErrors:
    NotFound, MultipleResults = range(2)


class ImportErrors:
    InvalidOwnerName = ugettext_noop('Invalid Owner Name')
    InvalidOwnerId = ugettext_noop('Invalid Owner ID')
    InvalidParentId = ugettext_noop('Invalid Parent ID')
    InvalidDate = ugettext_noop('Invalid Date')
    BlankExternalId = ugettext_noop('Blank External ID')
    CaseGeneration = ugettext_noop('Case Generation Error')
    DuplicateLocationName = ugettext_noop('Duplicated Location Name')
