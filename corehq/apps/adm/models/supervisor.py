from couchdbkit.ext.django.schema import IntegerProperty
from corehq.apps.adm.models import ADMColumn

class TotalCasesColumn(ADMColumn):
    pass

class InactiveCasesColumn(ADMColumn):
    inactive_milestone_days = IntegerProperty(default=45)

class ActiveCasesInDatespanColumn(ADMColumn):
    pass


class CasesLateValueColumn(ADMColumn):
    """

    """
    days_for_late = IntegerProperty()

class TotalFormSubmissionsColumn(ADMColumn):
    pass

class ClientsVisitedColumn(ADMColumn):
    pass

class InactiveClientsColumn(ADMColumn):
    inactivity_milestone = IntegerProperty()