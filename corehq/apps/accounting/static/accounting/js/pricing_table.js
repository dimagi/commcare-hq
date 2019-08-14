hqDefine('accounting/js/pricing_table', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/main',
    "hqwebapp/js/assert_properties",
], function (
    $,
    ko,
    _,
    initialPageData,
    utils,
    assertProperties
) {
    var PricingTable = function (options) {
        assertProperties.assert(options, [
            'editions',
            'planOptions',
            'currentPlan',
            'isRenewal',
            'startDateAfterMinimum',
            'isSubscriptionBelowMin',
            'nextSubscriptionEdition',
            'invoicingContact',
        ]);

        'use strict';
        var self = {};

        self.currentPlan = ko.observable(options.currentPlan);
        self.editions = options.editions;
        self.isRenewal = options.isRenewal;
        self.startDateAfterMinimumSubscription = options.startDateAfterMinimum;
        self.subscriptionBelowMinimum = options.isSubscriptionBelowMin;
        self.nextSubscriptionEdition = options.nextSubscriptionEdition;
        self.invoicingContact = options.invoicingContact;

        self.selectedPlan = ko.observable(options.currentPlan);

        self.showMonthlyPricing = ko.observable(false);

        self.refundCss = ko.computed(function () {
            if (self.showMonthlyPricing()) {
                return "hide-refund";
            }
        });

        self.isSubmitVisible = ko.computed(function () {
            return !! self.selectedPlan() && !(self.selectedPlan() === self.currentPlan());
        });

        self.isCurrentPlanCommunity = ko.observable(options.currentPlan === 'community');

        self.selectCommunityPlan = function () {
            self.selectedPlan('community');
        };
        self.isDowngrade = function () {
            return self.editions.indexOf(self.selectedPlan()) < self.editions.indexOf(self.currentPlan());
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

        self.form = undefined;
        self.openMinimumSubscriptionModal = function (pricingTable, e) {
            self.form = $(e.currentTarget).closest("form");

            var mailto = "<a href='mailto:" + self.invoicingContact + "'>" + self.invoicingContact + "</a>";
            if (self.isDowngrade() && self.subscriptionBelowMinimum) {
                var oldPlan = utils.capitalize(self.currentPlan());
                var newPlan = utils.capitalize(self.selectedPlan());
                var newStartDate = "<strong>" + self.startDateAfterMinimumSubscription + "</strong>";

                var message = "";
                if (self.nextSubscriptionEdition) {
                    message = _.template(gettext(
                        "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                        "<p>Your current <%= oldPlan %> Edition Plan subscription is scheduled to be downgraded " +
                        "to the <%= nextSubscription %> Edition Plan on <%= date %>.</p>" +
                        "<p>Continuing ahead will allow you to schedule your current <%= oldPlan %> Edition " +
                        "Plan subscription to be downgraded to the <%= newPlan %> Edition Plan " +
                        "on <%= date %>.</p>" +
                        "<p>If you have questions or if you would like to speak to us about your subscription, " +
                        "please reach out to <%= email %>.</p>"
                    ))({
                        oldPlan: oldPlan,
                        nextSubscription: self.nextSubscriptionEdition,
                        date: newStartDate,
                        newPlan: newPlan,
                        email: mailto,
                    });
                } else {
                    message = _.template(gettext(
                        "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                        "<p>Continuing ahead will allow you to schedule your current <%= oldPlan %> Edition " +
                        "Plan subscription to be downgraded to the <%= newPlan %> Edition Plan " +
                        "on <%= date %>.</p>" +
                        "If you have questions or if you would like to speak to us about your subscription, " +
                        "please reach out to <%= email %>."
                    ))({
                        oldPlan: oldPlan,
                        date: newStartDate,
                        newPlan: newPlan,
                        email: mailto,
                    });
                }
                var $modal = $("#modal-minimum-subscription");
                $modal.find('.modal-body')[0].innerHTML = message;
                $modal.modal('show');
            } else {
                self.form.submit();
            }
        };

        self.submitDowngradeForm = function () {
            if (self.form) {
                self.form.submit();
            }
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

        self.pricingTypeText = ko.computed(function () {
            if (parent.showMonthlyPricing()) {
                return django.gettext("Billed Monthly");
            }
            return django.gettext("Billed Annually");
        });

        self.pricingTypeCssClass = ko.computed(function () {
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
            isRenewal: initialPageData.get('is_renewal'),
            startDateAfterMinimum: initialPageData.get('start_date_after_minimum_subscription'),
            isSubscriptionBelowMin: initialPageData.get('subscription_below_minimum'),
            nextSubscriptionEdition: initialPageData.get('next_subscription_edition'),
            invoicingContact: initialPageData.get('invoicing_contact_email'),
        });

        // Applying bindings is a bit weird here, because we need logic in the modal,
        // but the only HTML ancestor the modal shares with the pricing table is <body>.
        $('#plans').koApplyBindings(pricingTable);
        $('#modal-minimum-subscription').koApplyBindings(pricingTable);

        pricingTable.init();
    });
});
