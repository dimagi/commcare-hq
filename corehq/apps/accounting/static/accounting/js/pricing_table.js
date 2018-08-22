hqDefine('accounting/js/pricing_table', function () {
    var pricingTableModel = function (editions, currentEdition, isRenewal, showMonthlyPricing) {
        'use strict';
        var self = {};

        self.currentEdition = currentEdition;
        self.isRenewal = isRenewal;
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

        self.showMonthlyPricing = ko.observable(showMonthlyPricing);

        self.form = undefined;
        self.openDowngradeModal = function(pricingTable, e) {
            var editionSlugs = _.map(self.editions(), function(e) { return e.slug(); });
            self.form = $(e.currentTarget).closest("form");
            if (editionSlugs.indexOf(self.selected_edition()) < editionSlugs.indexOf(self.currentEdition)) {
                var $modal = $("#modal-downgrade");
                $modal.modal('show');
            } else {
                self.form.submit();
            }
        };

        self.submitDowngrade = function(pricingTable, e) {
            var finish = function() {
                if (self.form) {
                    self.form.submit();
                }
            };

            var $button = $(e.currentTarget);
            $button.disableButton();
            $.ajax({
                method: "POST",
                url: hqImport('hqwebapp/js/initial_page_data').reverse('email_on_downgrade'),
                data: {
                    old_plan: self.currentEdition,
                    new_plan: self.selected_edition(),
                    note: $button.closest(".modal").find("textarea").val(),
                },
                success: finish,
                error: finish,
            });
        };

        self.updateIsAnnualPricing = function () {
            self.isAnnualPricing(true);
        };
        self.updateIsMonthlyPricing = function () {
            self.isAnnualPricing(true);
        };

        self.contactSales = function (pricingTable, e) {
            var $button = $(e.currentTarget);
            $button.disableButton();

            self.form = $(e.currentTarget).closest("form");
            self.currentEdition = self.currentEdition + " - annual pricing";
            self.form.submit();
        };

        self.init = function () {
            $('.col-edition').click(function () {
                self.selected_edition($(this).data('edition'));
            });
        };

        return self;
    };

    var pricingTableEditionModel = function (data, current_edition) {
        'use strict';
        var self = {};

        self.slug = ko.observable(data[0]);
        self.name = ko.observable(data[1].name);
        self.description = ko.observable(data[1].description);
        self.currentEdition = ko.observable(data[0] === current_edition);
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
                false
            );

        // Applying bindings is a bit weird here, because we need logic in the modal,
        // but the only HTML ancestor the modal shares with the pricing table is <body>.
        $('#plans').koApplyBindings(pricingTable);
        $('#modal-downgrade').koApplyBindings(pricingTable);

        pricingTable.init();
    }());
});
