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
    'corehq/apps/accounting/static/accounting/images/Dimagi-Logo-RGB.jpg'


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
        return ('''%(name)s%(company_name)s
%(first_line)s%(second_line)s
%(city)s%(region)s %(postal_code)s
%(country)s%(phone_number)s%(email_address)s%(website)s
        ''' % {
            'name': self.name,
            'company_name': prepend_newline_if_not_empty(self.company_name),
            'first_line': self.first_line,
            'second_line': prepend_newline_if_not_empty(self.second_line),
            'city': "%s, " % self.city if self.city else "",
            'region': self.region,
            'postal_code': self.postal_code,
            'country': self.country,
            'phone_number': prepend_newline_if_not_empty(self.phone_number),
            'email_address': prepend_newline_if_not_empty(self.email),
            'website': prepend_newline_if_not_empty(self.website),
        }).lstrip()


LIGHT_GRAY = (0.7, 0.7, 0.7)
BLACK = (0, 0, 0)
DEFAULT_FONT_SIZE = 12


def inches(num_inches):
    return inch * num_inches


def midpoint(x1, x2):
    return (x1 + x2) * 0.5


class InvoiceTemplate(object):

    def __init__(self, filename, logo_filename=LOGO_FILENAME,
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
                 is_wire=False, is_prepayment=False):
        self.canvas = Canvas(filename)
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)
        self.logo_filename = os.path.join(os.getcwd(), logo_filename)
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
        self.is_prepayment = is_prepayment

        self.items = []

    def add_item(self, description, quantity, unit_cost, subtotal, credits, total):
        self.items.append(PdfLineItem(description, quantity, unit_cost,
                                      subtotal, credits, total))

    def get_pdf(self):
        self.draw_logo()
        self.draw_from_address()
        self.draw_to_address()
        self.draw_project_name()
        if not self.is_prepayment:
            self.draw_statement_period()
        self.draw_invoice_label()
        self.draw_details()
        if not self.is_wire or self.is_prepayment:
            self.draw_table()
        self.draw_footer()

        self.canvas.showPage()
        self.canvas.save()

    def draw_logo(self):
        self.canvas.drawImage(self.logo_filename, inches(0.5), inches(2.5),
                              width=inches(1.5), preserveAspectRatio=True)

    def draw_text(self, string, x, y):
        text = self.canvas.beginText()
        text.setTextOrigin(x, y)
        for line in string.split('\n'):
            text.textLine(line)
        self.canvas.drawText(text)

    def draw_from_address(self):
        if self.from_address is not None:
            self.draw_text(unicode(self.from_address), inches(3), inches(11))

    def draw_to_address(self):
        origin_x = inches(1)
        origin_y = inches(9.2)
        self.canvas.translate(origin_x, origin_y)

        left = inches(0)
        right = inches(4.5)
        top = inches(0.3)
        middle_horizational = inches(0)
        bottom = inches(-1.7)
        self.canvas.rect(left, bottom, right - left, top - bottom)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, middle_horizational, right - left,
                         top - middle_horizational, fill=1)

        self.canvas.setFillColorRGB(*BLACK)
        self.draw_text("Bill To", left + inches(0.2),
                       middle_horizational + inches(0.1))

        if self.to_address is not None:
            self.draw_text(unicode(self.to_address), inches(0.1), inches(-0.2))

        self.canvas.translate(-origin_x, -origin_y)

    def draw_project_name(self):
        origin_x = inches(1)
        origin_y = inches(7.4)
        self.canvas.translate(origin_x, origin_y)

        left = inches(0)
        middle_vertical = inches(1)
        right = inches(4.5)
        top = inches(0)
        bottom = inches(-0.3)
        self.canvas.rect(left, bottom, right - left, top - bottom)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, bottom, middle_vertical - left, top - bottom,
                         fill=1)

        self.canvas.setFillColorRGB(*BLACK)
        self.canvas.drawCentredString(midpoint(left, middle_vertical),
                                      bottom + inches(0.1),
                                      "Project")
        self.canvas.drawString(middle_vertical + inches(0.2),
                               bottom + inches(0.1), self.project_name)

        self.canvas.translate(-origin_x, -origin_y)

    def draw_statement_period(self):
        origin_x = inches(1)
        origin_y = inches(6.75)
        self.canvas.translate(origin_x, origin_y)

        self.canvas.drawString(
            0, 0, "Statement period from %s to %s" %
                  (self.date_start.strftime(USER_DATE_FORMAT)
                   if self.date_start is not None else "",
                   self.date_end.strftime(USER_DATE_FORMAT)
                   if self.date_end is not None else ""))

        self.canvas.translate(-origin_x, -origin_y)

    def draw_invoice_label(self):
        self.canvas.setFontSize(size=24)
        self.canvas.drawString(inches(6.5), inches(10.8), "Invoice")
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)

    def draw_details(self):
        origin_x = inches(5.75)
        origin_y = inches(9.5)
        self.canvas.translate(origin_x, origin_y)

        left = inches(0)
        right = inches(2)
        bottom = inches(0)
        top = inches(1.25)
        label_height = (top - bottom) / 6.0
        label_offset = label_height * 0.8
        content_offset = 1.5 * label_offset
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

        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      top - label_offset, "Date")
        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      top - label_height - content_offset,
                                      str(self.invoice_date))

        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      top - label_offset, "Invoice #")
        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      top - label_height - content_offset,
                                      self.invoice_number)

        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      middle_y - label_offset, "Terms")
        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      middle_y - label_height - content_offset,
                                      self.terms)

        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      middle_y - label_offset, "Due Date")
        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      middle_y - label_height - content_offset,
                                      str(self.due_date))

        self.canvas.translate(-origin_x, -origin_y)

    def draw_table(self):
        origin_x = inches(0.5)
        origin_y = inches(6.2)
        self.canvas.translate(origin_x, origin_y)

        height = inches(2.9)
        description_x = inches(2.4)
        quantity_x = inches(3.15)
        rate_x = inches(3.9)
        subtotal_x = inches(5.1)
        credits_x = inches(6.3)
        total_x = inches(7.5)
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

        self.canvas.drawCentredString(midpoint(0, description_x),
                                      inches(0.1),
                                      "Product")
        self.canvas.drawCentredString(midpoint(description_x, quantity_x),
                                      inches(0.1),
                                      "Quantity")
        self.canvas.drawCentredString(midpoint(quantity_x, rate_x),
                                      inches(0.1),
                                      "Unit Cost")
        self.canvas.drawCentredString(midpoint(rate_x, subtotal_x),
                                      inches(0.1),
                                      "Subtotal")
        self.canvas.drawCentredString(midpoint(subtotal_x, credits_x),
                                      inches(0.1),
                                      "Credits Applied")
        self.canvas.drawCentredString(midpoint(credits_x, total_x),
                                      inches(0.1),
                                      "Total")

        coord_y = 0
        for item_index in range(len(self.items)):
            if coord_y < -height:
                raise InvoiceError("Cannot fit line items on invoice")
            item = self.items[item_index]

            description = Paragraph(item.description,
                                    ParagraphStyle('',
                                                   fontSize=12,
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
        from corehq.apps.domain.views import DomainBillingStatementsView

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(inches(5), inches(1.65), inches(3), inches(0.5),
                         fill=1)
        self.canvas.setFillColorRGB(*BLACK)

        self.canvas.drawString(inches(5.6), inches(3.05), "Subtotal:")
        self.canvas.drawString(inches(5.6), inches(2.75),
                               "Tax (%0.2f%%):" % self.tax_rate)
        self.canvas.drawString(inches(5.6), inches(2.45), "Credit:")
        self.canvas.drawString(inches(5.2), inches(1.85), "Total:")
        self.canvas.drawCentredString(midpoint(inches(7.0), inches(8.0)),
                                      inches(3.05),
                                      get_money_str(self.subtotal))
        self.canvas.drawCentredString(midpoint(inches(7.0), inches(8.0)),
                                      inches(2.75),
                                      get_money_str(self.applied_tax))
        self.canvas.drawCentredString(midpoint(inches(7.0), inches(8.0)),
                                      inches(2.45),
                                      get_money_str(self.applied_credit))
        self.canvas.drawCentredString(midpoint(inches(7.0), inches(8.0)),
                                      inches(1.85),
                                      get_money_str(self.total))

        self.canvas.drawString(inches(5), inches(1.4),
                               "Thank you for using CommCare HQ.")

        payment_description = (
            "Payment Options:<br />"
            "<strong>Credit card payments</strong> are preferred and can be made online here: "
            "<link href='%(payment_page)s' color='blue'>%(payment_page)s</link><br />"
            "<br />"
            "<strong>ACH or Wire:</strong> If you make payment via ACH or Wire, please make sure to email "
            "<font color='blue'>%(invoicing_contact_email)s</font> "
            "so that we can match your payment to the correct invoice.  Please include: "
            "Invoice #, Project Space, and payment date in the email. <br />"
        ) % {
            'invoicing_contact_email': settings.INVOICING_CONTACT_EMAIL,
            'payment_page': absolute_reverse(DomainBillingStatementsView.urlname, args=[self.project_name]),
        }
        payment_info = Paragraph(payment_description, ParagraphStyle(''))
        payment_info.wrapOn(self.canvas, inches(4.25), inches(0.9))
        payment_info.drawOn(self.canvas, inches(0.5), inches(1.8))

        ach_payment_text = (
            "<strong>ACH payment</strong> (preferred over wire payment for transfer in the US):<br />"
            "Bank: %(bank_name)s "
            "Bank Address: %(bank_address)s "
            "Account Number: %(account_number)s "
            "Routing Number or ABA: %(routing_number_ach)s<br />"
        ) % {
            'bank_name': self.bank_name,
            'bank_address': self.bank_address,
            'account_number': self.account_number,
            'routing_number_ach': self.routing_number_ach,
        }
        wire_payment_text = (
            "<strong>Wire payment</strong>:<br />"
            "Bank: %(bank_name)s "
            "Bank Address: %(bank_address)s "
            "Account Number: %(account_number)s "
            "Routing Number or ABA: %(routing_number_wire)s "
            "Swift Code: %(swift_code)s<br/>"
        ) % {
            'bank_name': self.bank_name,
            'bank_address': self.bank_address,
            'account_number': self.account_number,
            'routing_number_wire': self.routing_number_wire,
            'swift_code': self.swift_code,
        }
        payment_info2 = Paragraph('\n'.join([
            ach_payment_text,
            wire_payment_text,
        ]), ParagraphStyle(''))
        payment_info2.wrapOn(self.canvas, inches(4.25), inches(0.9))
        payment_info2.drawOn(self.canvas, inches(0.7), inches(0.4))
