$(function () {
    var urllib = hqImport('hqwebapp/js/urllib.js');
    function ConceptViewModel() {
        var self = this;
        self.concepts = ko.observableArray([]);
        self.syncButton = {
            inProgress: ko.observable(false),
            hasError: ko.observable(false),
            sync: function () {
                self.concepts([]);
                self.syncButton.inProgress(true);
                self.syncButton.hasError(false);
                $.get(urllib.reverse('openmrs_sync_concepts')).done(function () {
                    self.refreshConcepts();
                    self.syncButton.inProgress(false);
                    self.syncButton.hasError(false);
                }).fail(function () {
                    self.syncButton.inProgress(false);
                    self.syncButton.hasError(true);
                });
            },
        };
        self.refreshConcepts = function () {
            $.get(urllib.reverse('all_openmrs_concepts')).done(function (data) {
                conceptViewModel.concepts(data.concepts);
            });
        };
    }
    var conceptViewModel = new ConceptViewModel();
    $('#openmrs_concepts_template').koApplyBindings(conceptViewModel);
    conceptViewModel.refreshConcepts();

});
