var CaseManagement = function (o) {
    'use strict';
    var self = this;
    self.selected_cases = ko.observableArray();
    self.selected_owners = ko.observableArray();
    self.available_owners = ko.observableArray();

    self.owner_types = ["user", "group"];
    self.selected_owner_types = ko.observableArray();
    self.should_show_owners = ko.observable(true);
    self.enableSubmit = ko.observable(false);

    self.users = o.users;
    self.groups = o.groups;
    self.receiverUrl = o.receiverUrl;
    self.updatedCase = null;
    self.webUserID = o.webUserID;

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
                username = getOwnerName(owner_id, (owner_type === self.owner_types[0]) ? self.users : self.groups),
                date_message = (self.on_today) ? '<span title="0"></span>' :
                                '<span class="label label-warning" title="0">Out of range of filter. Will ' +
                                    'not appear on page refresh.</span>';
            $checkbox.data('owner', owner_id);
            $checkbox.data('ownertype', owner_type);
            var $row = $checkbox.parent().parent(),
                group_label = '';
            if (owner_type == self.owner_types[1])
                group_label = ' <span class="label label-inverse" title="'+username+'">group</span>';
            $row.find('td:nth-child(4)').html(username +group_label+' <span class="label label-info" title="' + username +
                                            '">updated</span>');
            $row.find('td:nth-child(5)').html('Today ' + date_message);
            $checkbox.attr("checked", false).change();
        };
    };

    self.updateSelectedOwnerType = function (data, event) {
        var $selectOwnerType = $(event.currentTarget);
        var ownerType = $selectOwnerType.val();
        if (ownerType == self.owner_types[0]) {
            self.available_owners(self.users);
            self.should_show_owners(true);
        } else if (ownerType == self.owner_types[1]) {
            self.available_owners(self.groups);
            self.should_show_owners(true);
        } else {
            self.available_owners([]);
            self.should_show_owners(false);
            self.enableSubmit(false);
        }
        if (!_.isEmpty($(event.srcElement)))
            self.enableSubmit(false);
    };

    self.updateSelectedOwner = function (data, event) {
        var $selectOwner = $(event.currentTarget);
        if ($selectOwner.val() == "") {
            self.enableSubmit(false);
        } else {
            self.enableSubmit(true);
        }
    };

    self.updateCaseSelection = function (data, event) {
        var $checkbox = $(event.currentTarget),
            caseID = $checkbox.data('caseid'),
            ownerID = $checkbox.data('owner'),
            ownerType = $checkbox.data('ownertype');

        var ind = self.selected_cases().indexOf(caseID);

        if ($checkbox.is(':checked')) {
            $checkbox.parent().parent().addClass('active');
            if (ind < 0) {
                self.selected_cases.push(caseID);
            }
            self.selected_owner_types.push(ownerType);
            self.selected_owners.push(ownerID);
        } else {
            $checkbox.parent().parent().removeClass('active');
            if (ind >= 0) {
                self.selected_cases.splice(ind, 1);
            }
            self.selected_owner_types.splice(self.selected_owner_types().indexOf(ownerType), 1);
            self.selected_owners.splice(self.selected_owners().indexOf(ownerID), 1);
        }
    };

    self.updateCaseOwners = function (form, event) {
        var new_owner = $(form).find('#reassign_owner_select').val(),
            owner_type = $(form).find('#reassign_owner_type_select').val(),
            $modal = $('#caseManagementStatusModal');
        if (_.isEmpty(new_owner)) {
            $modal.find('.modal-body').text("Please select an owner");
            $modal.modal('show');
            return false;
        }

        for (var i = 0; i < self.selected_cases().length; i++) {
            var case_id = self.selected_cases()[i],
                xform;
            xform = casexml.CaseDelta.wrap({
                    case_id: case_id,
                    properties: {owner_id: new_owner}
                }).asXFormInstance({
                        user_id: self.webUserID
                    }).serialize();

            $.ajax({
                url: self.receiverUrl,
                type: 'post',
                data: xform,
                success: updateCaseRow(case_id, new_owner, owner_type)
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

ko.bindingHandlers.grabUniqueDefault = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        var unique = _.unique(value);
        if (unique.length === 1) {
            $(element).val(unique[0]);
        } else {
            $(element).val("");
        }
        $(element).change();
    }
};