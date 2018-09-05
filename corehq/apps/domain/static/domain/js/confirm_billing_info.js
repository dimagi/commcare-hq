/* global Stripe */
hqDefine("domain/js/confirm_billing_info", function() {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        stripeCardManager = hqImport("accounting/js/stripe_card_manager");

    $('a.breadcrumb-2').click(function (e) {
        e.preventDefault();
        var url = $(this).attr('href');
        var $navigateForm = $('<form method="post" style="display: none;" />').attr('action', url + 'confirm/');
        $(this).after($navigateForm);
        $navigateForm.append($('<input type="hidden" name="plan_edition" />').val(initialPageData.get("plan").edition));
        $navigateForm.submit();
    });

    Stripe.setPublishableKey(initialPageData.get("stripe_public_key"));
    var cardManager = stripeCardManager.stripeCardManager({
        cards: initialPageData.get("cards"),
        url: initialPageData.reverse("cards_view"),
    });
    $(function() {
        $("#card-manager").koApplyBindings(cardManager);
    });
});
