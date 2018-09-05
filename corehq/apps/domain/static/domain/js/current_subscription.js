hqDefine("domain/js/current_subscription", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'accounting/js/credits',
    'accounting/js/payment_method_handler',
    'accounting/js/lib/stripe',
], function(
    $,
    initialPageData,
    credits,
    paymentMethodHandler,
    Stripe
) {
    $(function () {
        Stripe.setPublishableKey(initialPageData.get('stripe_public_key'));
        var paymentHandler = new paymentMethodHandler.PaymentMethodHandler(
            "add-credit-form",
            {
                submitBtnText: gettext("Buy Credits"),
                errorMessages: initialPageData.get("payment_error_messages"),
                credit_card_url: initialPageData.reverse("domain_credits_payment"),
                wire_url: initialPageData.reverse("domain_wire_payment"),
                wire_email: initialPageData.get("user_email"),
            }
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
            initialPageData.get("can_purchase_credits")
        );
        $('#subscriptionSummary').koApplyBindings(creditsHandler);
        creditsHandler.init();
    });

    $(function () {
        $('.hq-help').hqHelp();
    });
});
