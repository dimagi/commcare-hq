import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import stripeCardManager from "accounting/js/stripe_card_manager";
import "accounting/js/widgets";

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

var cardManager = stripeCardManager.stripeCardManager({
    cards: initialPageData.get("cards"),
    url: initialPageData.reverse("cards_view"),
});
$(function () {
    $("#card-manager").koApplyBindings(cardManager);
});
