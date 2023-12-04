import os

from django.conf import settings

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from corehq.apps.accounting.exceptions import InvoiceError
from corehq.apps.accounting.utils import get_money_str
from corehq.const import USER_DATE_FORMAT
from corehq.util.view_utils import absolute_reverse

LOGO_FILENAME = \
    'corehq/apps/accounting/static/accounting/images/Dimagi-Deep-Purple-Standard-Logo.jpg'


def prepend_newline_if_not_empty(string):
    if string is None:
        return ""
    if len(string) > 0:
        return "\n" + string
    else:
        return string


class PdfLineItem(object):

    def __init__(self, description, quantity, unit_cost, subtotal, credits, total):
        self.description = description
        self.quantity = quantity
        self.unit_cost = unit_cost
        self.subtotal = subtotal
        self.credits = credits
        self.total = total


class Address(object):

    def __init__(
        self,
        name='',
        company_name='',
        first_line='',
        second_line='',
        city='',
        region='',
        postal_code='',
        country='',
        phone_number='',
        email='',
        website=''
    ):
        self.name = name
        self.company_name = company_name
        self.first_line = first_line
        self.second_line = second_line
        self.city = city
        self.region = region
        self.postal_code = postal_code
        self.country = country
        self.phone_number = phone_number
        self.email = email
        self.website = website

    def __str__(self):
        return "{mailing_address}\n{contact_info}".format(
            mailing_address=self.mailing_address,
            contact_info=self.contact_info
        ).lstrip()

    @property
    def mailing_address(self):
        return '''{name}{company_name}
{first_line}{second_line}
{city}{region} {postal_code}
{country}'''.format(
            name=self.name,
            company_name=prepend_newline_if_not_empty(self.company_name),
            first_line=self.first_line,
            second_line=prepend_newline_if_not_empty(self.second_line),
            city="{}, ".format(self.city) if self.city else "",
            region=self.region,
            postal_code=self.postal_code,
            country=self.country
        ).lstrip()

    @property
    def contact_info(self):
        return "{phone_number}{email_address}{website}".format(
            phone_number=prepend_newline_if_not_empty(self.phone_number),
            email_address=prepend_newline_if_not_empty(self.email),
            website=prepend_newline_if_not_empty(self.website)
        ).lstrip()


LIGHT_GRAY = (0.9, 0.9, 0.9)
STROKE_COLOR = (0.85, 0.85, 0.85)
BLACK = (0, 0, 0)
DEFAULT_FONT_SIZE = 10
SMALL_FONT_SIZE = 8


def inches(num_inches):
    return inch * num_inches


def midpoint(x1, x2):
    return (x1 + x2) * 0.5


class InvoiceTemplate(object):
    # TODO: improve invoice rendering logic to be more robust:
    # - More than 4 lines for a "from" address block (more than 4 populated of:
    #   name, company_name, first_line, second_line, city/region/postal_code,
    #   country) results in the bottom of the header "from" block being obscured
    #   by the "BILL TO" block.
    # - Too much text in a "bank" address (enough to result in a wrap) garbles
    #   the footer.
    # - It's unclear if all combinations of `is_wire`, `is_customer` and
    #   `is_prepayment` are valid together. If there are invalid combinations,
    #   this class should raise `ValueError` on invalid args.
    # - Add tests to validate expectations.
    # - Flywire URL should be parameterized.
    # - Default logo file path assumes that Django's CWD is at the root of the
    #   repo, which isn't necessarily a safe assumption to make.

    def __init__(self, filename,
                 logo_image=os.path.join(os.getcwd(), LOGO_FILENAME),
                 from_address=Address(**settings.INVOICE_FROM_ADDRESS),
                 to_address=None, project_name='',
                 invoice_date=None, invoice_number='',
                 terms=settings.INVOICE_TERMS,
                 due_date=None, date_start=None, date_end=None,
                 bank_name=settings.BANK_NAME,
                 bank_address=Address(**settings.BANK_ADDRESS),
                 account_number=settings.BANK_ACCOUNT_NUMBER,
                 routing_number_ach=settings.BANK_ROUTING_NUMBER_ACH,
                 routing_number_wire=settings.BANK_ROUTING_NUMBER_WIRE,
                 swift_code=settings.BANK_SWIFT_CODE,
                 applied_credit=None,
                 subtotal=None, tax_rate=None, applied_tax=None, total=None,
                 is_wire=False, is_customer=False, is_prepayment=False, account_name=''):
        self.canvas = Canvas(filename)
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)
        self.logo_image = logo_image
        self.from_address = from_address
        self.to_address = to_address
        self.project_name = project_name
        self.invoice_date = invoice_date
        self.invoice_number = invoice_number
        self.terms = terms
        self.due_date = due_date
        self.date_start = date_start
        self.date_end = date_end
        self.bank_name = bank_name
        self.bank_address = bank_address
        self.account_number = account_number
        self.routing_number_ach = routing_number_ach
        self.routing_number_wire = routing_number_wire
        self.swift_code = swift_code
        self.applied_credit = applied_credit
        self.subtotal = subtotal
        self.tax_rate = tax_rate
        self.applied_tax = applied_tax
        self.total = total
        self.is_wire = is_wire
        self.is_customer = is_customer
        self.is_prepayment = is_prepayment
        self.account_name = account_name

        self.items = []

    def add_item(self, description, quantity, unit_cost, subtotal, credits, total):
        self.items.append(PdfLineItem(description, quantity, unit_cost,
                                      subtotal, credits, total))

    def get_pdf(self):
        if self.is_customer:
            items = self.items
            while len(items) > 0:
                items_to_draw = items[12:]
                items = items[:12]
                self.draw_customer_invoice(items, items_to_draw)
                items = items_to_draw
        else:
            self.draw_table_with_header_and_footer(self.items)

        # should only call save once to avoid reportlab exception
        self.canvas.save()

    def draw_customer_invoice(self, items, items_to_draw):
        if len(items) <= 4:
            self.draw_table_with_header_and_footer(items)
        else:
            self.draw_header()
            self.draw_table(items)
            self.canvas.showPage()
            if len(items_to_draw) == 0:
                self.draw_totals_on_new_page()

    def draw_logo(self):
        self.canvas.drawImage(self.logo_image, inches(0.5), inches(10.5),
                              height=inches(0.75), width=inches(1.25),
                              preserveAspectRatio=True, anchor="w")

    def draw_text(self, string, x, y):
        text = self.canvas.beginText()
        text.setTextOrigin(x, y)
        for line in string.split('\n'):
            text.textLine(line)
        self.canvas.drawText(text)

    def draw_from_address(self):
        top = inches(10.3)
        if self.from_address.mailing_address is not None:
            self.draw_text(
                str(self.from_address.mailing_address),
                inches(.5),
                top
            )
        if self.from_address.contact_info is not None:
            self.draw_text(
                str(self.from_address.contact_info),
                inches(2.5),
                top
            )

    def draw_to_address(self):
        origin_x = inches(.5)
        origin_y = inches(9.2)
        self.canvas.translate(origin_x, origin_y)

        left = inches(0)
        right = inches(7.25)
        top = inches(0.3)
        middle_horizational = inches(0)
        bottom = inches(-1.35)
        self.canvas.rect(left, bottom, right - left, top - bottom)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, middle_horizational, right - left,
                         top - middle_horizational, fill=1)

        self.canvas.setFillColorRGB(*BLACK)
        self.canvas.setFontSize(SMALL_FONT_SIZE)
        self.draw_text("BILL TO", left + inches(0.2),
                       middle_horizational + inches(0.1))
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)

        if self.to_address.mailing_address is not None:
            self.draw_text(
                str(self.to_address.mailing_address),
                left + inches(0.2),
                inches(-0.2)
            )
        if self.to_address.contact_info is not None:
            self.draw_text(
                str(self.to_address.contact_info),
                left + inches(4.2),
                inches(-0.2)
            )
        self.canvas.translate(-origin_x, -origin_y)

    def draw_project_name(self):
        origin_x = inches(.5)
        origin_y = inches(7.7)
        self.canvas.translate(origin_x, origin_y)

        left = inches(0)
        middle_vertical = inches(1)
        right = inches(7.25)
        top = inches(0)
        bottom = inches(-0.3)
        self.canvas.rect(left, bottom, right - left, top - bottom)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, bottom, middle_vertical - left, top - bottom,
                         fill=1)

        self.canvas.setFillColorRGB(*BLACK)
        self.canvas.setFontSize(SMALL_FONT_SIZE)
        self.canvas.drawCentredString(
            midpoint(left - inches(.1), middle_vertical),
            bottom + inches(0.1),
            "PROJECT"
        )
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)
        self.canvas.drawString(middle_vertical + inches(0.2),
                               bottom + inches(0.1), self.project_name)

        self.canvas.translate(-origin_x, -origin_y)

    def draw_account_name(self):
        origin_x = inches(.5)
        origin_y = inches(7.7)
        self.canvas.translate(origin_x, origin_y)

        left = inches(0)
        middle_vertical = inches(1)
        right = inches(7.25)
        top = inches(0)
        bottom = inches(-0.3)
        self.canvas.rect(left, bottom, right - left, top - bottom)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, bottom, middle_vertical - left, top - bottom,
                         fill=1)

        self.canvas.setFillColorRGB(*BLACK)
        self.canvas.setFontSize(SMALL_FONT_SIZE)
        self.canvas.drawCentredString(
            midpoint(left - inches(.1), middle_vertical),
            bottom + inches(0.1),
            "ACCOUNT"
        )
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)
        self.canvas.drawString(middle_vertical + inches(0.2),
                               bottom + inches(0.1), self.account_name)

        self.canvas.translate(-origin_x, -origin_y)

    def draw_statement_period(self):
        origin_x = inches(0.5)
        origin_y = inches(7.15)
        self.canvas.translate(origin_x, origin_y)

        self.canvas.drawString(
            0, 0, "Statement period from {} to {}.".format(
                self.date_start.strftime(USER_DATE_FORMAT)
                if self.date_start is not None else "",
                self.date_end.strftime(USER_DATE_FORMAT)
                if self.date_end is not None else ""
            )
        )

        self.canvas.translate(-origin_x, -origin_y)

    def draw_invoice_label(self):
        self.canvas.setFontSize(22)
        self.canvas.drawString(inches(2.5), inches(10.8), "INVOICE")
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)

    def draw_details(self):
        origin_x = inches(4.5)
        origin_y = inches(9.65)
        self.canvas.translate(origin_x, origin_y)

        left = inches(0)
        right = inches(3.25)
        bottom = inches(0)
        top = inches(1.6)
        label_height = (top - bottom) / 4.5
        label_offset = label_height * 0.6
        content_offset = 1.2 * label_offset
        middle_x = midpoint(left, right)
        middle_y = midpoint(bottom, top)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, middle_y - label_height,
                         right - left, label_height, fill=1)
        self.canvas.rect(left, top - label_height, right - left, label_height,
                         fill=1)
        self.canvas.setFillColorRGB(*BLACK)

        self.canvas.rect(left, bottom, right - left, top - bottom)
        self.canvas.rect(left, bottom, 0.5 * (right - left), top - bottom)
        self.canvas.rect(left, bottom, right - left, 0.5 * (top - bottom))

        self.canvas.setFontSize(SMALL_FONT_SIZE)
        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      top - label_offset, "DATE")
        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      top - label_offset, "INVOICE NO.")
        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      middle_y - label_offset, "TERMS")
        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      middle_y - label_offset, "DUE DATE")
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)

        # Date
        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      top - label_height - content_offset,
                                      str(self.invoice_date))
        # Invoice No.
        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      top - label_height - content_offset,
                                      self.invoice_number)
        # Terms
        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      middle_y - label_height - content_offset,
                                      self.terms)
        # Due Date
        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      middle_y - label_height - content_offset,
                                      str(self.due_date))

        self.canvas.translate(-origin_x, -origin_y)

    def draw_header(self):
        self.canvas.setStrokeColor(STROKE_COLOR)
        self.draw_logo()
        self.draw_from_address()
        self.draw_to_address()
        if self.is_customer:
            self.draw_account_name()
        else:
            self.draw_project_name()
        if not self.is_prepayment:
            self.draw_statement_period()
        self.draw_invoice_label()
        self.draw_details()

    def draw_table(self, items):
        origin_x = inches(0.5)
        origin_y = inches(6.72)
        self.canvas.translate(origin_x, origin_y)

        height = inches(0.725 * len(items))
        description_x = inches(2.4)
        quantity_x = inches(3.15)
        rate_x = inches(3.9)
        subtotal_x = inches(5.1)
        credits_x = inches(6.0)
        total_x = inches(7.25)
        header_height = inches(0.3)

        self.canvas.rect(0, 0, total_x, -height)
        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(0, 0, total_x, header_height,
                         fill=1)
        self.canvas.setFillColorRGB(*BLACK)
        self.canvas.line(description_x, header_height, description_x, -height)
        self.canvas.line(quantity_x, header_height, quantity_x, -height)
        self.canvas.line(rate_x, header_height, rate_x, -height)
        self.canvas.line(subtotal_x, header_height, subtotal_x, -height)
        self.canvas.line(credits_x, header_height, credits_x, -height)

        self.canvas.setFontSize(SMALL_FONT_SIZE)
        self.canvas.drawCentredString(midpoint(0, description_x),
                                      inches(0.1),
                                      "PRODUCT")
        self.canvas.drawCentredString(midpoint(description_x, quantity_x),
                                      inches(0.1),
                                      "QUANTITY")
        self.canvas.drawCentredString(midpoint(quantity_x, rate_x),
                                      inches(0.1),
                                      "UNIT COST")
        self.canvas.drawCentredString(midpoint(rate_x, subtotal_x),
                                      inches(0.1),
                                      "SUBTOTAL")
        self.canvas.drawCentredString(midpoint(subtotal_x, credits_x),
                                      inches(0.1),
                                      "CREDITS")
        self.canvas.drawCentredString(midpoint(credits_x, total_x),
                                      inches(0.1),
                                      "TOTAL")
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)

        coord_y = 0
        for item_index in range(len(items)):
            if coord_y < -height:
                raise InvoiceError("Cannot fit line items on invoice")
            item = items[item_index]

            description = Paragraph(item.description,
                                    ParagraphStyle('',
                                                   fontSize=DEFAULT_FONT_SIZE,
                                                   ))
            description.wrapOn(self.canvas, description_x - inches(0.2),
                               -header_height)
            coord_y -= description.height + inches(0.05)
            description.drawOn(self.canvas, inches(0.1), coord_y)
            self.canvas.drawCentredString(
                midpoint(description_x, quantity_x),
                coord_y,
                str(item.quantity)
            )
            self.canvas.drawCentredString(
                midpoint(quantity_x, rate_x),
                coord_y,
                get_money_str(item.unit_cost)
            )
            self.canvas.drawCentredString(
                midpoint(rate_x, subtotal_x),
                coord_y,
                get_money_str(item.subtotal)
            )
            self.canvas.drawCentredString(
                midpoint(subtotal_x, credits_x),
                coord_y,
                get_money_str(item.credits)
            )
            self.canvas.drawCentredString(
                midpoint(credits_x, total_x),
                coord_y,
                get_money_str(item.total)
            )
            coord_y -= inches(0.1)
            self.canvas.line(0, coord_y, total_x, coord_y)

        self.canvas.translate(-origin_x, -origin_y)

    def draw_footer(self):
        width = inches(5.00)
        left_x = inches(0.5)

        options = "PAYMENT OPTIONS:"
        self.canvas.setFontSize(SMALL_FONT_SIZE)
        options_text = Paragraph(options, ParagraphStyle(''))
        options_text.wrapOn(self.canvas, width, inches(.12))
        options_text.drawOn(self.canvas, left_x, inches(3.5))
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)

        flywire = """<strong>International payments:</strong>
                            Make payments in your local currency
                            via bank transfer or credit card by following this link:
                            <link href='{flywire_link}' color='blue'>{flywire_link}</link><br />""".format(
            flywire_link="https://wl.flywire.com/?destination=DMG"
        )
        flywire_text = Paragraph(flywire, ParagraphStyle(''))
        flywire_text.wrapOn(self.canvas, width, inches(.4))
        flywire_text.drawOn(self.canvas, left_x, inches(2.95))

        from corehq.apps.domain.views.accounting import DomainBillingStatementsView
        credit_card = """<strong>Credit card payments (USD)</strong> can be made online here:<br />
                            <link href='{payment_page}' color='blue'>{payment_page}</link><br />""".format(
            payment_page=absolute_reverse(
                DomainBillingStatementsView.urlname, args=[self.project_name])
        )
        credit_card_text = Paragraph(credit_card, ParagraphStyle(''))
        credit_card_text.wrapOn(self.canvas, width, inches(.5))
        credit_card_text.drawOn(self.canvas, left_x, inches(2.4))

        ach_or_wire = """<strong>ACH or Wire:</strong> If you make payment via ACH
                            or Wire, please make sure to email
                            <font color='blue'>{invoicing_contact_email}</font>
                            so that we can match your payment to the correct invoice.  Please include:
                            Invoice No., Project Space, and payment date in the email. <br />""".format(
            invoicing_contact_email=settings.INVOICING_CONTACT_EMAIL,
        )
        ach_or_wire_text = Paragraph(ach_or_wire, ParagraphStyle(''))
        ach_or_wire_text.wrapOn(self.canvas, width, inches(.5))
        ach_or_wire_text.drawOn(self.canvas, left_x, inches(1.7))

        ach_payment_text = """<strong>ACH payment</strong>
                            (preferred over wire payment for transfer in the US):<br />
                            Bank: {bank_name}
                            Bank Address: {bank_address}
                            Account Number: {account_number}
                            Routing Number or ABA: {routing_number_ach}<br />""".format(
            bank_name=self.bank_name,
            bank_address=self.bank_address,
            account_number=self.account_number,
            routing_number_ach=self.routing_number_ach
        )
        wire_payment_text = """<strong>Wire payment</strong>:<br />
                            Bank: {bank_name}
                            Bank Address: {bank_address}
                            Account Number: {account_number}
                            Routing Number or ABA: {routing_number_wire}
                            Swift Code: {swift_code}<br/>""".format(
            bank_name=self.bank_name,
            bank_address=self.bank_address,
            account_number=self.account_number,
            routing_number_wire=self.routing_number_wire,
            swift_code=self.swift_code
        )
        payment_info2 = Paragraph('\n'.join([
            ach_payment_text,
            wire_payment_text,
        ]), ParagraphStyle(''))
        payment_info2.wrapOn(self.canvas, width - inches(0.1), inches(0.9))
        payment_info2.drawOn(self.canvas, inches(0.6), inches(0.5))

    def draw_table_with_header_and_footer(self, items):
        self.draw_header()
        if not self.is_wire or self.is_prepayment:
            self.draw_table(items)
        self.draw_totals(totals_x=inches(5.85), line_height=inches(0.25), subtotal_y=inches(3.5))
        self.draw_footer()
        self.canvas.showPage()

    def draw_totals_on_new_page(self):
        self.canvas.setStrokeColor(STROKE_COLOR)
        self.draw_logo()
        self.draw_from_address()
        self.draw_to_address()
        self.draw_account_name()
        if not self.is_prepayment:
            self.draw_statement_period()
        self.draw_invoice_label()
        self.draw_details()

        self.draw_totals(totals_x=inches(5.85), line_height=inches(0.25), subtotal_y=inches(7.0))
        self.draw_footer()
        self.canvas.showPage()

    def draw_totals(self, totals_x, line_height, subtotal_y):
        tax_y = subtotal_y - line_height
        credit_y = tax_y - line_height
        total_y = credit_y - (line_height * 2)

        totals_money_x = totals_x + inches(1)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(
            inches(5.7),
            subtotal_y - inches(1.2),
            inches(2.05),
            inches(0.5),
            fill=1
        )
        self.canvas.setFillColorRGB(*BLACK)

        self.canvas.drawString(totals_x, subtotal_y, "Subtotal:")
        self.canvas.drawString(totals_x, tax_y,
                               "Tax (%0.2f%%):" % self.tax_rate)
        self.canvas.drawString(totals_x, credit_y, "Credit:")
        self.canvas.drawString(totals_x, total_y, "Total:")
        self.canvas.drawString(
            totals_money_x,
            subtotal_y,
            get_money_str(self.subtotal)
        )
        self.canvas.drawString(
            totals_money_x,
            tax_y,
            get_money_str(self.applied_tax)
        )
        self.canvas.drawString(
            totals_money_x,
            credit_y,
            get_money_str(self.applied_credit)
        )
        self.canvas.drawString(
            totals_money_x,
            total_y,
            get_money_str(self.total)
        )

        self.canvas.setFontSize(SMALL_FONT_SIZE)
        self.canvas.drawString(inches(5.85), subtotal_y - inches(1.4),
                               "Thank you for using CommCare HQ.")
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)
