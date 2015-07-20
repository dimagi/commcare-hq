from django.utils.translation import ugettext_lazy

class LookupErrors:
    NotFound, MultipleResults = range(2)


class ImportErrors:
    InvalidOwnerName = ugettext_lazy('Invalid Owner Name')
    InvalidOwnerId = ugettext_lazy('Invalid Owner ID')
    InvalidParentId = ugettext_lazy('Invalid Parent ID')
    InvalidDate = ugettext_lazy('Invalid Date')
    BlankExternalId = ugettext_lazy('Blank External ID')
    CaseGeneration = ugettext_lazy('Case Generation Error')
