hqDefine("data_interfaces/js/case_management",[
    'jquery',
    'underscore',
    'knockout',
    'case/js/casexml',
    'hqwebapp/js/initial_page_data',
], function ($, _, ko, casexmlModule, initialPageData) {
    var caseManagement = function (o) {
        'use strict';
        var self = {};

        self.receiverUrl = o.receiverUrl;
        self.updatedCase = null;
        self.webUserID = o.webUserID;
        self.webUserName = o.webUserName;
        self.formName = o.formName;

        // What's checked in the table below
        self.selectedCases = ko.observableArray();
        self.selectedOwners = ko.observableArray();
        self.selectedOwnerTypes = ko.observableArray();

        // What we're assigning to
        self.newOwner = ko.observable();

        self.isSubmitEnabled = ko.computed(function () {
            return !!self.newOwner();
        }, self);

        self.shouldShowOwners = ko.observable(true);

        var endDate = new Date(o.endDate),
            now = new Date();
        self.onToday = (endDate.toDateString() === now.toDateString());

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
                    dateMessage = (self.onToday) ? '<span title="0"></span>' :
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
            self.newOwner($('#reassign_owner_select').val());
        };

        self.updateCaseSelection = function (data, event) {
            var $checkbox = $(event.currentTarget),
                caseID = $checkbox.data('caseid'),
                ownerID = $checkbox.data('owner'),
                ownerType = $checkbox.data('ownertype');

            var ind = self.selectedCases().indexOf(caseID),
                $selectedRow = $checkbox.closest('tr');

            if ($checkbox.is(':checked')) {
                $selectedRow.addClass('active');
                if (ind < 0) {
                    self.selectedCases.push(caseID);
                }
                self.selectedOwnerTypes.push(ownerType);
                self.selectedOwners.push(ownerID);
            } else {
                $selectedRow.removeClass('active');
                if (ind >= 0) {
                    self.selectedCases.splice(ind, 1);
                }
                self.selectedOwnerTypes.splice(self.selectedOwnerTypes().indexOf(ownerType), 1);
                self.selectedOwners.splice(self.selectedOwners().indexOf(ownerID), 1);
            }
        };

        self.clearCaseSelection = function () {
            self.selectedCases.removeAll();
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
                for (var i = 0; i < self.selectedCases().length; i++) {
                    var caseId = self.selectedCases()[i],
                        xform;
                    xform = casexmlModule.casexml.CaseDelta.wrap({
                        case_id: caseId,
                        properties: {owner_id: newOwner},
                    }).asXFormInstance({
                        user_id: self.webUserID,
                        username: self.webUserName,
                        form_name: self.formName,
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
                caseManagementModel = caseManagement({
                    receiverUrl: initialPageData.reverse("receiver_secure_post"),
                    endDate: initialPageData.get("reassign_cases_enddate"),
                    webUserID: initialPageData.get("web_user_id"),
                    webUserName: initialPageData.get("web_username"),
                    formName: gettext("Case Reassignment (via HQ)"),
                });
                $(interfaceSelector).koApplyBindings(caseManagementModel);
            }

            var $select = $('#reassign_owner_select');
            if ($select.length) {
                $select.select2({
                    placeholder: gettext("Search for users or groups"),
                    ajax: {
                        url: initialPageData.reverse("reassign_case_options"),
                        data: function (params) {
                            return {
                                q: params.term,
                            };
                        },
                        dataType: 'json',
                        quietMillis: 250,
                        processResults: function (data) {
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
