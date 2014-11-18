from sqlagg.columns import SimpleColumn
from sqlagg.filters import BETWEEN, IN, EQ
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import SqlData, DataFormatter, TableDataFormat, DatabaseColumn
from custom.tdh.reports import UNNECESSARY_FIELDS


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
            row = ['' for i in range(len(enroll_sql_data.headers))] + row

        if classification_case_id in treatment_map:
            row.extend(treatment_map[classification_case_id])
        else:
            row.extend(['' for i in range(len(treatment_sql_data.headers))])
        result.append(row)

    return result


class BaseSqlData(SqlData):
    datatables = True
    no_value = {'sort_key': 0, 'html': 0}

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
        return [DatabaseColumn(k, SimpleColumn(k)) for k in self.group_by]

    @property
    def headers(self):
        return [DataTablesColumn(k) for k in self.group_by[1:]]

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
        return ['case_id', 'tablet_login_id', 'author_id', 'author_name', 'visit_date',
                'weight', 'height', 'muac', 'temp', 'zscore_hfa', 'mean_hfa', 'zscore_wfa', 'mean_wfa',
                'zscore_wfh', 'mean_wfh', 'classification_deshydratation', 'classification_diahree',
                'classification_infection', 'classification_malnutrition', 'classification_vih', 'bcg']


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

        return [DataTablesColumn(k) for k in TDHInfantClassificationFluff().__dict__['_obj'].keys() if
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
        return ['case_id', 'tablet_login_id', 'author_id', 'author_name', 'visit_date',
                'weight', 'height', 'muac', 'temp', 'zscore_hfa', 'mean_hfa', 'zscore_wfa', 'mean_wfa',
                'zscore_wfh', 'mean_wfh', 'classification_infection', 'classification_malnutrition',
                'classification_occular', 'classification_poids', 'classification_vih', 'bcg', 'opv_0']


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

        return [DataTablesColumn(k) for k in TDHNewbornClassificationFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS + ['case_id']]

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
        return ['case_id', 'tablet_login_id', 'author_id', 'author_name', 'visit_date', 'weight',
                'height', 'muac', 'temp', 'zscore_hfa', 'mean_hfa', 'zscore_wfa', 'mean_wfa', 'zscore_wfh',
                'mean_wfh', 'classification_anemie', 'classification_deshydratation', 'classification_diahree',
                'classification_dysenterie', 'classification_malnutrition', 'classification_oreille',
                'classification_paludisme', 'classification_pneumonie', 'classification_rougeole',
                'classification_vih', 'classifications_graves', 'bcg', 'measles_1', 'measles_2', 'opv_0', 'opv_1',
                'opv_2', 'opv_3', 'penta_1', 'penta_2', 'penta_3', 'pneumo_1', 'pneumo_2', 'pneumo_3',
                'rotavirus_1', 'rotavirus_2', 'rotavirus_3', 'yf']


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

        return [DataTablesColumn(k) for k in TDHChildClassificationFluff().__dict__['_obj'].keys() if
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
        return ['case_id', 'dob', 'name', 'sex', 'village']

    @property
    def headers(self):
        return [DataTablesColumn(k) for k in self.group_by]


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

        return [DataTablesColumn(k) for k in TDHEnrollChildFluff().__dict__['_obj'].keys() if
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
        return ['case_id', 'classification_vih', 'antibio', 'deshydratation_severe_sans_infection_title',
                'incapable_nourrir_title', 'infection_grave_title', 'infection_locale_title', 'pas_infection_title'
                , 'probleme_alimentation_title', 'signe_deshydratation_infection_title', 'vih_pas_infection_title',
                'vih_possible_title']


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

        return [DataTablesColumn(k) for k in TDHInfantTreatmentFluff().__dict__['_obj'].keys() if
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
        return ['case_id', 'antibio', 'conjonctivite_title', 'fable_poids_title', 'incapable_nourrir_title',
                'hypothermie_moderee_title', 'infection_grave_title', 'infection_grave_no_ref_title',
                'infection_locale_title', 'infection_peu_probable_title', 'maladie_grave_title',
                'pas_de_faible_poids_title', 'pas_de_probleme_alimentation_title', 'pas_infection_occulaire_title',
                'poids_tres_faible_title', 'probleme_alimentation_title', 'vih_peu_probable_title',
                'vih_possible_title', 'vih_probable_title']


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

        return [DataTablesColumn(k) for k in TDHNewbornTreatmentFluff().__dict__['_obj'].keys() if
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
        return ['case_id', 'antibio', 'artemether', 'deparasitage', 'perfusion_p1_b', 'perfusion_p2_b',
                'vitamine_a', 'anemie_title', 'anemie_grave_title', 'antecedent_rougeole_title',
                'deshydratation_severe_grave_title', 'deshydratation_severe_pas_grave_perfusion_title',
                'diahree_persistante_title', 'dysenterie_title', 'infection_aigue_oreille_title', 'mam_title',
                'masc_title', 'mass_title', 'mastoidite_title', 'paludisme_grave_title',
                'paludisme_grave_no_ref_title', 'paludisme_grave_tdr_negatif_title', 'paludisme_simple_title',
                'pas_deshydratation_title', 'pas_malnutrition_title', 'pas_pneumonie_title', 'pneumonie_title',
                'pneumonie_grave_title', 'rougeole_title', 'rougeole_complications_title',
                'rougeole_compliquee_title', 'signes_deshydratation_title', 'tdr_negatif_title',
                'vih_confirmee_title', 'vih_pas_title', 'vih_peu_probable_title', 'vih_possible_title',
                'vih_symp_confirmee_title', 'vih_symp_suspecte_title']


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

        return [DataTablesColumn(k) for k in TDHChildTreatmentFluff().__dict__['_obj'].keys() if
                k not in UNNECESSARY_FIELDS + ['case_id']]

    @property
    def group_by(self):
        from custom.tdh.models import TDHChildTreatmentFluff

        return [k for k in TDHChildTreatmentFluff().__dict__['_obj'].keys() if k not in UNNECESSARY_FIELDS]
