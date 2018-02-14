hqDefine('domain/js/update_billing_contact_info', function() {
    Stripe.setPublishableKey('{{ stripe_public_key }}');
    var cardManager = new hqImport("accounting/js/stripe_card_manager").StripeCardManager({
        cards: {{ cards|JSON }},
        url: '{{ card_base_url }}',
    });
    $("#card-manager").koApplyBindings(cardManager);

    $("#show_emails").click(function() {
        $('#emails-text').show();
        $(this).parent().hide();
    });
});
