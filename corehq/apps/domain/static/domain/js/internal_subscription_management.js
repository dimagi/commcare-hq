import "commcarehq";
import $ from "jquery";
import Alpine from "alpinejs";
import "hqwebapp/js/bootstrap5/widgets";

Alpine.data("subscriptionManagement", () => ({
    subscriptionType: $("#id_subscription_type").val() || null,
    trialLength: 90,
    get endDate() {
        const date = new Date();
        date.setHours(0, 0, 0, 0);
        date.setDate(date.getDate() + parseInt(this.trialLength));
        return date.toJSON().slice(0, 10);
    },
}));

Alpine.start();
