hqDefine("data_interfaces/js/case_management",[
    'jquery',
    'underscore',
    'knockout',
    'case/js/casexml',
    'hqwebapp/js/initial_page_data',
], function ($, _, ko, casexmlModule, initialPageData) {
    var CaseManagement = function (o) {
        'use strict';
        var self = {};

        self.receiverUrl = o.receiverUrl;
        self.updatedCase = null;
        self.webUserID = o.webUserID;
        self.webUserName = o.webUserName;
        self.form_name = o.form_name;

        // What's checked in the table below
        self.selected_cases = ko.observableArray();
        self.selected_owners = ko.observableArray();
        self.selected_owner_types = ko.observableArray();

        // What we're assigning to
        self.new_owner = ko.observable();

        self.is_submit_enabled = ko.computed(function () {
            return !!self.new_owner();
        }, self);

        self.should_show_owners = ko.observable(true);

        var enddate = new Date(o.enddate),
            now = new Date();
        self.on_today = (enddate.toDateString() === now.toDateString());

        var getOwnerType = function (ownerId) {
            if (ownerId.startsWith('u')) {
                return 'user';
            } else if (ownerId.startsWith('sg')) {
                return 'group';
            }
        };

        var updateCaseRow = function (caseId, ownerId, ownerType) {
            return function () {
                var $checkbox = $('#data-interfaces-reassign-cases input[data-caseid="' + caseId + '"].selected-commcare-case'),
                    username = $('#reassign_owner_select').data().select2.data().text,
                    dateMessage = (self.on_today) ? '<span title="0"></span>' :
                        '<span class="label label-warning" title="0">Out of range of filter. Will ' +
                                        'not appear on page refresh.</span>';
                $checkbox.data('owner', ownerId);
                $checkbox.data('ownertype', ownerType);

                var $row = $checkbox.closest("tr"),
                    groupLabel = '';

                if (ownerType === 'group') {
                    groupLabel = ' <span class="label label-inverse" title="' + username + '">group</span>';
                }

                $row.find('td:nth-child(4)').html(username + groupLabel + ' <span class="label label-info" title="' + username +
                                                '">updated</span>');
                $row.find('td:nth-child(5)').html('Today ' + dateMessage);
                $checkbox.prop("checked", false).change();
            };
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
            var newOwner = $(form).find('#reassign_owner_select').val(),
                $modal = $('#caseManagementStatusModal'),
                ownerType = getOwnerType(newOwner);

            if (newOwner.includes('__')) {
                // groups and users have different number of characters before the id
                // users are u__id and groups are sg__id
                newOwner = newOwner.slice(newOwner.indexOf('__') + 2);
            }

            if (_.isEmpty(newOwner)) {
                $modal.find('.modal-body').text("Please select an owner");
                $modal.modal('show');
            } else {
                $(form).find("[type='submit']").disableButton();
                for (var i = 0; i < self.selected_cases().length; i++) {
                    var caseId = self.selected_cases()[i],
                        xform;
                    xform = casexmlModule.casexml.CaseDelta.wrap({
                        case_id: caseId,
                        properties: {owner_id: newOwner},
                    }).asXFormInstance({
                        user_id: self.webUserID,
                        username: self.webUserName,
                        form_name: self.form_name,
                    }).serialize();

                    $.ajax({
                        url: self.receiverUrl,
                        type: 'post',
                        data: xform,
                        success: updateCaseRow(caseId, newOwner, ownerType),
                    });

                }
            }
        };

        return self;
    };

    ko.bindingHandlers.caseReassignmentForm = {
        update: function (element, valueAccessor) {
            var value = valueAccessor()();
            var $element = $(element);
            if (value.length > 0) {
                $element.slideDown();
            } else {
                $element.find("[type='submit']").enableButton();
                $element.slideUp();
            }
        },
    };

    $(function () {
        var interfaceSelector = '#data-interfaces-reassign-cases',
            caseManagementModel;

        var applyBindings = function () {
            if ($(interfaceSelector).length) {
                caseManagementModel = CaseManagement({
                    receiverUrl: initialPageData.reverse("receiver_secure_post"),
                    enddate: initialPageData.get("reassign_cases_enddate"),
                    webUserID: initialPageData.get("web_user_id"),
                    webUserName: initialPageData.get("web_username"),
                    form_name: gettext("Case Reassignment (via HQ)"),
                });
                $(interfaceSelector).koApplyBindings(caseManagementModel);
            }

            var $select = $('#reassign_owner_select');
            if ($select.length) {
                $select.select2({
                    placeholder: gettext("Search for users or groups"),
                    ajax: {
                        url: initialPageData.reverse("reassign_case_options"),
                        data: function (term) {
                            return {
                                q: term,
                            };
                        },
                        dataType: 'json',
                        quietMillis: 250,
                        results: function (data) {
                            return {
                                total: data.total,
                                results: data.results,
                            };
                        },
                        cache: true,
                    },
                });
            }
        };

        // Apply bindings whenever report content is refreshed
        applyBindings();
        $(document).on('ajaxSuccess', function (e, xhr, ajaxOptions) {
            var jsOptions = initialPageData.get("js_options");
            if (jsOptions && ajaxOptions.url.indexOf(jsOptions.asyncUrl) === -1) {
                return;
            }
            applyBindings();
        });

        // Event handlers for selecting & de-selecting cases
        // Similar to archive_forms.js, would be good to combine the two
        $(document).on("click", interfaceSelector + " a.select-all", function () {
            $(interfaceSelector).find('input.selected-commcare-case').prop('checked', true).change();
            return false;
        });

        function selectNone() {
            $(interfaceSelector).find('input.selected-commcare-case:checked').prop('checked', false).change();
        }

        $(document).on("click", interfaceSelector + " a.select-none", function () {
            selectNone();
            return false;
        });

        $(document).on("mouseup", interfaceSelector + " .dataTables_paginate a", selectNone);
        $(document).on("change", interfaceSelector + " .dataTables_length select", selectNone);

        $(document).on("change", interfaceSelector + " input.selected-commcare-case", function (e) {
            caseManagementModel.updateCaseSelection({}, e);
        });
    });
});
