import fluff
from couchforms.models import XFormInstance
from fluff.filters import ORFilter, ANDFilter
from casexml.apps.case.models import CommCareCase
from corehq.fluff.calculators.xform import FormPropertyFilter
from custom.intrahealth import INTRAHEALTH_DOMAINS, report_calcs, OPERATEUR_XMLNSES, get_real_date, \
    get_location_id, get_location_id_by_type, COMMANDE_XMLNSES, get_products, IsExistFormPropertyFilter, RAPTURE_XMLNSES, \
    get_rupture_products, LIVRAISON_XMLNSES, get_pps_name, get_district_name, get_month, get_products_code, \
    get_rupture_products_code

from custom.utils.utils import flat_field

IH_DELETED_TYPES = ('XFormArchived', 'XFormDuplicate', 'XFormDeprecated', 'XFormError')


def _get_all_forms():
    form_filters = []
    for xmlns in OPERATEUR_XMLNSES:
        form_filters.append(FormPropertyFilter(xmlns=xmlns))
    return form_filters


class CouvertureFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0])

    domains = INTRAHEALTH_DOMAINS
    group_by = ('domain', fluff.AttributeGetter('location_id', get_location_id))
    save_direct_to_sql = True
    deleted_types = IH_DELETED_TYPES

    location_id = flat_field(get_location_id)
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    pps_name = flat_field(lambda f: get_pps_name(f))
    district_name = flat_field(lambda f: get_district_name(f))
    month = flat_field(lambda f: get_month(f, 'real_date'))
    real_date_repeat = flat_field(get_real_date)
    registered = report_calcs.PPSRegistered()
    planned = report_calcs.PPSPlaned()


class TauxDeSatisfactionFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = ORFilter([
        FormPropertyFilter(xmlns=COMMANDE_XMLNSES[0]),
        FormPropertyFilter(xmlns=COMMANDE_XMLNSES[1])
        ])
    deleted_types = IH_DELETED_TYPES

    domains = INTRAHEALTH_DOMAINS
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'productName')),
                fluff.AttributeGetter('product_code', lambda f: get_products_code(f, 'productName')))
    save_direct_to_sql = True

    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    commandes = report_calcs.Commandes()
    recus = report_calcs.Recus()


class IntraHealthFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = ANDFilter([
        FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0]),
        IsExistFormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0],
                                  property_path="form",
                                  property_value='district_name'),
        IsExistFormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0], property_path="form", property_value='PPS_name')
    ])
    domains = INTRAHEALTH_DOMAINS
    deleted_types = IH_DELETED_TYPES
    save_direct_to_sql = True
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'product_name')),
                fluff.AttributeGetter('product_code', lambda f: get_products_code(f, 'product_name')))

    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    PPS_name = flat_field(lambda f: get_pps_name(f))
    district_name = flat_field(lambda f: get_district_name(f))
    location_id = flat_field(get_location_id)

    actual_consumption = report_calcs.PPSConsumption()
    billed_consumption = report_calcs.PPSConsumption(field='billed_consumption')
    stock = report_calcs.PPSConsumption('old_stock_total')
    total_stock = report_calcs.PPSConsumption('total_stock')
    quantity = report_calcs.PPSConsumption('display_total_stock')
    cmm = report_calcs.PPSConsumption('default_consumption')


class RecapPassageFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = ANDFilter([
        FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0]),
        IsExistFormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0], property_path="form", property_value='PPS_name')
    ])

    domains = INTRAHEALTH_DOMAINS
    deleted_types = IH_DELETED_TYPES
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_products(f, 'product_name')),
                fluff.AttributeGetter('product_code', lambda f: get_products_code(f, 'product_name')))
    save_direct_to_sql = True

    location_id = flat_field(get_location_id)
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    real_date_repeat = flat_field(get_real_date)
    PPS_name = flat_field(lambda f: f.form['PPS_name'])

    product = report_calcs.RecapPassage()


class TauxDeRuptureFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = ANDFilter([
        FormPropertyFilter(xmlns=RAPTURE_XMLNSES[0]),
        IsExistFormPropertyFilter(xmlns=RAPTURE_XMLNSES[0], property_path="form", property_value='district')
    ])
    domains = INTRAHEALTH_DOMAINS
    deleted_types = IH_DELETED_TYPES
    save_direct_to_sql = True
    group_by = (fluff.AttributeGetter('product_name', lambda f: get_rupture_products(f)),
                fluff.AttributeGetter('product_code', lambda f: get_rupture_products_code(f)))

    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    district_name = flat_field(lambda f: f.form['district'])
    PPS_name = flat_field(lambda f: CommCareCase.get(f.form['case']['@case_id']).name)

    total_stock = report_calcs.RupturesDeStocks('pps_stocked_out')


class LivraisonFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=LIVRAISON_XMLNSES[0])

    domains = INTRAHEALTH_DOMAINS
    group_by = ('domain', )
    save_direct_to_sql = True
    deleted_types = IH_DELETED_TYPES

    month = flat_field(lambda f: get_month(f, 'mois_visite'))
    duree_moyenne_livraison = report_calcs.DureeMoyenneLivraison()

    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: CommCareCase.get(f.form['case']['@case_id']).location_id)
    district_name = flat_field(lambda f: CommCareCase.get(f.form['case']['@case_id']).name)


CouvertureFluffPillow = CouvertureFluff.pillow()
RecapPassagePillow = RecapPassageFluff.pillow()
IntraHealthFluffPillow = IntraHealthFluff.pillow()
TauxDeSatisfactionFluffPillow = TauxDeSatisfactionFluff.pillow()
TauxDeRuptureFluffPillow = TauxDeRuptureFluff.pillow()
LivraisonFluffPillow = LivraisonFluff.pillow()
