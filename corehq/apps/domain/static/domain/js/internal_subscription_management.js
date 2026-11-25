import "commcarehq";
import Alpine from "alpinejs";
import moment from "moment";
import "hqwebapp/js/bootstrap5/widgets";

Alpine.data("subscriptionManagement", () => ({
    subscriptionType: document.getElementById("id_subscription_type")?.value || null,
    trialLength: 90,
    get endDate() {
        return moment().startOf("day").add(this.trialLength, "days").format("YYYY-MM-DD");
    },
}));

Alpine.start();
