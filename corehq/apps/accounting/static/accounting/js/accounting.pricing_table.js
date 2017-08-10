hqDefine('accounting/js/accounting.pricing_table.js', function () {
    var PricingTable = function (editions, current_edition, isRenewal) {
        'use strict';
        var self = this;

        self.currentEdition = current_edition;
        self.isRenewal = isRenewal;
        self.editions = ko.observableArray(_.map(editions, function (edition) {
            return new PricingTableEdition(edition, self.currentEdition);
        }));

        self.selected_edition = ko.observable(isRenewal ? current_edition : false);
        self.isSubmitVisible = ko.computed(function () {
            if (isRenewal){
                return true;
            }
            return !! self.selected_edition() && !(self.selected_edition() === self.currentEdition);
        });
        self.selectCurrentPlan = function () {
            self.selected_edition(self.currentEdition);
        };

        self.init = function () {
            $('.col-edition').click(function () {
                self.selected_edition($(this).data('edition'));
            });
        };
    };

    var PricingTableEdition = function (data, current_edition) {
        'use strict';
        var self = this;

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
    };

    $(function () {
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data.js').get,
            pricingTable = new PricingTable(
                initial_page_data('editions'),
                initial_page_data('current_edition'),
                initial_page_data('is_renewal')
            );
        $('#pricing-table').koApplyBindings(pricingTable);
        pricingTable.init();
    }());
});
