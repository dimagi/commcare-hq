class LookupErrors:
    NotFound, MultipleResults = range(2)


class ImportErrors:
    InvalidOwnerName = 'Invalid Owner Name'
    InvalidOwnerId = 'Invalid Owner ID'
    InvalidParentId = 'Invalid Parent ID'
    InvalidDate = 'Invalid Date'
    BlankExternalId = 'Blank External ID'
    CaseGeneration = 'Case Generation Error'
