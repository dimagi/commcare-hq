/**
 * Create a view model that is bound to an "Edit graph" button. The ui property
 * of this view model allows us to integrate the knockout elements with the
 * jquery based part of the ui.
 */
uiElement.GraphConfiguration = function(original) {
    var self = this;
    original = original || {};

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
        var graphViewModelCopy = new GraphViewModel(original);
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

    /**
     * Return an object representing this graph configuration that is suitable
     * for sending to and saving on the server.
     * @returns {{}}
     */
    self.val = function(){
        var graphViewModelAsPOJS = ko.toJS(self.graphViewModel);
        var ret = {};

        /**
         * Convert objects like {'en': null, 'fra': 'baguette'} to {'fra': 'baguette'}
         * @param obj
         * @returns {{}}
         */
        var omit_nulls = function(obj){
            var keys = _.keys(obj);
            var ret = {};
            for (var i=0; i < keys.length; i++){
                if (obj[keys[i]] != null){
                    ret[keys[i]] = obj[keys[i]];
                }
            }
            return ret;
        };

        // TODO: We could have a helper function called pairListToObj to make
        //       this a bit more readable

        ret['graph_type'] = graphViewModelAsPOJS['graphType'];
        ret['series'] = _.map(graphViewModelAsPOJS['series'], function(s){
            var series = {};
            // Only take the keys from the series that we care about
            series['data_path'] = s['dataPath'];
            series['x_function'] = s['xFunction'];
            series['y_function'] = s['yFunction'];
            // convert the list of config objects to a single object (since
            // order no longer matters)
            series['config'] = _.reduce(s['configPairs'], function(memo, pair){
                memo[pair['property']] = pair['value'];
                return memo;
            }, {});
            return series;
        });
        ret['annotations'] = _.map(graphViewModelAsPOJS['annotations'], function(obj){
            obj['display_text'] = obj['displayText'];
            delete obj['displayText'];
            return obj;
        });
        ret['locale_specific_config'] = _.reduce(
            graphViewModelAsPOJS['axisTitleConfigurations'], function(memo, conf){
                memo[conf['property']] = omit_nulls(conf['values']);
                return memo;
        }, {});
        ret['config'] = _.reduce(graphViewModelAsPOJS['configPairs'], function(memo, pair){
            memo[pair['property']] = pair['value'];
            return memo;
        }, {});

        return ret;
    }
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

var ConfigPropertyValuePair = function(original){
    var self = this;
    original = original || {};

    self.property = ko.observable(original.property === undefined ? "" : original.property);
    self.value = ko.observable(original.value === undefined ? "" : original.value);
};

var LocalizedConfigPropertyValuePair = function(original){
    var self = this;
    original = original || {};

    // These value should always be provided
    self.lang = original.lang;
    self.langs = original.langs;
    self.property = original.property;

    self.values = original.values || {};
    // Make the value for the current language observable:
    self.values[self.lang] =
        ko.observable(self.values[self.lang] === undefined ? null : ko.unwrap(
            self.values[self.lang])
        );

    /**
     * Return the backup value for self.lang.
     * ex: self.values = {'en': 'foo', 'it': 'bar'}
     *     self.langs = ['en', 'fra', 'it']
     *
     *     self.lang = 'fra'
     *     self.getBackup() === 'foo'
     *
     *     self.lang = 'it'
     *     self.getBackup() === 'bar'
     *
     * @returns {object}
     */
    self.getBackup = function(){
        var backup = {'value':null, 'lang': null};
        var modLangs = [self.lang].concat(self.langs);
        for (var i=0; i < modLangs.length; i++) {
            var possibleBackup = ko.unwrap(self.values[modLangs[i]]);
            if (possibleBackup !== undefined && possibleBackup != null) {
                backup = {
                    'value': possibleBackup,
                    'lang': modLangs[i]
                };
                break;
            }
        }
        return backup;
    };

};

var GraphViewModel = function(original){
    var self = this;
    original = original || {};

    self.lang = original.lang;
    self.langs = original.langs;

    self.graphDisplayName = ko.observable("My Partograph");
    self.availableGraphTypes = ko.observableArray(["xy", "bubble"]);
    self.selectedGraphType = ko.observable("xy");
    self.series = ko.observableArray([]);
    self.annotations = ko.observableArray([]);
    self.axisTitleConfigurations = ko.observableArray(_.map(
        ['x-axis-title', 'y-axis-title', 'secondary-y-title'],
        function(s){return new LocalizedConfigPropertyValuePair({
            'property': s,
            //TODO: initialize these values
            'lang': self.lang,
            'langs': self.langs
        })}
    ));

    self.configPropertyOptions = [
        // Axis min and max:
        'x-min',
        'x-max',
        'y-min',
        'y-max',
        'secondary-y-min',
        'secondary-y-max',
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
    // I could make these be lists of lists and have the bindings be functions
    // instead of just the name of the property
    self.configPropertyHints = {
        // Axis min and max:
        'x-min': 'ex: 0',
        'x-max': 'ex: 100',
        'y-min': 'ex: 0',
        'y-max': 'ex: 100',
        'secondary-y-min': 'ex: 0',
        'secondary-y-max': 'ex: 100',
        // Axis labels:
        'x-labels': 'ex: 3 or [1,3,5] or {"0":"freezing"}',
        'y-labels': 'ex: 3 or [1,3,5] or {"0":"freezing"}',
        'secondary-y-labels': 'ex: 3 or [1,3,5] or {"0":"freezing"}',
        // other:
        'show-grid': 'true or false',
        'show-axes': 'true or false',
        'zoom': 'true or false'
    };
    self.childCaseTypes = original.childCaseTypes || []; // TODO: What happens with original might change

    self.selectedGraphType.subscribe(function(newValue) {
        // Recreate the series objects to be of the correct type.
        self.series(_.map(self.series(), function(series){
            return new (self.getSeriesConstructor())(ko.toJS(series), self.childCaseTypes);
        }));
    });

    self.fromJS = function(obj){
        self.graphDisplayName(obj.graphDisplayName);
        self.selectedGraphType(obj.selectedGraphType);
        self.series(_.map(obj.series, function(o){
            return new (self.getSeriesConstructor())(o, self.childCaseTypes);
        }));
        self.annotations(_.map(obj.annotations, function(o){
            return new Annotation(o);
        }));
        self.axisTitleConfigurations(_.map(obj.axisTitleConfigurations, function(o){
            return new LocalizedConfigPropertyValuePair(o);
        }));
        self.childCaseTypes = obj.childCaseTypes.slice(0)
    };

    self.removeSeries = function (series){
        self.series.remove(series);
    };
    self.addSeries = function (series){
        self.series.push(new (self.getSeriesConstructor())({}, self.childCaseTypes));
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

var Annotation = function(original){
    var self = this;
    original = original || {};

    self.x = ko.observable(original.x === undefined ? undefined : original.x);
    self.y = ko.observable(original.y === undefined ? undefined : original.y);
    self.displayText = ko.observable(original.displayText === "" ? undefined : original.displayText);

};

var GraphSeries = function (original, childCaseTypes){
    var self = this;
    original = original || {};
    childCaseTypes = childCaseTypes || [];

    function orig_or_default(prop, fallback){
        return original[prop] === undefined ? fallback : original[prop]
    }
    /**
     * Return the default value for the data path field based on the given source.
     * This is used to change the data path field when a new source type is selected.
     * @param source
     * @returns {string}
     */
    self.getDefaultDataPath = function(source){
        if (source == "custom"){
             return "instance('name')/root/path-to-point/point";
        } else {
            //TODO: It puts the whole thing in there bad
            return "instance('casedb')/casedb/case[@case_type='"+source+"'][index/parent=current()/@case_id][@status='open']";
        }
    };


    self.sourceOptions = ko.observableArray(orig_or_default(
        'sourceOptions',
        _.map(childCaseTypes, function(s){
            return {
                'text': "Child case: " + s,
                'value' : s
            };
        }).concat([{'text':'custom', 'value':'custom'}])
    ));
    self.selectedSource = ko.observable(orig_or_default('selectedSource', self.sourceOptions()[0]));
    self.dataPath = ko.observable(orig_or_default('dataPath', self.getDefaultDataPath(self.selectedSource().value)));
    self.showDataPath = ko.observable(orig_or_default('showDataPath', false));
    self.xFunction = ko.observable(orig_or_default('xFunction',""));
    self.yFunction = ko.observable(orig_or_default('yFunction',""));
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
        if (newValue.value == "custom") {
            self.showDataPath(true);
        }
        self.dataPath(self.getDefaultDataPath(newValue.value));
    });
};
GraphSeries.prototype = new PairConfiguration();
GraphSeries.prototype.constructor = GraphSeries;

var XYGraphSeries = function(original, childCaseTypes){
    GraphSeries.apply(this, [original, childCaseTypes]);
    var self = this;
    self.configPropertyOptions = self.configPropertyOptions.concat(['secondary-y']);
    self.configPropertyHints['secondary-y'] = 'ex: false';
};
XYGraphSeries.prototype = new GraphSeries();
XYGraphSeries.constructor = XYGraphSeries;

var BubbleGraphSeries = function(original, childCaseTypes){
    GraphSeries.apply(this, [original, childCaseTypes]);
    var self = this;

    self.radiusFunction = ko.observable(original.radiusFunction === undefined ? "" : original.radiusFunction);
    self.configPropertyOptions = self.configPropertyOptions.concat(['max-radius']);
    self.configPropertyHints['max-radius'] = 'ex: 7';

};
BubbleGraphSeries.prototype = new GraphSeries();
BubbleGraphSeries.prototype.constructor = BubbleGraphSeries;