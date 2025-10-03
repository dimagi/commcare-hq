import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import userPaymentManager from "domain/js/user_payment_manager";
import "accounting/js/widgets";
import "hqwebapp/js/bootstrap5/knockout_bindings.ko";  // openModal

$(function () {
    var cardManager = userPaymentManager.userPaymentManager({
        cards: initialPageData.get("cards"),
        url: initialPageData.reverse("cards_view"),
    });
    $("#card-manager").koApplyBindings(cardManager);

    $("#show_emails").click(function () {
        $('#emails-text').show();
        $(this).parent().hide();
    });
});
