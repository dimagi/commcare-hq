hqDefine('accounting/js/pricing_table', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    "hqwebapp/js/assert_properties",
], function (
    $,
    ko,
    _,
    initialPageData,
    assertProperties
) {
    var PricingTable = function (options) {
        assertProperties.assert(options, [
            'editions',
            'planOptions',
            'currentPlan',
        ]);

        'use strict';
        var self = {};

        self.currentPlan = ko.observable(options.currentPlan);
        self.editions = options.editions;

        self.selectedPlan = ko.observable(options.currentPlan);

        self.showMonthlyPricing = ko.observable(false);

        self.refundCss = ko.computed(function () {
            if (self.showMonthlyPricing()) {
                return "hide-refund";
            }
            return "";
        });

        self.isSubmitVisible = ko.computed(function () {
            return !! self.selectedPlan() && !(self.selectedPlan() === self.currentPlan());
        });

        self.isCurrentPlanCommunity = ko.observable(options.currentPlan === 'community');

        self.selectCommunityPlan = function () {
            self.selectedPlan('community');
        };

        self.communityCss = ko.computed(function () {
            if (self.selectedPlan() === 'community') {
                return "selected-plan";
            }
            return "";
        });

        self.planOptions = ko.observableArray(_.map(options.planOptions, function (opt) {
          return new PlanOption(opt, self);
        }));

        self.showNext = ko.computed(function () {
            return self.selectedPlan() === 'community' || self.showMonthlyPricing();
        });

        self.openDowngradeModal = function(pricingTable, e) {
            if (
                self.editions.indexOf(self.selectedPlan()) <
                self.editions.indexOf(self.currentPlan())
            ) {
                var $modal = $("#modal-downgrade");
                $modal.modal('show');
            } else {
                self.form.submit();
            }
        };

        self.submitDowngrade = function(pricingTable, e) {
            var _submitForm = function() {
                self.form.submit();
            };

            var $button = $(e.currentTarget);
            $button.disableButton();

            $.ajax({
                method: "POST",
                url: initialPageData.reverse('email_on_downgrade'),
                data: {
                    old_plan: self.currentPlan(),
                    new_plan: self.selectedPlan(),
                    note: $button.closest(".modal").find("textarea").val(),
                },
                success: _submitForm,
                error: _submitForm,
            });
        };

        self.contactSales = function (pricingTable, e) {
            var $button = $(e.currentTarget);
            $button.disableButton();

            self.form = $(e.currentTarget).closest("form");
            self.currentPlan = self.currentPlan + " - annual pricing";
            self.form.submit();
        };

        self.init = function () {
            self.form = $("#select-plan-form");
        };

        return self;
    };

    var PlanOption = function (data, parent) {
        'use strict';
        var self = this;

        self.name = ko.observable(data.name);
        self.slug = ko.observable(data.name.toLowerCase());

        self.monthlyPrice = ko.observable(data.monthly_price);
        self.annualPrice = ko.observable(data.annual_price);
        self.description = ko.observable(data.description);

        self.isCurrentPlan = ko.computed(function () {
            return self.slug() === parent.currentPlan();
        });

        self.isSelectedPlan = ko.computed(function () {
            return self.slug() === parent.selectedPlan();
        });

        self.cssClass = ko.computed(function () {
            var cssClass = "tile-" + self.slug();
            if (self.isSelectedPlan()) {
                cssClass = cssClass + " selected-plan";
            }
            return cssClass;
        });

        self.selectPlan = function () {
            parent.selectedPlan(self.slug());
        };

        self.pricingTypeText = ko.computed(function (){
            if (parent.showMonthlyPricing()) {
                return django.gettext("Billed Monthly");
            }
            return django.gettext("Billed Annually");
        });

        self.pricingTypeCssClass = ko.computed(function (){
            if (parent.showMonthlyPricing()) {
                return 'pricing-type-monthly';
            }
            return 'pricing-type-annual';
        });

        self.displayPrice = ko.computed(function () {
            if (parent.showMonthlyPricing()) {
                return self.monthlyPrice();
            }
            return self.annualPrice();
        });

    };


    $(function () {
        var pricingTable = new PricingTable({
            editions: initialPageData.get('editions'),
            planOptions: initialPageData.get('planOptions'),
            currentPlan: initialPageData.get('currentPlan'),
        });

        // Applying bindings is a bit weird here, because we need logic in the modal,
        // but the only HTML ancestor the modal shares with the pricing table is <body>.
        $('#plans').koApplyBindings(pricingTable);
        $('#modal-downgrade').koApplyBindings(pricingTable);

        pricingTable.init();
    });
});
