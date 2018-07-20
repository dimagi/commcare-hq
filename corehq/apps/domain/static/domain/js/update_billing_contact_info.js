hqDefine('domain/js/update_billing_contact_info', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'accounting/js/stripe_card_manager',
    'stripe',
    'accounting/js/widgets'
], function (
    $,
    initialPageData,
    stripeCardManager,
    Stripe
) {
    $(function() {
        Stripe.setPublishableKey(initialPageData.get("stripe_public_key"));
        var cardManager = stripeCardManager.stripeCardManager({
            cards: initialPageData.get("cards"),
            url: initialPageData.reverse("cards_view"),
        });
        $("#card-manager").koApplyBindings(cardManager);

        $("#show_emails").click(function() {
            $('#emails-text').show();
            $(this).parent().hide();
        });
    });
});
