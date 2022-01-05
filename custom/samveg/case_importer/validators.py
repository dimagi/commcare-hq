from django.utils.translation import ugettext as _

from corehq.apps.case_importer.exceptions import CaseRowError
from custom.samveg.const import MANDATORY_COLUMNS


class MandatoryColumnsValidator:
    @classmethod
    def validate(cls, spreadsheet):
        errors = []
        columns = spreadsheet.get_header_columns()
        missing_columns = set()
        for mandatory_columns in MANDATORY_COLUMNS:
            missing_columns.update(set(mandatory_columns) - set(columns))
        if missing_columns:
            errors.append(_('Missing columns {column_names}').format(
                column_names=", ".join(missing_columns))
            )
        return errors


class MandatoryValueValidator:
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update):
        errors = []
        for mandatory_columns in MANDATORY_COLUMNS:
            if isinstance(mandatory_columns, list):
                if not any(raw_row.get(column) for column in mandatory_columns):
                    errors.append(
                        CaseRowError(_('Need either {column_names}').format(
                            row_number=row_num,
                            column_names=", ".join(mandatory_columns))
                        )
                    )
            else:
                mandatory_column = mandatory_columns
                if not raw_row.get(mandatory_column):
                    errors.append(
                        CaseRowError(_('Missing column {column_name}').format(
                            row_number=row_num,
                            column_name=mandatory_column)
                        )
                    )
        return fields_to_update, errors
