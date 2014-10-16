/**
 * Return a GraphViewModel with additional properties added for use as a ui element
 * Allows us to integrate the knockout elements with the jquery based part of the ui.
 * @returns {GraphViewModel}
 */
uiElement.graph_configuration = function() {
    var graphViewModel = new GraphViewModel();

    var $editButtonDiv = $('\
        <div> \
            <button class="btn" data-bind="click: openModal, visible: $data.edit"> \
                <i class="icon-pencil"></i> \
                Edit \
            </button> \
        </div>\
    ');
    graphViewModel.ui = $editButtonDiv;

    eventize(graphViewModel);
    // TODO: Fire change event on self when observables are edited

    return graphViewModel;
};

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

var GraphConfiguration = function(){
    var self = this;
    self.configPairs = ko.observableArray([new ConfigPropertyValuePair(), new ConfigPropertyValuePair()]);

    self.removeConfigPair = function (configPair){
        self.configPairs.remove(configPair);
    };
    self.addConfigPair = function (){
        console.log("Boom shaka laka");
        self.configPairs.push(new ConfigPropertyValuePair());
    }
};

var ConfigPropertyValuePair = function(){
    var self = this;

    self.property = ko.observable("");
    self.value = ko.observable("");
};

var GraphViewModel = function(){
    var self = this;
    self.edit = ko.observable(true);

    self.graphDisplayName = ko.observable("My Partograph");
    self.availableGraphTypes = ko.observableArray(["xy", "bubble"]);
    self.selectedGraphType = ko.observable("xy");
    self.series = ko.observableArray([]);
    self.annotations = ko.observableArray([new Annotation(), new Annotation()]);

    self.removeSeries = function (series){
        self.series.remove(series);
    };
    self.addSeries = function (series){
        if (self.selectedGraphType() == "xy"){
            self.series.push(new XYGraphSeries());
        } else if (self.selectedGraphType() == "bubble"){
            self.series.push(new BubbleGraphSeries());
        } else {
            throw "Invalid selectedGraphType";
        }
    };

    self.removeAnnotation = function (annotation){
        self.annotations.remove(annotation);
    };
    self.addAnnotation = function (){
        self.annotations.push(new Annotation());
    };
};
GraphViewModel.prototype = new GraphConfiguration();

var Annotation = function(){
    var self = this;

    self.x = ko.observable();
    self.y = ko.observable();
    self.displayText = ko.observable();
};

var XYGraphSeries = function(){
    var self = this;

    self.source = ko.observableArray(["something", "da otherthing"]);
    self.dataPath = ko.observable("");
    self.xFunction = ko.observable("");
    self.yFunction = ko.observable("");
};
XYGraphSeries.prototype = new GraphConfiguration();

var BubbleGraphSeries = function(){
    var self = this;
    self.radiusFunction = ko.observable("");
};
BubbleGraphSeries.prototype = new XYGraphSeries();