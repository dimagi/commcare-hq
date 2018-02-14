hqDefine('domain/js/update_billing_contact_info', function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        StripeCardManager = hqImport("accounting/js/stripe_card_manager").StripeCardManager;

    Stripe.setPublishableKey(initialPageData.get("stripe_public_key"));
    var cardManager = new StripeCardManager({
        cards: initialPageData.get("cards"),
        url: initialPageData.reverse("cards_view"),
    });
    $("#card-manager").koApplyBindings(cardManager);

    $("#show_emails").click(function() {
        $('#emails-text').show();
        $(this).parent().hide();
    });
});
