import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import credits from "accounting/js/credits";
import paymentMethodHandler from "accounting/js/payment_method_handler";

$(function () {
    var paymentHandler = paymentMethodHandler.paymentMethodHandler(
        "add-credit-form",
        {
            submitBtnText: gettext("Buy Credits"),
            errorMessages: initialPageData.get("payment_error_messages"),
            credit_card_url: initialPageData.reverse("domain_credits_payment"),
            wire_url: initialPageData.reverse("domain_wire_payment"),
            wire_email: initialPageData.get("user_email"),
            autopayCard: initialPageData.get("autopay_card"),
        },
    );
    var plan = initialPageData.get("plan");
    if (plan.cards) {
        paymentHandler.loadCards(plan.cards);
    }
    $('#paymentModal').koApplyBindings(paymentHandler);

    var creditsHandler = credits.creditsManager(
        plan.products,
        plan.features,
        paymentHandler,
        initialPageData.get("can_purchase_credits"),
    );
    $('#subscriptionSummary').koApplyBindings(creditsHandler);
    creditsHandler.init();
});

$(function () {
    $('.hq-help').hqHelp();
});
