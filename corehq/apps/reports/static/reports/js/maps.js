/* global HQReportDataTables:true */

// a map control map that lists the various display metrics for this report
// and allows you to select and display them
MetricsControl = L.Control.extend({
    options: {
        position: 'bottomleft'
    },

    onAdd: function(map) {
        this.activeMetric = null;

        this.$div = $('#metrics');
        this.div = this.$div[0];
        L.DomEvent.disableClickPropagation(this.div);
        this.$div.show();

        this.init();

        var m = this;
        map.on('popupopen', function(e) {
            var $popup = $(e.popup._container);
            var metric = m.activeMetric;
            if (metric == null) {
                return;
            }

            // highlight in detail popup
            $popup.find('.data').removeClass('detail_active');
            forEachDimension(metric, function(type, meta) {
                $popup.find('.data-' + meta.column).addClass('detail_active');
            });
        });

        return this.div;
    },

    init: function() {
        var koModel = new MetricsViewModel(this);
        $('#metrics').koApplyBindings(koModel);
        koModel.load(this.options.metrics);
    },

    // TODO support an explicit 'show just markers again' option

    render: function(metric) {
        this.activeMetric = metric;
        resetTable(this.options.data); // clear out handlers on table before makeDisplayContext adds new ones

        var m = this;
        loadData(this._map, this.options.data, makeDisplayContext(metric, function(f) {
            m.options.info.setActive(f, m.activeMetric);
        }));

        this.options.legend.render(metric);
        if (this.options.table) {
            this.options.table.fnDraw();  // update datatables filtering
        }
    }
});

// main entry point
function mapsInit(context) {
    var map = initMap($('#map'), context.layers, [30., 0.], 2);
    initData(context.data, context.config);
    var display = context.config.display;
    if (!display) {
        // we can add other things here eventually
        display = {
            'table': true
        }
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
    var map = L.map($div.attr('id'), {trackResize: false}).setView(default_pos, default_zoom);
    initLayers(map, layers);

    new ZoomToFitControl().addTo(map);
    new ToggleTableControl().addTo(map);
    L.control.scale().addTo(map);

    return map;
}

function initTable(data, config) {
    var row = function($table, header, items, toCell) {
        var $container = $table.find(header ? 'thead' : 'tbody');
        var $tr = $('<tr>');
        $.each(items, function(i, e) {
            var $cell = $(header ? '<th>' : '<td>');
            toCell($cell, e);
            $tr.append($cell);
        });
        $container.append($tr);
        return $tr;
    };

    $('#tabular').append('<thead></thead><tbody></tbody>');
    var colSorting = initTableHeader(config, data, row);
    $.each(data.features, function(i, e) {
        var ctx = infoContext(e, config, 'table');
        e.$tr = row($('#tabular'), false, ctx.info, function($cell, e) {
            $cell.html(e.value);
            var $sortkey = $('<span>');
            $sortkey.attr('title', e.raw);
            $cell.append($sortkey);
        });
    });

    $.fn.dataTableExt.afnFiltering.push(
        function(settings, row, i) {
            // datatables doesn't really offer a better way to do this;
            // you have to set all filtering up-front
            if (data.features[i] != void(0)) {
                return data.features[i].visible;
            }
            return true;
        }
    );
    var table;
    table = new HQReportDataTables({
        aoColumns: colSorting,
    });

    table.render();
    return table.datatable;
}

// the ridiculousness of this function is from handling nested column headers
function initTableHeader(config, data, mkRow) {
    var cols = getTableColumns(config);

    var maxDepth = function(col) {
        return 1 + (typeof col == 'string' ? 0 :
                    _.reduce(_.map(col.subcolumns, maxDepth), function(a, b) { return Math.max(a, b); }, 0));
    };
    var totalMaxDepth = maxDepth({subcolumns: cols}) - 1;
    var breadth = function(col) {
        return (typeof col == 'string' ? 1 :
                _.reduce(_.map(col.subcolumns, breadth), function(a, b) { return a + b; }, 0));
    };

    var headerRows = [];
    for (var i = 0; i < totalMaxDepth; i++) {
        headerRows.push([]);
    }

    config._table_columns_flat = [];

    var process = function(col, depth) {
        if (typeof col == 'string') {
            var entry = {title: getColumnTitle(col, config), terminal: true};
            config._table_columns_flat.push(col); // a bit hacky
        } else {
            var entry = {title: col.title, span: breadth(col)};
            $.each(col.subcolumns, function(i, e) {
                process(e, depth + 1);
            });
        }
        if (depth >= 0) {
            headerRows[depth].push(entry);
        }
    }
    process({subcolumns: cols}, -1);

    $.each(headerRows, function(depth, row) {
        mkRow($('#tabular'), true, row, function($cell, e) {
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

    var sortColumnAs = function(datatype) {
        return {
            'numeric': {sType: 'title-numeric'}
        }[datatype];
    };
    return _.map(getTableColumns(config, true), function(col) {
        var stats = summarizeColumn({column: col}, data);
        return sortColumnAs(stats.nonnumeric ? 'text' : 'numeric');
    });
}

function resetTable(data) {
    // we can't use $('#tabular tr') as that will only select the rows currently shown by datatables
    var rows = [];
    $.each(data.features, function(i, e) {
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
