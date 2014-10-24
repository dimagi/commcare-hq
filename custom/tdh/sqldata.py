from sqlagg.columns import SimpleColumn
from sqlagg.filters import BETWEEN, IN
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
    for classification_row in classification_sql_data.rows:
        enroll_flag = False
        treatment_flag = False
        row = classification_row[:classification_case_id_index] + classification_row[
            classification_case_id_index + 1:]
        for enroll_row in enroll_sql_data.rows:
            if enroll_row[enroll_case_id_index] == classification_row[classification_case_id_index]:
                row = enroll_row[:enroll_case_id_index] + enroll_row[enroll_case_id_index + 1:] + row
                enroll_flag = True
                break
        row = row if enroll_flag else ['' for i in range(len(enroll_sql_data.headers))] + row
        for treatment_row in treatment_sql_data.rows:
            if treatment_row[treatment_case_id_index] == classification_row[classification_case_id_index]:
                row = row + treatment_row[:treatment_case_id_index] + treatment_row[treatment_case_id_index + 1:]
                treatment_flag = True
                break
        row = row if treatment_flag else row + ['' for i in range(len(treatment_sql_data.headers))]
        result.append(row)

    return result


class BaseSqlData(SqlData):
    datatables = True
    no_value = {'sort_key': 0, 'html': 0}

    @property
    def filters(self):
        filters = [BETWEEN("date", "startdate", "enddate")]
        if self.config['emw']:
            filters.append(IN('user_id', 'emw'))
        return filters

    @property
    def group_by(self):
        return []

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


class InfantClassification(BaseSqlData):
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
