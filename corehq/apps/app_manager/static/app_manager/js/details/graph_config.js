/* global Clipboard */
hqDefine('app_manager/js/details/graph_config', function () {
    /**
     * Create a view model that is bound to an "Edit graph" button. The ui property
     * of this view model allows us to integrate the knockout elements with the
     * jquery based part of the ui.
     *
     * @param moduleOptions
     * A mapping of configuration options from the module. The following keys are required:
     *      lang
     *      langs
     *      childCaseTypes
     *      fixtures
     * @param serverRepresentationOfGraph
     * Object corresponding to a graph configuration saved in couch.
     * @constructor
     */
    var graphConfigurationUiElement = function (moduleOptions, serverRepresentationOfGraph) {
        var self = {};
        moduleOptions = moduleOptions || {};

        var $editButtonDiv = $(
            '<div>' +
            '<button class="btn btn-default" data-bind="click: openModal">' +
            '<i class="fa fa-pencil"></i> ' +
            gettext('Edit Graph') +
            '</button>' +
            '</div>'
        );

        self.ui = $editButtonDiv;
        self.graphView = graphViewModel(moduleOptions);
        self.graphView.populate(getGraphViewJS(serverRepresentationOfGraph, moduleOptions));

        self.openModal = function (uiElementViewModel) {

            // make a copy of the view model
            var graphViewCopy = graphViewModel(moduleOptions);
            graphViewCopy.populate(ko.toJS(uiElementViewModel.graphView));
            // Replace the original with the copy if save is clicked, otherwise discard it
            graphViewCopy.onSave = function () {
                uiElementViewModel.graphView = graphViewCopy;
                self.fire("change");
            };

            // Load the modal with the copy
            var $modalDiv = $(document.createElement("div"));
            $modalDiv.attr("data-bind", "template: 'graph_configuration_modal'");

            $modalDiv.koApplyBindings(graphViewCopy);

            var $modal = $modalDiv.find('.modal');
            $modal.appendTo('body');
            $modal.modal('show');
            $modal.on('hidden.bs.modal', function () {
                $modal.remove();
            });
        };
        self.setName = function (name) {
            self.graphView.graphDisplayName(name);
        };

        self.ui.koApplyBindings(self);
        hqImport("hqwebapp/js/bootstrap3/main").eventize(self);

        /**
         * Return an object representing this graph configuration that is suitable
         * for sending to and saving on the server.
         * @returns {{}}
         */
        self.val = function () {
            var graphViewAsPOJS = ko.toJS(self.graphView);
            var ret = {};

            /**
             * Convert objects like {'en': null, 'fra': 'baguette'} to {'fra': 'baguette'}
             * @param obj
             * @returns {{}}
             */
            var omitNulls = function (obj) {
                var keys = _.keys(obj);
                var ret = {};
                for (var i = 0; i < keys.length; i++) {
                    if (obj[keys[i]] !== null) {
                        ret[keys[i]] = obj[keys[i]];
                    }
                }
                return ret;
            };

            ret.graph_name = graphViewAsPOJS.graphDisplayName;
            ret.graph_type = graphViewAsPOJS.selectedGraphType;
            ret.series = _.map(graphViewAsPOJS.series, function (s) {
                var series = {};
                // Only take the keys from the series that we care about
                series.data_path = s.dataPath;
                series.x_function = s.xFunction;
                series.y_function = s.yFunction;
                if (s.radiusFunction !== undefined) {
                    series.radius_function = s.radiusFunction;
                }
                series.locale_specific_config = _.reduce(
                    s.localeSpecificConfigurations,
                    function (memo, conf) {
                        memo[conf.property] = omitNulls(conf.values);
                        return memo;
                    }, {});
                // convert the list of config objects to a single object (since
                // order no longer matters)
                series.config = _.reduce(s.configPairs, function (memo, pair) {
                    memo[pair.property] = pair.value;
                    return memo;
                }, {});
                return series;
            });
            ret.annotations = _.map(graphViewAsPOJS.annotations, function (obj) {
                obj.display_text = omitNulls(obj.values);
                delete obj.displayText;
                return obj;
            });
            ret.locale_specific_config = _.reduce(
                graphViewAsPOJS.axisTitleConfigurations,
                function (memo, conf) {
                    memo[conf.property] = omitNulls(conf.values);
                    return memo;
                }, {});
            ret.config = _.reduce(graphViewAsPOJS.configPairs, function (memo, pair) {
                memo[pair.property] = pair.value;
                return memo;
            }, {});
            return ret;
        };

        /**
         * Returns an object in in the same form as that returned by
         * ko.toJS(graphViewModel_instance).
         * @param serverGraphObject
         * An object in the form returned of that returned by self.val(). That is,
         * in the same form as the the graph configuration saved in couch.
         * @param moduleOptions
         * Additional options that are derived from the module (or app) like lang,
         * langs, childCaseTypes, and fixtures.
         * @returns {{}}
         */
        function getGraphViewJS(serverGraphObject, moduleOptions) {
            // This line is needed because old Columns that don't have a
            // graph_configuration will still call:
            //      this.graph_extra = graphConfigurationUiElement(..., this.original.graph_configuration)
            serverGraphObject = serverGraphObject || {};
            var ret = {};

            ret.graphDisplayName = serverRepresentationOfGraph.graph_name;
            ret.selectedGraphType = serverGraphObject.graph_type;
            ret.series = _.map(serverGraphObject.series, function (s) {
                var series = {};

                series.selectedSource = {
                    'text': 'custom',
                    'value': 'custom',
                };
                series.dataPath = s.data_path;
                series.dataPathPlaceholder = s.data_path_placeholder;
                series.xFunction = s.x_function;
                series.xPlaceholder = s.x_placeholder;
                series.yFunction = s.y_function;
                series.yPlaceholder = s.y_placeholder;
                if (s.radius_function !== undefined) {
                    series.radiusFunction = s.radius_function;
                }
                series.localeSpecificConfigurations = _.map(_.pairs(s.locale_specific_config), function (pair) {
                    return {
                        'lang': moduleOptions.lang,
                        'langs': moduleOptions.langs,
                        'property': pair[0],
                        'values': pair[1],
                    };
                });
                series.localeSpecificConfigurations = _.sortBy(series.localeSpecificConfigurations, 'property');
                series.configPairs = _.map(_.pairs(s.config), function (pair) {
                    return {
                        'property': pair[0],
                        'value': pair[1],
                    };
                });
                return series;
            });
            ret.annotations = _.map(serverGraphObject.annotations, function (obj) {
                obj.values = obj.display_text;
                delete obj.display_text;
                obj.lang = moduleOptions.lang;
                obj.langs = moduleOptions.langs;
                return obj;
            });
            ret.axisTitleConfigurations = _.map(_.pairs(serverGraphObject.locale_specific_config), function (pair) {
                return {
                    'lang': moduleOptions.lang,
                    'langs': moduleOptions.langs,
                    'property': pair[0],
                    'values': pair[1],
                };
            });
            ret.configPairs = _.map(_.pairs(serverGraphObject.config), function (pair) {
                return {
                    'property': pair[0],
                    'value': pair[1],
                };
            });
            ret.childCaseTypes = moduleOptions.childCaseTypes;
            ret.fixtures = moduleOptions.fixtures;

            return ret;
        }

        return self;
    };

    // private
    var pairConfiguration = function (original) {
        var self = {};
        original = original || {};

        self.configPairs = ko.observableArray(_.map(original.configPairs || [], function (pair) {
            return configPropertyValuePair(pair);
        }));
        self.configPropertyOptions = [''];
        self.configPropertyHints = {};

        self.removeConfigPair = function (configPair) {
            self.configPairs.remove(configPair);
        };
        self.addConfigPair = function () {
            self.configPairs.push(configPropertyValuePair());
        };

        return self;
    };

    // private
    var configPropertyValuePair = function (original) {
        var self = {};
        original = original || {};

        self.property = ko.observable(original.property === undefined ? "" : original.property);
        self.value = ko.observable(original.value === undefined ? "" : original.value);

        return self;
    };

    // private
    // TODO: Rename values to value (throughout the stack) to maintain consistency with enums!!
    var localizableValue = function (original) {
        var self = {};
        original = original || {};

        // These values should always be provided
        self.lang = original.lang;
        self.langs = original.langs;

        self.values = original.values || {};
        // Make the value for the current language observable
        self.values[self.lang] = ko.observable(
            self.values[self.lang] === undefined ? null :
                ko.unwrap(self.values[self.lang])
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
        self.getBackup = function () {
            var backup = {
                'value': null,
                'lang': null,
            };
            var modLangs = [self.lang].concat(self.langs);
            for (var i = 0; i < modLangs.length; i++) {
                var possibleBackup = ko.unwrap(self.values[modLangs[i]]);
                if (possibleBackup !== undefined && possibleBackup !== null) {
                    backup = {
                        'value': possibleBackup,
                        'lang': modLangs[i],
                    };
                    break;
                }
            }
            return backup;
        };

        return self;
    };

    // private
    var localizedConfigPropertyValuePair = function (original) {
        var self = localizableValue(original);
        original = original || {};

        // This should always be provided
        self.property = original.property;

        return self;
    };

    // private
    var graphViewModel = function (moduleOptions) {
        var self = pairConfiguration();
        moduleOptions = moduleOptions || {};

        self.lang = moduleOptions.lang;
        self.langs = moduleOptions.langs;

        self.graphDisplayName = ko.observable(moduleOptions.name || "Graph");
        self.availableGraphTypes = ko.observableArray(["xy", "bar", "bubble", "time"]);
        self.selectedGraphType = ko.observable("xy");
        self.series = ko.observableArray([]);
        self.annotations = ko.observableArray([]);
        self.axisTitleConfigurations = ko.observableArray(_.map(
            // If you add to this list, don't forget to update theOrder in populate() (I know this is gross)
            ['x-title', 'y-title', 'secondary-y-title'],
            function (s) {
                return localizedConfigPropertyValuePair({
                    'property': s,
                    'lang': self.lang,
                    'langs': self.langs,
                });
            }
        ));

        self.configPropertyOptions = [
            '',
            // Axis min and max:
            'x-min',
            'x-max',
            'y-min',
            'y-max',
            'secondary-y-min',
            'secondary-y-max',
            // Axis labels:
            'x-labels',
            'x-labels-time-format',
            'y-labels',
            'secondary-y-labels',
            // other:
            'show-axes',
            'show-data-labels',
            'show-grid',
            'show-legend',
            'bar-orientation',
            'stack',
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
            'x-labels': 'ex: 3 or \'[1,3,5]\' or \'{"0":"freezing"}\'',
            'x-labels-time-format': 'ex: \'%Y-%m\'',
            'y-labels': 'ex: 3 or \'[1,3,5]\' or \'{"0":"freezing"}\'',
            'secondary-y-labels': 'ex: 3 or [1,3,5] or {"0":"freezing"}',
            // other:
            'show-axes': 'true() or false()',
            'show-data-labels': 'true() or false()',
            'show-grid': 'true() or false()',
            'show-legend': 'true() or false()',
            'bar-orientation': '\'horizontal\' or \'vertical\'',
            'stack': 'true() or false()',
        };
        self.childCaseTypes = moduleOptions.childCaseTypes || [];
        self.fixtures = moduleOptions.fixtures || [];
        self.lang = moduleOptions.lang;
        self.langs = moduleOptions.langs;

        self.selectedGraphType.subscribe(function () {
            // Recreate the series objects to be of the correct type.
            self.series(_.map(self.series(), function (series) {
                return self.createSeries(ko.toJS(series), self.childCaseTypes, self.fixtures, self.lang, self.langs);
            }));
        });

        self.populate = function (obj) {
            self.graphDisplayName(obj.graphDisplayName);
            self.selectedGraphType(obj.selectedGraphType);
            self.series(_.map(obj.series, function (o) {
                return self.createSeries(o, self.childCaseTypes, self.fixtures, self.lang, self.langs);
            }));
            self.annotations(_.map(obj.annotations, function (o) {
                return annotation(o);
            }));

            if (obj.axisTitleConfigurations.length !== 0) {
                self.axisTitleConfigurations(_.map(obj.axisTitleConfigurations, function (o) {
                    return localizedConfigPropertyValuePair(o);
                }));
            }
            // This is dumb:
            // might make more sense to sort this in getGraphViewModelJS. Either way it's annoying.
            var theOrder = {
                'x-title': 0,
                'y-title': 1,
                'secondary-y-title': 2,
            };
            self.axisTitleConfigurations.sort(function (a, b) {
                return theOrder[a.property] - theOrder[b.property];
            });

            self.configPairs(_.map(obj.configPairs, function (pair) {
                return configPropertyValuePair(pair);
            }));

            self.childCaseTypes = obj.childCaseTypes.slice(0);
            self.fixtures = obj.fixtures.slice(0);
        };

        self.removeSeries = function (series) {
            self.series.remove(series);
        };
        self.addSeries = function () {
            self.series.push(self.createSeries({}, self.childCaseTypes, self.fixtures, self.lang, self.langs));
        };
        /**
         * Return the proper Series object constructor based on the current state
         * of the view model.
         */
        self.createSeries = function () {
            if (!_.contains(self.availableGraphTypes(), self.selectedGraphType())) {
                throw new Error("Invalid selectedGraphType: " + self.selectedGraphType());
            }
            if (self.selectedGraphType() === "bubble") {
                return bubbleGraphSeries.apply(undefined, arguments);
            } else if (self.selectedGraphType() === "bar") {
                return barGraphSeries.apply(undefined, arguments);
            } else {
                return xyGraphSeries.apply(undefined, arguments);
            }
        };

        self.removeAnnotation = function (annotation) {
            self.annotations.remove(annotation);
        };
        self.addAnnotation = function () {
            self.annotations.push(annotation({
                lang: self.lang,
                langs: self.langs,
            }));
        };

        return self;
    };

    // private
    var annotation = function (original) {
        var self = localizableValue(original);
        original = original || {};

        self.x = ko.observable(original.x === undefined ? undefined : original.x);
        self.y = ko.observable(original.y === undefined ? undefined : original.y);

        return self;
    };

    // private
    var graphSeries = function (original, childCaseTypes, fixtures, lang, langs) {
        var self = pairConfiguration(original);
        original = original || {};
        childCaseTypes = childCaseTypes || [];
        fixtures = fixtures || [];
        self.lang = lang;
        self.langs = langs;

        function origOrDefault(prop, fallback) {
            return original[prop] === undefined ? fallback : original[prop];
        }

        self.getFixtureInstanceId = function (fixtureName) {
            return "item-list:" + fixtureName;
        };

        /**
         * Return the default value for the data path field based on the given source.
         * This is used to change the data path field when a new source type is selected.
         * @param source
         * @returns {string}
         */
        self.getDefaultDataPath = function (source) {
            if (source.type === "custom") {
                return "instance('name')/root/path-to-point/point";
            } else if (source.type === 'case') {
                return "instance('casedb')/casedb/case[@case_type='" + source.name + "'][@status='open'][index/parent=current()/@case_id]";
            } else if (source.type === 'fixture') {
                return "instance('" + self.getFixtureInstanceId(source.name) + "')/" + source.name + "_list/" + source.name;
            }
        };

        self.sourceOptions = ko.observableArray(origOrDefault(
            'sourceOptions',
            _.map(childCaseTypes, function (s) {
                return {
                    'text': "Child case: " + s,
                    'value': {
                        'type': 'case',
                        'name': s,
                    },
                };
            }).concat(_.map(fixtures, function (s) {
                return {
                    'text': "Lookup table: " + s,
                    'value': {
                        type: 'fixture',
                        name: s,
                    },
                };
            })).concat([{
                'text': 'custom',
                'value': 'custom',
            }])
        ));

        self.selectedSource = ko.observable(origOrDefault('selectedSource', self.sourceOptions()[0]));
        // Fix selectedSource reference:
        //  (selectedSource has to be a reference to an object in sourceOptions.
        //   Thus, when original specifies a selectedSource we must find the matching
        //   object in sourceOptions.)
        if (!_.contains(self.sourceOptions(), self.selectedSource())) {
            var curSource = self.selectedSource();
            var source = _.find(self.sourceOptions(), function (opt) {
                return _.isEqual(opt, curSource);
            });
            self.selectedSource(source);
        }
        self.dataPath = ko.observable(origOrDefault('dataPath', self.getDefaultDataPath(self.selectedSource().value)));
        self.dataPathPlaceholder = ko.observable(origOrDefault('dataPathPlaceholder', ""));
        self.showDataPath = ko.observable(origOrDefault('showDataPath', false));
        self.xFunction = ko.observable(origOrDefault('xFunction', ""));
        self.xPlaceholder = ko.observable(origOrDefault('xPlaceholder', ""));
        self.yFunction = ko.observable(origOrDefault('yFunction', ""));
        self.yPlaceholder = ko.observable(origOrDefault('yPlaceholder', ""));
        self.copyPlaceholder = function (series, e) {
            var $button = $(e.currentTarget);
            var clipboard = new Clipboard($button[0]);
            $button.tooltip({
                title: gettext('Copied!'),
            });
            clipboard.on('success', function () {
                $button.tooltip('show');
                window.setTimeout(function () {
                    $button.tooltip('hide');
                }, 1000);
            });
            clipboard.onClick(e);
        };

        var seriesValidationWarning = gettext(
            "It is recommended that you leave this value blank. Future changes to your report's " +
            "chart configuration will not be reflected here."
        );
        self.dataPathWarning = ko.computed(function () {
            if (!self.dataPathPlaceholder() || !self.dataPath()) {
                return;
            }
            self.showDataPath(true);
            return seriesValidationWarning;
        });
        self.xWarning = ko.computed(function () {
            if (!self.xPlaceholder() || !self.xFunction()) {
                return;
            }
            return seriesValidationWarning;
        });
        self.yWarning = ko.computed(function () {
            if (!self.yPlaceholder() || !self.yFunction()) {
                return;
            }
            return seriesValidationWarning;
        });
        self.showDataPathCopy = ko.computed(function () {
            return self.dataPathPlaceholder() && !self.dataPathWarning();
        });
        self.showXCopy = ko.computed(function () {
            return self.xPlaceholder() && !self.xWarning();
        });
        self.showYCopy = ko.computed(function () {
            return self.yPlaceholder() && !self.yWarning();
        });
        self.xLabel = "X";
        self.yLabel = "Y";
        self.configPropertyOptions = [
            '',
            'fill-below',
            'line-color',
            'name',
            'x-name',
        ];
        self.configPropertyHints = {
            'fill-below': "ex: '#aarrggbb'",
            'line-color': "ex: '#aarrggbb'",
            'name': "ex: 'My Y-Values 1'",
            'x-name': "ex: 'My X-Values'",
        };
        self.localeSpecificConfigurations = ko.observableArray(_.map(
            ['name', 'x-name'],
            function (s) {
                return localizedConfigPropertyValuePair({
                    'property': s,
                    'lang': self.lang,
                    'langs': self.langs,
                });
            }
        ));
        if (original.localeSpecificConfigurations && original.localeSpecificConfigurations.length !== 0) {
            self.localeSpecificConfigurations(_.map(original.localeSpecificConfigurations, function (o) {
                return localizedConfigPropertyValuePair(o);
            }));
        }
        self.localeSpecificConfigurations.sort();

        self.toggleShowDataPath = function () {
            self.showDataPath(!self.showDataPath());
        };
        self.selectedSource.subscribe(function (newValue) {
            if (newValue.value === "custom") {
                self.showDataPath(true);
            }
            self.dataPath(self.getDefaultDataPath(newValue.value));
        });

        return self;
    };

    // private
    var xyGraphSeries = function (original, childCaseTypes, fixtures, lang, langs) {
        var self = graphSeries(original, childCaseTypes, fixtures, lang, langs);
        self.configPropertyOptions = self.configPropertyOptions.concat(['is-data', 'point-style', 'secondary-y']);
        self.configPropertyHints['is-data'] = 'true() or false()';
        // triangle-up and triangle-down are also options
        self.configPropertyHints['point-style'] = "'none', 'circle', 'cross', 'diamond', ...";
        self.configPropertyHints['secondary-y'] = 'true() or false()';
        return self;
    };

    // private
    var barGraphSeries = function (original, childCaseTypes, fixtures, lang, langs) {
        var self = graphSeries(original, childCaseTypes, fixtures, lang, langs);

        self.xLabel = "Label";
        self.yLabel = "Value";
        self.configPropertyOptions = self.configPropertyOptions.concat(['bar-color']);
        self.configPropertyHints['bar-color'] = "if(x > 100, '#55ff00ff', 'ffff00ff')";

        return self;
    };

    // private
    var bubbleGraphSeries = function (original, childCaseTypes, fixtures, lang, langs) {
        var self = xyGraphSeries(original, childCaseTypes, fixtures, lang, langs);

        self.radiusFunction = ko.observable(original.radiusFunction === undefined ? "" : original.radiusFunction);
        self.configPropertyOptions = self.configPropertyOptions.concat(['max-radius']);
        self.configPropertyHints['max-radius'] = 'ex: 7';

        return self;
    };

    return {
        graphConfigurationUiElement: graphConfigurationUiElement,
    };
});
