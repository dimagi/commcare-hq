hqDefine('domain/js/bootstrap3/update_billing_contact_info', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'accounting/js/stripe_card_manager',
    'accounting/js/widgets',
    'hqwebapp/js/bootstrap3/knockout_bindings.ko', // openModal
    'commcarehq',
], function (
    $,
    initialPageData,
    stripeCardManager,
) {
    $(function () {
        var cardManager = stripeCardManager.stripeCardManager({
            cards: initialPageData.get("cards"),
            url: initialPageData.reverse("cards_view"),
            elementSelector: '#stripe-card-container',
        });
        $("#card-manager").koApplyBindings(cardManager);

        $("#show_emails").click(function () {
            $('#emails-text').show();
            $(this).parent().hide();
        });
    });
});
