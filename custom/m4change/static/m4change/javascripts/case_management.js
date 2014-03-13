ignore = false;

var CaseManagement = function (o) {
    'use strict';
    var self = this;

    // What's checked in the table below
    self.selected_forms = ko.observableArray();
    self.selected_cases = ko.observableArray();
    self.selected_domains = ko.observableArray();
    self.domain = o.domain;

    var updateCaseRow = function () {
        return function(data) {
            for (var i = 0; i < self.selected_forms().length; i++) {
                var $checkbox = $('#case-management input[data-formid="' + self.selected_forms()[i] + '"].selected-commcare-case'),
                    $selectedRow,
                    $row = $checkbox.parent().parent();
                ignore = true;
                $checkbox.attr("checked", false).change();
                $selectedRow = $checkbox.parent().parent();
                $selectedRow.removeClass('active');
                $row.find('td:nth-child(7)').html(' <span class="label label-info">updated</span>');
            }
            self.clearSelection();
            ignore = false;
        }
    };

    self.updateCaseSelection = function (data, event) {
        var $checkbox = $(event.currentTarget),
            caseID = $checkbox.data('caseid'),
            formID = $checkbox.data('formid'),
            formDomain = $checkbox.data('domain');

        var ind = self.selected_forms().indexOf(formID),
            $selectedRow = $checkbox.parent().parent();

        if ($checkbox.is(':checked')) {
            $selectedRow.addClass('active');
            if (ind < 0) {
                self.selected_forms.push(formID);
            }
            self.selected_cases.push(caseID);
            self.selected_domains.push(formDomain);
        } else if (!ignore) {
            $selectedRow.removeClass('active');
            if (ind >= 0) {
                self.selected_forms.splice(ind, 1);
            }
            self.selected_cases.splice(self.selected_cases().indexOf(caseID));
            self.selected_domains.splice(self.selected_domains().indexOf(formDomain), 1);
        }
    };

    self.clearSelection = function () {
        self.selected_forms.removeAll();
        self.selected_cases.removeAll();
        self.selected_domains.removeAll();
    };

    self.updateStatus = function (status) {
        var data_to_send = [],
            stringArray = new Array();

        for (var i = 0; i < self.selected_forms().length; i++) {
            var form_id = self.selected_forms()[i],
                form_domain = self.selected_domains()[i];

            stringArray[0] = form_id;
            stringArray[1] = status;
            stringArray[2] = self.domain;
            data_to_send.push(stringArray);
        }
        $.ajax({
            url: '/a/' + self.domain + '/update_service_status/',
            type: 'post',
            data: { requested_forms: data_to_send },
            success: updateCaseRow()
        });
    };

    self.updateCaseOwnersReview = function () {
        self.updateStatus("approved");
    };

     self.updateCaseOwnersCancel = function () {
         self.updateStatus("canceled");
    };

     self.updateCaseOwnersReject = function () {
         self.updateStatus("rejected");
    };
};

ko.bindingHandlers.caseReassignmentForm = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        if (value.length > 0) {
            $(element).slideDown();
        } else {
            $(element).slideUp();
        }
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

ko.bindingHandlers.comboboxOptions = {
    init: function (element, _, allBindingsAccessor) {
        if ($(element).data('combobox')) {
            return;
        }
        $(element).combobox({
            placeholder: allBindingsAccessor()['comboboxCaption']
        });

        var combobox = $(element).data('combobox');
        combobox.$button.click(function () {
            if (combobox.$element.val() === '') {
                $(element).val(null).change();
            }
        });
        $(element).change(function () {
            if ($(this).val() === '') {
                combobox.$element.val('');
            }
        });
    },
    update: function (element, valueAccessor, allBindingsAccessor) {
        ko.bindingHandlers.options.update(element, valueAccessor, allBindingsAccessor);
        var value = ko.utils.unwrapObservable(valueAccessor());
        if (!$(element).find('[value=""]').size()) {
            $(element).append('<option value=""></option>');
        }
        $(element).data('combobox').refresh();
    }
};
