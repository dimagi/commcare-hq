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
    var ENTERPRISE = 'enterprise';
    var ADVANCED = 'advanced';
    var PRO = 'pro';
    var STANDARD = 'standard';
    var COMMUNITY = 'community';

    var pricingTableModel = function (options) {
        assertProperties.assert(options, ['editions', 'currentEdition', 'isRenewal', 'startDateAfterMinimum',
            'isSubscriptionBelowMin', 'nextSubscriptionEdition', 'invoicing_contact']);

        'use strict';
        var self = {};

        self.currentEdition = options.currentEdition;
        self.isRenewal = options.isRenewal;
        self.startDateAfterMinimumSubscription = options.startDateAfterMinimum;
        self.subscriptionBelowMinimum = options.isSubscriptionBelowMin;
        self.nextSubscriptionEdition = options.nextSubscriptionEdition;
        self.invoicing_contact = options.invoicing_contact;
        self.editions = ko.observableArray(_.map(options.editions, function (edition) {
            return pricingTableEditionModel(edition, self.currentEdition);
        }));

        self.selected_edition = ko.observable(options.isRenewal ? options.currentEdition : false);
        self.isSubmitVisible = ko.computed(function () {
            if (self.isRenewal){
                return true;
            }
            return !! self.selected_edition() && !(self.selected_edition() === self.currentEdition);
        });
        self.selectCurrentPlan = function () {
            self.selected_edition(self.currentEdition);
        };
        self.isDowngrade = function (oldPlan, newPlan) {
            if (oldPlan === ENTERPRISE) {
                if (_.contains([ADVANCED, PRO, STANDARD, COMMUNITY], newPlan)) {
                    return true;
                }
            }
            else if (oldPlan === ADVANCED) {
                if (_.contains([PRO, STANDARD, COMMUNITY], newPlan)) {
                    return true;
                }
            }
            else if (oldPlan === PRO) {
                if (_.contains([STANDARD, COMMUNITY], newPlan)) {
                    return true;
                }
            } else if (oldPlan === STANDARD) {
                if (newPlan === COMMUNITY) {
                    return true;
                }
            }
            return false;
        };

        self.form = undefined;
        self.openMinimumSubscriptionModal = function (pricingTable, e) {
            self.form = $(e.currentTarget).closest("form");

            var mailto = "<a href=\'mailto:" + self.invoicing_contact + "'>billing-support@dimagi.com</a>";
            if (self.isDowngrade(self.currentEdition, self.selected_edition()) && self.subscriptionBelowMinimum) {
                var oldPlan = utils.capitalize(self.currentEdition);
                var newPlan = utils.capitalize(self.selected_edition());
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

        self.init = function () {
            $('.col-edition').click(function () {
                self.selected_edition($(this).data('edition'));
            });
        };

        return self;
    };

    var pricingTableEditionModel = function (data, currentEdition) {
        'use strict';
        var self = {};

        self.slug = ko.observable(data[0]);
        self.name = ko.observable(data[1].name);
        self.description = ko.observable(data[1].description);
        self.currentEdition = ko.observable(data[0] === currentEdition);
        self.notCurrentEdition = ko.computed(function (){
            return !self.currentEdition();
        });
        self.col_css = ko.computed(function () {
            return 'col-edition col-edition-' + self.slug();
        });
        self.isCommunity = ko.computed(function () {
            return self.slug() === COMMUNITY;
        });
        self.isStandard = ko.computed(function () {
            return self.slug() === STANDARD;
        });
        self.isPro = ko.computed(function () {
            return self.slug() === PRO;
        });
        self.isAdvanced = ko.computed(function () {
            return self.slug() === ADVANCED;
        });
        self.isEnterprise = ko.computed(function () {
            return self.slug() === ENTERPRISE;
        });

        return self;
    };

    $(function () {
        var pricingTable = pricingTableModel({
            editions: initialPageData.get('editions'),
            currentEdition: initialPageData.get('current_edition'),
            isRenewal: initialPageData.get('is_renewal'),
            startDateAfterMinimum: initialPageData.get('start_date_after_minimum_subscription'),
            isSubscriptionBelowMin: initialPageData.get('subscription_below_minimum'),
            nextSubscriptionEdition: initialPageData.get('next_subscription_edition'),
            invoicing_contact: initialPageData.get('invoicing_contact_email'),
        });

        // Applying bindings is a bit weird here, because we need logic in the modal,
        // but the only HTML ancestor the modal shares with the pricing table is <body>.
        $('#pricing-table').koApplyBindings(pricingTable);
        $('#modal-minimum-subscription').koApplyBindings(pricingTable);

        pricingTable.init();
    });
});
