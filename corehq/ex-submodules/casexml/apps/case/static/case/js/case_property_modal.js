/* globals hqDefine, ko, $ */

hqDefine('case/js/case_property_modal', function(){
    'use strict';

    var CasePropertyModal = function(propertyName, changes){
        var self = this;

        self.propertyName = ko.observable(propertyName);
        self.changes = ko.observableArray(changes);
        self.lastTransactionChecked = ko.observable(0);

        self.showSpinner = ko.observable(true);
        self.showError = ko.observable(false);

        self.showMoreButton = ko.computed(function(){
            return self.lastTransactionChecked() !== -1 && !self.showError() && !self.showSpinner();
        });

        self.init = function(name){
            self.lastTransactionChecked(0);
            self.propertyName(name);
            self.changes([]);
            self.getChanges();
        };

        self.getChanges = function(){
            self.showSpinner(true);
            self.showError(false);
            $.get({
                url: hqImport("hqwebapp/js/initial_page_data").reverse('case_property_changes', self.propertyName()),
                data: {
                    next_transaction: self.lastTransactionChecked(),
                },
                success: function(data){
                    self.changes.push.apply(self.changes, data.changes);
                    self.lastTransactionChecked(data.last_transaction_checked);
                    self.showSpinner(false);
                },
                error: function(){
                    self.showError(true);
                    self.showSpinner(false);
                },
            });
        };

        self.fetchMore = function(){
            self.lastTransactionChecked(self.lastTransactionChecked() + 1);
            self.getChanges();
        };

    };

    $(function(){
        var $casePropertyNames = $("a.case-property-name"),
            $propertiesModal = $("#case-properties-modal"),
            modalData = new CasePropertyModal();

        $propertiesModal.koApplyBindings(modalData);
        $casePropertyNames.click(function(){
            modalData.init($(this).data('property-name'));
            $propertiesModal.modal();
        });

    });
    return CasePropertyModal;
});
