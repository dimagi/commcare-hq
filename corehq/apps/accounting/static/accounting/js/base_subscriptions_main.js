
import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import widgets from "accounting/js/widgets";
import "accounting/js/credits_tab";
import "jquery-ui/ui/widgets/datepicker";
import "jquery-ui-built-themes/redmond/jquery-ui.min.css";

var subscriptionInfoHandlerModel = function () {
    var self = {};

    var asyncSelect2Handler = widgets.asyncSelect2Handler;
    self.domain = asyncSelect2Handler('domain');
    self.account = asyncSelect2Handler('account');
    self.plan_version = asyncSelect2Handler('plan_version');

    self.init = function () {
        self.domain.init();
        self.account.init();
        self.plan_version.init();
        self.plan_version.getAdditionalData = function () {
            return {
                'edition': $('#id_plan_edition').val(),
                'visibility': $('#id_plan_visibility').val(),
                'most_recent_version': $('#id_most_recent_version').val(),
            };
        };
        $(function () {
            var deselectPlanVersion = function () {
                var $planVer = $('#id_plan_version');
                $planVer.val('');
                $planVer.select2('val', '');
            };
            $('#id_plan_edition').change(deselectPlanVersion);
            $('#id_plan_visibility').change(deselectPlanVersion);
            $('#id_most_recent_version').change(deselectPlanVersion);
        });
    };

    return self;
};

var invoiceModel = function () {
    var self = {};
    var invoice = $('#id_do_not_invoice').prop("checked");
    self.noInvoice = ko.observable(invoice);
    var skipAutoDowngrade = $('#id_skip_auto_downgrade').prop("checked");
    self.skipAutoDowngrade = ko.observable(skipAutoDowngrade);
    return self;
};

$(function () {
    $("#id_start_date").datepicker({
        dateFormat: "yy-mm-dd",
    });
    $("#id_end_date").datepicker({
        dateFormat: "yy-mm-dd",
    });
    $("#id_new_date_end").datepicker({
        dateFormat: "yy-mm-dd",
    });

    var subscriptionInfoHandler = subscriptionInfoHandlerModel();
    subscriptionInfoHandler.init();

    var invoice = invoiceModel();
    // fieldset is not unique enough a css identifier
    // historically this has taken the first one without checking
    // todo: use a more specific identifier to make less brittle
    if ($('fieldset').length) {
        $('fieldset').first().koApplyBindings(invoice);
    }
});
