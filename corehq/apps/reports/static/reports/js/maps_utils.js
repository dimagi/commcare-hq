hqDefine("reports/js/maps_utils", function () {
    var module = {};
    module.displayDimensions = ['size', 'color', 'icon'];
    module.tableToggle = false;

    function setMapHeight(map, animate) {
        var $map = $('#map');
        var height = $(window).height() - $map.offset().top;
        if (module.tableToggle) {
            height *= .6;
        } else {
            height -= 0.5 * $('.datatable thead').height();
        }
        height = Math.max(height, 300);
        if (animate) {
            $map.animate({
                height: height,
            }, null, null, function () {
                map.invalidateSize();
            });
        } else {
            $map.height(height);
            map.invalidateSize();
        }
    }

    function forEachDimension(metric, callback) {
        $.each(module.displayDimensions, function (i, e) {
            if (typeof metric[e] === 'object') {
                callback(e, metric[e]);
            }
        });
    }

    // iterate over all metrics, which can potentially be stored in a tree structure
    function forEachMetric(metrics, callback) {
        $.each(metrics, function (i, e) {
            if (e.group) {
                forEachMetric(e.children, callback);
            } else {
                callback(e);
            }
        });
    }

    function MetricsViewModel(control) {
        var model = this;

        model.root = ko.observable();
        model.defaultMetric = null;

        model.load = function (metrics) {
            this.root(new MetricModel({
                title: '_root',
                children: metrics,
            }, null, this));
            this.root().expanded(true);

            if (this.defaultMetric) {
                this.defaultMetric.onclick();
            } else {
                this.renderMetric(null);
            }
        };

        model.renderMetric = function (metric) {
            control.render(metric);
        };

        model.unselectAll = function () {
            var unselect = function (node) {
                $.each(node.children(), function (i, e) {
                    unselect(e);
                });
                node.selected(false);
            };
            unselect(this.root());
        };
    }

    function MetricModel(data, parent, root) {
        var m = this;

        m.metric = null;
        m.name = ko.observable();
        m.children = ko.observableArray();
        m.expanded = ko.observable(false);
        m.selected = ko.observable(false);
        m.parent = parent;

        m.group = ko.computed(function () {
            return this.children().length > 0;
        }, m);

        m.onclick = function () {
            if (this.group()) {
                this.toggle();
            } else {
                this.select();
                root.renderMetric(this.metric);
            }
        };

        m.toggle = function () {
            this.expanded(!this.expanded());
        };

        m.select = function () {
            root.unselectAll();

            var node = this;
            while (node != null) {
                node.selected(true);
                node.expanded(true);
                node = node.parent;
            }
        };

        m.load = function (data) {
            this.metric = data;
            this.name(data.title);
            this.children($.map(data.children || [], function (e) {
                return new MetricModel(e, m, root);
            }));
            if (data['default']) {
                root.defaultMetric = this;
            }
        };

        m.load(data);
    }

    var LegendControl = L.Control.extend({
        options: {
            position: 'bottomright',
        },

        onAdd: function () {
            this.$div = $('#legend');
            this.div = this.$div[0];
            return this.div;
        },

        render: function (metric) {
            if (metric == null) {
                this.$div.hide();
                return;
            }

            this.$div.show();
            this.$div.empty();
            renderLegend(this.$div, metric, this.options.config);
        },
    });

    var HeadsUpControl = L.Control.extend({
        options: {
            position: 'bottomright',
        },

        onAdd: function () {
            this.$div = $('#info');
            this.div = this.$div[0];
            return this.div;
        },

        setActive: function (feature, metric) {
            if (feature == null ||
                (metric == null && !this.options.config.name_column)) { // nothing to show
                this.$div.hide();
                return;
            }

            var cols = [];
            if (metric != null) {
                forEachDimension(metric, function (type, meta) {
                    var col = meta.column;
                    if (cols.indexOf(col) == -1) {
                        cols.push(col);
                    }
                });
            }

            var context = infoContext(feature, this.options.config, cols);
            var TEMPLATE = $('#info_popup').text();
            var template = _.template(TEMPLATE);
            var content = template(context);
            this.$div.html(content);
            this.$div.show();
        },
    });

    // a control button that will fit the map viewport to the currently displayed data
    var ZoomToFitControl = L.Control.extend({
        options: {
            position: 'topright',
        },

        onAdd: function (map) {
            this.$div = $('#zoomtofit');
            this.$div.find('#zoomtofit-target').click(function () {
                zoomToAll(map);
            });
            return this.$div[0];
        },
    });

    // a control button to scroll table into view
    var ToggleTableControl = L.Control.extend({
        options: {
            position: 'topright',
        },

        onAdd: function (map) {
            this.$div = $('#toggletable');
            this.$div.find('#toggletable-target').click(function () {
                module.tableToggle = !module.tableToggle;
                setMapHeight(map, true);
            });
            return this.$div[0];
        },
    });

    // a wordmark for mapbox
    var MapBoxWordMark = L.Control.extend({
        options: {
            position: 'bottomleft',
        },

        onAdd: function () {
            var div = L.DomUtil.create('div', 'map');
            div.innerHTML = '<a href="http://mapbox.com/about/maps" class="mapbox-wordmark" target="_blank">Mapbox</a>';
            return div;
        },
    });



    function load(context, iconPath) {
        L.Icon.Default.imagePath = iconPath;
        var map = mapsInit(context);

        var resize = function () {
            setMapHeight(map);
        };
        $(window).resize(resize);
        $('#reportFiltersAccordion').on('shown', resize);
        $('#reportFiltersAccordion').on('hidden', resize);
        resize();
    }

    // perform any pre-processing of the raw data
    function initData(data, config) {
        // instantiate data formatting functions
        config._fmt = {};
        $.each(config.numeric_format || {}, function (k, v) {
            try {
                // TODO allow these functions to access other properties for that row?
                config._fmt[k] = eval('(function(x) { ' + v + '})');
            } catch (err) {
                console.log('error in formatter function [' + v + ']');
            }
        });

        // make a default detail view if not specified
        if (config.detail_columns == null) {
            config.detail_columns = getAllCols(config, data);
        }
        if (config.table_columns == null) {
            config.table_columns = config.detail_columns.slice(0);
        }

        // typecast values
        $.each(data.features, function (i, e) {
            $.each(e.properties, function (k, v) {
                e.properties[k] = typecast(v);
            });
        });

        // pre-cache popup detail
        $.each(data.features, function (i, e) {
            e.popupContent = formatDetailPopup(e, config);
        });

        // show any alerts
        processMetadata(data.metadata || {});
    }

    // set up the configured display metrics
    function initMetrics(map, table, data, config) {
        // auto-generate metrics from data columns (if none provided)
        if (!config.metrics || config.debug) {
            autoConfiguration(config, data);
        }

        if (config.metrics) {
            config.metrics = ([]).concat([{
                title: 'Auto',
                group: true,
                children: config.metrics,
            }]);
        }
        // set sensible defaults for metric parameters (if omitted)
        forEachMetric(config.metrics, function (metric) {
            setMetricDefaults(metric, data, config);
        });

        // typecast values
        $.each(config.metrics, function (i, e) {
            forEachDimension(e, function (dim, meta) {
                if (meta.thresholds) {
                    meta.thresholds = _.map(meta.thresholds, typecast);
                }
                if (meta.colorstops) {
                    meta.colorstops = _.map(meta.colorstops, function (e) {
                        return [typecast(e[0]), e[1]];
                    });
                }
                if (meta.categories) {
                    var _cat = {};
                    $.each(meta.categories, function (k, v) {
                        _cat[typecast(k)] = v;
                    });
                    meta.categories = _cat;
                }
            });
        });

        // necessary closures (TODO make a class?)
        forEachMetric(config.metrics, function (metric) {
            forEachDimension(metric, function (type, meta) {
                meta._enumCaption = function (val, labelFallbacks) {
                    return getEnumCaption(meta.column, val, config, labelFallbacks);
                };
                meta._formatNum = function (val) {
                    return formatValue(meta.column, val, config);
                };
            });
        });

        var l = new LegendControl({
            config: config,
        }).addTo(map);
        var h = new HeadsUpControl({
            config: config,
        }).addTo(map);
        var metrics = {
            metrics: config.metrics,
            data: data,
            legend: l,
            info: h,
        };
        if (table !== undefined) {
            metrics.table = table;
        }
        var m = new MetricsControl(metrics).addTo(map);

        zoomToAll(map);
    }

    function initLayers(map, layersSpec) {
        var LAYER_FAMILIES = {
            'fallback': {
                url_template: 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                args: {
                    attribution: '<a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
                },
            },
            'mapbox': {
                url_template: 'http://api.tiles.mapbox.com/v3/{apikey}/{z}/{x}/{y}.png',
                args: {
                    attribution: '<a href="http://www.mapbox.com/about/maps/">MapBox</a>',
                },
            },
        };

        var mkLayer = function (spec) {
            if (spec.family) {
                var familySpec = LAYER_FAMILIES[spec.family];
                spec.url_template = familySpec.url_template;
                spec.args = spec.args || {};
                $.each(familySpec.args || {}, function (k, v) {
                    spec.args[k] = v;
                });
            }
            return L.tileLayer(spec.url_template, spec.args);
        };

        var layers = {};
        var defaultLayer = null;
        $.each(layersSpec, function (k, v) {
            layers[k] = mkLayer(v);
            if (v['default']) {
                defaultLayer = k;
            }
        });
        L.control.layers(layers).addTo(map);

        if (!defaultLayer) {
            defaultLayer = _.keys(layers)[0];
        }
        map.addLayer(layers[defaultLayer]);
    }

    function processMetadata(metadata) {
        if (metadata.capped_rows) {
            var $capped = $('#results-capped');
            $capped.show();
            $capped.find('#rows-total').text(metadata.total_rows);
            $capped.find('#rows-capped').text(metadata.capped_rows);
        }
    }

    function zoomToAll(map) {
        if (map.activeOverlay) {
            setTimeout(function () {
                var bounds = map.activeOverlay.getBounds();
                if (bounds.isValid()) {
                    map.fitBounds(map.activeOverlay.getBounds(), {
                        padding: [60, 60],
                    });
                }
            }, 0); // run at next tick to avoid race condition and freeze
            // (https://github.com/Leaflet/Leaflet/issues/2021)
        }
    }

    // generate the proper geojson styling for the given display metric
    function makeDisplayContext(metric, setActiveFeature) {
        return {
            filter: function (feature, layer) {
                if (feature.geometry.type == "Point") {
                    feature._conf = markerFactory(metric, feature.properties);
                } else {
                    feature._conf = featureStyle(metric, feature.properties);
                }
                // TODO support placeholder markers for 'null' instead of hiding entirely?
                // store visibility on the feature object so datatables can access it
                feature.visible = (feature._conf != null);
                if (!feature.visible) {
                    if (!feature.$tr) {
                        return feature.visible;
                    }
                    feature.$tr.addClass('inactive-row');
                }
                return feature.visible;
            },
            style: function (feature) {
                return feature._conf;
            },
            pointToLayer: function (feature, latlng) {
                return feature._conf(latlng);
            },
            onEachFeature: function (feature, layer) {
                // popup
                layer.bindPopup(feature.popupContent, {
                    maxWidth: 600,
                    autoPanPadding: [200, 100],
                });
                var tableEnabled = feature.$tr; // todo: might want to make this more explicit

                var handlePopups = function () {
                    // open popup on table row click / highlight table row on popup open
                    var selectRow = function ($tr) {
                        $('#tabular tr').removeClass('selected-row');
                        if ($tr != null) {
                            $tr.addClass('selected-row');
                        }
                    };

                    feature.$tr.click(function () {
                        var popupAnchor = null;
                        $(".selected-row").removeClass('selected-row');
                        if (layer.getBounds) { // polygon layer
                            popupAnchor = layer.getBounds().getCenter();
                            // TODO would be better to compute polygon centroid
                        }
                        layer.openPopup(popupAnchor);
                        // FIXME openPopup seems to crash for MultiPolygons (https://github.com/Leaflet/Leaflet/issues/2046)
                        selectRow(feature.$tr);
                    });
                    layer.on('popupopen', function () {
                        selectRow(feature.$tr);
                    });
                    layer.on('popupclose', function () {
                        selectRow(null);
                    });
                };


                if (tableEnabled) {
                    handlePopups();
                }

                // highlight layer / table row on hover-over
                if (feature.geometry.type != 'Point') {
                    layer._activate = function () {
                        layer.setStyle(module.activeStyle);
                    };
                    layer._deactivate = function () {
                        layer.setStyle(feature._conf);
                    };
                }
                var hoverOn = function () {
                    if (layer._activate) {
                        layer._activate();
                        if (layer.bringToFront) {
                            // normal markers don't have this method; mimic with 'riseOnHover'
                            layer.bringToFront();
                        }
                    }
                    if (tableEnabled) {
                        feature.$tr.addClass('hover-row');
                    }
                    setActiveFeature(feature);
                };
                var hoverOff = function () {
                    if (layer._deactivate) {
                        layer._deactivate();
                    }
                    if (tableEnabled) {
                        feature.$tr.removeClass('hover-row');
                    }
                    setActiveFeature(null);
                };
                layer.on({
                    mouseover: hoverOn,
                    mouseout: hoverOff,
                });
                if (tableEnabled) {
                    feature.$tr.hover(hoverOn, hoverOff);
                }

            },
        };
    }

    function markerFactory(metric, props) {
        if (metric == null) {
            return defaultMarker(props);
        }

        try {
            if (metric.icon) {
                return iconMarker(metric, props);
            } else {
                return circleMarker(metric, props);
            }
        } catch (err) {
            // marker cannot be rendered due to data error
            // TODO log or display 'error' marker?
            console.log(err);
            return null;
        }
    }

    function featureStyle(metric, props) {
        if (metric == null) {
            return defaultFeatureStyle(props);
        }

        try {
            var fill = getColor(metric.color, props);
            if (fill == null) {
                return null;
            }

            return {
                color: "#000",
                weight: 1,
                opacity: 1,
                fillColor: fill.color,
                fillOpacity: fill.alpha,
            };
        } catch (err) {
            // marker cannot be rendered due to data error
            // TODO log or display 'error' marker?
            console.log(err);
            return null;
        }
    }

    module.activeStyle = {
        color: '#ff0',
        weight: 2,
        opacity: 1,
    };

    function mkMarker(latlng, options) {
        options = options || {};
        options.riseOnHover = true;

        var marker = new L.marker(latlng, options);
        marker._activate = function () {
            $(marker._icon).addClass('glow');
        };
        marker._deactivate = function () {
            $(marker._icon).removeClass('glow');
        };

        return marker;
    }

    function defaultMarker() {
        return mkMarker;
    }

    function defaultFeatureStyle() {
        return {
            color: "#000",
            weight: 1,
            opacity: .8,
            fillColor: '#888',
            fillOpacity: .3,
        };
    }

    function circleMarker(metric, props) {
        var size = getSize(metric.size, props);
        var fill = getColor(metric.color, props);
        if (size == null || fill == null) {
            return null;
        }

        return function (latlng) {
            var style = {
                color: "#000",
                weight: 1,
                opacity: 1,
                radius: size,
                fillColor: fill.color,
                fillOpacity: fill.alpha,
            };
            var marker = L.circleMarker(latlng, style);
            marker._activate = function () {
                marker.setStyle(module.activeStyle);
            };
            marker._deactivate = function () {
                marker.setStyle(style);
            };
            return marker;
        };
    }

    function iconMarker(metric, props) {
        var icon = getIcon(metric.icon, props);
        if (icon == null) {
            return null;
        }

        return function (latlng) {
            var marker = mkMarker(latlng, {
                icon: L.icon({
                    iconUrl: icon.url,
                }),
            });
            var img = new Image();
            img.onload = function () {
                // leaflet needs explicit icon dimensions
                marker.setIcon(L.icon({
                    iconUrl: icon.url,
                    iconSize: [this.width, this.height],
                }));
            };
            img.src = icon.url;

            return marker;
        };
    }

    var DEFAULT_SIZE = 10;
    var DEFAULT_MIN_SIZE = 3;

    function getSize(meta, props) {
        if (meta == null) {
            return DEFAULT_SIZE;
        } else if (isNumeric(meta)) {
            return meta;
        } else {
            var val = getPropValue(props, meta);
            if (isNull(val)) {
                return null;
            } else if (!isNumeric(val)) {
                throw new TypeError('numeric value required [' + val + ']');
            }

            return Math.min(Math.max(markerSize(val, meta.baseline), meta.min || DEFAULT_MIN_SIZE), meta.max || 9999);
        }
    }

    // scale value with area of marker
    function markerSize(val, baseline) {
        return DEFAULT_SIZE * Math.sqrt(val / baseline);
    }

    var DEFAULT_COLOR = 'rgba(255, 120, 0, .8)';

    function getColor(meta, props) {
        var c = (function () {
            if (meta == null) {
                return DEFAULT_COLOR;
            } else if (typeof meta === 'string') {
                return meta;
            } else {
                var val = getPropValue(props, meta);
                if (meta.categories) {
                    return matchCategories(val, meta.categories);
                } else {
                    if (isNull(val)) {
                        return null;
                    } else if (!isNumeric(val)) {
                        throw new TypeError('numeric value required [' + val + ']');
                    } else {
                        return matchSpline(val, meta.colorstops, blendColor);
                    }
                }
            }
        })();
        if (c == null) {
            return null;
        }

        c = $.Color(c);
        return {
            color: c.toHexString(),
            alpha: c.alpha(),
        };
    }

    function getIcon(meta, props) {
        //TODO support css sprites
        var icon = (function () {
            if (typeof meta === 'string') {
                return meta;
            } else {
                var val = getPropValue(props, meta);
                return matchCategories(val, meta.categories);
            }
        })();
        if (icon == null) {
            return null;
        }
        return {
            url: icon,
        };
    }

    function getPropValue(props, meta) {
        var val = props[meta.column];
        if (isNull(val)) {
            return null;
        }

        if (meta.thresholds) {
            if (!isNumeric(val)) {
                throw new TypeError('numeric value required [' + val + ']');
            }
            val = matchThresholds(val, meta.thresholds);
        }
        return val;
    }

    // return formatted info about a row/feature, suitable for display
    // in different places (detail popup, hover infobox, table row, etc.)
    function infoContext(feature, config, mode) {
        var propCols = _.keys(feature.properties);
        var infoCols;
        if (mode == null) {
            throw "no context mode provided!";
        } else if (mode == 'detail') {
            infoCols = config.detail_columns;
        } else if (mode == 'table') {
            infoCols = getTableColumns(config, true);
        } else {
            // 'mode' is an explicit list (subset) of columns
            propCols = mode;
            infoCols = mode;
        }
        var formatForDisplay = function (col, datum) {
            // if display value was explicitly provided from server, use it above all else
            // note: this pattern has drawbacks -- namely the browser doesn't know how to
            // properly format legend labels -- so should only really be used for
            // backwards compatibility or prototyping
            var displayOverrideCol = '__disp_' + col;
            if (_.has(feature.properties, displayOverrideCol)) {
                return feature.properties[displayOverrideCol];
            }

            var fallback = {
                _null: '\u2014',
            };
            fallback[datum] = formatValue(col, datum, config);
            return getEnumCaption(col, datum, config, fallback);
        };
        var displayProperties = {};
        var rawProperties = {};
        var propTitles = {};
        $.each(propCols, function (i, k) {
            var v = feature.properties[k];
            displayProperties[k] = formatForDisplay(k, v);
            rawProperties[k] = (v instanceof Date ? v.getTime() : v);
            // can't use iso date as sort key; datatables expects numeric sorting for date columns
            propTitles[k] = getColumnTitle(k, config);
        });

        var context = {
            props: displayProperties,
            raw: rawProperties,
            titles: propTitles,
            name: (config.name_column ? feature.properties[config.name_column] : null),
            info: [],
        };
        $.each(infoCols, function (i, e) {
            context.info.push({
                slug: e, // FIXME this will cause problems if column keys have weird chars or spaces
                label: propTitles[e],
                value: displayProperties[e],
                raw: rawProperties[e],
            });
        });

        return context;
    }

    function formatDetailPopup(feature, config) {
        var DEFAULT_TEMPLATE = $('#default_detail_popup').text();
        var TEMPLATE = config.detail_template || DEFAULT_TEMPLATE;

        var template = _.template(TEMPLATE);
        var content = template(infoContext(feature, config, 'detail'));
        return content;
    }

    // attempt to set sensible defaults for any missing parameters in the metric definitions
    function setMetricDefaults(metric, data, config) {
        if (metric.auto) {
            // must update metric in place
            _.extend(metric, autoMetricForColumn(metric.auto, data));
            delete metric.auto;
        }

        if (!metric.title) {
            var varcols = [];
            forEachDimension(metric, function (type, meta) {
                var col = meta.column;
                if (varcols.indexOf(col) == -1) {
                    varcols.push(col);
                }
            });
            metric.title = $.map(varcols, function (e) {
                return getColumnTitle(e, config);
            }).join(' / ');
        }

        if (typeof metric.size === 'object') {
            if (!metric.size.baseline) {
                var stats = summarizeColumn(metric.size, data);
                metric.size.baseline = (stats.mean || 1);
            }
        }

        if (typeof metric.color === 'object') {
            if (!metric.color.categories && !metric.color.colorstops) {
                var stats = summarizeColumn(metric.color, data);
                var numericData = (!metric.color.thresholds && !stats.nonnumeric);
                if (numericData) {
                    metric.color.colorstops = (magnitudeBasedField(stats) ?
                        [
                            [0, 'rgba(20, 20, 20, .8)'],
                            [stats.max || 1, DEFAULT_COLOR],
                        ] :
                        [
                            [stats.min, 'rgba(0, 0, 255, .8)'],
                            [stats.min == stats.max ? 0 : stats.max, 'rgba(255, 0, 0, .8)'],
                        ]);
                } else {
                    if (metric.color.thresholds) {
                        var enums = metric.color.thresholds.slice(0);
                        enums.splice(0, 0, '-');
                    } else {
                        var enums = stats.distinct;
                    }

                    var cat = {};
                    $.each(enums, function (i, e) {
                        var hue = i * 360. / enums.length;
                        cat[e] = 'hsla(' + hue + ', 100%, 50%, .8)';
                    });
                    metric.color.categories = cat;
                }
            }
        }

        if (typeof metric.icon === 'object') {
            if (!metric.icon.categories) {
                metric.icon.categories = {
                    _other: '/static/reports/css/leaflet/images/default_custom.png',
                };
            }
        }
    }

    function getAllCols(config, data) {
        var isIgnored = function (col) {
            var ignoreCols = [config.name_column];
            var ignorePrefix = '__disp_';
            return (ignoreCols.indexOf(col) != -1 ||
                col.indexOf(ignorePrefix) == 0);
        };

        var _cols = {};
        $.each(data.features, function (i, e) {
            $.each(e.properties, function (k) {
                if (!isIgnored(k)) {
                    _cols[k] = true;
                }
            });
        });
        return _.sortBy(_.keys(_cols), function (e) {
            return getColumnTitle(e, config);
        });
    }

    function autoConfiguration(config, data) {
        var metrics = $.map(getAllCols(config, data), function (e) {
            return {
                auto: e,
            };
        });
        // metrics may already exist if we're in debug mode
        config.metrics = (config.metrics || []).concat([{
            title: 'Auto',
            group: true,
            children: metrics,
        }]);
    }

    function autoMetricForColumn(col, data) {
        var meta = {
            column: col,
        };
        var stats = summarizeColumn(meta, data);
        var metric = {};
        if (stats.nonnumeric || !magnitudeBasedField(stats) || stats.nonpoint) {
            metric.color = meta;
        } else {
            metric.size = meta;
        }
        return metric;
    }

    function summarizeColumn(meta, data) {
        // cache the computed results
        if (!meta._stats) {
            meta._stats = _summarizeColumn(meta, data);
            //console.log(meta.column, meta._stats);
        }
        return meta._stats;
    }

    // compute statistics on a given column of data for the purpose of determining
    // sensible styling defaults
    function _summarizeColumn(meta, data) {
        var _uniq = {};
        var sum = 0;
        var count = 0; // of numeric values only
        var min = null;
        var max = null;
        var nonnumeric = false;
        var nonpoint = false;
        var hasDates = false;

        var iterate = function (callback) {
            $.each(data.features, function (i, e) {
                var val = getPropValue(e.properties, meta);
                if (isNull(val)) {
                    return;
                }

                var numeric = isNumeric(val);
                var polygon = e.geometry.type != 'Point';
                if (numeric && !(val instanceof Date)) {
                    val = +val;
                }
                callback(val, numeric, polygon);
            });
        };

        iterate(function (val, numeric, polygon) {
            _uniq[val] = true;
            if (numeric) {
                if (val instanceof Date) {
                    hasDates = true;
                }

                count++;
                sum += val;
                // note: Math.min/max will not preserve dates
                min = (min == null || val < min ? val : min);
                max = (max == null || val > max ? val : max);
            } else {
                nonnumeric = true;
            }
            if (polygon) {
                nonpoint = true;
            }
        });
        var uniq = [];
        $.each(_uniq, function (k) {
            uniq.push(k);
        });
        uniq.sort();

        var mean = (count > 0 ? sum / count : null);
        var stdev = null;
        if (count > 1) {
            var _accum = 0;
            iterate(function (val, numeric) {
                if (numeric) {
                    _accum += Math.pow(val - mean, 2.);
                }
            });
            stdev = Math.sqrt(_accum / (count - 1));
        }

        return {
            distinct: uniq,
            mean: mean,
            stdev: stdev,
            min: min,
            max: max,
            nonnumeric: nonnumeric,
            nonpoint: nonpoint,
            hasDates: hasDates,
        };
    }

    // based on the results of summarizeColumn, determine if this column is better
    // represented as a magnitude (0-max) or narrower range (min-max)
    function magnitudeBasedField(stats) {
        if (stats.min < 0 || stats.hasDates) {
            return false;
        } else if (stats.stdev != null && stats.stdev > 0) {
            var effectiveRange = Math.max(stats.max, 0) - Math.min(stats.min, 0);
            return (stats.stdev / effectiveRange > .1);
        } else {
            return true;
        }
    }

    function getEnumValues(meta) {
        var labelFallbacks = {};
        var toLabel = function (e) {
            return meta._enumCaption(e, labelFallbacks);
        };

        if (meta.thresholds) {
            var enums = meta.thresholds.slice(0);
            enums.splice(0, 0, '-');

            $.each(enums, function (i, e) {
                labelFallbacks[e] = (function () {
                    if (i == 0) {
                        return '< ' + meta._formatNum(enums[1]);
                    } else if (i == enums.length - 1) {
                        return '> ' + meta._formatNum(e);
                    } else {
                        return meta._formatNum(e) + ' \u2013 ' + meta._formatNum(enums[i + 1]);
                    }
                })();
            });

            if (meta.categories && meta.categories._null) {
                enums.push('_null');
            }
        } else {
            var enums = _.keys(meta.categories);
            var special = _.filter(enums, function (e) {
                return e[0] == '_';
            });
            enums = _.filter(enums, function (e) {
                return e[0] != '_';
            });

            enums = _.sortBy(enums, toLabel);
            // move special categories to the end
            $.each(['_other', '_null'], function (i, e) {
                if (special.indexOf(e) != -1) {
                    enums.push(e);
                }
            });
        }

        return $.map(enums, function (e) {
            return {
                label: toLabel(e),
                value: e,
            };
        });
    }

    function getEnumCaption(column, value, config, fallbacks) {
        if (isNull(value)) {
            value = '_null';
        }
        var captions = (config.enum_captions || {})[column] || {};

        fallbacks = fallbacks || {};
        $.each({
            '_other': gettext('Other'),
            '_null': gettext('No Data'),
        }, function (k, v) {
            fallbacks[k] = fallbacks[k] || v;
        });
        var fallback = fallbacks[value] || value;

        return captions[value] || fallback;
    }

    function formatValue(column, value, config) {
        if (isNull(value)) {
            return null;
        }

        var defaultFormat = function (val) {
            var raw = '' + val;

            if (val instanceof Date) {
                // this is janky -- just crop out tz cruft and seconds
                return raw.substring(0, 21) + ' ' + raw.substring(28, 33);
            } else {
                // TODO default format for numbers (add commas, etc.)
                return raw;
            }
        };

        var formatter = config._fmt[column] || defaultFormat;
        return formatter(value);
    }

    function getColumnTitle(col, config) {
        return (config.column_titles || {})[col] || col;
    }

    function getTableColumns(config, flat) {
        if (flat) {
            return config._table_columns_flat;
        }

        var cols = config.table_columns.slice(0);
        if (config.name_column) {
            cols.splice(0, 0, config.name_column);
        }
        return cols;
    }

    function renderLegend($e, metric, config) {
        forEachDimension(metric, function (type, meta) {
            var col = meta.column;
            var $h = $('<h4>');
            $h.text(getColumnTitle(col, config));
            $e.append($h);

            var $div = $('<div>');
            ({
                size: sizeLegend,
                color: colorLegend,
                icon: iconLegend,
            })[type]($div, meta);
            $e.append($div);
        });
    }

    function sizeLegend($e, meta) {
        var rows = $.map([.5, 0, -.5], function (e) {
            var val = niceRoundNumber(Math.pow(10., e) * meta.baseline);
            return {
                val: val,
                valfmt: meta._formatNum(val),
                radius: markerSize(val, meta.baseline),
            };
        });

        var $rendered = $(_.template($('#legend_size').text())({
            entries: rows,
        }));

        $.each(rows, function (i, e) {
            var $r = $rendered.find('#sizerow-' + i);
            var diameter = 2 * e.radius;
            $r.find('.circle').css('width', diameter + 'px');
            $r.find('.circle').css('height', diameter + 'px');
        });

        $e.append($rendered);
    }

    function colorLegend($e, meta) {
        if (meta.colorstops) {
            colorScaleLegend($e, meta);
        } else {
            enumLegend($e, meta, function ($cell, value) {
                $cell.css('background-color', value);
            });
        }
    }

    function iconLegend($e, meta) {
        enumLegend($e, meta, function ($cell, value) {
            var $icon = $('<img>');
            $icon.attr('src', value);
            $cell.append($icon);
        });
    }

    var SCALEBAR_HEIGHT = 150; //px
    var SCALEBAR_WIDTH = 20; // TODO seems like we want to tie this to em-height instead
    var TICK_SPACING = 40; //px
    var MIN_BUFFER = 15; //px
    function colorScaleLegend($e, meta) {
        var EPOCH2000 = 946684800;
        var fromDate = function (s) {
            return s / 1000. - EPOCH2000;
        };
        var toDate = function (s) {
            return new Date((s + EPOCH2000) * 1000.);
        };

        var min = meta.colorstops[0][0];
        var max = meta.colorstops.slice(-1)[0][0];
        var dateScale = (min instanceof Date);
        if (dateScale) {
            min = fromDate(min);
            max = fromDate(max);
        }
        var range = max - min;
        var step = range / (SCALEBAR_HEIGHT - 1);

        var $canvas = makeConvas(SCALEBAR_WIDTH, SCALEBAR_HEIGHT);
        var ctx = $canvas[0].getContext('2d');
        for (var i = 0; i < SCALEBAR_HEIGHT; i++) {
            var k = i / (SCALEBAR_HEIGHT - 1);
            var x = blendLinear(min, max, k);
            var y = $.Color(matchSpline(dateScale ? toDate(x) : x, meta.colorstops, blendColor)).toRgbaString();
            ctx.fillStyle = y;
            ctx.fillRect(0, SCALEBAR_HEIGHT - 1 - i, SCALEBAR_WIDTH, 1);
        }

        var interval = (dateScale ? niceRoundInterval : niceRoundNumber)(step * TICK_SPACING);
        var tickvals = [];
        for (var j = interval * Math.ceil(min / interval); j <= max; j += interval) {
            // TODO snap date intervals >= 1 month to start of month
            tickvals.push(j);
        }
        var bufferDist = step * MIN_BUFFER;
        if (tickvals[0] - min > bufferDist) {
            tickvals.splice(0, 0, min);
        }
        if (max - tickvals.slice(-1)[0] > bufferDist) {
            tickvals.push(max);
        }

        var ticks = $.map(tickvals, function (e) {
            return {
                label: meta._formatNum(dateScale ? toDate(e) : e),
                coord: (1. - (e - min) / range) * SCALEBAR_HEIGHT,
            };
        });

        var $rendered = $(_.template($('#legend_colorscale').text())({
            ticks: ticks,
        }));
        $rendered.find('#scalebar').append($canvas);
        $e.append($rendered);
    }

    function enumLegend($e, meta, renderValue) {
        var enums = getEnumValues(meta);

        var $rendered = $(_.template($('#legend_enum').text())({
            enums: enums,
        }));

        $.each(enums, function (i, e) {
            var $r = $rendered.find('#enumrow-' + i);
            var cat = matchCategories(e.value, meta.categories);
            renderValue($r.find('.enum'), cat);
        });

        $e.append($rendered);
    }


    // note: Date objects are considered numeric
    function isNumeric(x) {
        return (!isNull(x) && !isNaN(+x));
    }

    function isNull(x) {
        return (x === undefined || x === null || x === '');
    }

    // convert certain json values to a more suitable type
    function typecast(x) {
        if (x === true) {
            return 'y';
        } else if (x === false) {
            return 'n';
        }

        // js date conversion is overzealous (e.g, 'Sample 2' parses as a valid date)
        // add regex check as a quick fix for now
        if (!isNumeric(x) && /[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}Z?)?/.test(x)) {
            var asDate = new Date(x);
            if (!isNaN(asDate.getTime())) {
                return asDate;
            }
        }

        return x;
    }



    // convert a numerical value into an enumerated value based on cutoff thresholds
    // 'thresholds' must be in ascending order
    // e.g., thresholds of [2, 5, 10] creates 4 buckets: <2; [2, 5); [5, 10); >=10
    // return the lower bound of the matching bucket, or '-' for the lowest bucket
    function matchThresholds(val, thresholds, returnIndex) {
        var cat = (returnIndex ? -1 : '-');
        $.each(thresholds, function (i, e) {
            if (e <= val) {
                cat = (returnIndex ? i : e);
            } else {
                return false;
            }
        });
        return cat;
    }

    // match an enumerated value to its display value
    // 'categories' is a mapping of enum values to display values
    // 'categories' may define a mapping for '_other', which will be used for
    // all values that do not have an explicit value assigned, otherwise
    // those values will resolve to null
    // 'categories' may also define a special mapping '_null' which will match
    // null values
    function matchCategories(val, categories) {
        if (isNull(val)) {
            return categories._null;
        } else if (_.has(categories, val)) {
            return categories[val];
        } else {
            return categories._other;
        }
    }

    // linearly interpolate a value along a spline specified by 'stops'
    // 'stops' is a list of [x, y] coordinates that map out a line
    // returns the y-value of this line for x-value = val
    // blendfunc may be provided if the y-values are not scalar
    function matchSpline(val, stops, blendfunc) {
        blendfunc = blendfunc || blendLinear;

        stops = _.sortBy(stops, function (e) {
            return e[0];
        });
        var x = [];
        var y = [];
        $.each(stops, function (i, e) {
            x.push(e[0]);
            y.push(e[1]);
        });

        var bracket = matchThresholds(val, x);
        var lo = (bracket === '-' ? -1 : x.indexOf(bracket));
        var hi = lo + 1;
        if (lo === -1) {
            return y[hi];
        } else if (hi === x.length) {
            return y[lo];
        } else {
            return blendfunc(y[lo], y[hi], (val - x[lo]) / (x[hi] - x[lo]));
        }
    }

    // linearly interpolate two values (a and b). k = 0.0 - 1.0
    function blendLinear(a, b, k) {
        return a * (1 - k) + b * k;
    }

    // linearly blend two colors together. a and b are colors; return a color
    // 'k' distance (0.0 - 1.0) from a to b.
    function blendColor(a, b, k) {
        var GAMMA = 2.2;

        // convert to linear color space and premultiply alpha
        var toLinear = function (c) {
            var channels = $.Color(c).rgba();
            for (var i = 0; i < 3; i++) {
                channels[i] = Math.pow((channels[i] + .5) / 256., GAMMA);
                channels[i] *= channels[3];
            }
            return channels;
        };

        // reverse toLinear()
        var fromLinear = function (channels) {
            for (var i = 0; i < 3; i++) {
                channels[i] /= channels[3];
                channels[i] = Math.floor(256. * Math.pow(channels[i], 1. / GAMMA));
            }
            return $.Color(channels);
        };

        var lA = toLinear(a);
        var lB = toLinear(b);
        var lBlend = [];
        for (var i = 0; i < 4; i++) {
            lBlend.push(blendLinear(lA[i], lB[i], k));
        }
        return fromLinear(lBlend);
    }

    function niceRoundNumber(x, stops, orderOfMagnitude) {
        orderOfMagnitude = orderOfMagnitude || 10;
        stops = stops || [1, 2, 5];
        // numbers will snap to .1, .2, .5, 1, 2, 5, 10, 20, 50, 100, 200, etc.

        var xLog = Math.log(x) / Math.log(orderOfMagnitude);
        var exponent = Math.floor(xLog);
        var xNorm = Math.pow(orderOfMagnitude, xLog - exponent);

        var getStop = function (i) {
            return (i === stops.length ? orderOfMagnitude * stops[0] : stops[i]);
        };
        var cutoffs = $.map(stops, function (e, i) {
            var multiplier = getStop(i + 1);
            var cutoff = Math.sqrt(e * multiplier);
            if (cutoff >= orderOfMagnitude) {
                multiplier /= orderOfMagnitude;
                cutoff /= orderOfMagnitude;
            }
            return {
                cutoff: cutoff,
                mult: multiplier,
            };
        });
        cutoffs = _.sortBy(cutoffs, function (co) {
            return co.cutoff;
        });

        var bucket = matchThresholds(xNorm, $.map(cutoffs, function (co) {
            return co.cutoff;
        }), true);
        var multiplier = (bucket === -1 ? cutoffs.slice(-1)[0].mult / orderOfMagnitude : cutoffs[bucket].mult);
        return Math.pow(orderOfMagnitude, exponent) * multiplier;
    }

    function niceRoundInterval(seconds) {
        var HOUR = 60 * 60;
        var DAY = 24 * HOUR;
        var YEAR = 365.2425 * DAY;
        var MONTH = YEAR / 12;

        if (seconds < 1) {
            return niceRoundNumber(seconds);
        } else if (seconds < HOUR) {
            return niceRoundNumber(seconds, [1, 2, 5, 10, 30], 60);
        } else if (seconds < YEAR) {
            return niceRoundNumber(seconds, [1, // needed for wraparound
                HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR,
                DAY, 3 * DAY, 7 * DAY,
                0.5 * MONTH, MONTH, 3 * MONTH, 6 * MONTH,
            ], YEAR);
        } else {
            return YEAR * niceRoundNumber(seconds / YEAR);
        }
    }

    function testNiceRoundNumber() {
        var test = function (args) {
            var result = niceRoundNumber.apply(this, args);
            console.log(args, result);
        };
        var testStops = function (stops, vals) {
            for (var OoM = -2; OoM < 3; OoM++) {
                $.each(vals, function (i, e) {
                    test([Math.pow(10., OoM) * e, stops]);
                });
            }
        };

        testStops([1.5, 3, 6], [1, 1.5, 2.1, 2.2, 3, 4.2, 4.3, 6, 9.4, 9.5]);
        testStops([3, 8], [1, 1.5, 1.6, 3, 4.8, 4.9, 8]);
        testStops([5], [1, 1.5, 1.6, 5]);
        testStops([1], [1, 3.1, 3.2]);
    }

    function testNiceRoundInterval() {
        var M = 60;
        var H = 60 * M;
        var D = 24 * H;
        var Y = 365.2425 * D;
        var MO = Y / 12;

        var format = function (x) {
            var units = [1, M, H, D, MO, Y];
            var labels = ['s', 'm', 'h', 'd', 'mo', 'y'];
            var i = matchThresholds(x, units, true);
            if (i < 0) {
                i = 0;
            }
            return (x / units[i]).toFixed(2) + labels[i];
        };
        var test = function (x) {
            var result = niceRoundInterval(x);
            console.log(format(x), format(result));
        };

        _.map([
            0.1, 0.14, 0.15, 0.2, 0.31, 0.32, 0.5, 0.7, 0.71,
            1, 1.4, 1.5, 2, 3.1, 3.2, 5, 7, 7.1, 10, 17, 18, 30, 42, 43,
            M, 1.4 * M, 1.5 * M, 2 * M, 3.1 * M, 3.2 * M, 5 * M, 7 * M, 7.1 * M, 10 * M, 17 * M, 18 * M, 30 * M, 42 * M, 43 * M,
            H, 1.7 * H, 1.8 * H, 3 * H, 4.2 * H, 4.3 * H, 6 * H, 8.4 * H, 8.5 * H, 12 * H, 16 * H, 17 * H,
            D, 1.7 * D, 1.8 * D, 3 * D, 4.5 * D, 4.6 * D, 7 * D, 10 * D, 11 * D, 0.5 * MO, 0.7 * MO, 0.71 * MO,
            MO, 1.7 * MO, 1.8 * MO, 3 * MO, 4.2 * MO, 4.3 * MO, 6 * MO, 8.4 * MO, 8.5 * MO,
            Y, 1.4 * Y, 1.5 * Y, 2 * Y, 3.1 * Y, 3.2 * Y, 5 * Y, 7 * Y, 7.1 * Y,
            10 * Y, 14 * Y, 15 * Y, 20 * Y, 31 * Y, 32 * Y, 50 * Y, 70 * Y, 71 * Y, 100 * Y,
        ], test);
    }

    // create a (hidden) canvas
    function makeConvas(w, h) {
        var $canvas = $('<canvas />');
        $canvas.attr('width', w);
        $canvas.attr('height', h);
        return $canvas;
    }

    // a map control map that lists the various display metrics for this report
    // and allows you to select and display them
    var MetricsControl = L.Control.extend({
        options: {
            position: 'bottomleft',
        },

        onAdd: function (map) {
            this.activeMetric = null;

            this.$div = $('#metrics');
            this.div = this.$div[0];
            L.DomEvent.disableClickPropagation(this.div);
            this.$div.show();

            this.init();

            var m = this;
            map.on('popupopen', function (e) {
                var $popup = $(e.popup._container);
                var metric = m.activeMetric;
                if (metric == null) {
                    return;
                }

                // highlight in detail popup
                $popup.find('.data').removeClass('detail_active');
                forEachDimension(metric, function (type, meta) {
                    $popup.find('.data-' + meta.column).addClass('detail_active');
                });
            });

            return this.div;
        },

        init: function () {
            var koModel = new MetricsViewModel(this);
            $('#metrics').koApplyBindings(koModel);
            koModel.load(this.options.metrics);
        },

        // TODO support an explicit 'show just markers again' option

        render: function (metric) {
            this.activeMetric = metric;
            resetTable(this.options.data); // clear out handlers on table before makeDisplayContext adds new ones

            var m = this;
            loadData(this._map, this.options.data, makeDisplayContext(metric, function (f) {
                m.options.info.setActive(f, m.activeMetric);
            }));

            this.options.legend.render(metric);
            if (this.options.table) {
                this.options.table.fnDraw();  // update datatables filtering
            }
        },
    });

    // main entry point
    function mapsInit(context) {
        var map = initMap($('#map'), context.layers, [30., 0.], 2);
        initData(context.data, context.config);
        var display = context.config.display;
        if (!display) {
            // we can add other things here eventually
            display = {
                'table': true,
            };
        }
        if (display.table) {
            var table = initTable(context.data, context.config);
        }
        initMetrics(map, table, context.data, context.config);
        $('#zoomtofit').css('display', 'block');
        $('#toggletable').css('display', 'block');
        return map;
    }

    // initialize leaflet map
    function initMap($div, layers, default_pos, default_zoom) {
        var map = L.map($div.attr('id'), {
            trackResize: false,
            zoomControl: false,
        }).setView(default_pos, default_zoom);
        initLayers(map, layers);

        new ZoomToFitControl().addTo(map);
        new ToggleTableControl().addTo(map);
        L.control.scale().addTo(map);

        // Moving all the zoom controls to the bottom right for consistency.
        // Could not test this instance because of other issues.
        L.control.zoom({
            position: 'bottomright',
        }).addTo(map);

        return map;
    }

    function initTable(data, config) {
        var row = function ($table, header, items, toCell) {
            var $container = $table.find(header ? 'thead' : 'tbody');
            var $tr = $('<tr>');
            $.each(items, function (i, e) {
                var $cell = $(header ? '<th>' : '<td>');
                toCell($cell, e);
                $tr.append($cell);
            });
            $container.append($tr);
            return $tr;
        };

        $('#tabular').append('<thead></thead><tbody></tbody>');
        var colSorting = initTableHeader(config, data, row);
        $.each(data.features, function (i, e) {
            var ctx = infoContext(e, config, 'table');
            e.$tr = row($('#tabular'), false, ctx.info, function ($cell, e) {
                $cell.html(e.value);
                var $sortkey = $('<span>');
                $sortkey.attr('title', e.raw);
                $cell.append($sortkey);
            });
        });

        $.fn.dataTableExt.afnFiltering.push(
            function (settings, row, i) {
                // datatables doesn't really offer a better way to do this;
                // you have to set all filtering up-front
                if (data.features[i] != void(0)) {
                    return data.features[i].visible;
                }
                return true;
            }
        );
        var table;
        table = hqImport("reports/js/config.dataTables.bootstrap").HQReportDataTables({
            aoColumns: colSorting,
        });

        table.render();
        return table.datatable;
    }

    // the ridiculousness of this function is from handling nested column headers
    function initTableHeader(config, data, mkRow) {
        var cols = getTableColumns(config);

        var maxDepth = function (col) {
            return 1 + (typeof col === 'string' ? 0 :
                _.reduce(_.map(col.subcolumns, maxDepth), function (a, b) { return Math.max(a, b); }, 0));
        };
        var totalMaxDepth = maxDepth({subcolumns: cols}) - 1;
        var breadth = function (col) {
            return (typeof col === 'string' ? 1 :
                _.reduce(_.map(col.subcolumns, breadth), function (a, b) { return a + b; }, 0));
        };

        var headerRows = [];
        for (var i = 0; i < totalMaxDepth; i++) {
            headerRows.push([]);
        }

        config._table_columns_flat = [];

        var process = function (col, depth) {
            if (typeof col === 'string') {
                var entry = {title: getColumnTitle(col, config), terminal: true};
                config._table_columns_flat.push(col); // a bit hacky
            } else {
                var entry = {title: col.title, span: breadth(col)};
                $.each(col.subcolumns, function (i, e) {
                    process(e, depth + 1);
                });
            }
            if (depth >= 0) {
                headerRows[depth].push(entry);
            }
        };
        process({subcolumns: cols}, -1);

        $.each(headerRows, function (depth, row) {
            mkRow($('#tabular'), true, row, function ($cell, e) {
                $cell.text(e.title);
                if (e.span) {
                    $cell.attr('colspan', e.span);
                }
                if (e.terminal) {
                    $cell.prepend('<i class="fa icon-white"></i>&nbsp;');
                    $cell.attr('rowspan', totalMaxDepth - depth);
                }
            });
        });

        var sortColumnAs = function (datatype) {
            return {
                'numeric': {sType: 'title-numeric'},
            }[datatype];
        };
        return _.map(getTableColumns(config, true), function (col) {
            var stats = summarizeColumn({column: col}, data);
            return sortColumnAs(stats.nonnumeric ? 'text' : 'numeric');
        });
    }

    function resetTable(data) {
        // we can't use $('#tabular tr') as that will only select the rows currently shown by datatables
        var rows = [];
        $.each(data.features, function (i, e) {
            if (e.$tr) {
                rows.push(e.$tr[0]);
            }
        });
        rows = $(rows);
        rows.off('click').off('mouseenter').off('mouseleave');
        rows.removeClass('inactive-row');
    }

    // render a display metric to the map
    function loadData(map, data, display_context) {
        if (map.activeOverlay) {
            map.removeLayer(map.activeOverlay);
            map.activeOverlay = null;
        }

        var points = L.geoJson(data, display_context);
        points.addTo(map);
        map.activeOverlay = points;
    }

    return {
        load: load,
        setMapHeight: setMapHeight,
        ZoomToFitControl: ZoomToFitControl,
        MapBoxWordMark: MapBoxWordMark,
        zoomToAll: zoomToAll,
    };
});
