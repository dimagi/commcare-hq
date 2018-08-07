hqDefine('accounting/js/pricing_table', function () {
    var pricingTableModel = function (editions, currentEdition, isRenewal, startDate, isSubscriptionBelowMin) {
        'use strict';
        var self = {};

        self.currentEdition = currentEdition;
        self.isRenewal = isRenewal;
        self.startDateAfterMinimumSubscription = startDate;
        self.subscriptionBelowMinimum = isSubscriptionBelowMin;
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
                if (newPlan === 'Enterprise' || newPlan === 'Pro' ||
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
            if (self.isDowngrade(oldPlan, newPlan) && self.subscriptionBelowMinimum) {
                var $modal = $("#modal-minimum-subscription");
                $modal.find('.modal-body')[0].innerHTML =
                    "CommCare bills on a monthly basis. If you cancel now, your subscription will downgrade to " +
                    "the " + newPlan + " plan on " + newStartDate + ". Would you still like to schedule this " +
                    "downgrade? You will still have full access to your " + oldPlan + " subscription until " +
                    newStartDate + ".";
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
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get,
            pricingTable = pricingTableModel(
                initial_page_data('editions'),
                initial_page_data('current_edition'),
                initial_page_data('is_renewal'),
                initial_page_data('start_date_after_minimum_subscription'),
                initial_page_data('subscription_below_minimum')
            );

        // Applying bindings is a bit weird here, because we need logic in the modal,
        // but the only HTML ancestor the modal shares with the pricing table is <body>.
        $('#pricing-table').koApplyBindings(pricingTable);
        $('#modal-minimum-subscription').koApplyBindings(pricingTable);

        pricingTable.init();
    }());
});
