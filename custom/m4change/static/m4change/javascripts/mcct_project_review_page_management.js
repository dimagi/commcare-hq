ignore = false;

var McctProjectReviewPageManagement = function (o) {
    'use strict';
    var self = this;

    // What's checked in the table below
    self.selected_forms = ko.observableArray();
    self.selected_cases = ko.observableArray();
    self.domain = o.domain;
    self.reject_reason = null;

    var updateRow = function () {
        return function(data) {
            for (var i = 0; i < self.selected_forms().length; i++) {
                var $checkbox = $('#mcct_project_review_page_management input[data-formid="' + self.selected_forms()[i] + '"].selected-element'),
                    $selectedRow,
                    $row = $checkbox.parent().parent();
                ignore = true;
                $checkbox.prop("checked", false).change();
                $selectedRow = $checkbox.parent().parent();
                $selectedRow.removeClass('active');
                $row.find('input[type="checkbox"].selected-element').parent().html(' <span class="label label-info">updated</span>');
            }
            self.clearSelection();
            ignore = false;
        };
    };

    self.updateSelection = function (data, event) {
        var $checkbox = $(event.currentTarget),
            caseID = $checkbox.data('caseid'),
            formID = $checkbox.data('formid'),
            ind = self.selected_forms().indexOf(formID),
            $selectedRow = $checkbox.parent().parent();

        if ($checkbox.is(':checked')) {
            $selectedRow.addClass('active');
            if (ind < 0) {
                self.selected_forms.push(formID);
            }
            self.selected_cases.push(caseID);
        } else if (!ignore) {
            $selectedRow.removeClass('active');
            if (ind >= 0) {
                self.selected_forms.splice(ind, 1);
            }
            self.selected_cases.splice(self.selected_cases().indexOf(caseID));
        }
    };

    self.clearSelection = function () {
        self.selected_forms.removeAll();
        self.selected_cases.removeAll();

    };

    self.updateStatus = function (status) {
        var data_to_send = [];

        for (var i = 0; i < self.selected_forms().length; i++) {
            data_to_send.push([
                self.selected_forms()[i],
                status,
                self.reject_reason
            ]);
        }
        $.ajax({
            url: '/a/' + self.domain + '/update_service_status/',
            type: 'post',
            data: { requested_forms: data_to_send },
            success: updateRow()
        });
    };
};

ko.bindingHandlers.mcctProjectReviewPage = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        $("#report_buttons").find("button, select").prop("disabled", value.length === 0);
    }
};

ko.bindingHandlers.grabUniqueDefault = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        var unique = _.unique(value);
        if (unique.length === 1) {
            $(element).val(unique[0]);
        }
        $(element).trigger('change');
    }
};
