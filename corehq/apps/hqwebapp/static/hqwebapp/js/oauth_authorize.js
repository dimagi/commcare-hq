import "commcarehq";
import Alpine from "alpinejs";
import "hqwebapp/js/alpinejs/directives/select2";

Alpine.data("consentForm", () => ({
    selectedDomains: [],
    domainCount: 0,

    init() {
        this.domainCount = this.$refs.domains.options.length;
    },

    setAllDomains(selected) {
        Array.from(this.$refs.domains.options).forEach((option) => {
            option.selected = selected;
        });
        // Emit this event so select2 knows a change has happened;
        // programmatically setting selected is otherwise silent
        this.$refs.domains.dispatchEvent(new Event("change"));
    },

    get allDomainsSelected() {
        return this.domainCount > 0 && this.selectedDomains.length === this.domainCount;
    },
}));

Alpine.start();
