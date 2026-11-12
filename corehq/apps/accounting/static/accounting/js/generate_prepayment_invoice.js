import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import paymentMethodHandler from "accounting/js/payment_method_handler";
import credits from "accounting/js/credits";
import "accounting/js/widgets";

const FORM_ID = 'prepayment-invoice-form';

$(function () {
    const $page = $('#prepaymentInvoice');
    const $domainSelect = $('form [name="domain"]');
    const paymentHandler = paymentMethodHandler.paymentMethodHandler(FORM_ID, {
        submitBtnText: gettext("Generate Invoice"),
        scheduleBtnText: gettext("Schedule Invoice"),
        errorMessages: initialPageData.get("payment_error_messages"),
        wire_email: initialPageData.get("wire_email"),
        wire_url: initialPageData.reverse("accounting_generate_prepayment_invoice"),
    });

    paymentHandler.paymentMethod(paymentHandler.WIRE);
    $('#paymentModal').koApplyBindings(paymentHandler);

    const creditsHandler = credits.creditsManager([], [], paymentHandler, true);
    $page.koApplyBindings(creditsHandler);
    creditsHandler.init();

    $domainSelect.on('change', function () {
        paymentHandler.domain($domainSelect.val());
    });
});
