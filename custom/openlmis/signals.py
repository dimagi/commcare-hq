from django.dispatch import receiver
from corehq import Domain
from corehq.apps.commtrack.models import Product, Program
from corehq.apps.commtrack.signals import supply_point_modified, stock_point_submission
from custom.openlmis.api import OpenLMISEndpoint, Requisition
from custom.openlmis.commtrack import sync_supply_point_to_openlmis, sync_stock_data_to_openlmis

@receiver(supply_point_modified)
def supply_point_updated(sender, supply_point, created, **kwargs):
    project = Domain.get_by_name(supply_point.domain)
    if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:
        endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
        sync_supply_point_to_openlmis(supply_point, endpoint)

@receiver(stock_point_submission)
def stock_data_submission(sender, cases, endpoint=None, **kwargs):

    if cases:
        project = Domain.get_by_name(cases[0].domain)

        if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:

            if endpoint is None:
                endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)

            # get agentCode and programCode - I assume all cases are part of the same program
            agentCode = (cases[0].get_supply_point_case()).location.site_code
            programCode = Program.get(cases[0].get_product().program_id).code

            products = []
            for rq in cases:
                product = rq.get_product()
                products.append({'productCode': product.code,
                                 'beginningBalance': product.beginningBalance,
                                 'quantityReceived': product.quantityReceived,
                                 'quantityDispensed': product.quantityDispensed,
                                 'lossesAndAdjustments': product.lossesAndAdjustments,
                                 'newPatientCount': product.newPatientCount,
                                 'stockOnHand': product.stockOnHand,
                                 'stockOutDays': product.stockOutDays,
                                 'quantityRequested': product.quantityRequested,
                                 'reasonForRequestedQuantity': product.reasonForRequestedQuantity,
                                 'remarks': product.remarks})

            stock_data = {  'agentCode': agentCode,
                            'programCode': programCode,
                            'products': products
            }
            response = sync_stock_data_to_openlmis(submission=stock_data, openlmis_endpoint=endpoint)

            if response['requisitionId'] is not None:
                for rq in cases:
                    rq.external_id = response['requisitionId']
                    rq.save()