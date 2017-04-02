/* globals _, ko, casexml, $ */

var CaseManagement = function (o) {
    'use strict';
    var self = this;

    self.receiverUrl = o.receiverUrl;
    self.updatedCase = null;
    self.webUserID = o.webUserID;
    self.webUserName = o.webUserName;
    self.form_name = o.form_name;

    self.owners_by_type = {
        'user': o.users
    };
    if (o.groups) {
        self.owners_by_type.group = o.groups;
    }
    self.owner_types = _.keys(self.owners_by_type);
    self.is_only_user_reassign = self.owner_types.length === 1;

    // What's checked in the table below
    self.selected_cases = ko.observableArray();
    self.selected_owners = ko.observableArray();
    self.selected_owner_types = ko.observableArray();

    // What we're assigning to
    self.new_owner_type = ko.observable();
    self.new_owner = ko.observable();

    // What's in the select box
    self.available_owners = ko.computed(function () {
        var owner_type = self.new_owner_type() || 'user';
        return self.owners_by_type[owner_type];
    });

    self.is_submit_enabled = ko.computed(function () {
        return !!self.new_owner();
    }, self);

    self.should_show_owners = ko.observable(true);

    var enddate = new Date(o.enddate),
        now = new Date();
    self.on_today = (enddate.toDateString() === now.toDateString());

    var getOwnerName = function (owner, owner_list) {
        for (var i = 0; i < owner_list.length; i++) {
            if (owner_list[i].ownerid === owner) {
                return owner_list[i].name;
            }
        }
        return "Unknown";
    };

    var updateCaseRow = function (case_id, owner_id, owner_type) {
        return function(data, textStatus) {
            var $checkbox = $('#case-management input[data-caseid="' + case_id + '"].selected-commcare-case'),
                username = getOwnerName(owner_id, self.owners_by_type[owner_type]),
                date_message = (self.on_today) ? '<span title="0"></span>' :
                                '<span class="label label-warning" title="0">Out of range of filter. Will ' +
                                    'not appear on page refresh.</span>';
            $checkbox.data('owner', owner_id);
            $checkbox.data('ownertype', owner_type);

            var $row = $checkbox.closest("tr"),
                group_label = '';

            if (owner_type === 'group') {
                group_label = ' <span class="label label-inverse" title="'+username+'">group</span>';
            }

            $row.find('td:nth-child(4)').html(username +group_label+' <span class="label label-info" title="' + username +
                                            '">updated</span>');
            $row.find('td:nth-child(5)').html('Today ' + date_message);
            $checkbox.prop("checked", false).change();
        };
    };

    self.changeNewOwnerType = function () {
        self.new_owner_type($('#reassign_owner_type_select').val());
    };

    self.changeNewOwner = function () {
        self.new_owner($('#reassign_owner_select').val());
    };

    self.updateCaseSelection = function (data, event) {
        var $checkbox = $(event.currentTarget),
            caseID = $checkbox.data('caseid'),
            ownerID = $checkbox.data('owner'),
            ownerType = $checkbox.data('ownertype');

        var ind = self.selected_cases().indexOf(caseID),
            $selectedRow = $checkbox.closest('tr');

        if ($checkbox.is(':checked')) {
            $selectedRow.addClass('active');
            if (ind < 0) {
                self.selected_cases.push(caseID);
            }
            self.selected_owner_types.push(ownerType);
            self.selected_owners.push(ownerID);
        } else {
            $selectedRow.removeClass('active');
            if (ind >= 0) {
                self.selected_cases.splice(ind, 1);
            }
            self.selected_owner_types.splice(self.selected_owner_types().indexOf(ownerType), 1);
            self.selected_owners.splice(self.selected_owners().indexOf(ownerID), 1);
        }
    };

    self.clearCaseSelection = function () {
        self.selected_cases.removeAll();
    };

    self.updateCaseOwners = function (form) {
        var new_owner = $(form).find('#reassign_owner_select').val(),
            owner_type = $(form).find('#reassign_owner_type_select').val(),
            $modal = $('#caseManagementStatusModal');

        if (_.isEmpty(new_owner)) {
            $modal.find('.modal-body').text("Please select an owner");
            $modal.modal('show');
        } else {
            $(form).find("[type='submit']").disableButton();
            for (var i = 0; i < self.selected_cases().length; i++) {
                var case_id = self.selected_cases()[i],
                    xform;
                xform = casexml.CaseDelta.wrap({
                    case_id: case_id,
                    properties: {owner_id: new_owner}
                }).asXFormInstance({
                    user_id: self.webUserID,
                    username: self.webUserName,
                    form_name: self.form_name
                }).serialize();

                $.ajax({
                    url: self.receiverUrl,
                    type: 'post',
                    data: xform,
                    success: updateCaseRow(case_id, new_owner, owner_type)
                });

            }
        }
    };
};

ko.bindingHandlers.caseReassignmentForm = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        var $element = $(element);
        if (value.length > 0) {
            $element.slideDown();
        } else {
            $element.find("[type='submit']").enableButton();
            $element.slideUp();
        }
    }
};

ko.bindingHandlers.grabUniqueDefault = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        var unique = _.unique(value);
        if (unique.length === 1) {
            $(element).val(unique[0]);
        } else {
            // okay, so ideally this should deselect the select and combobox. unfortunately I think this requires
            // some reworking of the combobox, so just have it set at whatever value is set by default for now is fine.
            // bleh.
        }
        $(element).trigger('change');
    }
};
