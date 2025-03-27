hqDefine('domain/js/bootstrap5/update_billing_contact_info', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'accounting/js/stripe_card_manager',
    'accounting/js/widgets',
    'hqwebapp/js/bootstrap5/knockout_bindings.ko', // openModal
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
        });
        $("#card-manager").koApplyBindings(cardManager);

        $("#show_emails").click(function () {
            $('#emails-text').show();
            $(this).parent().hide();
        });
    });
});
