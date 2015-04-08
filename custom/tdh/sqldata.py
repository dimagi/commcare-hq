from sqlagg.columns import SimpleColumn
from sqlagg.filters import BETWEEN, IN, EQ
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import SqlData, DataFormatter, TableDataFormat, DatabaseColumn
from custom.tdh.reports import UNNECESSARY_FIELDS, CHILD_HEADERS_MAP, INFANT_HEADERS_MAP, NEWBORN_HEADERS_MAP


def merge_rows(classification_sql_data, enroll_sql_data, treatment_sql_data):
    result = []
    classification_case_id_index = [id for id, column in enumerate(classification_sql_data.columns)
                                    if column.slug == 'case_id'][0]
    enroll_case_id_index = [id for id, column in enumerate(enroll_sql_data.columns)
                            if column.slug == 'case_id'][0]
    treatment_case_id_index = [id for id, column in enumerate(treatment_sql_data.columns)
                               if column.slug == 'case_id'][0]
    enroll_map = {row[enroll_case_id_index]: row for row in enroll_sql_data.rows}
    treatment_map = {row[treatment_case_id_index]: row[:treatment_case_id_index]
                     + row[treatment_case_id_index + 1:] for row in treatment_sql_data.rows}

    for classification_row in classification_sql_data.rows:
        row = classification_row[:classification_case_id_index] + classification_row[
            classification_case_id_index + 1:]
        classification_case_id = classification_row[classification_case_id_index]
        if classification_case_id in enroll_map:
            row = enroll_map[classification_case_id] + row
        else:
            row = [classification_case_id] + ['' for i in range(len(enroll_sql_data.headers) - 1)] + row

        if classification_case_id in treatment_map:
            row.extend(treatment_map[classification_case_id])
        else:
            row.extend(['' for i in range(len(treatment_sql_data.headers))])
        result.append(row)

    return result


class BaseSqlData(SqlData):
    datatables = True
    no_value = {'sort_key': 0, 'html': 0}

    def header(self, header):
        if self.__class__.__name__[0] == 'N':
            return NEWBORN_HEADERS_MAP[header] if header in NEWBORN_HEADERS_MAP else header
        elif self.__class__.__name__[0] == 'I':
            return INFANT_HEADERS_MAP[header] if header in INFANT_HEADERS_MAP else header
        else:
            return CHILD_HEADERS_MAP[header] if header in CHILD_HEADERS_MAP else header

    @property
    def filters(self):
        filters = [BETWEEN("date", "startdate", "enddate"), EQ('domain', 'domain')]
        if self.config['emw']:
            filters.append(IN('user_id', 'emw'))
        return filters

    @property
    def group_by(self):
        return []

    @property
    def columns(self):
        columns = []
        for k in self.group_by:
            if k in ['zscore_hfa', 'zscore_wfa', 'zscore_wfh', 'mean_hfa', 'mean_wfa', 'mean_wfh']:
                columns.append(DatabaseColumn(k, SimpleColumn(k),
                                              format_fn=lambda x: "%.2f" % float(x if x else 0)))
            else:
                columns.append(DatabaseColumn(k, SimpleColumn(k)))
        return columns

    @property
    def headers(self):
        return [DataTablesColumn(self.header(k)) for k in self.group_by[1:]]

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))


class InfantConsultationHistory(BaseSqlData):
    table_name = "fluff_TDHInfantClassificationFluff"
    slug = 'infant_consultation_history'
    title = 'Infant Consultation History'

    @property
    def columns(self):
        return EnrollChild().columns + InfantClassification(config=self.config).columns + InfantTreatment().columns

    @property
    def headers(self):
        return DataTablesHeader(
            *EnrollChild().headers + InfantClassification(config=self.config).headers + InfantTreatment().headers)

    @property
    def group_by(self):
        return EnrollChild().group_by + InfantClassification(
            config=self.config).group_by + InfantTreatment().group_by

    @property
    def rows(self):
        return merge_rows(InfantClassification(config=self.config), EnrollChild(), InfantTreatment())


class InfantConsultationHistoryComplete(BaseSqlData):
    table_name = "fluff_TDHInfantClassificationFluff"
    slug = 'infant_consultation_history'
    title = 'Infant Consultation History'

    @property
    def columns(self):
        return EnrollChild().columns + InfantClassificationExtended(
            config=self.config).columns + InfantTreatmentExtended().columns

    @property
    def headers(self):
        return DataTablesHeader(*EnrollChild().headers + InfantClassificationExtended(
            config=self.config).headers + InfantTreatmentExtended().headers)

    @property
    def group_by(self):
        return EnrollChild().group_by + InfantClassificationExtended(
            config=self.config).group_by + InfantTreatmentExtended().group_by

    @property
    def rows(self):
        return merge_rows(InfantClassificationExtended(config=self.config), EnrollChild(),
                          InfantTreatmentExtended())


class NewbornConsultationHistory(BaseSqlData):
    table_name = "fluff_TDHNewbornClassificationFluff"
    slug = 'newborn_consultation_history'
    title = 'Newborn Consultation History'

    @property
    def columns(self):
        return EnrollChild().columns + NewbornClassification(
            config=self.config).columns + NewbornTreatment().columns

    @property
    def headers(self):
        return DataTablesHeader(*EnrollChild().headers + NewbornClassification(
            config=self.config).headers + NewbornTreatment().headers)

    @property
    def group_by(self):
        return EnrollChild().group_by + NewbornClassification(
            config=self.config).group_by + NewbornTreatment().group_by

    @property
    def rows(self):
        return merge_rows(NewbornClassification(config=self.config), EnrollChild(), NewbornTreatment())


class NewbornConsultationHistoryComplete(BaseSqlData):
    table_name = "fluff_TDHNewbornClassificationFluff"
    slug = 'newborn_consultation_history'
    title = 'Newborn Consultation History'

    @property
    def columns(self):
        return EnrollChild().columns + NewbornClassificationExtended(
            config=self.config).columns + NewbornTreatmentExtended().columns

    @property
    def headers(self):
        return DataTablesHeader(*EnrollChild().headers + NewbornClassificationExtended(
            config=self.config).headers + NewbornTreatmentExtended().headers)

    @property
    def group_by(self):
        return EnrollChild().group_by + NewbornClassificationExtended(
            config=self.config).group_by + NewbornTreatmentExtended().group_by

    @property
    def rows(self):
        return merge_rows(NewbornClassificationExtended(config=self.config), EnrollChild(),
                          NewbornTreatmentExtended())


class ChildConsultationHistory(BaseSqlData):
    table_name = "fluff_TDHChildClassificationFluff"
    slug = 'newborn_consultation_history'
    title = 'Newborn Consultation History'

    @property
    def columns(self):
        return EnrollChild().columns + ChildClassification(config=self.config).columns + ChildTreatment().columns

    @property
    def headers(self):
        return DataTablesHeader(
            *EnrollChild().headers + ChildClassification(config=self.config).headers + ChildTreatment().headers)

    @property
    def group_by(self):
        return EnrollChild().group_by + ChildClassification(
            config=self.config).group_by + ChildTreatment().group_by

    @property
    def rows(self):
        return merge_rows(ChildClassification(config=self.config), EnrollChild(), ChildTreatment())


class ChildConsultationHistoryComplete(BaseSqlData):
    table_name = "fluff_TDHChildClassificationFluff"
    slug = 'newborn_consultation_history'
    title = 'Newborn Consultation History'

    @property
    def columns(self):
        return EnrollChild().columns + ChildClassificationExtended(
            config=self.config).columns + ChildTreatmentExtended().columns

    @property
    def headers(self):
        return DataTablesHeader(
            *EnrollChild().headers + ChildClassificationExtended(
                config=self.config).headers + ChildTreatmentExtended().headers)

    @property
    def group_by(self):
        return EnrollChild().group_by + ChildClassificationExtended(
            config=self.config).group_by + ChildTreatmentExtended().group_by

    @property
    def rows(self):
        return merge_rows(ChildClassificationExtended(config=self.config), EnrollChild(), ChildTreatmentExtended())


class InfantClassification(BaseSqlData):
    table_name = "fluff_TDHInfantClassificationFluff"
    slug = 'infant_classification'
    title = 'Infant Classification'

    @property
    def group_by(self):
        return ['case_id', 'bcg', 'tablet_login_id', 'author_id', 'author_name', 'visit_date', 'consultation_type',
                'number', 'weight', 'height', 'muac', 'temp', 'zscore_hfa', 'mean_hfa', 'zscore_wfa', 'mean_wfa',
                'zscore_wfh', 'mean_wfh', 'classification_deshydratation', 'classification_diahree',
                'classification_infection', 'classification_malnutrition', 'classification_vih', 'inf_bac_qa',
                'inf_bac_freq_resp', 'inf_bac_qc', 'inf_bac_qd', 'inf_bac_qe', 'inf_bac_qf', 'inf_bac_qg',
                'inf_bac_qh', 'inf_bac_qj', 'inf_bac_qk', 'inf_bac_ql', 'inf_bac_qm', 'diarrhee_qa',
                'alimentation_qa', 'alimentation_qb', 'alimentation_qc', 'alimentation_qd', 'alimentation_qf',
                'alimentation_qg', 'alimentation_qh', 'vih_qa', 'vih_qb', 'vih_qc', 'vih_qd', 'vih_qe', 'vih_qf',
                'vih_qg', 'vih_qh', 'vih_qi', 'vih_qj', 'vih_qk', 'vih_ql', 'other_comments']


class InfantClassificationExtended(BaseSqlData):
    table_name = "fluff_TDHInfantClassificationFluff"
    slug = 'infant_classification'
    title = 'Infant Classification'

    @property
    def columns(self):
        from custom.tdh.models import TDHInfantClassificationFluff

        return [DatabaseColumn(k, SimpleColumn(k)) for k in TDHInfantClassificationFluff().__dict__['_obj'].keys()
                if k not in UNNECESSARY_FIELDS]

    @property
    def headers(self):
        from custom.tdh.models import TDHInfantClassificationFluff

        return [DataTablesColumn(self.header(k)) for k in TDHInfantClassificationFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS + ['case_id']]

    @property
    def group_by(self):
        from custom.tdh.models import TDHInfantClassificationFluff

        return [k for k in TDHInfantClassificationFluff().__dict__['_obj'].keys() if k not in UNNECESSARY_FIELDS]


class NewbornClassification(BaseSqlData):
    table_name = "fluff_TDHNewbornClassificationFluff"
    slug = 'newborn_classification'
    title = 'Newborn Classification'

    @property
    def group_by(self):
        return ['case_id', 'bcg', 'tablet_login_id', 'author_id', 'author_name', 'visit_date', 'consultation_type',
                'number', 'weight', 'height', 'muac', 'temp', 'zscore_hfa', 'mean_hfa', 'zscore_wfa', 'mean_wfa',
                'zscore_wfh', 'mean_wfh', 'classification_infection', 'classification_malnutrition',
                'classification_occular', 'classification_poids', 'classification_vih', 'inf_bac_qa', 'inf_bac_qb',
                'inf_bac_freq_resp', 'inf_bac_qd', 'inf_bac_qe', 'inf_bac_qf', 'inf_bac_qg', 'inf_bac_qh',
                'inf_bac_qi', 'inf_bac_qj', 'poids_qa', 'inf_occ_qa', 'vih_qa', 'vih_qb', 'vih_qc', 'vih_qd',
                'vih_qe', 'vih_qf', 'vih_qg', 'alimentation_qa', 'alimentation_qb', 'alimentation_qd',
                'alimentation_qf', 'alimentation_qg', 'other_comments']


class NewbornClassificationExtended(BaseSqlData):
    table_name = "fluff_TDHNewbornClassificationFluff"
    slug = 'newborn_classification'
    title = 'Newborn Classification'

    @property
    def columns(self):
        from custom.tdh.models import TDHNewbornClassificationFluff

        return [DatabaseColumn(k, SimpleColumn(k)) for k in TDHNewbornClassificationFluff().__dict__['_obj'].keys()
                if k not in UNNECESSARY_FIELDS]

    @property
    def headers(self):
        from custom.tdh.models import TDHNewbornClassificationFluff

        return [DataTablesColumn(self.header(k)) for k in TDHNewbornClassificationFluff().__dict__['_obj'].keys()
                if k not in UNNECESSARY_FIELDS + ['case_id']]

    @property
    def group_by(self):
        from custom.tdh.models import TDHNewbornClassificationFluff

        return [k for k in TDHNewbornClassificationFluff().__dict__['_obj'].keys() if k not in UNNECESSARY_FIELDS]


class ChildClassification(BaseSqlData):
    table_name = "fluff_TDHChildClassificationFluff"
    slug = 'child_consultation_history'
    title = 'Child Consultation History'

    @property
    def group_by(self):
        return ['case_id', 'bcg', 'tablet_login_id', 'author_id', 'author_name', 'visit_date', 'consultation_type',
                'number', 'weight', 'height', 'muac', 'temp', 'zscore_hfa', 'mean_hfa', 'zscore_wfa', 'mean_wfa',
                'zscore_wfh', 'mean_wfh', 'measles_1', 'measles_2', 'opv_0', 'opv_1', 'opv_2', 'opv_3', 'penta_1',
                'penta_2', 'penta_3', 'pneumo_1', 'pneumo_2', 'pneumo_3', 'rotavirus_1', 'rotavirus_2',
                'rotavirus_3', 'yf', 'classification_anemie', 'classification_deshydratation',
                'classification_diahree', 'classification_dysenterie', 'classification_malnutrition',
                'classification_oreille', 'classification_paludisme', 'classification_pneumonie',
                'classification_rougeole', 'classification_vih', 'classifications_graves', 'boire', 'vomit',
                'convulsions_passe', 'lethargie', 'convulsions_present', 'toux_presence', 'toux_presence_duree',
                'freq_resp', 'tirage', 'stridor', 'diarrhee', 'diarrhee_presence', 'diarrhee_presence_duree',
                'sang_selles', 'conscience_agitation', 'yeux_enfonces', 'soif', 'pli_cutane', 'fievre_presence',
                'fievre_presence_duree', 'fievre_presence_longue', 'tdr', 'urines_foncees', 'saignements_anormaux',
                'raideur_nuque', 'ictere', 'choc', 'eruption_cutanee', 'ecoulement_nasal', 'yeux_rouge',
                'ecoulement_oculaire', 'ulcerations', 'cornee', 'oreille', 'oreille_probleme', 'oreille_douleur',
                'oreille_ecoulement', 'oreille_ecoulement_duree', 'oreille_gonflement', 'paleur_palmaire',
                'oedemes', 'test_appetit', 'serologie_enfant', 'test_enfant', 'pneumonie_recidivante',
                'diarrhee_dernierement', 'candidose_buccale', 'hypertrophie_ganglions_lymphatiques',
                'augmentation_glande_parotide', 'test_mere', 'serologie_mere', 'other_comments']


class ChildClassificationExtended(BaseSqlData):
    table_name = "fluff_TDHChildClassificationFluff"
    slug = 'child_classification'
    title = 'Child Classification'

    @property
    def columns(self):
        from custom.tdh.models import TDHChildClassificationFluff

        return [DatabaseColumn(k, SimpleColumn(k)) for k in TDHChildClassificationFluff().__dict__['_obj'].keys()
                if k not in UNNECESSARY_FIELDS]

    @property
    def headers(self):
        from custom.tdh.models import TDHChildClassificationFluff

        return [DataTablesColumn(self.header(k)) for k in TDHChildClassificationFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS + ['case_id']]

    @property
    def group_by(self):
        from custom.tdh.models import TDHChildClassificationFluff

        return [k for k in TDHChildClassificationFluff().__dict__['_obj'].keys() if k not in UNNECESSARY_FIELDS]


class EnrollChild(BaseSqlData):
    table_name = "fluff_TDHEnrollChildFluff"
    slug = 'enroll_child'
    title = 'Enroll Child'

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return ['case_id', 'dob', 'sex', 'village']

    @property
    def headers(self):
        return [DataTablesColumn(self.header(k)) for k in self.group_by]


class EnrollChildExtended(BaseSqlData):
    table_name = "fluff_TDHEnrollChildFluff"
    slug = 'enroll_child'
    title = 'Enroll Child'

    @property
    def filters(self):
        return []

    @property
    def columns(self):
        from custom.tdh.models import TDHEnrollChildFluff

        return [DatabaseColumn(k, SimpleColumn(k)) for k in TDHEnrollChildFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS]

    @property
    def headers(self):
        from custom.tdh.models import TDHEnrollChildFluff

        return [DataTablesColumn(self.header(k)) for k in TDHEnrollChildFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS + ['case_id']]

    @property
    def group_by(self):
        from custom.tdh.models import TDHEnrollChildFluff

        return [k for k in TDHEnrollChildFluff().__dict__['_obj'].keys() if k not in UNNECESSARY_FIELDS]


class InfantTreatment(BaseSqlData):
    table_name = "fluff_TDHInfantTreatmentFluff"
    slug = 'infant_treatment'
    title = 'Infant Treatment'

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return ['case_id', 'infection_grave_treat_0', 'infection_grave_treat_1', 'infection_grave_treat_2',
                'infection_grave_no_ref_treat_0', 'infection_grave_no_ref_treat_1',
                'infection_grave_no_ref_treat_2', 'infection_grave_no_ref_treat_5', 'infection_locale_treat_0',
                'infection_locale_treat_1', 'maladie_grave_treat_0', 'maladie_grave_treat_1']


class InfantTreatmentExtended(BaseSqlData):
    table_name = "fluff_TDHInfantTreatmentFluff"
    slug = 'infant_treatment'
    title = 'Infant Treatment'

    @property
    def filters(self):
        return []

    @property
    def columns(self):
        from custom.tdh.models import TDHInfantTreatmentFluff

        return [DatabaseColumn(k, SimpleColumn(k)) for k in TDHInfantTreatmentFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS]

    @property
    def headers(self):
        from custom.tdh.models import TDHInfantTreatmentFluff

        return [DataTablesColumn(self.header(k)) for k in TDHInfantTreatmentFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS + ['case_id']]

    @property
    def group_by(self):
        from custom.tdh.models import TDHInfantTreatmentFluff

        return [k for k in TDHInfantTreatmentFluff().__dict__['_obj'].keys() if k not in UNNECESSARY_FIELDS]


class NewbornTreatment(BaseSqlData):
    table_name = "fluff_TDHNewbornTreatmentFluff"
    slug = 'newborn_treatment'
    title = 'Newborn Treatment'

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return ['case_id', 'infection_grave_treat_0', 'infection_grave_treat_1', 'infection_grave_no_ref_treat_0',
                'infection_grave_no_ref_treat_1', 'infection_locale_treat_0', 'infection_locale_treat_1',
                'incapable_nourrir_treat_0', 'incapable_nourrir_treat_1']


class NewbornTreatmentExtended(BaseSqlData):
    table_name = "fluff_TDHNewbornTreatmentFluff"
    slug = 'newborn_treatment'
    title = 'Newborn Treatment'

    @property
    def filters(self):
        return []

    @property
    def columns(self):
        from custom.tdh.models import TDHNewbornTreatmentFluff

        return [DatabaseColumn(k, SimpleColumn(k)) for k in TDHNewbornTreatmentFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS]

    @property
    def headers(self):
        from custom.tdh.models import TDHNewbornTreatmentFluff

        return [DataTablesColumn(self.header(k)) for k in TDHNewbornTreatmentFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS + ['case_id']]

    @property
    def group_by(self):
        from custom.tdh.models import TDHNewbornTreatmentFluff

        return [k for k in TDHNewbornTreatmentFluff().__dict__['_obj'].keys() if k not in UNNECESSARY_FIELDS]


class ChildTreatment(BaseSqlData):
    table_name = "fluff_TDHChildTreatmentFluff"
    slug = 'child_treatment'
    title = 'Child Treatment'

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return ['case_id', 'pneumonie_grave_treat_0',
                'pneumonie_grave_treat_1', 'pneumonie_grave_treat_4', 'pneumonie_grave_no_ref_treat_0',
                'pneumonie_grave_no_ref_treat_1', 'pneumonie_grave_no_ref_treat_3',
                'pneumonie_grave_no_ref_treat_5', 'pneumonie_grave_no_ref_treat_6', 'pneumonie_treat_0',
                'pneumonie_treat_1', 'deshydratation_severe_pas_grave_perfusion_treat_3',
                'deshydratation_severe_pas_grave_perfusion_treat_4',
                'deshydratation_severe_pas_grave_perfusion_treat_5',
                'deshydratation_severe_pas_grave_perfusion_treat_6',
                'deshydratation_severe_pas_grave_perfusion_treat_8',
                'deshydratation_severe_pas_grave_perfusion_treat_9',
                'deshydratation_severe_pas_grave_perfusion_treat_10',
                'deshydratation_severe_pas_grave_perfusion_treat_11',
                'deshydratation_severe_pas_grave_perfusion_treat_15',
                'deshydratation_severe_pas_grave_perfusion_treat_16',
                'deshydratation_severe_pas_grave_sng_treat_2', 'deshydratation_severe_pas_grave_sng_treat_3',
                'deshydratation_severe_pas_grave_sans_sng_sans_perfusion_treat_3',
                'deshydratation_severe_pas_grave_sans_sng_sans_perfusion_treat_4', 'signes_deshydratation_treat_0',
                'signes_deshydratation_treat_3', 'pas_deshydratation_treat_1', 'dysenterie_treat_1',
                'dysenterie_treat_2', 'dysenterie_treat_3', 'diahree_persistante_treat_0',
                'diahree_persistante_treat_1', 'paludisme_grave_treat_0', 'paludisme_grave_treat_1',
                'paludisme_grave_treat_2', 'paludisme_grave_treat_4', 'paludisme_grave_treat_5',
                'paludisme_grave_treat_7', 'paludisme_grave_no_ref_treat_0', 'paludisme_grave_no_ref_treat_1',
                'paludisme_grave_no_ref_treat_2', 'paludisme_grave_no_ref_treat_3',
                'paludisme_grave_no_ref_treat_5', 'paludisme_grave_no_ref_treat_6', 'paludisme_simple_treat_1',
                'paludisme_simple_treat_2', 'paludisme_simple_treat_3', 'paludisme_simple_treat_4',
                'paludisme_simple_treat_6', 'rougeole_compliquee_treat_0', 'rougeole_compliquee_treat_1',
                'rougeole_compliquee_treat_2', 'rougeole_compliquee_treat_3', 'rougeole_complications_treat_0',
                'rougeole_complications_treat_1', 'rougeole_treat_0', 'rougeole_treat_1', 'rougeole_treat_2',
                'rougeole_treat_3', 'antecedent_rougeole_treat_0', 'antecedent_rougeole_treat_1',
                'mastoidite_treat_0', 'mastoidite_treat_1', 'mastoidite_treat_2',
                'infection_aigue_oreille_treat_0', 'infection_aigue_oreille_treat_1', 'anemie_grave_treat_0',
                'anemie_treat_0', 'anemie_treat_1', 'anemie_treat_2', 'anemie_treat_3', 'anemie_treat_4',
                'anemie_treat_5', 'anemie_treat_6', 'mass_treat_2', 'mass_treat_3', 'mass_treat_4', 'mass_treat_5',
                'mass_treat_7', 'mass_treat_8', 'mam_treat_2', 'mam_treat_3', 'mam_treat_5', 'mam_treat_6',
                'mam_treat_7', 'pas_malnutrition_treat_2', 'pas_malnutrition_treat_3',
                'vih_symp_confirmee_treat_1', 'vih_symp_confirmee_treat_2', 'vih_symp_confirmee_treat_4',
                'vih_confirmee_treat_1', 'vih_confirmee_treat_2', 'vih_confirmee_treat_4',
                'vih_symp_probable_treat_1', 'vih_symp_probable_treat_2', 'vih_symp_probable_treat_3',
                'vih_possible_treat_1', 'vih_possible_treat_2', 'vih_possible_treat_3',
                'paludisme_grave_tdr_negatif_treat_0', 'paludisme_grave_tdr_negatif_treat_1',
                'paludisme_grave_tdr_negatif_treat_3', 'paludisme_grave_tdr_negatif_treat_4',
                'paludisme_grave_tdr_negatif_treat_6', 'vitamine_a']


class ChildTreatmentExtended(BaseSqlData):
    table_name = "fluff_TDHChildTreatmentFluff"
    slug = 'child_treatment'
    title = 'Child Treatment'

    @property
    def filters(self):
        return []

    @property
    def columns(self):
        from custom.tdh.models import TDHChildTreatmentFluff

        return [DatabaseColumn(k, SimpleColumn(k)) for k in TDHChildTreatmentFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS]

    @property
    def headers(self):
        from custom.tdh.models import TDHChildTreatmentFluff

        return [DataTablesColumn(self.header(k)) for k in TDHChildTreatmentFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS + ['case_id']]

    @property
    def group_by(self):
        from custom.tdh.models import TDHChildTreatmentFluff

        return [k for k in TDHChildTreatmentFluff().__dict__['_obj'].keys() if k not in UNNECESSARY_FIELDS]
