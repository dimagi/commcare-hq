import "commcarehq";
import "hqwebapp/js/htmx_base";
import Alpine from "alpinejs";
import stripeCardManager from "domain/js/new_stripe_card_manager";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import "accounting/js/widgets";  // for asyncSelect2Handler

$('a.breadcrumb-2').click(function (e) {
    e.preventDefault();
    var url = $(this).attr('href');
    var $navigateForm = $('<form method="post" style="display: none;" />').attr('action', url + 'confirm/');
    $(this).after($navigateForm);
    $navigateForm.append($('<input type="hidden" name="plan_edition" />').val(initialPageData.get("plan").edition));
    $navigateForm.submit();
});


Alpine.data('newStripeCardManager', stripeCardManager);

Alpine.data('requiredBillingDetails', () => ({
    firstName: '',
    lastName: '',
    firstLine: '',
    city: '',
    postalCode: '',
    country: '',
    emailList: [],
    hasAutopay: false,
    isSubmitting: false,
    basicInfoComplete() {
        return (this.firstName
            && this.lastName && this.firstLine && this.city
            && this.postalCode && this.country && this.emailList
        );
    },
    showAutopayAndInfoRequiredNotice() {
        return !this.hasAutopay && !this.basicInfoComplete();
    },
    showAutopayRequiredNotice() {
        return !this.hasAutopay && this.basicInfoComplete();
    },
    showBillingInfoRequiredNotice() {
        return !this.basicInfoComplete() && this.hasAutopay;
    },
    showAutopayConfirmNotice() {
        return this.hasAutopay && this.basicInfoComplete();
    },
    isSubmitDisabled() {
        return !this.basicInfoComplete() || !this.hasAutopay;
    },
}));

Alpine.start();
