
import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import utils from "hqwebapp/js/bootstrap3/main";
import assertProperties from "hqwebapp/js/assert_properties";

const PricingTable = function (options) {
    assertProperties.assert(options, [
        'editions',
        'planOptions',
        'currentEdition',
        'currentIsAnnualPlan',
        'isRenewal',
        'startDateAfterMinimum',
        'isSubscriptionBelowMin',
        'nextSubscriptionEdition',
        'invoicingContact',
        'isPriceDiscounted',
        'currentPrice',
    ]);

    const self = {};

    self.currentEdition = options.currentEdition;
    self.nextSubscription = options.nextSubscriptionEdition;
    self.startDateAfterMinimumSubscription = options.startDateAfterMinimum;
    self.currentPrice = options.currentPrice;
    self.isPriceDiscounted = options.isPriceDiscounted;
    self.currentIsAnnualPlan = options.currentIsAnnualPlan;
    self.editions = options.editions;
    self.isRenewal = options.isRenewal;
    self.subscriptionBelowMinimum = options.isSubscriptionBelowMin;
    self.invoicingContact = options.invoicingContact;

    self.isCurrentPlanFreeEdition = options.currentEdition === 'free';
    self.isCurrentPlanPaused = options.currentEdition === 'paused';

    self.isNextPlanPaused = self.nextSubscription === 'Paused';
    self.isNextPlanDowngrade = self.nextSubscription && !self.isNextPlanPaused;

    self.oSelectedEdition = ko.observable(options.currentEdition);
    self.oShowAnnualPricing = ko.observable(options.currentIsAnnualPlan);

    self.oIsSubmitDisabled = ko.computed(function () {
        const isSubscribablePlan = !!self.oSelectedEdition() && !['free', 'enterprise'].includes(self.oSelectedEdition());
        const isSamePaySchedule = self.currentIsAnnualPlan === self.oShowAnnualPricing();
        const isCurrentPlan = self.oSelectedEdition() === self.currentEdition && !self.nextSubscription && isSamePaySchedule;
        const isNextPlan = self.nextSubscription && self.oSelectedEdition() === self.nextSubscription.toLowerCase();
        return !isSubscribablePlan || isNextPlan || isCurrentPlan;
    });

    self.oPausedCss = ko.computed(function () {
        if (self.oSelectedEdition() === 'paused') {
            return "selected-plan";
        }
        return "";
    });

    self.oPlanOptions = ko.observableArray(_.map(options.planOptions, function (opt) {
        return new PlanOption(opt, self);
    }));

    self.selectPausedPlan = function () {
        self.oSelectedEdition('paused');
    };

    self.isDowngrade = function () {
        return self.editions.indexOf(self.oSelectedEdition()) < self.editions.indexOf(self.currentEdition);
    };

    self.form = undefined;
    self.openMinimumSubscriptionModal = function (pricingTable, e) {
        self.form = $(e.currentTarget).closest("form");

        const invoicingContact = _.escape(self.invoicingContact);
        if (self.isDowngrade() && self.subscriptionBelowMinimum) {
            const oldPlan = utils.capitalize(self.currentEdition);
            const newPlan = utils.capitalize(self.oSelectedEdition());
            const newStartDate = self.startDateAfterMinimumSubscription;

            let message = "",
                title = gettext("Downgrading?");
            if (self.oSelectedEdition() === 'paused') {
                title = gettext("Pausing Subscription?");
                message = _.template(gettext(
                    "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                    "<p>Continuing ahead will allow you to schedule your current <%- oldPlan %> " +
                    "Edition Plan subscription to be paused on <strong> <%- date %> </strong></p>" +
                    "<p>If you have questions or if you would like to speak to us about your subscription, " +
                    "please reach out to <a href='mailto: <%- invoicingContact %>'><%- invoicingContact %></a>.</p>",
                ))({
                    date: newStartDate,
                    newPlan: newPlan,
                    oldPlan: oldPlan,
                    invoicingContact: invoicingContact,
                });
            } else if (self.isNextPlanPaused) {
                message = _.template(gettext(
                    "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                    "<p>Your current <%- oldPlan %> Edition Plan subscription is scheduled to be paused " +
                    "on <strong> <%- date %> </strong></p>" +
                    "<p>Continuing ahead will allow you to schedule your current <%- oldPlan %> Edition " +
                    "Plan subscription to be downgraded to the <%- newPlan %> Edition Plan " +
                    "on <strong> <%- date %> </strong></p>" +
                    "<p>If you have questions or if you would like to speak to us about your subscription, " +
                    "please reach out to <a href='mailto: <%- invoicingContact %>'><%- invoicingContact %></a>.</p>",
                ))({
                    oldPlan: oldPlan,
                    date: newStartDate,
                    newPlan: newPlan,
                    invoicingContact: invoicingContact,
                });
            } else if (self.isNextPlanDowngrade) {
                message = _.template(gettext(
                    "<p>All CommCare subscriptions require a 30 day minimum commitment.</p>" +
                    "<p>Your current <%- oldPlan %> Edition Plan subscription is scheduled to be downgraded " +
                    "to the <%- nextSubscription %> Edition Plan on <strong> <%- date %> </strong></p>" +
                    "<p>Continuing ahead will allow you to schedule your current <%- oldPlan %> Edition " +
                    "Plan subscription to be downgraded to the <%- newPlan %> Edition Plan " +
                    "on <strong> <%- date %> </strong></p>" +
                    "<p>If you have questions or if you would like to speak to us about your subscription, " +
                    "please reach out to <a href='mailto: <%- invoicingContact %>'><%- invoicingContact %></a>.</p>",
                ))({
                    oldPlan: oldPlan,
                    nextSubscription: self.nextSubscription,
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
                    "please reach out to <a href='mailto: <%- invoicingContact %>'><%- invoicingContact %></a>.",
                ))({
                    oldPlan: oldPlan,
                    date: newStartDate,
                    newPlan: newPlan,
                    invoicingContact: invoicingContact,
                });
            }
            const $modal = $("#modal-minimum-subscription");
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

    self.init = function () {
        self.form = $("#select-plan-form");
    };

    return self;
};

const planDisplayName = function (name) {
    const plans = {
        'Free': gettext('Free edition'),
        'Standard': 'Standard',
        'Pro': 'Pro',
        'Advanced': 'Advanced',
    };
    return plans[name] || '';
};

const PlanOption = function (data, parent) {
    const self = this;

    self.name = planDisplayName(data.name);
    self.slug = data.name.toLowerCase();

    self.monthlyPrice = data.monthly_price;
    self.annualPrice = data.annual_price;
    self.description = data.description;

    self.isFreeEdition = self.slug === 'free';
    self.isCurrentEdition = self.slug === parent.currentEdition;

    self.nextPlan = parent.nextSubscription;
    self.nextDate = parent.startDateAfterMinimumSubscription;

    self.showPausedNotice = parent.isNextPlanPaused && self.isCurrentEdition;
    self.showDowngradeNotice = self.isCurrentEdition && parent.isNextPlanDowngrade;

    self.oIsSelectedPlan = ko.computed(function () {
        return self.slug === parent.oSelectedEdition();
    });

    self.oCssClass = ko.computed(function () {
        let cssClass = "tile-" + self.slug;
        if (self.oIsSelectedPlan()) {
            cssClass = cssClass + " selected-plan";
        }
        return cssClass;
    });

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
        return self.isCurrentEdition && parent.isPriceDiscounted && !parent.oShowAnnualPricing();
    });

    self.oDisplayPrice = ko.computed(function () {
        if (self.oDisplayDiscountNotice()) {
            return parent.currentPrice;
        }
        if (parent.oShowAnnualPricing()) {
            return self.annualPrice;
        }
        return self.monthlyPrice;
    });

    self.selectPlan = function () {
        parent.oSelectedEdition(self.slug);
    };
};


$(function () {
    const pricingTable = new PricingTable({
        editions: initialPageData.get('editions'),
        planOptions: initialPageData.get('planOptions'),
        currentEdition: initialPageData.get('currentEdition'),
        currentIsAnnualPlan: initialPageData.get('currentIsAnnualPlan'),
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
