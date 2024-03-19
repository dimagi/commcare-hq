"use strict";
hqDefine('accounting/js/pricing_table', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/main',
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
            'isPriceDiscounted',
            'currentPrice',
        ]);

        var self = {};

        self.oCurrentPlan = ko.observable(options.currentPlan);
        self.oNextSubscription = ko.observable(options.nextSubscriptionEdition);
        self.oStartDateAfterMinimumSubscription = ko.observable(options.startDateAfterMinimum);
        self.oCurrentPrice = ko.observable(options.currentPrice);
        self.oIsPriceDiscounted = ko.observable(options.isPriceDiscounted);
        self.editions = options.editions;
        self.isRenewal = options.isRenewal;
        self.subscriptionBelowMinimum = options.isSubscriptionBelowMin;
        self.invoicingContact = options.invoicingContact;

        self.oSelectedPlan = ko.observable(options.currentPlan);

        self.oShowAnnualPricing = ko.observable(false);

        self.oRefundCss = ko.computed(function () {
            if (self.oShowAnnualPricing()) {
                return "show-refund";
            }
        });

        self.oIsSubmitDisabled = ko.computed(function () {
            var isCurrentPlan = self.oSelectedPlan() === self.oCurrentPlan() && !self.oNextSubscription(),
                isNextPlan = self.oNextSubscription() && self.oSelectedPlan() === self.oNextSubscription().toLowerCase();
            return !self.oSelectedPlan() || isNextPlan || isCurrentPlan;
        });

        self.oIsCurrentPlanCommunity = ko.observable(options.currentPlan === 'community');
        self.oIsCurrentPlanPaused = ko.observable(options.currentPlan === 'paused');

        self.oIsNextPlanPaused = ko.computed(function () {
            return self.oNextSubscription() === 'Paused';
        });

        self.oIsNextPlanDowngrade = ko.computed(function () {
            return self.oNextSubscription() && !self.oIsNextPlanPaused();
        });

        self.selectPausedPlan = function () {
            self.oSelectedPlan('paused');
        };
        self.isDowngrade = function () {
            return self.editions.indexOf(self.oSelectedPlan()) < self.editions.indexOf(self.oCurrentPlan());
        };

        self.oPausedCss = ko.computed(function () {
            if (self.oSelectedPlan() === 'paused') {
                return "selected-plan";
            }
            return "";
        });

        self.oPlanOptions = ko.observableArray(_.map(options.planOptions, function (opt) {
            return new PlanOption(opt, self);
        }));

        self.oShowNext = ko.computed(function () {
            return !self.oShowAnnualPricing();
        });

        self.form = undefined;
        self.openMinimumSubscriptionModal = function (pricingTable, e) {
            self.form = $(e.currentTarget).closest("form");

            var invoicingContact = _.escape(self.invoicingContact);
            if (self.isDowngrade() && self.subscriptionBelowMinimum) {
                var oldPlan = utils.capitalize(self.oCurrentPlan());
                var newPlan = utils.capitalize(self.oSelectedPlan());
                var newStartDate = self.oStartDateAfterMinimumSubscription();

                var message = "",
                    title = gettext("Downgrading?");
                if (self.oSelectedPlan() === 'paused') {
                    title = gettext("Pausing Subscription?");
                    message = _.template(gettext(
                        "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                        "<p>Continuing ahead will allow you to schedule your current <%- oldPlan %> " +
                        "Edition Plan subscription to be paused on <strong> <%- date %> </strong></p>" +
                        "<p>If you have questions or if you would like to speak to us about your subscription, " +
                        "please reach out to <a href='mailto: <%- invoicingContact %>'><%- invoicingContact %></a>.</p>"
                    ))({
                        date: newStartDate,
                        newPlan: newPlan,
                        oldPlan: oldPlan,
                        invoicingContact: invoicingContact,
                    });
                } else if (self.oIsNextPlanPaused()) {
                    message = _.template(gettext(
                        "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                        "<p>Your current <%- oldPlan %> Edition Plan subscription is scheduled to be paused " +
                        "on <strong> <%- date %> </strong></p>" +
                        "<p>Continuing ahead will allow you to schedule your current <%- oldPlan %> Edition " +
                        "Plan subscription to be downgraded to the <%- newPlan %> Edition Plan " +
                        "on <strong> <%- date %> </strong></p>" +
                        "<p>If you have questions or if you would like to speak to us about your subscription, " +
                        "please reach out to <a href='mailto: <%- invoicingContact %>'><%- invoicingContact %></a>.</p>"
                    ))({
                        oldPlan: oldPlan,
                        date: newStartDate,
                        newPlan: newPlan,
                        invoicingContact: invoicingContact,
                    });
                } else if (self.oIsNextPlanDowngrade()) {
                    message = _.template(gettext(
                        "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                        "<p>Your current <%- oldPlan %> Edition Plan subscription is scheduled to be downgraded " +
                        "to the <%- nextSubscription %> Edition Plan on <strong> <%- date %> </strong></p>" +
                        "<p>Continuing ahead will allow you to schedule your current <%- oldPlan %> Edition " +
                        "Plan subscription to be downgraded to the <%- newPlan %> Edition Plan " +
                        "on <strong> <%- date %> </strong></p>" +
                        "<p>If you have questions or if you would like to speak to us about your subscription, " +
                        "please reach out to <a href='mailto: <%- invoicingContact %>'><%- invoicingContact %></a>.</p>"
                    ))({
                        oldPlan: oldPlan,
                        nextSubscription: self.oNextSubscription(),
                        date: newStartDate,
                        newPlan: newPlan,
                        invoicingContact: invoicingContact,
                    });
                } else {
                    message = _.template(gettext(
                        "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                        "<p>Continuing ahead will allow you to schedule your current <%- oldPlan %> Edition " +
                        "Plan subscription to be downgraded to the <%- newPlan %> Edition Plan " +
                        "on <strong> <%- date %> </strong></p>" +
                        "If you have questions or if you would like to speak to us about your subscription, " +
                        "please reach out to <a href='mailto: <%- invoicingContact %>'><%- invoicingContact %></a>."
                    ))({
                        oldPlan: oldPlan,
                        date: newStartDate,
                        newPlan: newPlan,
                        invoicingContact: invoicingContact,
                    });
                }
                var $modal = $("#modal-minimum-subscription");
                $modal.find('.modal-body')[0].innerHTML = message;
                $modal.find('.modal-title')[0].innerHTML = title;
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
            self.oCurrentPlan(self.oCurrentPlan() + " - annual pricing");
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

        self.oName = ko.observable(data.name);
        self.oSlug = ko.observable(data.name.toLowerCase());

        self.oMonthlyPrice = ko.observable(data.monthly_price);
        self.oAnnualPrice = ko.observable(data.annual_price);
        self.oDescription = ko.observable(data.description);

        self.oIsCurrentPlan = ko.computed(function () {
            return self.oSlug() === parent.oCurrentPlan();
        });

        self.oIsSelectedPlan = ko.computed(function () {
            return self.oSlug() === parent.oSelectedPlan();
        });

        self.oShowDowngradeNotice = ko.computed(function () {
            return self.oIsCurrentPlan() && parent.oIsNextPlanDowngrade();
        });

        self.oNextPlan = ko.computed(function () {
            return parent.oNextSubscription();
        });

        self.oNextDate = ko.computed(function () {
            return parent.oStartDateAfterMinimumSubscription();
        });

        self.oShowPausedNotice = ko.computed(function () {
            return parent.oIsNextPlanPaused() && self.oIsCurrentPlan();
        });

        self.oCssClass = ko.computed(function () {
            var cssClass = "tile-" + self.oSlug();
            if (self.oIsSelectedPlan()) {
                cssClass = cssClass + " selected-plan";
            }
            return cssClass;
        });

        self.selectPlan = function () {
            parent.oSelectedPlan(self.oSlug());
        };

        self.oPricingTypeText = ko.computed(function () {
            if (parent.oShowAnnualPricing()) {
                return gettext("Billed Annually");
            }
            return gettext("Billed Monthly");
        });

        self.oPricingTypeCssClass = ko.computed(function () {
            if (parent.oShowAnnualPricing()) {
                return 'pricing-type-annual';
            }
            return 'pricing-type-monthly';
        });

        self.oDisplayDiscountNotice = ko.computed(function () {
            return self.oIsCurrentPlan() && parent.oIsPriceDiscounted() && !parent.oShowAnnualPricing();
        });

        self.oDisplayPrice = ko.computed(function () {
            if (self.oDisplayDiscountNotice()) {
                return parent.oCurrentPrice();
            }
            if (parent.oShowAnnualPricing()) {
                return self.oAnnualPrice();
            }
            return self.oMonthlyPrice();
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
            currentPrice: initialPageData.get('current_price'),
            isPriceDiscounted: initialPageData.get('is_price_discounted'),
        });

        // Applying bindings is a bit weird here, because we need logic in the modal,
        // but the only HTML ancestor the modal shares with the pricing table is <body>.
        $('#plans').koApplyBindings(pricingTable);
        $('#modal-minimum-subscription').koApplyBindings(pricingTable);

        pricingTable.init();
    });
});
