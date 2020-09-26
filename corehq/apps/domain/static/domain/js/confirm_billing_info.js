hqDefine("domain/js/confirm_billing_info", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'accounting/js/lib/stripe',
    'accounting/js/stripe_card_manager',
], function (
    $,
    ko,
    initialPageData,
    Stripe,
    stripeCardManager
) {
    $('a.breadcrumb-2').click(function (e) {
        e.preventDefault();
        var url = $(this).attr('href');
        var $navigateForm = $('<form method="post" style="display: none;" />').attr('action', url + 'confirm/');
        $(this).after($navigateForm);
        $navigateForm.append($('<input type="hidden" name="plan_edition" />').val(initialPageData.get("plan").edition));
        $navigateForm.submit();
    });

    document.getElementById('btn-subscribe-to-plan').onclick = function () {
        document.getElementById('downgrade-email-note').value = initialPageData.get("downgrade_email_note");
    };

    Stripe.setPublishableKey(initialPageData.get("stripe_public_key"));
    var cardManager = stripeCardManager.stripeCardManager({
        cards: initialPageData.get("cards"),
        url: initialPageData.reverse("cards_view"),
    });
    $(function () {
        $("#card-manager").koApplyBindings(cardManager);
    });
});
