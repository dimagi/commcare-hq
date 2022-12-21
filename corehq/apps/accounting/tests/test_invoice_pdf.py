import os
from datetime import date
from decimal import Decimal
from io import BytesIO
from itertools import chain, product
from unittest.mock import patch

from django.test import SimpleTestCase
from reportlab.lib.utils import ImageReader

from corehq.tests.util.artifact import artifact

from ..invoice_pdf import (
    Address,
    InvoiceTemplate,
)


class TestInvoicePdf(SimpleTestCase):
    """Generates invoice PDF files and ensures they match the reference files
    that exist in version control.

    This tests against updates to the ``reportlab`` dependency to ensure library
    updates don't break rendered invoice PDFs.

    It is possible that new versions of reportlab could result in different PDF
    content (causing this test to fail), but the resulting PDF still being
    acceptable. If this happens, use the ``create_test_pdf_templates``
    management command to generate new reference PDFs and verify that they look
    the same (or close enough) as the old ones.
    """

    def test_invoice_template(self):
        renderer = InvoiceRenderer()
        print("")  # improves output with `test --nocapture`, noop otherwise
        for fpath, rendered in renderer.iter_invoices():
            rendered.seek(0)
            # write the rendered PDF as an artifact if the test fails
            with (
                open(fpath, "rb") as expected_pdf,
                artifact(os.path.basename(fpath), rendered),
            ):
                self.assertEqual(
                    expected_pdf.read(),
                    rendered.getvalue(),
                    f"{fpath!r} differs from rendered PDF",
                )


class InvoiceRenderer:

    TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

    # Use ImageReader for tests because reportlab creates a unique ID for all
    # embedded images in order to determine if it can reuse an image or needs
    # to embed it again (if drawn more than once). When calling `drawImage()`
    # with a filename, it uses the file path as the unique ID, meaning that the
    # PDF contents will differ across systems where __file__ differs.
    # see: https://github.com/MrBitBucket/reportlab-mirror/blob/fdea80e7/src/reportlab/pdfgen/canvas.py#L955-L972
    TEST_LOGO = ImageReader(os.path.join(TEST_DATA_DIR, "logo.jpg"))

    INVOICE_KWARG_CHOICES = {
        # keys must be valid kwarg names of `InvoiceTemplate.__init__()`
        "is_wire": (True, False),
        "is_customer": (True, False),
        "is_prepayment": (True, False),
    }
    INVALID_INVOICE_KWARGS = [
        # Add invalid kwarg combinations here, these will be skipped. Example:
        # {"is_wire": True, "is_customer": True, "is_prepayment": True},
        #
        # TODO: if you add any of these, add new tests for them using
        # `with self.assertRaises(ValueError):`.
    ]

    def iter_invoices(self):

        def empty(*args, **kw):
            """Callable used to prevent reportlab from building PDFs with
            volatile values (ones that change on every render).
            """
            return b""

        for invoice_id, (kwargs, items) in enumerate(chain(
            self.iter_all_kwarg_configs(),
            self.iter_multi_page_configs(),
        )):
            invoice_name = f"invoice_{invoice_id:03}.pdf"
            print(
                f"rendering invoice {invoice_name!r} with {len(items)} items "
                f"and kwargs: {kwargs}"
            )
            invoice_path = os.path.join(self.TEST_DATA_DIR, invoice_name)
            rendered = BytesIO()
            # Patch these so the rendered PDF doesn't change even if the
            # defaults in [local]settings.py change. Using `patch()` because
            # `override_settings()` didn't work (cached values?).
            with (
                patch("corehq.apps.accounting.invoice_pdf.settings.BASE_ADDRESS", "server.local"),
                patch("corehq.apps.accounting.invoice_pdf.settings.INVOICING_CONTACT_EMAIL", "bills@example.com"),
            ):
                # create a new invoice
                invoice = self.get_invoice(rendered, **kwargs)

                # add the line items
                for item in items:
                    invoice.add_item(*item)

                # Prevent /CreationDate and /ModDate metadata values
                # see: https://stackoverflow.com/a/52359214
                invoice.canvas.setDateFormatter(empty)

                # Prevent /ID metadata value
                # HACK: Canvas doesn't expose a setter to customize this
                invoice.canvas._doc.ID = empty

                # render the PDF
                invoice.get_pdf()
            yield invoice_path, rendered

    def iter_all_kwarg_configs(self):
        """Yields every combination of kwargs possible from
        ``INVOICE_KWARG_CHOICES`` excluding those in ``INVALID_INVOICE_KWARGS``.
        """
        # use the same line items for all kwarg configs
        line_items = []
        for item in range(4):
            line_items.append((
                f"Week {item + 1}",  # description
                "1",  # quantity
                Decimal("11.0"),  # unit_cost
                Decimal("11.0"),  # subtotal
                Decimal("-0.50"),  # credits
                Decimal("10.50"),  # total
            ))
        # NOTE: depends on the fact that python dicts are ordered
        keys = list(self.INVOICE_KWARG_CHOICES)
        for argv in product(*self.INVOICE_KWARG_CHOICES.values()):
            kwargs = {keys[i]: v for i, v in enumerate(argv)}
            if kwargs not in self.INVALID_INVOICE_KWARGS:
                yield kwargs, line_items

    def iter_multi_page_configs(self):
        # use the same kwargs for all multi-page configs
        kwargs = {"is_wire": False, "is_customer": True, "is_prepayment": False}
        per_line_credit = Decimal("-0.05")
        for item_desc, item_count in [
            ("Multi-page", 5),
            ("Long line descriptions coupled with lots of items", 18),
        ]:
            items = []
            # the test PDF has a "TOTAL" of 42.00, make the lines add up to that
            per_line = Decimal(f"{42.0 / item_count:.2f}")
            for item_index in range(item_count):
                items.append((
                    f"{item_desc} {item_index + 1}",  # description
                    "1",  # quantity
                    per_line,  # unit_cost
                    per_line,  # subtotal
                    per_line_credit,  # credits
                    per_line + per_line_credit,  # total
                ))
            yield kwargs, items

    def get_invoice(self, file_or_path, *, is_wire, is_customer, is_prepayment):
        """Returns an invoice instantiated with all available args passed
        positionally.

        NOTE: the required kwargs of this function must match the keys of
        ``INVOICE_KWARG_CHOICES``.
        """
        return InvoiceTemplate(
            file_or_path,  # filename
            self.TEST_LOGO,  # logo_image
            self.get_address("Tony"),  # from_address
            self.get_address("Jono"),  # to_address
            "group-therapy",  # project_name
            date(2022, 5, 10),  # invoice_date
            "42",  # invoice_number
            "30",  # terms
            date(2022, 6, 10),  # due_date
            date(2022, 4, 1),  # date_start
            date(2022, 4, 30),  # date_end
            "$",  # bank_name
            self.get_address("Paavo"),  # bank_address
            "123",  # account_number
            "456",  # routing_number_ach
            "789",  # routing_number_wire
            "---",  # swift_code
            Decimal('-20.00'),  # applied_credit
            Decimal('42.00'),  # subtotal
            Decimal('6'),  # tax_rate
            Decimal('2.52'),  # applied_tax
            Decimal('24.52'),  # total
            is_wire,  # is_wire
            is_customer,  # is_customer
            is_prepayment,  # is_prepayment
            "Above & Beyond",  # account_name
        )

    @staticmethod
    def get_address(name):
        """Returns an address that renders well in any address part of an
        Invoice PDF.
        """
        return Address(
            name=name,
            company_name="",
            first_line=f"1 {name[::-1].title()} St",
            second_line="",
            city="Trance",
            region="AB",
            postal_code="300",
            country="Around the World",
            phone_number="",
            email=f"{name.lower()}@example.com",
            # Don't populate `website` because doing so for a bank address will
            # likely make the bank info wrap in the footer and garble the text.
            website="",
        )
