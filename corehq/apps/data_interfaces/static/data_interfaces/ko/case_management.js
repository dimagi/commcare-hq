var CaseManagement = function (owners, cases, receiverUrl, enddate) {
    'use strict';
    var self = this;
    self.selected_cases = ko.observableArray();
    self.selected_owners = ko.observableArray();
    self.available_owners = owners;
    self.cases = cases;
    self.receiverUrl = receiverUrl;
    self.updatedCase = null;

    enddate = new Date(enddate);
    var now = new Date();
    self.on_today = (enddate.toDateString() === now.toDateString());

    function getUsername(userid) {
        for (var i = 0; i < self.available_owners.length; i++) {
            if (self.available_owners[i].userid === userid) {
                return self.available_owners[i].username;
            }
        }
        return "Unknown";
    }

    var updateCaseRow = function (case_id, user_id) {
        return function(data, textStatus) {
            var $checkbox = $('#case-management input[data-caseid="' + case_id + '"].selected-commcare-case'),
                username = getUsername(user_id),
                date_message = (self.on_today) ? '<span title="0"></span>' : '<span class="label label-warning" title="0">Out of range of filter. Will not appear on page refresh.</span>';
            $checkbox.data('owner', user_id);
            var $row = $checkbox.parent().parent();
            $row.find('td:nth-child(4)').html(username + ' <span class="label label-info" title="' + username + '">updated</span>');
            $row.find('td:nth-child(5)').html('Today ' + date_message);
            $checkbox.attr("checked", false).change();
        };
    };

    self.updateCaseSelection = function (data, event) {
        var $checkbox = $(event.currentTarget),
            caseID = $checkbox.data('caseid'),
            ownerID = $checkbox.data('owner');
        var ind = self.selected_cases().indexOf(caseID);
        if ($checkbox.is(':checked')) {
            $checkbox.parent().parent().addClass('active');
            if (ind < 0) {
                self.selected_cases.push(caseID);
            }
            self.selected_owners.push(ownerID);
        } else {
            $checkbox.parent().parent().removeClass('active');
            if (ind >= 0) {
                self.selected_cases.splice(ind, 1);
            }
            self.selected_owners.splice(self.selected_owners().indexOf(ownerID), 1);
        }
    };

    self.updateCaseOwners = function (form, event) {
        var new_owner = $(form).find('select').val(),
            $modal = $('#caseManagementStatusModal');
        if (_.isEmpty(new_owner)) {
            $modal.find('.modal-body').text("Please select an owner");
            $modal.modal('show');
            return false;
        }

        for (var i = 0; i < self.selected_cases().length; i++) {
            var case_id = self.selected_cases()[i];
            var selected_case = self.cases[case_id],
                xform;
            selected_case.case_id = case_id;
            xform = casexml.CaseDelta.wrap(selected_case).asXFormInstance({
                user_id: new_owner
            }).serialize();

            $.ajax({
                url: self.receiverUrl,
                type: 'post',
                data: xform,
                success: updateCaseRow(selected_case.case_id, new_owner)
            });

        }
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

ko.bindingHandlers.caseReassignmentOwners = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        var unique_owners = _.unique(value);
        if (unique_owners.length === 1) {
            $(element).val(unique_owners[0]);
        } else {
            $(element).val("");
        }
    }
};