hqDefine('accounting/js/confirm_plan', function () {
    var confirmPlanModel = function (isUpgrade, nextInvoiceDate, currentPlan, isDowngradeBeforeMinimum,
                                     currentSubscriptionEndDate) {
        debugger;
        'use strict';
        var self = {};
        self.isUpgrade = isUpgrade;
        self.nextInvoiceDate = nextInvoiceDate;
        self.currentPlan = currentPlan;
        self.isDowngradeBeforeMinimum = isDowngradeBeforeMinimum;
        self.currentSubscriptionEndDate = currentSubscriptionEndDate;

        self.openDowngradeModal = function() {
            debugger;
            // var editionSlugs = _.map(self.editions(), function(e) { return e.slug(); });
            // self.form = $(e.currentTarget).closest("form");
            // if (editionSlugs.indexOf(self.selected_edition()) < editionSlugs.indexOf(self.currentEdition)) {
            //     var $modal = $("#modal-downgrade");
            //     $modal.modal('show');
            // } else {
            //     self.form.submit();
            // }
        };
        self.submitDowngrade = function() {
            debugger;
            // var $button = $(e.currentTarget);
            // $button.disableButton();
            // $.ajax({
            //     method: "POST",
            //     url: hqImport('hqwebapp/js/initial_page_data').reverse('email_on_downgrade'),
            //     data: {
            //         old_plan: self.currentEdition,
            //         new_plan: self.selected_edition(),
            //         note: $button.closest(".modal").find("textarea").val(),
            //     },
            //     success: finish,
            //     error: finish,
            // });
        };

        return self;
    };


    $(function () {
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get;
        confirmPlanModel = confirmPlanModel(
            initial_page_data('is_upgrade'),
            initial_page_data('next_invoice_date'),
            initial_page_data('current_plan'),
            initial_page_data('is_downgrade_before_minimum'),
            initial_page_data('current_subscription_end_date')
        );
        $('#modal-downgrade').koApplyBindings(confirmPlanModel);
    }());
});
