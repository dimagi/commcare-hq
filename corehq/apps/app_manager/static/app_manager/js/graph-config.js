var openGraphConfigurationModal = function(){
    var $modalDiv = $('<div data-bind="template: \'graph_configuration_modal\'"></div>');
    var myGraphViewModel = new GraphViewModel();
    ko.applyBindings(myGraphViewModel, $modalDiv.get(0));
    var $modal = $modalDiv.find('.modal');

    $modal.appendTo('body');
    $modal.modal('show');
    $modal.on('hidden', function () {
        $modal.remove();
    });
};

var GraphViewModel = function(){
    var self = this;

    self.graphDisplayName =  ko.observable("My Partograph");
    self.availableGraphTypes =  ko.observableArray(["xy", "line", "scatter", "bubble"]);
    self.annotations = ko.observableArray([new Annotation()]);
};

var Annotation = function(){
    var self = this;

    self.x = ko.observable(0);
    self.y = ko.observable(0);
    self.displayText = ko.observable("");
};