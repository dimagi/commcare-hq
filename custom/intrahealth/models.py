import fluff
from couchforms.models import XFormInstance
from fluff.filters import ORFilter
from corehq.fluff.calculators.xform import FormPropertyFilter
from custom.intrahealth import INTRAHEALTH_DOMAINS, report_calcs, OPERATEUR_XMLNSES, get_real_date, \
    get_location_id, get_location_id_by_type, COMMANDE_XMLNSES


def _get_all_forms():
    form_filters = []
    for xmlns in OPERATEUR_XMLNSES:
        form_filters.append(FormPropertyFilter(xmlns=xmlns))
    return form_filters


def flat_field(fn):
    def getter(item):
        return unicode(fn(item) or "")
    return fluff.FlatField(getter)


class CouvertureFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=OPERATEUR_XMLNSES[0])

    domains = INTRAHEALTH_DOMAINS
    group_by = ('domain', fluff.AttributeGetter('location_id', get_location_id))
    save_direct_to_sql = True

    location_id = flat_field(get_location_id)
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    real_date_repeat = flat_field(get_real_date)
    registered = report_calcs.PPSRegistered()
    planned = report_calcs.PPSPlaned()

class TauxDeSatisfactionFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = ORFilter([
        FormPropertyFilter(xmlns=COMMANDE_XMLNSES[0]),
        FormPropertyFilter(xmlns=COMMANDE_XMLNSES[1])
        ])

    domains = INTRAHEALTH_DOMAINS
    # group_by = ('domain', fluff.AttributeGetter('location_id', get_location_id))
    save_direct_to_sql = True

    # location_id = flat_field(get_location_id)
    region_id = flat_field(lambda f: get_location_id_by_type(form=f, type=u'r\xe9gion'))
    district_id = flat_field(lambda f: get_location_id_by_type(form=f, type='district'))
    diu_commandes = report_calcs.Commandes([u"diu"])
    diu_recus = report_calcs.Recus([u"diu"])
    implant_commandes = report_calcs.Commandes([u"jadelle"])
    implant_recus = report_calcs.Recus([u"jadelle"])
    injectable_commandes = report_calcs.Commandes([u"d\xe9po-provera", u"depo-provera"])
    injectable_recus = report_calcs.Recus([u"d\xe9po-provera", u"depo-provera"])
    microlut_commandes = report_calcs.Commandes([u"microlut/ovrette"])
    microlut_recus = report_calcs.Recus([u"microlut/ovrette"])
    microgynon_commandes = report_calcs.Commandes([u"microgynon/lof."])
    microgynon_recus = report_calcs.Recus([u"microgynon/lof."])
    masculin_commandes = report_calcs.Commandes([u"pr\xe9servatif masculin", u"preservatif masculin"])
    masculin_recus = report_calcs.Recus([u"pr\xe9servatif masculin", u"preservatif masculin"])
    feminin_commandes = report_calcs.Commandes([u"pr\xe9servatif f\xe9minin", u"preservatif feminin"])
    feminin_recus = report_calcs.Recus([u"pr\xe9servatif f\xe9minin", u"preservatif feminin"])
    cu_commandes = report_calcs.Commandes([u"cu"])
    cu_recus = report_calcs.Recus([u"cu"])
    collier_commandes = report_calcs.Commandes([u"collier"])
    collier_recus = report_calcs.Recus([u"collier"])



CouvertureFluffPillow = CouvertureFluff.pillow()
TauxDeSatisfactionFluffPillow = TauxDeSatisfactionFluff.pillow()