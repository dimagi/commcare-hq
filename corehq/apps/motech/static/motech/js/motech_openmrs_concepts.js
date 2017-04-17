$(function () {
    function ConceptViewModel() {
        var self = this;
        self.concepts = ko.observableArray([]);
    }
    var conceptViewModel = new ConceptViewModel();
    $('#openmrs_concepts_table').koApplyBindings(conceptViewModel);
    var urllib = hqImport('hqwebapp/js/urllib.js');
    $.get(urllib.reverse('all_openmrs_concepts')).done(function (data) {
        conceptViewModel.concepts(data.concepts);
    });
});
