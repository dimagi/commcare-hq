/**
 * Create a view model that is bound to an "Edit graph" button. The ui property
 * of this view model allows us to integrate the knockout elements with the
 * jquery based part of the ui.
 */
uiElement.GraphConfiguration = function(original) {
    var self = this;

    //TODO: Put this in a template somewhere?
    var $editButtonDiv = $('\
        <div> \
            <button class="btn" data-bind="click: openModal, visible: $data.edit"> \
                <i class="icon-pencil"></i> \
                Edit Graph\
            </button> \
        </div>\
    ');

    self.ui = $editButtonDiv;
    self.graphViewModel = new GraphViewModel(original);
    self.edit = ko.observable(true);
    self.openModal = function (uiElementViewModel){

        // make a copy of the view model
        var graphViewModelCopy = new GraphViewModel();
        graphViewModelCopy.fromJS(ko.toJS(uiElementViewModel.graphViewModel));
        // Replace the original with the copy if save is clicked, otherwise discard it
        graphViewModelCopy.onSave = function(){
            uiElementViewModel.graphViewModel = graphViewModelCopy;
        };

        // Load the modal with the copy
        var $modalDiv = $('<div data-bind="template: \'graph_configuration_modal\'"></div>');

        ko.applyBindings(graphViewModelCopy, $modalDiv.get(0));

        var $modal = $modalDiv.find('.modal');
        $modal.appendTo('body');
        $modal.modal('show');
        $modal.on('hidden', function () {
            $modal.remove();
        });
    };

    ko.applyBindings(self, self.ui.get(0));
    eventize(self);
    // TODO: Fire change event on self when observables are edited (so that save button is activated) ?
    //       see uiElement.key_value_mapping
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

var GraphViewModel = function(original){
    var self = this;

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

    self.fromJS = function(obj){
        self.graphDisplayName(obj.graphDisplayName);
        self.selectedGraphType(obj.selectedGraphType);
        self.series(_.map(obj.series, function(o){
            var newSeries = new (self.getSeriesConstructor())();
            newSeries.fromJS(o);
            return newSeries;
        }));
        self.annotations(_.map(obj.annotations, function(o){
            var newAnnotation = new Annotation();
            newAnnotation.fromJS(o);
            return newAnnotation;
        }));
    };

    self.removeSeries = function (series){
        self.series.remove(series);
    };
    self.addSeries = function (series){
        self.series.push(new (self.getSeriesConstructor())());
    };
    /**
     * Return the proper Series object constructor based on the current state
     * of the view model.
     */
    self.getSeriesConstructor = function(){
        if (self.selectedGraphType() == "xy"){
            return XYGraphSeries
        } else if (self.selectedGraphType() == "bubble"){
            return BubbleGraphSeries
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

    self.fromJS = function(obj){
        self.x(obj.x);
        self.y(obj.y);
        self.displayText(obj.displayText);
    };
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

    self.fromJS = function(obj){
        self.sourceOptions(obj.sourceOptions);
        self.selectedSource(obj.selectedSource);
        self.dataPath(obj.dataPath);
        self.showDataPath(obj.showDataPath);
        self.xFunction(obj.xFunction);
        self.yFunction(obj.yFunction);
        self.yFunction(obj.yFunction);
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

    self.fromJS = function(obj){
        this.__proto__.fromJS(obj);
        this.radiusFunction(obj.radiusFunction);
    };
};
BubbleGraphSeries.prototype = new GraphSeries();