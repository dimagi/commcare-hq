from corehq.fluff.calculators.xform import FormPropertyFilter
from couchforms.models import XFormInstance
import fluff
from custom.tdh import TDH_DOMAINS, ENROLL_CHILD_XMLNSES, INFANT_CLASSIFICATION_XMLNSES, INFANT_TREATMENT_XMLNSES, \
    NEWBORN_CLASSIFICATION_XMLNSES, NEWBORN_TREATMENT_XMLNSES, CHILD_CLASSIFICATION_XMLNSES, \
    CHILD_TREATMENT_XMLNSES
from custom.utils.utils import flat_field


class TDHNullEmitter(fluff.Calculator):
    @fluff.null_emitter
    def numerator(self, case):
        yield None


class TDHDateEmiiter(fluff.Calculator):
    @fluff.date_emitter
    def total(self, form):
        yield {
            'date': form.received_on,
            'value': 0
        }


class TDHEnrollChildFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=ENROLL_CHILD_XMLNSES[0])
    domains = TDH_DOMAINS
    save_direct_to_sql = True

    case_id = flat_field(lambda f: f.form['case_rec_child']['case']['@case_id'])
    name = flat_field(lambda f: f.form.get('demographics', {}).get('name', ''))
    sex = flat_field(lambda f: f.form.get('demographics', {}).get('sex', ''))
    mother_name = flat_field(lambda f: f.form.get('demographics', {}).get('mother_name', ''))
    village = flat_field(lambda f: f.form.get('demographics', {}).get('village', ''))
    last_visit_date = flat_field(lambda f: f.form['case_rec_child']['case']['update'].get('last_visit_date', ''))
    dob = flat_field(lambda f: f.form.get('age_questions', {}).get('dob', ''))
    dob_known = flat_field(lambda f: f.form.get('age_questions', {}).get('dob_known', ''))
    age_in_years = flat_field(lambda f: f.form.get('age_in_years', ''))

    numerator = TDHNullEmitter()


class TDHInfantClassificationFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=INFANT_CLASSIFICATION_XMLNSES[0])
    domains = TDH_DOMAINS
    save_direct_to_sql = True

    group_by = ('domain', )

    case_id = flat_field(lambda f: f.form['case']['@case_id'])
    user_id = flat_field(lambda f: f.form['case']['@user_id'])
    tablet_login_id = flat_field(lambda f: f.form['meta']['username'])
    author_id = flat_field(lambda f: f.form.get('selected_user_id', ''))
    author_name = flat_field(lambda f: f.form.get('selected_user_name', ''))
    L_hfa = flat_field(lambda f: f.form.get('L_hfa', ''))
    L_wfa = flat_field(lambda f: f.form.get('L_wfa', ''))
    L_wfh = flat_field(lambda f: f.form.get('L_wfh', ''))
    M_hfa = flat_field(lambda f: f.form.get('M_hfa', ''))
    M_wfa = flat_field(lambda f: f.form.get('M_wfa', ''))
    M_wfh = flat_field(lambda f: f.form.get('M_wfh', ''))
    S_hfa = flat_field(lambda f: f.form.get('S_hfa', ''))
    S_wfa = flat_field(lambda f: f.form.get('S_wfa', ''))
    S_wfh = flat_field(lambda f: f.form.get('S_wfh', ''))
    age_in_months = flat_field(lambda f: f.form.get('age_in_months', ''))
    bad_height = flat_field(lambda f: f.form.get('bad_height', ''))
    dob = flat_field(lambda f: f.form.get('dob', ''))
    au_moins_deux_signes_vih = flat_field(lambda f: f.form.get('au_moins_deux_signes_vih', ''))
    incapable_nourir = flat_field(lambda f: f.form.get('incapable_nourir', ''))
    infection_bac_grave = flat_field(lambda f: f.form.get('infection_bac_grave', ''))
    infection_bac_locale = flat_field(lambda f: f.form.get('infection_bac_locale', ''))
    mean_hfa = flat_field(lambda f: f.form.get('mean_hfa', ''))
    mean_wfa = flat_field(lambda f: f.form.get('mean_wfa', ''))
    mean_wfh = flat_field(lambda f: f.form.get('mean_wfh', ''))

    alimentation_low = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_low', ''))
    alimentation_medium = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_medium', ''))
    alimentation_qa = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qa', ''))
    alimentation_qb = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qb', ''))
    alimentation_qc = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qc', ''))
    alimentation_qd = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qd', ''))
    alimentation_qe = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qe', ''))
    alimentation_qf = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qf', ''))
    alimentation_qg = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qg', ''))
    alimentation_qh = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qh', ''))

    centile_hfa = flat_field(lambda f: f.form.get('centile_hfa', ''))
    centile_wfa = flat_field(lambda f: f.form.get('centile_wfa', ''))
    centile_wfh = flat_field(lambda f: f.form.get('centile_wfh', ''))
    classification_deshydratation = flat_field(lambda f: f.form.get('classification_deshydratation', ''))
    classification_diahree = flat_field(lambda f: f.form.get('classification_diahree', ''))
    classification_infection = flat_field(lambda f: f.form.get('classification_infection', ''))
    classification_malnutrition = flat_field(lambda f: f.form.get('classification_malnutrition', ''))
    classification_vih = flat_field(lambda f: f.form.get('classification_vih', ''))

    diarrhee_non = flat_field(lambda f: f.form.get('diarrhee', {}).get('diarrhee_non', ''))
    diarrhee_qa = flat_field(lambda f: f.form.get('diarrhee', {}).get('diarrhee_qa', ''))

    inf_bac_freq_resp = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_freq_resp', ''))
    inf_bac_grave = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_grave', ''))
    inf_bac_non = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_non', ''))
    inf_bac_qa = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qa', ''))
    inf_bac_qc = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qc', ''))
    inf_bac_qd = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qd', ''))
    inf_bac_qe = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qe', ''))
    inf_bac_qf = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qf', ''))
    inf_bac_qg = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qg', ''))
    inf_bac_qh = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qh', ''))
    inf_bac_qi = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qi', ''))
    inf_bac_qj = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qj', ''))
    inf_bac_qk = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qk', ''))
    inf_bac_ql = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_ql', ''))
    inf_bac_qm = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qm', ''))

    muac_change = flat_field(lambda f: f.form.get('muac_change', ''))
    muac_change_status = flat_field(lambda f: f.form.get('muac_change_status', ''))
    muac_grading = flat_field(lambda f: f.form.get('muac_grading', ''))
    pas_signes_vih = flat_field(lambda f: f.form.get('pas_signes_vih', ''))

    sd2neg_hfa = flat_field(lambda f: f.form.get('sd2neg_hfa', ''))
    sd2neg_wfa = flat_field(lambda f: f.form.get('sd2neg_wfa', ''))
    sd2neg_wfh = flat_field(lambda f: f.form.get('sd2neg_wfh', ''))
    sd2pos_hfa = flat_field(lambda f: f.form.get('sd2pos_hfa', ''))
    sd2pos_wfa = flat_field(lambda f: f.form.get('sd2pos_wfa', ''))
    sd2pos_wfh = flat_field(lambda f: f.form.get('sd2pos_wfh', ''))
    sd3neg_hfa = flat_field(lambda f: f.form.get('sd3neg_hfa', ''))
    sd3neg_wfa = flat_field(lambda f: f.form.get('sd3neg_wfa', ''))
    sd3neg_wfh = flat_field(lambda f: f.form.get('sd3neg_wfh', ''))
    sd3pos_hfa = flat_field(lambda f: f.form.get('sd3pos_hfa', ''))
    sd3pos_wfa = flat_field(lambda f: f.form.get('sd3pos_wfa', ''))
    sd3pos_wfh = flat_field(lambda f: f.form.get('sd3pos_wfh', ''))

    selected_user_id_and_name = flat_field(lambda f: f.form.get('selected_user_id_and_name', ''))

    seriousness_alimentation = flat_field(lambda f: f.form.get('seriousness_alimentation', ''))
    seriousness_diarrhee = flat_field(lambda f: f.form.get('seriousness_diarrhee', ''))
    seriousness_inf_bac = flat_field(lambda f: f.form.get('seriousness_inf_bac', ''))
    seriousness_vih = flat_field(lambda f: f.form.get('seriousness_vih', ''))
    sex = flat_field(lambda f: f.form.get('sex', ''))
    sex_loaded = flat_field(lambda f: f.form.get('sex_loaded', ''))
    signes_deshy_evident = flat_field(lambda f: f.form.get('signes_deshy_evident', ''))
    signes_deshy_severe = flat_field(lambda f: f.form.get('signes_deshy_severe', ''))
    signes_pb_alim = flat_field(lambda f: f.form.get('signes_pb_alim', ''))
    update_vaccines = flat_field(lambda f: f.form.get('update_vaccines', ''))

    vaccines = flat_field(lambda f: ', '.join([k for k, v in f.form.get('vaccines', {}).iteritems()
                                               if v == 'yes']))
    bcg = flat_field(lambda f: f.form.get('vaccines', {}).get('bcg', ''))
    vih_non = flat_field(lambda f: f.form.get('vih', {}).get('vih_non', ''))
    vih_qa = flat_field(lambda f: f.form.get('vih', {}).get('vih_qa', ''))
    vih_qb = flat_field(lambda f: f.form.get('vih', {}).get('vih_qb', ''))
    vih_qc = flat_field(lambda f: f.form.get('vih', {}).get('vih_qc', ''))
    vih_qd = flat_field(lambda f: f.form.get('vih', {}).get('vih_qd', ''))
    vih_qe = flat_field(lambda f: f.form.get('vih', {}).get('vih_qe', ''))
    vih_qf = flat_field(lambda f: f.form.get('vih', {}).get('vih_qf', ''))
    vih_qg = flat_field(lambda f: f.form.get('vih', {}).get('vih_qg', ''))
    vih_qh = flat_field(lambda f: f.form.get('vih', {}).get('vih_qh', ''))
    vih_qi = flat_field(lambda f: f.form.get('vih', {}).get('vih_qi', ''))
    vih_qj = flat_field(lambda f: f.form.get('vih', {}).get('vih_qj', ''))
    vih_qk = flat_field(lambda f: f.form.get('vih', {}).get('vih_qk', ''))
    vih_ql = flat_field(lambda f: f.form.get('vih', {}).get('vih_ql', ''))
    vih_symp_possible = flat_field(lambda f: f.form.get('vih', {}).get('vih_symp_possible', ''))

    visit_date = flat_field(lambda f: f.form.get('visit_date', ''))
    visit_type = flat_field(lambda f: f.form.get('visit_type', ''))

    height = flat_field(lambda f: f.form.get('vitals', {}).get('height', ''))
    muac = flat_field(lambda f: f.form.get('vitals', {}).get('muac', ''))
    temp = flat_field(lambda f: f.form.get('vitals', {}).get('temp', ''))
    weight = flat_field(lambda f: f.form.get('vitals', {}).get('weight', ''))

    zscore_grading_hfa = flat_field(lambda f: f.form.get('zscore_grading_hfa', ''))
    zscore_grading_wfa = flat_field(lambda f: f.form.get('zscore_grading_wfa', ''))
    zscore_grading_wfh = flat_field(lambda f: f.form.get('zscore_grading_wfh', ''))
    zscore_hfa = flat_field(lambda f: f.form.get('zscore_hfa', ''))
    zscore_hfa_change = flat_field(lambda f: f.form.get('zscore_hfa_change', ''))
    zscore_hfa_change_status = flat_field(lambda f: f.form.get('zscore_hfa_change_status', ''))
    zscore_wfa = flat_field(lambda f: f.form.get('zscore_wfa', ''))
    zscore_wfa_change = flat_field(lambda f: f.form.get('zscore_wfa_change', ''))
    zscore_wfa_change_status = flat_field(lambda f: f.form.get('zscore_wfa_change_status', ''))
    zscore_wfh = flat_field(lambda f: f.form.get('zscore_wfh', ''))
    zscore_wfh_change = flat_field(lambda f: f.form.get('zscore_wfh_change', ''))
    zscore_wfh_change_status = flat_field(lambda f: f.form.get('zscore_wfh_change_status', ''))

    last_height = flat_field(lambda f: f.form['case']['update'].get('last_height', ''))
    last_weight = flat_field(lambda f: f.form['case']['update'].get('last_weight', ''))

    numerator = TDHDateEmiiter()


class TDHNewbornClassificationFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=NEWBORN_CLASSIFICATION_XMLNSES[0])
    domains = TDH_DOMAINS
    save_direct_to_sql = True

    group_by = ('domain', )

    case_id = flat_field(lambda f: f.form['case']['@case_id'])
    user_id = flat_field(lambda f: f.form['case']['@user_id'])
    tablet_login_id = flat_field(lambda f: f.form['meta']['username'])
    author_id = flat_field(lambda f: f.form.get('selected_user_id', ''))
    author_name = flat_field(lambda f: f.form.get('selected_user_name', ''))
    L_hfa = flat_field(lambda f: f.form.get('L_hfa', ''))
    L_wfa = flat_field(lambda f: f.form.get('L_wfa', ''))
    L_wfh = flat_field(lambda f: f.form.get('L_wfh', ''))
    M_hfa = flat_field(lambda f: f.form.get('M_hfa', ''))
    M_wfa = flat_field(lambda f: f.form.get('M_wfa', ''))
    M_wfh = flat_field(lambda f: f.form.get('M_wfh', ''))
    S_hfa = flat_field(lambda f: f.form.get('S_hfa', ''))
    S_wfa = flat_field(lambda f: f.form.get('S_wfa', ''))
    S_wfh = flat_field(lambda f: f.form.get('S_wfh', ''))
    age_in_months = flat_field(lambda f: f.form.get('age_in_months', ''))
    age_in_weeks = flat_field(lambda f: f.form.get('age_in_weeks', ''))
    bad_height = flat_field(lambda f: f.form.get('bad_height', ''))
    dob = flat_field(lambda f: f.form.get('dob', ''))
    infection_locale = flat_field(lambda f: f.form.get('infection_locale', ''))
    maladie_grave = flat_field(lambda f: f.form.get('maladie_grave', ''))
    maladie_grave_alim = flat_field(lambda f: f.form.get('maladie_grave_alim', ''))
    mean_hfa = flat_field(lambda f: f.form.get('mean_hfa', ''))
    mean_wfa = flat_field(lambda f: f.form.get('mean_wfa', ''))
    mean_wfh = flat_field(lambda f: f.form.get('mean_wfh', ''))

    alimentation_low = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_low', ''))
    alimentation_medium = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_medium', ''))
    alimentation_high = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_high', ''))
    alimentation_qa = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qa', ''))
    alimentation_qb = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qb', ''))
    alimentation_qc = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qc', ''))
    alimentation_qd = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qd', ''))
    alimentation_qe = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qe', ''))
    alimentation_qf = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qf', ''))
    alimentation_qg = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qg', ''))
    alimentation_qh = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qh', ''))
    alimentation_qi = flat_field(lambda f: f.form.get('alimentation', {}).get('alimentation_qi', ''))

    centile_hfa = flat_field(lambda f: f.form.get('centile_hfa', ''))
    centile_wfa = flat_field(lambda f: f.form.get('centile_wfa', ''))
    centile_wfh = flat_field(lambda f: f.form.get('centile_wfh', ''))
    classification_infection = flat_field(lambda f: f.form.get('classification_infection', ''))
    classification_malnutrition = flat_field(lambda f: f.form.get('classification_malnutrition', ''))
    classification_occular = flat_field(lambda f: f.form.get('classification_occular', ''))
    classification_poids = flat_field(lambda f: f.form.get('classification_poids', ''))
    classification_vih = flat_field(lambda f: f.form.get('classification_vih', ''))

    diarrhee_non = flat_field(lambda f: f.form.get('diarrhee', {}).get('diarrhee_non', ''))
    diarrhee_qa = flat_field(lambda f: f.form.get('diarrhee', {}).get('diarrhee_qa', ''))

    inf_bac_freq_resp = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_freq_resp', ''))
    inf_bac_grave = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_grave', ''))
    inf_bac_hypo = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_hypo', ''))
    inf_bac_locale = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_locale', ''))
    inf_bac_peu_probable = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_peu_probable', ''))
    inf_bac_qa = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qa', ''))
    inf_bac_qb = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qb', ''))
    inf_bac_qd = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qd', ''))
    inf_bac_qe = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qe', ''))
    inf_bac_qf = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qf', ''))
    inf_bac_qg = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qg', ''))
    inf_bac_qh = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qh', ''))
    inf_bac_qi = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qi', ''))
    inf_bac_qj = flat_field(lambda f: f.form.get('inf_bac', {}).get('inf_bac_qj', ''))

    inf_occ_low = flat_field(lambda f: f.form.get('inf_occ', {}).get('inf_occ_low', ''))
    inf_occ_medium = flat_field(lambda f: f.form.get('inf_occ', {}).get('inf_occ_medium', ''))
    inf_occ_qa = flat_field(lambda f: f.form.get('inf_occ', {}).get('inf_bac_qj', ''))

    muac_change = flat_field(lambda f: f.form.get('muac_change', ''))
    muac_change_status = flat_field(lambda f: f.form.get('muac_change_status', ''))
    muac_grading = flat_field(lambda f: f.form.get('muac_grading', ''))
    pb_alim = flat_field(lambda f: f.form.get('pb_alim', ''))
    prev_muac = flat_field(lambda f: f.form.get('prev_muac', ''))
    prev_zscore_hfa = flat_field(lambda f: f.form.get('prev_muac', ''))
    prev_zscore_wfa = flat_field(lambda f: f.form.get('prev_muac', ''))
    prev_zscore_wfh = flat_field(lambda f: f.form.get('prev_muac', ''))

    poids_high = flat_field(lambda f: f.form.get('poids', {}).get('poids_high', ''))
    poids_medium = flat_field(lambda f: f.form.get('poids', {}).get('poids_medium', ''))
    poids_low = flat_field(lambda f: f.form.get('poids', {}).get('poids_low', ''))
    poids_qa = flat_field(lambda f: f.form.get('poids', {}).get('poids_qa', ''))

    sd2neg_hfa = flat_field(lambda f: f.form.get('sd2neg_hfa', ''))
    sd2neg_wfa = flat_field(lambda f: f.form.get('sd2neg_wfa', ''))
    sd2neg_wfh = flat_field(lambda f: f.form.get('sd2neg_wfh', ''))
    sd2pos_hfa = flat_field(lambda f: f.form.get('sd2pos_hfa', ''))
    sd2pos_wfa = flat_field(lambda f: f.form.get('sd2pos_wfa', ''))
    sd2pos_wfh = flat_field(lambda f: f.form.get('sd2pos_wfh', ''))
    sd3neg_hfa = flat_field(lambda f: f.form.get('sd3neg_hfa', ''))
    sd3neg_wfa = flat_field(lambda f: f.form.get('sd3neg_wfa', ''))
    sd3neg_wfh = flat_field(lambda f: f.form.get('sd3neg_wfh', ''))
    sd3pos_hfa = flat_field(lambda f: f.form.get('sd3pos_hfa', ''))
    sd3pos_wfa = flat_field(lambda f: f.form.get('sd3pos_wfa', ''))
    sd3pos_wfh = flat_field(lambda f: f.form.get('sd3pos_wfh', ''))

    selected_user_id_and_name = flat_field(lambda f: f.form.get('selected_user_id_and_name', ''))

    seriousness_alimentation = flat_field(lambda f: f.form.get('seriousness_alimentation', ''))
    seriousness_inf_bac = flat_field(lambda f: f.form.get('seriousness_inf_bac', ''))
    seriousness_inf_occ = flat_field(lambda f: f.form.get('seriousness_inf_occ', ''))
    seriousness_poids = flat_field(lambda f: f.form.get('seriousness_poids', ''))
    seriousness_vih = flat_field(lambda f: f.form.get('seriousness_vih', ''))
    sex = flat_field(lambda f: f.form.get('sex', ''))
    sex_loaded = flat_field(lambda f: f.form.get('sex_loaded', ''))
    signes_hiv = flat_field(lambda f: f.form.get('signes_hiv', ''))
    update_vaccines = flat_field(lambda f: f.form.get('update_vaccines', ''))

    vaccines = flat_field(lambda f: ', '.join([k for k, v in f.form.get('vaccines', {}).iteritems()
                                               if v == 'yes']))
    bcg = flat_field(lambda f: f.form.get('vaccines', {}).get('bcg', ''))
    opv_0 = flat_field(lambda f: f.form.get('vaccines', {}).get('opv_0', ''))

    vih_peu_probable = flat_field(lambda f: f.form.get('vih', {}).get('vih_peu_probable', ''))
    vih_possible = flat_field(lambda f: f.form.get('vih', {}).get('vih_possible', ''))
    vih_probable = flat_field(lambda f: f.form.get('vih', {}).get('vih_probable', ''))
    vih_qa = flat_field(lambda f: f.form.get('vih', {}).get('vih_qa', ''))
    vih_qb = flat_field(lambda f: f.form.get('vih', {}).get('vih_qb', ''))
    vih_qc = flat_field(lambda f: f.form.get('vih', {}).get('vih_qc', ''))
    vih_qd = flat_field(lambda f: f.form.get('vih', {}).get('vih_qd', ''))
    vih_qe = flat_field(lambda f: f.form.get('vih', {}).get('vih_qe', ''))
    vih_qf = flat_field(lambda f: f.form.get('vih', {}).get('vih_qf', ''))
    vih_qg = flat_field(lambda f: f.form.get('vih', {}).get('vih_qg', ''))

    visit_date = flat_field(lambda f: f.form.get('visit_date', ''))
    visit_type = flat_field(lambda f: f.form.get('visit_type', ''))

    height = flat_field(lambda f: f.form.get('vitals', {}).get('height', ''))
    muac = flat_field(lambda f: f.form.get('vitals', {}).get('muac', ''))
    temp = flat_field(lambda f: f.form.get('vitals', {}).get('temp', ''))
    weight = flat_field(lambda f: f.form.get('vitals', {}).get('weight', ''))

    zscore_grading_hfa = flat_field(lambda f: f.form.get('zscore_grading_hfa', ''))
    zscore_grading_wfa = flat_field(lambda f: f.form.get('zscore_grading_wfa', ''))
    zscore_grading_wfh = flat_field(lambda f: f.form.get('zscore_grading_wfh', ''))
    zscore_hfa = flat_field(lambda f: f.form.get('zscore_hfa', ''))
    zscore_hfa_change = flat_field(lambda f: f.form.get('zscore_hfa_change', ''))
    zscore_hfa_change_status = flat_field(lambda f: f.form.get('zscore_hfa_change_status', ''))
    zscore_wfa = flat_field(lambda f: f.form.get('zscore_wfa', ''))
    zscore_wfa_change = flat_field(lambda f: f.form.get('zscore_wfa_change', ''))
    zscore_wfa_change_status = flat_field(lambda f: f.form.get('zscore_wfa_change_status', ''))
    zscore_wfh = flat_field(lambda f: f.form.get('zscore_wfh', ''))
    zscore_wfh_change = flat_field(lambda f: f.form.get('zscore_wfh_change', ''))
    zscore_wfh_change_status = flat_field(lambda f: f.form.get('zscore_wfh_change_status', ''))

    last_height = flat_field(lambda f: f.form['case']['update'].get('last_height', ''))
    last_weight = flat_field(lambda f: f.form['case']['update'].get('last_weight', ''))

    numerator = TDHDateEmiiter()


class TDHChildClassificationFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=CHILD_CLASSIFICATION_XMLNSES[0])
    domains = TDH_DOMAINS
    save_direct_to_sql = True

    group_by = ('domain', )

    case_id = flat_field(lambda f: f.form['case']['@case_id'])
    user_id = flat_field(lambda f: f.form['case']['@user_id'])
    tablet_login_id = flat_field(lambda f: f.form['meta']['username'])
    author_id = flat_field(lambda f: f.form.get('selected_user_id', ''))
    author_name = flat_field(lambda f: f.form.get('selected_user_name', ''))
    L_hfa = flat_field(lambda f: f.form.get('L_hfa', ''))
    L_wfa = flat_field(lambda f: f.form.get('L_wfa', ''))
    L_wfh = flat_field(lambda f: f.form.get('L_wfh', ''))
    M_hfa = flat_field(lambda f: f.form.get('M_hfa', ''))
    M_wfa = flat_field(lambda f: f.form.get('M_wfa', ''))
    M_wfh = flat_field(lambda f: f.form.get('M_wfh', ''))
    S_hfa = flat_field(lambda f: f.form.get('S_hfa', ''))
    S_wfa = flat_field(lambda f: f.form.get('S_wfa', ''))
    S_wfh = flat_field(lambda f: f.form.get('S_wfh', ''))
    age_in_months = flat_field(lambda f: f.form.get('age_in_months', ''))
    age_in_weeks = flat_field(lambda f: f.form.get('age_in_weeks', ''))
    bad_height = flat_field(lambda f: f.form.get('bad_height', ''))
    dob = flat_field(lambda f: f.form.get('dob', ''))
    anemie_grave = flat_field(lambda f: f.form.get('anemie_grave', ''))
    au_moins_deux_maladies = flat_field(lambda f: f.form.get('au_moins_deux_maladies', ''))
    au_plus_une_maladie = flat_field(lambda f: f.form.get('au_plus_une_maladie', ''))
    mastoidite = flat_field(lambda f: f.form.get('mastoidite', ''))
    mean_hfa = flat_field(lambda f: f.form.get('mean_hfa', ''))
    mean_wfa = flat_field(lambda f: f.form.get('mean_wfa', ''))
    mean_wfh = flat_field(lambda f: f.form.get('mean_wfh', ''))

    anemia_none = flat_field(lambda f: f.form.get('anemie', {}).get('anemia_none', ''))
    anemia_normal = flat_field(lambda f: f.form.get('anemie', {}).get('anemia_normal', ''))
    anemia_serious = flat_field(lambda f: f.form.get('anemie', {}).get('anemia_serious', ''))
    paleur_palmaire = flat_field(lambda f: f.form.get('anemie', {}).get('paleur_palmaire', ''))

    centile_hfa = flat_field(lambda f: f.form.get('centile_hfa', ''))
    centile_wfa = flat_field(lambda f: f.form.get('centile_wfa', ''))
    centile_wfh = flat_field(lambda f: f.form.get('centile_wfh', ''))
    classification_anemie = flat_field(lambda f: f.form.get('classification_anemie', ''))
    classification_deshydratation = flat_field(lambda f: f.form.get('classification_deshydratation', ''))
    classification_diahree = flat_field(lambda f: f.form.get('classification_diahree', ''))
    classification_dysenterie = flat_field(lambda f: f.form.get('classification_dysenterie', ''))
    classification_malnutrition = flat_field(lambda f: f.form.get('classification_malnutrition', ''))
    classification_oreille = flat_field(lambda f: f.form.get('classification_oreille', ''))
    classification_paludisme = flat_field(lambda f: f.form.get('classification_paludisme', ''))
    classification_pneumonie = flat_field(lambda f: f.form.get('classification_pneumonie', ''))
    classification_rougeole = flat_field(lambda f: f.form.get('classification_rougeole', ''))
    classification_vih = flat_field(lambda f: f.form.get('classification_vih', ''))
    classifications_graves = flat_field(lambda f: f.form.get('classifications_graves', ''))

    deshydratation_evident = flat_field(lambda f: f.form.get('deshydratation_evident', ''))
    deshydratation_severe = flat_field(lambda f: f.form.get('deshydratation_severe', ''))

    boire = flat_field(lambda f: f.form.get('danger', {}).get('boire', ''))
    convulsions_passe = flat_field(lambda f: f.form.get('danger', {}).get('convulsions_passe', ''))
    convulsions_present = flat_field(lambda f: f.form.get('danger', {}).get('convulsions_present', ''))
    high_danger = flat_field(lambda f: f.form.get('danger', {}).get('high_danger', ''))
    lethargie = flat_field(lambda f: f.form.get('danger', {}).get('lethargie', ''))
    low_danger = flat_field(lambda f: f.form.get('danger', {}).get('low_danger', ''))
    vomit = flat_field(lambda f: f.form.get('danger', {}).get('vomit', ''))

    conscience_agitation = flat_field(lambda f: f.form.get('diarrhee', {}).get('conscience_agitation', ''))
    diarrhee_presence = flat_field(lambda f: f.form.get('diarrhee', {}).get('diarrhee_presence', ''))
    diarrhee_presence_duree = flat_field(lambda f: f.form.get('diarrhee', {}).get('diarrhee_presence_duree', ''))
    dysentery = flat_field(lambda f: f.form.get('diarrhee', {}).get('dysentery', ''))
    no_dehydration = flat_field(lambda f: f.form.get('diarrhee', {}).get('no_dehydration', ''))
    persistent = flat_field(lambda f: f.form.get('diarrhee', {}).get('persistent', ''))
    pli_cutane = flat_field(lambda f: f.form.get('diarrhee', {}).get('pli_cutane', ''))
    sang_selles = flat_field(lambda f: f.form.get('diarrhee', {}).get('sang_selles', ''))
    severe_dehydration = flat_field(lambda f: f.form.get('diarrhee', {}).get('severe_dehydration', ''))
    severe_persistent = flat_field(lambda f: f.form.get('diarrhee', {}).get('severe_persistent', ''))
    soif = flat_field(lambda f: f.form.get('diarrhee', {}).get('soif', ''))
    some_dehydration = flat_field(lambda f: f.form.get('diarrhee', {}).get('some_dehydration', ''))
    yeux_enfonces = flat_field(lambda f: f.form.get('diarrhee', {}).get('yeux_enfonces', ''))

    diarrhee_persistente = flat_field(lambda f: f.form.get('diarrhee_persistente', ''))
    diarrhee_persistente_severe = flat_field(lambda f: f.form.get('diarrhee_persistente_severe', ''))

    choc = flat_field(lambda f: f.form.get('fievre', {}).get('choc', ''))
    cornee = flat_field(lambda f: f.form.get('fievre', {}).get('cornee', ''))
    ecoulement_nasal = flat_field(lambda f: f.form.get('fievre', {}).get('ecoulement_nasal', ''))
    ecoulement_oculaire = flat_field(lambda f: f.form.get('fievre', {}).get('ecoulement_oculaire', ''))
    eruption_cutanee = flat_field(lambda f: f.form.get('fievre', {}).get('eruption_cutanee', ''))
    fievre_presence = flat_field(lambda f: f.form.get('fievre', {}).get('fievre_presence', ''))
    fievre_presence_duree = flat_field(lambda f: f.form.get('fievre', {}).get('fievre_presence_duree', ''))
    fievre_presence_longue = flat_field(lambda f: f.form.get('fievre', {}).get('fievre_presence_longue', ''))
    history_measles = flat_field(lambda f: f.form.get('fievre', {}).get('history_measles', ''))
    ictere = flat_field(lambda f: f.form.get('fievre', {}).get('ictere', ''))
    malaria = flat_field(lambda f: f.form.get('fievre', {}).get('malaria', ''))
    malaria_severe = flat_field(lambda f: f.form.get('fievre', {}).get('malaria_severe', ''))
    malaria_severe_neg_tdr = flat_field(lambda f: f.form.get('fievre', {}).get('malaria_severe_neg_tdr', ''))
    measles = flat_field(lambda f: f.form.get('fievre', {}).get('measles', ''))
    measles_complex = flat_field(lambda f: f.form.get('fievre', {}).get('measles_complex', ''))
    measles_severe = flat_field(lambda f: f.form.get('fievre', {}).get('measles_severe', ''))
    raideur_nuque = flat_field(lambda f: f.form.get('fievre', {}).get('raideur_nuque', ''))
    saignements_anormaux = flat_field(lambda f: f.form.get('fievre', {}).get('saignements_anormaux', ''))
    tdr = flat_field(lambda f: f.form.get('fievre', {}).get('tdr', ''))
    tdr_negative = flat_field(lambda f: f.form.get('fievre', {}).get('tdr_negative', ''))
    ulcerations = flat_field(lambda f: f.form.get('fievre', {}).get('ulcerations', ''))
    urines_foncees = flat_field(lambda f: f.form.get('fievre', {}).get('urines_foncees', ''))
    yeux_rouge = flat_field(lambda f: f.form.get('fievre', {}).get('yeux_rouge', ''))

    frequence_elevee = flat_field(lambda f: f.form.get('frequence_elevee', ''))
    height_rounded = flat_field(lambda f: f.form.get('height_rounded', ''))
    ma_mam = flat_field(lambda f: f.form.get('ma_mam', ''))
    ma_mas = flat_field(lambda f: f.form.get('ma_mas', ''))
    ma_normal = flat_field(lambda f: f.form.get('ma_normal', ''))

    malnutrition_mam = flat_field(lambda f: f.form.get('malnutrition', {}).get('malnutrition_mam', ''))
    malnutrition_masc = flat_field(lambda f: f.form.get('malnutrition', {}).get('malnutrition_masc', ''))
    malnutrition_mass = flat_field(lambda f: f.form.get('malnutrition', {}).get('malnutrition_mass', ''))
    malnutrition_na = flat_field(lambda f: f.form.get('malnutrition', {}).get('malnutrition_na', ''))
    no_malnutrition = flat_field(lambda f: f.form.get('malnutrition', {}).get('no_malnutrition', ''))
    oedemes = flat_field(lambda f: f.form.get('malnutrition', {}).get('oedemes', ''))
    test_appetit = flat_field(lambda f: f.form.get('malnutrition', {}).get('test_appetit', ''))

    muac_change = flat_field(lambda f: f.form.get('muac_change', ''))
    muac_change_status = flat_field(lambda f: f.form.get('muac_change_status', ''))
    muac_grading = flat_field(lambda f: f.form.get('muac_grading', ''))
    paludisme_grave = flat_field(lambda f: f.form.get('paludisme_grave', ''))
    pas_de_deshydratation = flat_field(lambda f: f.form.get('pas_de_deshydratation', ''))
    pneumonie_grave = flat_field(lambda f: f.form.get('pneumonie_grave', ''))
    prev_muac = flat_field(lambda f: f.form.get('prev_muac', ''))
    prev_zscore_hfa = flat_field(lambda f: f.form.get('prev_muac', ''))
    prev_zscore_wfa = flat_field(lambda f: f.form.get('prev_muac', ''))
    prev_zscore_wfh = flat_field(lambda f: f.form.get('prev_muac', ''))
    rougeole_compliquee = flat_field(lambda f: f.form.get('rougeole_compliquee', ''))
    rougeole_ou_antecedent = flat_field(lambda f: f.form.get('rougeole_ou_antecedent', ''))

    ear_infection_acute = flat_field(lambda f: f.form.get('oreille', {}).get('ear_infection_acute', ''))
    ear_mastoiditis = flat_field(lambda f: f.form.get('oreille', {}).get('ear_mastoiditis', ''))
    oreille_douleur = flat_field(lambda f: f.form.get('oreille', {}).get('oreille_douleur', ''))
    oreille_ecoulement = flat_field(lambda f: f.form.get('oreille', {}).get('oreille_ecoulement', ''))
    oreille_ecoulement_duree = flat_field(lambda f: f.form.get('oreille', {}).get('oreille_ecoulement_duree', ''))
    oreille_gonflement = flat_field(lambda f: f.form.get('oreille', {}).get('oreille_gonflement', ''))
    oreille_probleme = flat_field(lambda f: f.form.get('oreille', {}).get('oreille_probleme', ''))

    sd2neg_hfa = flat_field(lambda f: f.form.get('sd2neg_hfa', ''))
    sd2neg_wfa = flat_field(lambda f: f.form.get('sd2neg_wfa', ''))
    sd2neg_wfh = flat_field(lambda f: f.form.get('sd2neg_wfh', ''))
    sd2pos_hfa = flat_field(lambda f: f.form.get('sd2pos_hfa', ''))
    sd2pos_wfa = flat_field(lambda f: f.form.get('sd2pos_wfa', ''))
    sd2pos_wfh = flat_field(lambda f: f.form.get('sd2pos_wfh', ''))
    sd3neg_hfa = flat_field(lambda f: f.form.get('sd3neg_hfa', ''))
    sd3neg_wfa = flat_field(lambda f: f.form.get('sd3neg_wfa', ''))
    sd3neg_wfh = flat_field(lambda f: f.form.get('sd3neg_wfh', ''))
    sd3pos_hfa = flat_field(lambda f: f.form.get('sd3pos_hfa', ''))
    sd3pos_wfa = flat_field(lambda f: f.form.get('sd3pos_wfa', ''))
    sd3pos_wfh = flat_field(lambda f: f.form.get('sd3pos_wfh', ''))

    selected_user_id_and_name = flat_field(lambda f: f.form.get('selected_user_id_and_name', ''))

    seriousness_anemie = flat_field(lambda f: f.form.get('seriousness_anemie', ''))
    seriousness_danger = flat_field(lambda f: f.form.get('seriousness_danger', ''))
    seriousness_diarrhee = flat_field(lambda f: f.form.get('seriousness_diarrhee', ''))
    seriousness_fievre = flat_field(lambda f: f.form.get('seriousness_fievre', ''))
    seriousness_malnutrition = flat_field(lambda f: f.form.get('seriousness_malnutrition', ''))
    seriousness_oreille = flat_field(lambda f: f.form.get('seriousness_oreille', ''))
    seriousness_toux = flat_field(lambda f: f.form.get('seriousness_toux', ''))
    seriousness_vih = flat_field(lambda f: f.form.get('seriousness_vih', ''))
    sex = flat_field(lambda f: f.form.get('sex', ''))
    sex_loaded = flat_field(lambda f: f.form.get('sex_loaded', ''))
    signes_danger = flat_field(lambda f: f.form.get('signes_danger', ''))
    signes_rougeole = flat_field(lambda f: f.form.get('signes_rougeole', ''))
    tdr_ok = flat_field(lambda f: f.form.get('tdr_ok', ''))

    freq_resp = flat_field(lambda f: f.form.get('toux', {}).get('freq_resp', ''))
    high_toux = flat_field(lambda f: f.form.get('toux', {}).get('high_toux', ''))
    low_toux = flat_field(lambda f: f.form.get('toux', {}).get('low_toux', ''))
    medium_toux = flat_field(lambda f: f.form.get('toux', {}).get('medium_toux', ''))
    stridor = flat_field(lambda f: f.form.get('toux', {}).get('stridor', ''))
    tirage = flat_field(lambda f: f.form.get('toux', {}).get('tirage', ''))
    toux_presence = flat_field(lambda f: f.form.get('toux', {}).get('toux_presence', ''))
    toux_presence_duree = flat_field(lambda f: f.form.get('toux', {}).get('toux_presence_duree', ''))

    update_vaccines = flat_field(lambda f: f.form.get('update_vaccines', ''))

    vaccines = flat_field(lambda f: ', '.join([k for k, v in f.form.get('vaccines', {}).iteritems()
                                               if v == 'yes']))
    bcg = flat_field(lambda f: f.form.get('vaccines', {}).get('bcg', ''))
    measles_1 = flat_field(lambda f: f.form.get('vaccines', {}).get('measles_1', ''))
    measles_2 = flat_field(lambda f: f.form.get('vaccines', {}).get('measles_2', ''))
    opv_0 = flat_field(lambda f: f.form.get('vaccines', {}).get('opv_0', ''))
    opv_1 = flat_field(lambda f: f.form.get('vaccines', {}).get('opv_1', ''))
    opv_2 = flat_field(lambda f: f.form.get('vaccines', {}).get('opv_2', ''))
    opv_3 = flat_field(lambda f: f.form.get('vaccines', {}).get('opv_3', ''))
    penta_1 = flat_field(lambda f: f.form.get('vaccines', {}).get('penta_1', ''))
    penta_2 = flat_field(lambda f: f.form.get('vaccines', {}).get('penta_2', ''))
    penta_3 = flat_field(lambda f: f.form.get('vaccines', {}).get('penta_3', ''))
    pneumo_1 = flat_field(lambda f: f.form.get('vaccines', {}).get('pneumo_1', ''))
    pneumo_2 = flat_field(lambda f: f.form.get('vaccines', {}).get('pneumo_2', ''))
    pneumo_3 = flat_field(lambda f: f.form.get('vaccines', {}).get('pneumo_3', ''))
    rotavirus_1 = flat_field(lambda f: f.form.get('vaccines', {}).get('rotavirus_1', ''))
    rotavirus_2 = flat_field(lambda f: f.form.get('vaccines', {}).get('rotavirus_2', ''))
    rotavirus_3 = flat_field(lambda f: f.form.get('vaccines', {}).get('rotavirus_3', ''))
    yf = flat_field(lambda f: f.form.get('vaccines', {}).get('yf', ''))

    augmentation_glande_parotide = flat_field(
        lambda f: f.form.get('vih', {}).get('augmentation_glande_parotide', ''))
    candidose_buccale = flat_field(lambda f: f.form.get('vih', {}).get('candidose_buccale', ''))
    diarrhee_dernierement = flat_field(lambda f: f.form.get('vih', {}).get('diarrhee_dernierement', ''))
    hypertrophie_ganglions_lymphatiques = flat_field(
        lambda f: f.form.get('vih', {}).get('hypertrophie_ganglions_lymphatiques', ''))
    pneumonie_recidivante = flat_field(lambda f: f.form.get('vih', {}).get('pneumonie_recidivante', ''))
    serologie_enfant = flat_field(lambda f: f.form.get('vih', {}).get('serologie_enfant', ''))
    serologie_mere = flat_field(lambda f: f.form.get('vih', {}).get('serologie_mere', ''))
    test_enfant = flat_field(lambda f: f.form.get('vih', {}).get('test_enfant', ''))
    test_mere = flat_field(lambda f: f.form.get('vih', {}).get('test_mere', ''))
    vih_confirmee = flat_field(lambda f: f.form.get('vih', {}).get('vih_confirmee', ''))
    vih_pas = flat_field(lambda f: f.form.get('vih', {}).get('vih_pas', ''))
    vih_peu_probable = flat_field(lambda f: f.form.get('vih', {}).get('vih_peu_probable', ''))
    vih_possible = flat_field(lambda f: f.form.get('vih', {}).get('vih_possible', ''))
    vih_symp_confirmee = flat_field(lambda f: f.form.get('vih', {}).get('vih_symp_confirmee', ''))
    vih_symp_probable = flat_field(lambda f: f.form.get('vih', {}).get('vih_symp_probable', ''))
    vih_symp_suspecte = flat_field(lambda f: f.form.get('vih', {}).get('vih_symp_suspecte', ''))

    visit_date = flat_field(lambda f: f.form.get('visit_date', ''))
    visit_type = flat_field(lambda f: f.form.get('visit_type', ''))

    height = flat_field(lambda f: f.form.get('vitals', {}).get('height', ''))
    muac = flat_field(lambda f: f.form.get('vitals', {}).get('muac', ''))
    temp = flat_field(lambda f: f.form.get('vitals', {}).get('temp', ''))
    weight = flat_field(lambda f: f.form.get('vitals', {}).get('weight', ''))

    zscore_grading_hfa = flat_field(lambda f: f.form.get('zscore_grading_hfa', ''))
    zscore_grading_wfa = flat_field(lambda f: f.form.get('zscore_grading_wfa', ''))
    zscore_grading_wfh = flat_field(lambda f: f.form.get('zscore_grading_wfh', ''))
    zscore_hfa = flat_field(lambda f: f.form.get('zscore_hfa', ''))
    zscore_hfa_change = flat_field(lambda f: f.form.get('zscore_hfa_change', ''))
    zscore_hfa_change_status = flat_field(lambda f: f.form.get('zscore_hfa_change_status', ''))
    zscore_wfa = flat_field(lambda f: f.form.get('zscore_wfa', ''))
    zscore_wfa_change = flat_field(lambda f: f.form.get('zscore_wfa_change', ''))
    zscore_wfa_change_status = flat_field(lambda f: f.form.get('zscore_wfa_change_status', ''))
    zscore_wfh = flat_field(lambda f: f.form.get('zscore_wfh', ''))
    zscore_wfh_change = flat_field(lambda f: f.form.get('zscore_wfh_change', ''))
    zscore_wfh_change_status = flat_field(lambda f: f.form.get('zscore_wfh_change_status', ''))

    show_muac_status = flat_field(lambda f: f.form.get('zscore_results', {}).get('show_muac_status', ''))
    show_zscore_hfa = flat_field(lambda f: f.form.get('zscore_results', {}).get('show_zscore_hfa', ''))
    show_zscore_wfa = flat_field(lambda f: f.form.get('zscore_results', {}).get('show_zscore_wfa', ''))
    show_zscore_wfh = flat_field(lambda f: f.form.get('zscore_results', {}).get('show_zscore_wfh', ''))
    warn_bad_height = flat_field(lambda f: f.form.get('zscore_results', {}).get('warn_bad_height', ''))

    last_height = flat_field(lambda f: f.form['case']['update'].get('last_height', ''))
    last_weight = flat_field(lambda f: f.form['case']['update'].get('last_weight', ''))

    numerator = TDHDateEmiiter()


class TDHInfantTreatmentFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=INFANT_TREATMENT_XMLNSES[0])
    domains = TDH_DOMAINS
    save_direct_to_sql = True

    case_id = flat_field(lambda f: f.form.get('child_case_id'))
    antibio_valid_meds = flat_field(lambda f: f.form.get('antibio_valid_meds', ''))
    child_age = flat_field(lambda f: f.form.get('child_age', ''))
    child_age_loaded = flat_field(lambda f: f.form.get('child_age_loaded', ''))
    child_weight = flat_field(lambda f: f.form.get('child_weight', ''))
    child_weight_loaded = flat_field(lambda f: f.form.get('child_weight_loaded', ''))
    classification_deshydratation = flat_field(lambda f: f.form.get('classification_deshydratation', ''))
    classification_deshydratation_loaded = flat_field(
        lambda f: f.form.get('classification_deshydratation_loaded', ''))
    classification_diahree = flat_field(lambda f: f.form.get('classification_diahree', ''))
    classification_diahree_loaded = flat_field(lambda f: f.form.get('classification_diahree_loaded', ''))
    classification_infection = flat_field(lambda f: f.form.get('classification_infection', ''))
    classification_infection_loaded = flat_field(lambda f: f.form.get('classification_infection_loaded', ''))
    classification_malnutrition = flat_field(lambda f: f.form.get('classification_malnutrition'))
    classification_malnutrition_loaded = flat_field(lambda f: f.form.get('classification_malnutrition_loaded', ''))
    classification_vih = flat_field(lambda f: f.form.get('classification_vih', ''))
    classification_vih_loaded = flat_field(lambda f: f.form.get('classification_vih_loaded', ''))
    other_treatments = flat_field(lambda f: f.form.get('other_treatments', ''))
    vitamine_a_valid_meds = flat_field(lambda f: f.form.get('vitamine_a_valid_meds', ''))

    antibio = flat_field(
        lambda f: f.form.get('select_meds', {}).get('antibio', '') if f.form.get('select_meds', {}) else '')
    deshydratation_severe = flat_field(
        lambda f: f.form.get('select_treatments', {}).get('deshydratation_severe', '') if f.form.get(
            'select_treatments', {}) else '')
    infection_grave = flat_field(lambda f: f.form.get('select_treatments', {})
                                 .get('infection_grave', '') if f.form.get('select_treatments', {}) else '')
    signe_deshydratation = flat_field(
        lambda f: f.form.get('select_treatments', {}).get('signe_deshydratation', '') if f.form.get(
            'select_treatments', {}) else '')

    deshydratation_severe_sans_infection_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_sans_infection', {})
        .get('deshydratation_severe_sans_infection_title', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('deshydratation_severe_sans_infection', {}) else '')
    deshydratation_severe_sans_infection_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_sans_infection', {})
        .get('deshydratation_severe_sans_infection_treat_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('deshydratation_severe_sans_infection', {}) else '')

    incapable_nourrir_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_2', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_3_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_3_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_3_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_3_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')

    infection_grave_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_3_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_3_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_4_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_5_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')

    infection_locale_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {})
        .get('infection_locale_treat_2_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_2_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {})
        .get('infection_locale_treat_2_help_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_2_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {})
        .get('infection_locale_treat_2_help_2', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')

    pas_infection_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {}).get('pas_infection_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {}).get('pas_infection_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {}).get('pas_infection_treat_0_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {})
        .get('pas_infection_treat_0_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_0_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {}).get('pas_infection_treat_0_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_0_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {})
        .get('pas_infection_treat_0_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_0_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {}).get('pas_infection_treat_0_help_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_0_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {})
        .get('pas_infection_treat_0_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {}).get('pas_infection_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {}).get('pas_infection_treat_1_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_infection', {}) else '')
    pas_infection_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection', {})
        .get('pas_infection_treat_1_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection', {}) else '')

    probleme_alimentation_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_title', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_0_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_1', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_1_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_2', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_3', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_4', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_4_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_5', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_6', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_6_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_6_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_6_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_6_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_7', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_8', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')

    signe_deshydratation_infection_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('signe_deshydratation_infection', {})
        .get('signe_deshydratation_infection_title', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signe_deshydratation_infection', {}) else '')
    signe_deshydratation_infection_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signe_deshydratation_infection', {})
        .get('signe_deshydratation_infection_treat_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signe_deshydratation_infection', {}) else '')
    signe_deshydratation_infection_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signe_deshydratation_infection', {})
        .get('signe_deshydratation_infection_treat_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signe_deshydratation_infection', {}) else '')
    signe_deshydratation_infection_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signe_deshydratation_infection', {})
        .get('signe_deshydratation_infection_treat_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signe_deshydratation_infection', {}) else '')

    vih_pas_infection_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas_infection', {}).get('vih_pas_infection_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas_infection', {}) else '')
    vih_pas_infection_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas_infection', {}).get('vih_pas_infection_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas_infection', {}) else '')
    vih_pas_infection_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas_infection', {}).get('vih_pas_infection_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas_infection', {}) else '')

    vih_possible_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}) .get('vih_possible_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')

    numerator = TDHNullEmitter()


class TDHNewbornTreatmentFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=NEWBORN_TREATMENT_XMLNSES[0])
    domains = TDH_DOMAINS
    save_direct_to_sql = True

    case_id = flat_field(lambda f: f.form.get('child_case_id'))
    antibio_valid_meds = flat_field(lambda f: f.form.get('antibio_valid_meds', ''))
    child_age = flat_field(lambda f: f.form.get('child_age', ''))
    child_age_loaded = flat_field(lambda f: f.form.get('child_age_loaded', ''))
    child_weight = flat_field(lambda f: f.form.get('child_weight', ''))
    child_weight_loaded = flat_field(lambda f: f.form.get('child_weight_loaded', ''))
    classification_occular = flat_field(lambda f: f.form.get('classification_occular', ''))
    classification_occular_loaded = flat_field(lambda f: f.form.get('classification_occular_loaded', ''))
    classification_poids = flat_field(lambda f: f.form.get('classification_poids', ''))
    classification_poids_loaded = flat_field(lambda f: f.form.get('classification_poids_loaded', ''))
    classification_infection = flat_field(lambda f: f.form.get('classification_infection', ''))
    classification_infection_loaded = flat_field(lambda f: f.form.get('classification_infection_loaded', ''))
    classification_malnutrition = flat_field(lambda f: f.form.get('classification_malnutrition'))
    classification_malnutrition_loaded = flat_field(lambda f: f.form.get('classification_malnutrition_loaded', ''))
    classification_vih = flat_field(lambda f: f.form.get('classification_vih', ''))
    classification_vih_loaded = flat_field(lambda f: f.form.get('classification_vih_loaded', ''))
    other_treatments = flat_field(lambda f: f.form.get('other_treatments', ''))

    antibio = flat_field(
        lambda f: f.form.get('select_meds', {}).get('antibio', '') if f.form.get('select_meds', {}) else '')
    infection_grave = flat_field(
        lambda f: f.form.get('select_treatments', {}).get('infection_grave', '') if f.form.get(
            'select_treatments', {}) else '')

    conjonctivite_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('conjonctivite', {}).get('conjonctivite_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('conjonctivite', {}) else '')
    conjonctivite_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('conjonctivite', {}).get('conjonctivite_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('conjonctivite', {}) else '')
    conjonctivite_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('conjonctivite', {}).get('conjonctivite_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('conjonctivite', {}) else '')
    conjonctivite_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('conjonctivite', {}).get('conjonctivite_treat_1_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('conjonctivite', {}) else '')
    conjonctivite_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('conjonctivite', {}).get('conjonctivite_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('conjonctivite', {}) else '')
    conjonctivite_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('conjonctivite', {}).get('conjonctivite_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('conjonctivite', {}) else '')
    conjonctivite_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('conjonctivite', {}).get('conjonctivite_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('conjonctivite', {}) else '')

    fable_poids_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('conjonctivite_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_treat_0_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_treat_0_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_0_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_treat_0_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_0_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_treat_0_help_1_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')
    fable_poids_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('fable_poids', {}).get('fable_poids_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('fable_poids', {}) else '')

    incapable_nourrir_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_2_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_2_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_3_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_3_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_3_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {})
        .get('incapable_nourrir_treat_3_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('incapable_nourrir', {}) else '')
    incapable_nourrir_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('incapable_nourrir', {}).get('incapable_nourrir_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('incapable_nourrir', {}) else '')

    hypothermie_moderee_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {}).get('hypothermie_moderee_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('hypothermie_moderee', {}) else '')
    hypothermie_moderee_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {})
        .get('hypothermie_moderee_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('hypothermie_moderee', {}) else '')
    hypothermie_moderee_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {})
        .get('hypothermie_moderee_treat_0_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('hypothermie_moderee', {}) else '')
    hypothermie_moderee_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {})
        .get('hypothermie_moderee_treat_0_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('hypothermie_moderee', {}) else '')
    hypothermie_moderee_treat_0_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {})
        .get('hypothermie_moderee_treat_0_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('hypothermie_moderee', {}) else '')
    hypothermie_moderee_treat_0_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {})
        .get('hypothermie_moderee_treat_0_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('hypothermie_moderee', {}) else '')
    hypothermie_moderee_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {})
        .get('hypothermie_moderee_treat_1', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('hypothermie_moderee', {}) else '')
    hypothermie_moderee_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {})
        .get('hypothermie_moderee_treat_2', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('hypothermie_moderee', {}) else '')
    hypothermie_moderee_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('hypothermie_moderee', {})
        .get('hypothermie_moderee_treat_3', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('hypothermie_moderee', {}) else '')

    infection_grave_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_2_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {})
        .get('infection_grave_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_4_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_5_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {})
        .get('infection_grave_treat_5_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_6_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_6_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {})
        .get('infection_grave_treat_6_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_7_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_7_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_7_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {})
        .get('infection_grave_treat_7_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_8_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_8_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_8_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {})
        .get('infection_grave_treat_8_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_8_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_8_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_8_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {})
        .get('infection_grave_treat_8_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave', {}) else '')
    infection_grave_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave', {}).get('infection_grave_treat_9', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_grave', {}) else '')

    infection_grave_no_ref_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_title', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_1', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_2', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_3', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_4', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_4_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_5', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_5_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_5_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_6', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_6_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_6_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_6_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_7', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_7_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_7_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_7_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_7_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_8', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_8_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_8_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_8_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_8_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_9', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_10 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_10', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_10_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_10_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_10_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_10_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_10_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_10_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')
    infection_grave_no_ref_treat_10_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_grave_no_ref', {})
        .get('infection_grave_no_ref_treat_10_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_grave_no_ref', {}) else '')

    infection_locale_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {})
        .get('infection_locale_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_2_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {})
        .get('infection_locale_treat_2_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {})
        .get('infection_locale_treat_4_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_locale', {}) else '')
    infection_locale_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('infection_locale_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')
    show_antibio_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_locale', {}).get('show_antibio_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('infection_locale', {}) else '')

    infection_peu_probable_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_peu_probable', {})
        .get('infection_peu_probable_title', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_peu_probable', {}) else '')
    infection_peu_probable_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_peu_probable', {})
        .get('infection_peu_probable_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_peu_probable', {}) else '')
    infection_peu_probable_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_peu_probable', {})
        .get('infection_peu_probable_treat_1', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_peu_probable', {}) else '')
    infection_peu_probable_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_peu_probable', {})
        .get('infection_peu_probable_treat_2', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('infection_peu_probable', {}) else '')

    maladie_grave_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('maladie_grave', {}).get('maladie_grave_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('maladie_grave', {}) else '')
    maladie_grave_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('maladie_grave', {}).get('maladie_grave_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('maladie_grave', {}) else '')
    maladie_grave_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('maladie_grave', {}).get('maladie_grave_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('maladie_grave', {}) else '')
    maladie_grave_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('maladie_grave', {}).get('maladie_grave_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('maladie_grave', {}) else '')
    maladie_grave_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('maladie_grave', {}).get('maladie_grave_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('maladie_grave', {}) else '')

    pas_de_faible_poids_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_faible_poids', {}).get('pas_de_faible_poids_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_de_faible_poids', {}) else '')
    pas_de_faible_poids_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_faible_poids', {})
        .get('pas_de_faible_poids_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('pas_de_faible_poids', {}) else '')
    pas_de_faible_poids_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_faible_poids', {})
        .get('pas_de_faible_poids_treat_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_de_faible_poids', {}) else '')
    pas_de_faible_poids_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_faible_poids', {})
        .get('pas_de_faible_poids_treat_1_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_de_faible_poids', {}) else '')
    pas_de_faible_poids_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_faible_poids', {})
        .get('pas_de_faible_poids_treat_1_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_de_faible_poids', {}) else '')
    pas_de_faible_poids_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_faible_poids', {})
        .get('pas_de_faible_poids_treat_2', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('pas_de_faible_poids', {}) else '')

    pas_de_probleme_alimentation_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_probleme_alimentation', {})
        .get('pas_de_probleme_alimentation_title', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_de_probleme_alimentation', {}) else '')
    pas_de_probleme_alimentation_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_probleme_alimentation', {})
        .get('pas_de_probleme_alimentation_treat_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_de_probleme_alimentation', {}) else '')
    pas_de_probleme_alimentation_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_probleme_alimentation', {})
        .get('pas_de_probleme_alimentation_treat_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_de_probleme_alimentation', {}) else '')
    pas_de_probleme_alimentation_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_de_probleme_alimentation', {})
        .get('pas_de_probleme_alimentation_treat_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_de_probleme_alimentation', {}) else '')

    pas_infection_occulaire_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection_occulaire', {})
        .get('pas_infection_occulaire_title', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection_occulaire', {}) else '')
    pas_infection_occulaire_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection_occulaire', {})
        .get('pas_infection_occulaire_treat_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection_occulaire', {}) else '')
    pas_infection_occulaire_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection_occulaire', {})
        .get('pas_infection_occulaire_treat_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection_occulaire', {}) else '')
    pas_infection_occulaire_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection_occulaire', {})
        .get('pas_infection_occulaire_treat_1_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection_occulaire', {}) else '')
    pas_infection_occulaire_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection_occulaire', {})
        .get('pas_infection_occulaire_treat_1_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection_occulaire', {}) else '')
    pas_infection_occulaire_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_infection_occulaire', {})
        .get('pas_infection_occulaire_treat_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_infection_occulaire', {}) else '')

    poids_tres_faible_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {}).get('poids_tres_faible_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {}).get('poids_tres_faible_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {})
        .get('poids_tres_faible_treat_0_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {}).get('poids_tres_faible_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {}).get('poids_tres_faible_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {})
        .get('poids_tres_faible_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {}).get('poids_tres_faible_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_3_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {})
        .get('poids_tres_faible_treat_3_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {}).get('poids_tres_faible_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {})
        .get('poids_tres_faible_treat_4_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('poids_tres_faible', {}) else '')
    poids_tres_faible_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('poids_tres_faible', {}).get('poids_tres_faible_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('poids_tres_faible', {}) else '')

    probleme_alimentation_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_title', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_1', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_1_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_1_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_1_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_1_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_1_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_1_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_2', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_3', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_4', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_5', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_6', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_7', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_8', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_9', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_10 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_10', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_11 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_11', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_12 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_12', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_13 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_13', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_14 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_14', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_15 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_15', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_16 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_16', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')
    probleme_alimentation_treat_17 = flat_field(
        lambda f: f.form.get('treatments', {}).get('probleme_alimentation', {})
        .get('probleme_alimentation_treat_17', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('probleme_alimentation', {}) else '')

    vih_peu_probable_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {}).get('vih_peu_probable_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {}).get('vih_peu_probable_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {}).get('vih_peu_probable_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {}).get('vih_peu_probable_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')

    vih_possible_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_0_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_0_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')

    vih_probable_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_probable', {}).get('vih_probable_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_probable', {}) else '')
    vih_probable_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_probable', {}).get('vih_probable_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_probable', {}) else '')
    vih_probable_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_probable', {}).get('vih_probable_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_probable', {}) else '')
    vih_probable_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_probable', {}).get('vih_probable_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_probable', {}) else '')
    vih_probable_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_probable', {}).get('vih_probable_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_probable', {}) else '')
    vih_probable_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_probable', {}).get('vih_probable_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_probable', {}) else '')

    numerator = TDHNullEmitter()


class TDHChildTreatmentFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = FormPropertyFilter(xmlns=CHILD_TREATMENT_XMLNSES[0])
    domains = TDH_DOMAINS
    save_direct_to_sql = True

    case_id = flat_field(lambda f: f.form.get('child_case_id'))
    antibio_valid_meds = flat_field(lambda f: f.form.get('antibio_valid_meds', ''))
    artemether_valid_meds = flat_field(lambda f: f.form.get('artemether_valid_meds', ''))
    child_age = flat_field(lambda f: f.form.get('child_age', ''))
    child_age_loaded = flat_field(lambda f: f.form.get('child_age_loaded', ''))
    child_weight = flat_field(lambda f: f.form.get('child_weight', ''))
    child_weight_loaded = flat_field(lambda f: f.form.get('child_weight_loaded', ''))
    classification_anemie = flat_field(lambda f: f.form.get('classification_anemie', ''))
    classification_anemie_loaded = flat_field(lambda f: f.form.get('classification_anemie_loaded', ''))
    classification_deshydratation = flat_field(lambda f: f.form.get('classification_deshydratation', ''))
    classification_deshydratation_loaded = flat_field(
        lambda f: f.form.get('classification_deshydratation_loaded', ''))
    classification_diahree = flat_field(lambda f: f.form.get('classification_diahree', ''))
    classification_diahree_loaded = flat_field(lambda f: f.form.get('classification_diahree_loaded', ''))
    classification_dysenterie = flat_field(lambda f: f.form.get('classification_dysenterie', ''))
    classification_dysenterie_loaded = flat_field(lambda f: f.form.get('classification_dysenterie_loaded', ''))
    classification_malnutrition = flat_field(lambda f: f.form.get('classification_malnutrition', ''))
    classification_malnutrition_loaded = flat_field(lambda f: f.form.get('classification_malnutrition_loaded', ''))
    classification_oreille = flat_field(lambda f: f.form.get('classification_oreille', ''))
    classification_oreille_loaded = flat_field(lambda f: f.form.get('classification_oreille_loaded', ''))
    classification_paludisme = flat_field(lambda f: f.form.get('classification_paludisme'))
    classification_paludisme_loaded = flat_field(lambda f: f.form.get('classification_paludisme_loaded', ''))
    classification_pneumonie = flat_field(lambda f: f.form.get('classification_pneumonie'))
    classification_pneumonie_loaded = flat_field(lambda f: f.form.get('classification_pneumonie_loaded', ''))
    classification_rougeole = flat_field(lambda f: f.form.get('classification_pneumonie'))
    classification_rougeole_loaded = flat_field(lambda f: f.form.get('classification_pneumonie_loaded', ''))
    classification_vih = flat_field(lambda f: f.form.get('classification_vih', ''))
    classification_vih_loaded = flat_field(lambda f: f.form.get('classification_vih_loaded', ''))
    deparasitage_valid_meds = flat_field(lambda f: f.form.get('deparasitage_valid_meds', ''))
    other_treatments = flat_field(lambda f: f.form.get('other_treatments', ''))
    perfusion_p1_a_valid_meds = flat_field(lambda f: f.form.get('perfusion_p1_a_valid_meds', ''))
    perfusion_p1_b_valid_meds = flat_field(lambda f: f.form.get('perfusion_p1_b_valid_meds', ''))
    perfusion_p2_a_valid_meds = flat_field(lambda f: f.form.get('perfusion_p2_a_valid_meds', ''))
    perfusion_p2_b_valid_meds = flat_field(lambda f: f.form.get('perfusion_p2_b_valid_meds', ''))

    antibio = flat_field(
        lambda f: f.form.get('select_meds', {}).get('antibio', '') if f.form.get('select_meds', {}) else '')
    artemether = flat_field(
        lambda f: f.form.get('select_meds', {}).get('artemether', '') if f.form.get('select_meds', {}) else '')
    deparasitage = flat_field(
        lambda f: f.form.get('select_meds', {}).get('deparasitage', '') if f.form.get('select_meds', {}) else '')
    perfusion_p1_b = flat_field(
        lambda f: f.form.get('select_meds', {}).get('perfusion_p1_b', '') if f.form.get('select_meds', {}) else '')
    perfusion_p2_b = flat_field(
        lambda f: f.form.get('select_meds', {}).get('perfusion_p2_b', '') if f.form.get('select_meds', {}) else '')
    vitamine_a = flat_field(
        lambda f: f.form.get('select_meds', {}).get('vitamine_a', '') if f.form.get('select_meds', {}) else '')

    deshydratation_severe_grave = flat_field(
        lambda f: f.form.get('select_treatments', {}).get('deshydratation_severe_grave', '') if f.form.get(
            'select_treatments', {}) else '')
    diahree_persistante_severe_grave = flat_field(
        lambda f: f.form.get('select_treatments', {}).get('diahree_persistante_severe_grave', '') if f.form.get(
            'select_treatments', {}) else '')
    paludisme_grave = flat_field(
        lambda f: f.form.get('select_treatments', {}).get('paludisme_grave', '') if f.form.get(
            'select_treatments', {}) else '')
    pneumonie_grave = flat_field(
        lambda f: f.form.get('select_treatments', {}).get('pneumonie_grave', '') if f.form.get(
            'select_treatments', {}) else '')

    anemie_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_7_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_7_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_8_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_8_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_9', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_9_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_9_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_9_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_9_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_10 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_10', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_10_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_10_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_10_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_10_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_11 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_11', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_11_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_11_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_11_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_11_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_12 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_12', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_12_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_12_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    anemie_treat_12_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('anemie_treat_12_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    show_artemether_amod_enf = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('show_artemether_amod_enf', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    show_artemether_amod_nour = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('show_artemether_amod_enf', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    show_artemether_lum_enf = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('show_artemether_amod_enf', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')
    show_deparasitage_meb = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie', {}).get('show_artemether_amod_enf', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie', {}) else '')

    anemie_grave_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie_grave', {}).get('anemie_grave_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie_grave', {}) else '')
    anemie_grave_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie_grave', {}).get('anemie_grave_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie_grave', {}) else '')
    anemie_grave_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie_grave', {}).get('anemie_grave_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie_grave', {}) else '')
    anemie_grave_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie_grave', {}).get('anemie_grave_treat_1_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie_grave', {}) else '')
    anemie_grave_treat_1_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie_grave', {}).get('anemie_grave_treat_1_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie_grave', {}) else '')
    anemie_grave_treat_1_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie_grave', {}).get('anemie_grave_treat_1_help_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie_grave', {}) else '')
    anemie_grave_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('anemie_grave', {}).get('anemie_grave_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('anemie_grave', {}) else '')

    antecedent_rougeole_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('antecedent_rougeole', {}).get('antecedent_rougeole_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('antecedent_rougeole', {}) else '')
    antecedent_rougeole_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('antecedent_rougeole', {})
        .get('antecedent_rougeole_treat_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('antecedent_rougeole', {}) else '')
    antecedent_rougeole_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('antecedent_rougeole', {})
        .get('antecedent_rougeole_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('antecedent_rougeole', {}) else '')
    antecedent_rougeole_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('antecedent_rougeole', {})
        .get('antecedent_rougeole_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('antecedent_rougeole', {}) else '')

    deshydratation_severe_grave_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_grave', {})
        .get('deshydratation_severe_grave_title', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('deshydratation_severe_grave', {}) else '')
    deshydratation_severe_grave_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_grave', {})
        .get('deshydratation_severe_grave_treat_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('deshydratation_severe_grave', {}) else '')
    deshydratation_severe_grave_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_grave', {})
        .get('deshydratation_severe_grave_treat_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('deshydratation_severe_grave', {}) else '')
    deshydratation_severe_grave_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_grave', {})
        .get('deshydratation_severe_grave_treat_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('deshydratation_severe_grave', {}) else '')

    deshydratation_severe_pas_grave_perfusion_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_title', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_0_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_2', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_4', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_6', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_7', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_9', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_11 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_11', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_12 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_12', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_14 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_14', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_15 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_15', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_16 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_16', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_17 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_17', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_18 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_18', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    deshydratation_severe_pas_grave_perfusion_treat_18_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('deshydratation_severe_pas_grave_perfusion_treat_18_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    show_antibio_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('show_antibio_1', '') if f.form.get('treatments', {}) and f.form.get('treatments', {}).get(
            'deshydratation_severe_pas_grave_perfusion', {}) else '')
    show_perfusion_p1_b_ringer = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('show_perfusion_p1_b_ringer', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('deshydratation_severe_pas_grave_perfusion', {}) else '')
    show_perfusion_p2_b_iso = flat_field(
        lambda f: f.form.get('treatments', {}).get('deshydratation_severe_pas_grave_perfusion', {})
        .get('show_perfusion_p2_b_iso', '') if f.form.get('treatments', {}) and f.form.get('treatments', {}).get(
            'deshydratation_severe_pas_grave_perfusion', {}) else '')

    diahree_persistante_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {}).get('diahree_persistante_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('diahree_persistante', {}) else '')
    diahree_persistante_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {})
        .get('diahree_persistante_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('diahree_persistante', {}) else '')
    diahree_persistante_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {})
        .get('diahree_persistante_treat_1', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('diahree_persistante', {}) else '')
    diahree_persistante_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {})
        .get('diahree_persistante_treat_2', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('diahree_persistante', {}) else '')
    diahree_persistante_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {})
        .get('diahree_persistante_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('diahree_persistante', {}) else '')
    diahree_persistante_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {})
        .get('diahree_persistante_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('diahree_persistante', {}) else '')
    diahree_persistante_treat_2_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {})
        .get('diahree_persistante_treat_2_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('diahree_persistante', {}) else '')
    diahree_persistante_treat_2_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {})
        .get('diahree_persistante_treat_2_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('diahree_persistante', {}) else '')
    diahree_persistante_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante', {})
        .get('diahree_persistante_treat_3', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('diahree_persistante', {}) else '')

    diahree_persistante_severe_grave_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante_severe_grave', {})
        .get('diahree_persistante_severe_grave_title', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('diahree_persistante_severe_grave', {}) else '')
    diahree_persistante_severe_grave_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('diahree_persistante_severe_grave', {})
        .get('diahree_persistante_severe_grave_treat_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('diahree_persistante_severe_grave', {}) else '')

    dysenterie_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('', {}) else '')
    dysenterie_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('dysenterie_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('dysenterie', {}) else '')
    dysenterie_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('dysenterie_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('dysenterie', {}) else '')
    dysenterie_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('dysenterie_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('dysenterie', {}) else '')
    dysenterie_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('dysenterie_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('dysenterie', {}) else '')
    dysenterie_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('dysenterie_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('dysenterie', {}) else '')
    dysenterie_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('dysenterie_treat_4_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('dysenterie', {}) else '')
    dysenterie_treat_4_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('dysenterie_treat_4_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('dysenterie', {}) else '')
    dysenterie_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('dysenterie', {}).get('dysenterie_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('dysenterie', {}) else '')

    infection_aigue_oreille_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_aigue_oreille', {})
        .get('infection_aigue_oreille_title', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_aigue_oreille', {}) else '')
    infection_aigue_oreille_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_aigue_oreille', {})
        .get('conjonctivite_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {}).get(
            'infection_aigue_oreille', {}) else '')
    infection_aigue_oreille_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_aigue_oreille', {})
        .get('infection_aigue_oreille_treat_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_aigue_oreille', {}) else '')
    infection_aigue_oreille_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_aigue_oreille', {})
        .get('infection_aigue_oreille_treat_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_aigue_oreille', {}) else '')
    infection_aigue_oreille_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_aigue_oreille', {})
        .get('infection_aigue_oreille_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_aigue_oreille', {}) else '')
    infection_aigue_oreille_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_aigue_oreille', {})
        .get('infection_aigue_oreille_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_aigue_oreille', {}) else '')
    infection_aigue_oreille_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_aigue_oreille', {})
        .get('infection_aigue_oreille_treat_3', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('infection_aigue_oreille', {}) else '')
    infection_aigue_oreille_show_antibio_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('infection_aigue_oreille', {}).get('show_antibio_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get(
            'infection_aigue_oreille', {}) else '')

    mam_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_0_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_0_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_9', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')
    mam_treat_10 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mam', {}).get('mam_treat_10', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mam', {}) else '')

    masc_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_1_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_1_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_1_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_1_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_1_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_1_help_1_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_1_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_1_help_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_1_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_1_help_2_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')
    masc_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('masc', {}).get('masc_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('masc', {}) else '')

    mass_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_0_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_0_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_1_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_1_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_9', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_10 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_10', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_11 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_11', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_11_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_11_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_11_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_11_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_12 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_11', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_12_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_12_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_12_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_12_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')
    mass_treat_13 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mass', {}).get('mass_treat_13', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mass', {}) else '')

    mastoidite_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('mastoidite', {}).get('mastoidite_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mastoidite', {}) else '')
    mastoidite_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mastoidite', {}).get('mastoidite_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mastoidite', {}) else '')
    mastoidite_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mastoidite', {}).get('mastoidite_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mastoidite', {}) else '')
    mastoidite_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mastoidite', {}).get('mastoidite_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mastoidite', {}) else '')
    mastoidite_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mastoidite', {}).get('mastoidite_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mastoidite', {}) else '')
    mastoidite_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('mastoidite', {}).get('mastoidite_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('mastoidite', {}) else '')

    paludisme_grave_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_0_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {})
        .get('paludisme_grave_treat_0_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_3_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_3_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_3_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {})
        .get('paludisme_grave_treat_3_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_3_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_3_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_3_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {})
        .get('paludisme_grave_treat_3_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_3_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_3_help_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_3_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {})
        .get('paludisme_grave_treat_3_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_7_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {}).get('paludisme_grave_treat_7_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_grave', {}) else '')
    paludisme_grave_treat_7_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave', {})
        .get('paludisme_grave_treat_7_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave', {}) else '')

    paludisme_grave_no_ref_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_title', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_0', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_0_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_1', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_2', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_3', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_4', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_4_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_4_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_4_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_4_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_4_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_4_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_4', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_6', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('paludisme_grave_no_ref', {}) else '')
    paludisme_grave_no_ref_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_no_ref', {})
        .get('paludisme_grave_no_ref_treat_6_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_no_ref', {}) else '')

    paludisme_grave_tdr_negatif_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_title', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_2_help_0_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_2_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_2_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_2_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_2_help_1_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_2_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_2_help_2', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_2_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_2_help_2_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_3', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_4', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_5', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_6', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_6_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_6_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')
    paludisme_grave_tdr_negatif_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {})
        .get('paludisme_grave_tdr_negatif_treat_6_help_0_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('paludisme_grave_tdr_negatif', {}) else '')

    paludisme_simple_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {})
        .get('paludisme_simple_treat_5_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {})
        .get('paludisme_simple_treat_5_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_8_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {})
        .get('paludisme_simple_treat_8_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_8_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {})
        .get('paludisme_simple_treat_8_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_9', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_simple_treat_10 = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('paludisme_simple_treat_10', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')
    paludisme_show_artemether_amod_enf = flat_field(
        lambda f: f.form.get('treatments', {}).get('paludisme_simple', {}).get('show_artemether_amod_enf', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('paludisme_simple', {}) else '')

    pas_deshydratation_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {}).get('pas_deshydratation_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {}).get('pas_deshydratation_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {}).get('pas_deshydratation_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {}).get('pas_deshydratation_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {})
        .get('pas_deshydratation_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {})
        .get('pas_deshydratation_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {}).get('pas_deshydratation_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_3_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {})
        .get('pas_deshydratation_treat_3_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_3_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {})
        .get('pas_deshydratation_treat_3_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_deshydratation', {}) else '')
    pas_deshydratation_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_deshydratation', {})
        .get('pas_deshydratation_treat_4', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_deshydratation', {}) else '')

    pas_malnutrition_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('pas_malnutrition_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('pas_malnutrition_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {})
        .get('pas_malnutrition_treat_0_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {})
        .get('pas_malnutrition_treat_0_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('pas_malnutrition_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {})
        .get('pas_malnutrition_treat_1_help_0', '') if f.form.get(
            'treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {})
        .get('pas_malnutrition_treat_1_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('pas_malnutrition_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('pas_malnutrition_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('pas_malnutrition_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('pas_malnutrition_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {})
        .get('pas_malnutrition_treat_5_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {})
        .get('pas_malnutrition_treat_5_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_show_vitamine_a_100 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('show_vitamine_a_100', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')
    pas_malnutrition_show_vitamine_a_200 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_malnutrition', {}).get('show_vitamine_a_200', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_malnutrition', {}) else '')

    pas_pneumonie_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {}).get('pas_pneumonie_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {}).get('pas_pneumonie_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {}).get('pas_pneumonie_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {})
        .get('pas_pneumonie_treat_1_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {}).get('pas_pneumonie_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {}).get('pas_pneumonie_treat_2_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {})
        .get('pas_pneumonie_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_2_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {})
        .get('pas_pneumonie_treat_2_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {}).get('pas_pneumonie_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_pneumonie', {}) else '')
    pas_pneumonie_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pas_pneumonie', {}).get('pas_pneumonie_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pas_pneumonie', {}) else '')

    pneumonie_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_4_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_4_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_4_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_5_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_5_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_6_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_6_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_6_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('pneumonie_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')
    pneumonie_show_antibio_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie', {}).get('show_antibio_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie', {}) else '')

    pneumonie_grave_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_3_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_3_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_3_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {})
        .get('pneumonie_grave_treat_3_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_4_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {})
        .get('pneumonie_grave_treat_4_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_5_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {})
        .get('pneumonie_grave_treat_5_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {})
        .get('pneumonie_grave_treat_6', '') if f.form.get('treatments', {}) and f.form.get('treatments', {})
        .get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_6_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_6_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {})
        .get('pneumonie_grave_treat_6_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_7_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {})
        .get('pneumonie_grave_treat_7_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave', {}) else '')
    pneumonie_grave_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave', {}).get('pneumonie_grave_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('pneumonie_grave', {}) else '')

    pneumonie_grave_no_ref_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_title', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_2', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_3', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_3_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_3_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_4', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_4_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_4_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_5', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_5_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_5_help_0_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_6', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_6_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_7', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_7_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_7_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_8', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')
    pneumonie_grave_no_ref_treat_10 = flat_field(
        lambda f: f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {})
        .get('pneumonie_grave_no_ref_treat_10', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('pneumonie_grave_no_ref', {}) else '')

    rougeole_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole', {}) else '')
    rougeole_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole', {}) else '')
    rougeole_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole_treat_1', {}) else '')
    rougeole_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole', {}) else '')
    rougeole_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole_treat_3', {}) else '')
    rougeole_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole', {}) else '')
    rougeole_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_treat_4_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole', {}) else '')
    rougeole_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole', {}) else '')
    rougeole_show_antibio_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('rougeole_show_antibio_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole', {}) else '')
    rougeole_show_vitamine_a_200 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole', {}).get('show_vitamine_a_200', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole', {}) else '')

    rougeole_complications_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_title', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_complications', {}) else '')
    rougeole_complications_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_treat_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_complications', {}) else '')
    rougeole_complications_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_treat_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_complications_treat_1', {}) else '')
    rougeole_complications_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_treat_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_complications', {}) else '')
    rougeole_complications_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_treat_2_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('rougeole_complications', {}) else '')
    rougeole_complications_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_treat_3', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_complications_treat_3', {}) else '')
    rougeole_complications_treat_3_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_treat_3_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('rougeole_complications', {}) else '')
    rougeole_complications_treat_3_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_treat_3_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('rougeole_complications', {}) else '')
    rougeole_complications_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_complications', {})
        .get('rougeole_complications_treat_4', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_complications', {}) else '')

    rougeole_compliquee_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {}).get('rougeole_compliquee_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole_compliquee', {}) else '')
    rougeole_compliquee_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {})
        .get('rougeole_compliquee_treat_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_compliquee', {}) else '')
    rougeole_compliquee_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {})
        .get('rougeole_compliquee_treat_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_compliquee_treat_1', {}) else '')
    rougeole_compliquee_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {})
        .get('rougeole_compliquee_treat_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_compliquee', {}) else '')
    rougeole_compliquee_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {})
        .get('rougeole_compliquee_treat_3', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_compliquee_treat_3', {}) else '')
    rougeole_compliquee_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {})
        .get('rougeole_compliquee_treat_4', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_compliquee', {}) else '')
    rougeole_compliquee_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {})
        .get('rougeole_compliquee_treat_5', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_compliquee', {}) else '')
    rougeole_compliquee_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {})
        .get('rougeole_compliquee_treat_6', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_compliquee', {}) else '')
    rougeole_compliquee_show_antibio_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {})
        .get('rougeole_compliquee_show_antibio_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('rougeole_compliquee', {}) else '')
    rougeole_compliquee_show_vitamine_a_100 = flat_field(
        lambda f: f.form.get('treatments', {}).get('rougeole_compliquee', {}).get('show_vitamine_a_100', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('rougeole_compliquee', {}) else '')

    signes_deshydratation_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_title', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation', {}) else '')
    signes_deshydratation_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation', {}) else '')
    signes_deshydratation_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation', {}) else '')
    signes_deshydratation_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_3', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation_treat_3', {}) else '')
    signes_deshydratation_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_4', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation', {}) else '')
    signes_deshydratation_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_5', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation', {}) else '')
    signes_deshydratation_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_5_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_5_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_5_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_6', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation', {}) else '')
    signes_deshydratation_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_7', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation', {}) else '')
    signes_deshydratation_treat_7_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_7_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_8', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_8_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_8_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_8_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_8_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_8_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_8_help_1', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_8_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_8_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_9', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_10 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_10', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_10_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_10_help_0', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_10_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_10_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_11 = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_11', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('signes_deshydratation_treat_1', {}) else '')
    signes_deshydratation_treat_11_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('signes_deshydratation', {})
        .get('signes_deshydratation_treat_11_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('signes_deshydratation_treat_1', {}) else '')

    tdr_negatif_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('tdr_negatif', {}).get('tdr_negatif_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('tdr_negatif', {}) else '')
    tdr_negatif_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('tdr_negatif', {}).get('tdr_negatif_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('tdr_negatif', {}) else '')

    vih_confirmee_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_0_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {})
        .get('vih_confirmee_treat_0_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_0_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {})
        .get('vih_confirmee_treat_0_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_0_help_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {})
        .get('vih_confirmee_treat_0_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0_help_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_0_help_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_0_help_3_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {})
        .get('vih_confirmee_treat_0_help_3_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_5_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {})
        .get('vih_confirmee_treat_5_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_6_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_6_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {})
        .get('vih_confirmee_treat_6_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_6_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_6_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_6_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {})
        .get('vih_confirmee_treat_6_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_8_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_8_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_8_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {})
        .get('vih_confirmee_treat_8_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_confirmee', {}) else '')
    vih_confirmee_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_confirmee', {}).get('vih_confirmee_treat_9', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_confirmee', {}) else '')

    vih_pas_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1_help_0_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1_help_1_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1_help_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1_help_2_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1_help_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1_help_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_1_help_3_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_1_help_3_prompt', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')
    vih_pas_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_pas', {}).get('vih_pas_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_pas', {}) else '')

    vih_peu_probable_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {}).get('vih_peu_probable_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {}).get('vih_peu_probable_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {}).get('vih_peu_probable_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {})
        .get('vih_peu_probable_treat_1_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {})
        .get('vih_peu_probable_treat_1_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {})
        .get('vih_peu_probable_treat_1_help_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {})
        .get('vih_peu_probable_treat_1_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {})
        .get('vih_peu_probable_treat_1_help_2', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {})
        .get('vih_peu_probable_treat_1_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1_help_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {})
        .get('vih_peu_probable_treat_1_help_3', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_1_help_3_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {})
        .get('vih_peu_probable_treat_1_help_3_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_peu_probable', {}) else '')
    vih_peu_probable_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_peu_probable', {}).get('vih_peu_probable_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_peu_probable', {}) else '')

    vih_possible_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_0_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {})
        .get('vih_possible_treat_0_help_0_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_0_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {})
        .get('vih_possible_treat_0_help_1_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_0_help_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_0_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {})
        .get('vih_possible_treat_0_help_2_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_4_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_4_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_4_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {})
        .get('vih_possible_treat_4_help_0_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_5_help_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {})
        .get('vih_possible_treat_5_help_0_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_5_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_5_help_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_5_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {})
        .get('vih_possible_treat_5_help_1_prompt', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')
    vih_possible_show_antibio_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_possible', {}).get('vih_possible_show_antibio_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_possible', {}) else '')

    vih_symp_confirmee_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_0_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_0_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_0_help_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_0_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_0_help_2', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_0_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0_help_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_0_help_3', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_0_help_3_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_0_help_3_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_4 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_4', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_5 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_5', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_5_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_5_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_5_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_5_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_6 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_6', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_6_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_6_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_6_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_6_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_6_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_6_help_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_6_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_6_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_7 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_7', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_8 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_8', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_8_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_8_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_8_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_treat_8_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_treat_9 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {}).get('vih_symp_confirmee_treat_9', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')
    vih_symp_confirmee_show_antibio_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_confirmee', {})
        .get('vih_symp_confirmee_show_antibio_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_confirmee', {}) else '')

    vih_symp_suspecte_title = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {}).get('vih_symp_suspecte_title', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {}).get('vih_symp_suspecte_treat_0', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_0_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_0_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_0_help_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_0_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_0_help_2', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_0_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0_help_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_0_help_3', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_0_help_3_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_0_help_3_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {}).get('vih_symp_suspecte_treat_1', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {}).get('vih_symp_suspecte_treat_2', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2_help_0 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_2_help_0', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2_help_0_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_2_help_0_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2_help_1 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_2_help_1', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2_help_1_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_2_help_1_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2_help_2 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_2_help_2', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2_help_2_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_2_help_2_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2_help_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_2_help_3', '') if f.form.get('treatments', {})
        and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_2_help_3_prompt = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {})
        .get('vih_symp_suspecte_treat_2_help_3_prompt', '') if f.form.get('treatments', {}) and f.form.get(
            'treatments', {}).get('vih_symp_suspecte', {}) else '')
    vih_symp_suspecte_treat_3 = flat_field(
        lambda f: f.form.get('treatments', {}).get('vih_symp_suspecte', {}).get('vih_symp_suspecte_treat_3', '')
        if f.form.get('treatments', {}) and f.form.get('treatments', {}).get('vih_symp_suspecte', {}) else '')

    numerator = TDHNullEmitter()


TDHEnrollChildFluffPillow = TDHEnrollChildFluff.pillow()
TDHInfantClassificationFluffPillow = TDHInfantClassificationFluff.pillow()
TDHInfantTreatmentFluffPillow = TDHInfantTreatmentFluff.pillow()
TDHNewbornClassificationFluffPillow = TDHNewbornClassificationFluff.pillow()
TDHNewbornTreatmentFluffPillow = TDHNewbornTreatmentFluff.pillow()
TDHChildClassificationFluffPillow = TDHChildClassificationFluff.pillow()
TDHChildTreatmentFluffPillow = TDHChildTreatmentFluff.pillow()
