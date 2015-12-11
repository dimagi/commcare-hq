from django.forms.forms import Form
from django.forms.fields import *
from django.core.exceptions import ValidationError
from corehq.util.spreadsheets.excel import WorksheetNotFound, \
    WorkbookJSONReader
from openpyxl.utils.exceptions import InvalidFileException
from django.utils.translation import ugettext as _, ugettext_noop

class MessageBankForm(Form):
    message_bank_file = FileField(required=False)

    def clean_message_bank_file(self):
        value = self.cleaned_data.get("message_bank_file")

        if not value:
            raise ValidationError(_("Please choose a file."))

        try:
            workbook = WorkbookJSONReader(value)
        except InvalidFileException:
            raise ValidationError(_("Invalid format. Please convert to Excel 2007 or higher (.xlsx) and try again."))

        try:
            worksheet = workbook.get_worksheet()
        except WorksheetNotFound:
            raise ValidationError(_("Workbook has no worksheets."))

        message_ids = {}
        messages = []
        row_num = 2
        for row in worksheet:
            if "ID" not in row:
                raise ValidationError(_("Column 'ID' not found."))
            if "Message" not in row:
                raise ValidationError(_("Column 'Message' not found."))

            msg_id = row.get("ID")
            text = row.get("Message")

            try:
                assert isinstance(msg_id, basestring)
                msg_id = msg_id.strip()
                assert len(msg_id) > 1
                assert msg_id[0].upper() in "ABCDEFGH"
            except Exception:
                raise ValidationError(_("Invalid ID at row %(row_num)s") % {"row_num" : row_num})

            if msg_id in message_ids:
                raise ValidationError(_("Duplicate ID at row %(row_num)s") % {"row_num" : row_num})

            try:
                assert isinstance(text, basestring)
                text = text.strip()
                assert len(text) > 0
            except Exception:
                raise ValidationError(_("Invalid Message at row %(row_num)s") % {"row_num" : row_num})

            try:
                msg_id.encode("ascii")
            except Exception:
                raise ValidationError(_("ID at row %(row_num)s contains invalid character(s)") % {"row_num" : row_num})

            try:
                text.encode("ascii")
            except Exception:
                raise ValidationError(_("Message at row %(row_num)s contains invalid character(s)") % {"row_num" : row_num})

            if len(text) > 160:
                raise ValidationError(_("Message at row %(row_num)s is longer than 160 characters.") % {"row_num" : row_num})

            messages.append({
                "msg_id" : msg_id,
                "text" : text,
            })
            message_ids[msg_id] = True
            row_num += 1

        return messages

