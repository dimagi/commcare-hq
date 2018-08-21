hqDefine('accounting/js/pricing_table', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    var pricingTableModel = function (editions, currentEdition, isRenewal, startDate, isSubscriptionBelowMin,
    nextSubscription) {
        'use strict';
        var self = {};

        self.currentEdition = currentEdition;
        self.isRenewal = isRenewal;
        self.startDateAfterMinimumSubscription = startDate;
        self.subscriptionBelowMinimum = isSubscriptionBelowMin;
        self.nextSubscription = nextSubscription;
        self.editions = ko.observableArray(_.map(editions, function (edition) {
            return pricingTableEditionModel(edition, self.currentEdition);
        }));

        self.selected_edition = ko.observable(isRenewal ? currentEdition : false);
        self.isSubmitVisible = ko.computed(function () {
            if (isRenewal){
                return true;
            }
            return !! self.selected_edition() && !(self.selected_edition() === self.currentEdition);
        });
        self.selectCurrentPlan = function () {
            self.selected_edition(self.currentEdition);
        };
        self.capitalizeString = function (s) {
            return s.charAt(0).toUpperCase() + s.slice(1);
        };
        self.isDowngrade = function (oldPlan, newPlan) {
            if (oldPlan === 'Enterprise') {
                if (newPlan === 'Advanced' || newPlan === 'Pro' ||
                    newPlan === 'Standard' || newPlan === 'Community') {
                    return true;
                }
            }
            else if (oldPlan === 'Advanced') {
                if (newPlan === 'Pro' || newPlan === 'Standard' || newPlan === 'Community') {
                    return true;
                }
            } else if (oldPlan === 'Pro') {
                if (newPlan === 'Standard' || newPlan === 'Community') {
                    return true;
                }
            } else if (oldPlan === 'Standard') {
                if (newPlan === 'Community') {
                    return true;
                }
            }
            return false;
        };

        self.form = undefined;
        self.openMinimumSubscriptionModal = function (pricingTable, e) {
            self.form = $(e.currentTarget).closest("form");

            var oldPlan = self.capitalizeString(self.currentEdition);
            var newPlan = self.capitalizeString(self.selected_edition());
            var newStartDate = self.startDateAfterMinimumSubscription;
            var mailto = "<a href=\'mailto:billing-support@dimagi.com\'>billing-support@dimagi.com</a>";
            if (self.isDowngrade(oldPlan, newPlan) && self.subscriptionBelowMinimum) {
                var message = "All CommCare subscriptions require a 30 day minimum commitment.";
                if (self.nextSubscription) {
                    message += " Your current " + oldPlan + " Edition Plan subscription is scheduled to be " +
                        "downgraded to the " + self.nextSubscription + " Edition Plan on " + newStartDate + ". ";
                }
                message += " Continuing ahead will allow you to schedule your current " + oldPlan + " Edition " +
                    "Plan subscription to be downgraded to the " + newPlan + " Edition Plan on " + newStartDate +
                    ". If you have questions or if you would like to speak to us about your subscription, " +
                    "please reach out to " + mailto + ".";
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
            return self.slug() === 'community';
        });
        self.isStandard = ko.computed(function () {
            return self.slug() === 'standard';
        });
        self.isPro = ko.computed(function () {
            return self.slug() === 'pro';
        });
        self.isAdvanced = ko.computed(function () {
            return self.slug() === 'advanced';
        });
        self.isEnterprise = ko.computed(function () {
            return self.slug() === 'enterprise';
        });

        return self;
    };

    $(function () {
        var pricingTable = pricingTableModel(
            initialPageData.get('editions'),
            initialPageData.get('current_edition'),
            initialPageData.get('is_renewal'),
            initialPageData.get('start_date_after_minimum_subscription'),
            initialPageData.get('subscription_below_minimum'),
            initialPageData.get('next_subscription')
        );

        // Applying bindings is a bit weird here, because we need logic in the modal,
        // but the only HTML ancestor the modal shares with the pricing table is <body>.
        $('#pricing-table').koApplyBindings(pricingTable);
        $('#modal-minimum-subscription').koApplyBindings(pricingTable);

        pricingTable.init();
    });
});
