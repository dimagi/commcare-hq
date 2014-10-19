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

var PairConfiguration = function(){
    var self = this;
    self.configPairs = ko.observableArray([]);
    self.configPropertyOptions = [];
    self.configPropertyHints = {};

    self.removeConfigPair = function (configPair){
        self.configPairs.remove(configPair);
    };
    self.addConfigPair = function (){
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
    self.annotations = ko.observableArray([]);
    self.configPropertyOptions = [
        // Axis min and max:
        'x-min',
        'x-max',
        'y-min',
        'y-max',
        'secondary-y-min',
        'secondary-y-max',
        // Axis titles:
        'x-title',
        'y-title',
        'secondary-y-title',
        // Axis labels:
        'x-labels',
        'y-labels',
        'secondary-y-labels',
        // other:
        'show-grid',
        'show-axes',
        'zoom'
    ];
    // Note: I don't like repeating the list of property options in the hints map.
    // I could use configPropertyHints.keys() to generate the options, but that
    // doesn't guarantee order...
    self.configPropertyHints = {
        // Axis min and max:
        'x-min': 'ex: 0',
        'x-max': 'ex: 100',
        'y-min': 'ex: 0',
        'y-max': 'ex: 100',
        'secondary-y-min': 'ex: 0',
        'secondary-y-max': 'ex: 100',
        // Axis titles:
        'x-title': 'ex: days',
        'y-title': 'ex: temperature',
        'secondary-y-title': 'ex: temperature',
        // Axis labels:
        'x-labels': 'ex: 3 or [1,3,5] or {"0":"freezing"}',
        'y-labels': 'ex: 3 or [1,3,5] or {"0":"freezing"}',
        'secondary-y-labels': 'ex: 3 or [1,3,5] or {"0":"freezing"}',
        // other:
        'show-grid': 'true or false',
        'show-axes': 'true or false',
        'zoom': 'true or false'
    };

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
GraphViewModel.prototype = new PairConfiguration();

var Annotation = function(){
    var self = this;

    self.x = ko.observable();
    self.y = ko.observable();
    self.displayText = ko.observable();
};
var GraphSeries = function (){
    var self = this;

    self.sourceOptions = ko.observableArray(["child case type 1", "child case type 2", "custom"]);
    self.selectedSource = ko.observable("child case type 1");
    self.dataPath = ko.observable("");
    self.showDataPath = ko.observable(false);
    self.xFunction = ko.observable("");
    self.yFunction = ko.observable("");
    self.configPropertyOptions = [
        'fill-above',
        'fill-below',
        'line-color',
        'point-style'
    ];
    self.configPropertyHints = {
        'fill-above': 'ex: #aarrggbb',
        'fill-below': 'ex: #aarrggbb',
        'line-color': 'ex: #aarrggbb',
        'point-style': 'circle, x, or none'
    };

    self.toggleShowDataPath = function() {
        self.showDataPath(!self.showDataPath())
    };
    self.selectedSource.subscribe(function(newValue) {
        if (newValue == "custom") {
            self.showDataPath(true);
        }
    });
};
GraphSeries.prototype = new PairConfiguration();

var XYGraphSeries = function(){
    var self = this;
    self.configPropertyOptions = self.configPropertyOptions.concat(['secondary-y']);
    self.configPropertyHints['secondary-y'] = 'ex: false';
};
XYGraphSeries.prototype = new GraphSeries();

var BubbleGraphSeries = function(){
    var self = this;
    self.radiusFunction = ko.observable("");
    self.configPropertyOptions = self.configPropertyOptions.concat(['max-radius']);
    self.configPropertyHints['max-radius'] = 'ex: 7';
};
BubbleGraphSeries.prototype = new GraphSeries();