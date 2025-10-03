import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import { userPaymentManager } from "domain/js/user_payment_manager";
import "accounting/js/widgets";
import "hqwebapp/js/bootstrap5/knockout_bindings.ko";  // openModal

$(function () {
    var userCardManager = userPaymentManager({
        cards: initialPageData.get("cards"),
        url: initialPageData.reverse("cards_view"),
    });
    $("#user-card-manager").koApplyBindings(userCardManager);

    $("#show_emails").click(function () {
        $('#emails-text').show();
        $(this).parent().hide();
    });
});
