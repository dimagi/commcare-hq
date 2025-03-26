import csv
from io import StringIO

from django.utils.translation import ugettext_lazy as _

from corehq.motech.repeaters.repeater_generators import (
    BasePayloadGenerator,
    get_form_json_payload,
)


class FormJsonCsvPayloadGenerator(BasePayloadGenerator):
    format_name = 'form_json_csv'
    format_label = _('CSV')

    def get_payload(self, repeat_record, form) -> str:
        """
        Returns a CSV row with the following columns:
        * domain
        * form_id
        * received_on
        * form_json

        """
        form_json = get_form_json_payload(form, include_attachments=False)
        row = (
            form.domain,
            form.form_id,
            form.received_on,
            form_json,
        )
        with StringIO() as buffer:
            csv_writer = csv.writer(buffer)
            csv_writer.writerow(row)
            return buffer.getvalue()

    @property
    def content_type(self):
        return 'text/csv'
