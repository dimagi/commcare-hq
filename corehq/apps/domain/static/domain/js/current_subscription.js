/* global Stripe */
hqDefine("domain/js/current_subscription", function() {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        CreditsManager = hqImport('accounting/js/credits').CreditsManager,
        PaymentMethodHandler = hqImport('accounting/js/payment_method_handler').PaymentMethodHandler;

    $(function () {
        Stripe.setPublishableKey(initialPageData.get('stripe_public_key'));
        var paymentHandler = new PaymentMethodHandler(
            "add-credit-form",
            {
                submitBtnText: gettext("Buy Credits"),
                errorMessages: initialPageData.get("payment_error_messages"),
                credit_card_url: initialPageData.get("credit_card_url"),
                wire_url: initialPageData.get("wire_url"),
                wire_email: initialPageData.get("user_email"),
            }
        );
        var plan = initialPageData.get("plan");
        if (plan.cards) {
            paymentHandler.loadCards(plan.cards);
        }
        $('#paymentModal').koApplyBindings(paymentHandler);

        var creditsHandler = new CreditsManager(
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