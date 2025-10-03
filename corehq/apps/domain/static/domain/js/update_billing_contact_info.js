import "commcarehq";
import "hqwebapp/js/htmx_base";
import Alpine from "alpinejs";
import stripeCardManager from "domain/js/new_stripe_card_manager";
import $ from "jquery";
import "accounting/js/widgets";  // for asyncSelect2Handler

$(function () {
    $("#show_emails").click(function () {
        $('#emails-text').show();
        $(this).parent().hide();
    });
});

Alpine.data('newStripeCardManager', stripeCardManager);

Alpine.start();
