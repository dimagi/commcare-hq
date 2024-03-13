
hqDefine("data_interfaces/js/case_management",[
    'jquery',
    'underscore',
    'knockout',
    'case/js/casexml',
    'hqwebapp/js/initial_page_data',
    'reports/js/standard_hq_report',
    'hqwebapp/js/bootstrap3/alert_user',
], function ($, _, ko, casexmlModule, initialPageData, standardHqReport, alertUser) {
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
        self.selectAllMatches = ko.observable(false);

        // What we're assigning to
        self.newOwner = ko.observable();

        self.isSubmitEnabled = ko.computed(function () {
            return !!self.newOwner();
        }, self);

        self.selectedCount = ko.computed(function () {
            return self.selectedCases().length;
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

        var updateCaseRowReassign = function (caseId, ownerId, ownerType) {
            return function () {
                var $checkbox = $('#data-interfaces-reassign-cases input[data-caseid="' + caseId + '"].selected-commcare-case');
                var $row = $checkbox.closest("tr");
                var labelMessage = gettext("Out of range of filter. Will not appear on page refresh.");
                var username = $('#reassign_owner_select').data().select2.data().text,
                    dateMessage = (self.onToday) ? '<span title="0"></span>' :
                        '<span class="label label-warning" title="0">' + labelMessage + '</span>';
                $checkbox.data('owner', ownerId);
                $checkbox.data('ownertype', ownerType);

                var groupLabel = '';

                if (ownerType === 'group') {
                    groupLabel = ' <span class="label label-inverse" title="' + username + '">group</span>';
                }

                var labelText = gettext("updated");
                $row.find('td:nth-child(4)').html(username + groupLabel + ' <span class="label label-info" title="' + username +
                                                '">' + labelText + '</span>');
                $row.find('td:nth-child(5)').html('Today ' + dateMessage);
                $checkbox.prop("checked", false).change();
            };
        };

        var updateCaseRowCopy = function (caseIds) {
            return function () {
                var caseIdsArr = caseIds.slice();
                for (var i = 0 ; i < caseIdsArr.length ; i++) {
                    var caseId = caseIdsArr[i];
                    var $checkbox = $('#data-interfaces-reassign-cases input[data-caseid="' + caseId + '"].selected-commcare-case');
                    var $row = $checkbox.closest("tr");
                    var labelMessage = gettext("Case copied");
                    var dateMessage = (self.onToday) ? '<span title="0"></span>' :
                        '<span class="label label-info" title="0">' + labelMessage + '</span>';
                    $row.find('td:nth-child(5)').html('Today ' + dateMessage);
                    $checkbox.prop("checked", false).change();
                }
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

        self.updateAllMatches = function (ownerId) {
            var paramsObject = self.getReportParamsObject();
            paramsObject['new_owner_id'] = ownerId;
            var bulkReassignUrl = window.location.href.replace("data/edit", "data/edit/bulk");
            $.postGo(
                bulkReassignUrl,
                paramsObject
            );
        };

        self.onSubmit = function (form) {
            if (initialPageData.get("action") === "copy") {
                self.copyCases(form);
            } else {
                self.updateCaseOwners(form);
            }
        };

        self.copyCases = function (form) {
            var newOwner = $(form).find('#reassign_owner_select').val(),
                $modal = $('#caseManagementStatusModal');

            if (newOwner.includes('__')) {
                // groups and users have different number of characters before the id
                // users are u__id and groups are sg__id
                newOwner = newOwner.slice(newOwner.indexOf('__') + 2);
            }
            if (_.isEmpty(newOwner)) {
                $modal.find('.modal-body').text("Please select an owner");
                $modal.modal('show');
            } else {
                if (self.selectAllMatches()) {
                    self.updateAllMatches(newOwner);
                    return;
                }
                $(form).find("[type='submit']").disableButton();
                var sensitiveProperties = JSON.parse(self.getReportParamsObject().sensitive_properties);

                $.ajax({
                    url: initialPageData.reverse("copy_cases"),
                    type: 'POST',
                    data: JSON.stringify({
                        case_ids: self.selectedCases(),
                        owner_id: newOwner,
                        sensitive_properties: sensitiveProperties,
                    }),
                    contentType: "application/json",
                    success: function (response) {
                        updateCaseRowCopy(self.selectedCases())();
                        var message = gettext("Cases copied") + ": " + response.copied_cases;
                        alertUser.alert_user(message, "success");
                    },
                    error: function (response) {
                        self.clearCaseSelection();
                        alertUser.alert_user(response.responseJSON.error, "danger");
                    },
                });
            }
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
                if (self.selectAllMatches()) {
                    self.updateAllMatches(newOwner);
                    return;
                }
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
                        success: updateCaseRowReassign(caseId, newOwner, ownerType),
                    });

                }
            }
        };

        self.getReportParamsObject = function () {
            var report = standardHqReport.getStandardHQReport();
            var params = new URLSearchParams(report.getReportParams());
            return Object.fromEntries(params.entries());
        };

        return self;
    };

    ko.bindingHandlers.caseActionForm = {
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
                caseManagementModel.selectAllMatches.subscribe(function (selectAllMatches) {
                    if (selectAllMatches) {
                        selectAll();
                    } else {
                        selectNone();
                    }
                });
                $(interfaceSelector).koApplyBindings(caseManagementModel);
            }

            var caseAction = initialPageData.get('action');
            var placeholderText = "";

            if (caseAction === 'copy') {
                placeholderText = gettext("Search for users");
            } else {
                placeholderText = gettext("Search for users or groups");
            }

            var $select = $('#reassign_owner_select');
            if ($select.length) {
                $select.select2({
                    placeholder: placeholderText,
                    ajax: {
                        url: initialPageData.reverse("case_action_options"),
                        data: function (params) {
                            return {
                                q: params.term,
                                action: caseAction,
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
            caseManagementModel.selectAllMatches(false);
            selectAll();
            return false;
        });

        function selectAll() {
            $(interfaceSelector).find('input.selected-commcare-case').prop('checked', true).change();
        }

        function selectNone() {
            $(interfaceSelector).find('input.selected-commcare-case:checked').prop('checked', false).change();
        }

        $(document).on("click", interfaceSelector + " a.select-none", function () {
            caseManagementModel.selectAllMatches(false);
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
