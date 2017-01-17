/*global FormplayerFrontend, Util */

FormplayerFrontend.module("Menus.Views", function (Views, FormplayerFrontend, Backbone, Marionette, $) {
    Views.MenuView = Marionette.ItemView.extend({
        tagName: "tr",
        className: "formplayer-request",
        events: {
            "click": "rowClick",
            "click .js-module-audio-play": "audioPlay",
            "click .js-module-audio-pause": "audioPause",
        },

        getTemplate: function () {
            if (this.model.get('audioUri')) {
                return "#menu-view-item-audio-template";
            } else {
                return "#menu-view-item-template";
            }
        },

        rowClick: function (e) {
            e.preventDefault();
            if (!($(e.originalEvent.srcElement).hasClass('js-module-audio-icon')
                || $(e.originalEvent.srcElement).hasClass('js-module-audio-play')
                || $(e.originalEvent.srcElement).hasClass('js-module-audio-pause'))
            ) {
                var model = this.model;
                FormplayerFrontend.trigger("menu:select", model.get('index'));
            }
        },
        audioPlay: function (e) {
            e.preventDefault();
            var $playBtn = $(e.originalEvent.srcElement).closest('.js-module-audio-play');
            var $pauseBtn = $playBtn.parent().find('.js-module-audio-pause');
            $pauseBtn.removeClass('hide');
            $playBtn.addClass('hide');
            var $audioElem = $playBtn.parent().find('.js-module-audio');
            if ($audioElem.data('isFirstPlay') !== 'yes') {
                $audioElem.data('isFirstPlay', 'yes');
                $audioElem.one('ended', function () {
                    $playBtn.removeClass('hide');
                    $pauseBtn.addClass('hide');
                    $audioElem.data('isFirstPlay', 'no');
                });
            }
            $audioElem.get(0).play();
        },
        audioPause: function (e) {
            e.preventDefault();
            var $pauseBtn = $(e.originalEvent.srcElement).closest('.js-module-audio-pause');
            $pauseBtn.parent().find('.js-module-audio-play').removeClass('hide');
            $pauseBtn.addClass('hide');
            $pauseBtn.parent().find('.js-module-audio').get(0).pause();
        },
        templateHelpers: function () {
            var imageUri = this.options.model.get('imageUri');
            var audioUri = this.options.model.get('audioUri');
            var navState = this.options.model.get('navigationState');
            var appId = Util.currentUrlToObject().appId;
            return {
                navState: navState,
                imageUrl: imageUri ? FormplayerFrontend.request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.request('resourceMap', audioUri, appId) : "",
            };
        },
    });

    Views.MenuListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#menu-view-list-template",
        childView: Views.MenuView,
        childViewContainer: "tbody",
        templateHelpers: function () {
            return {
                title: this.options.title,
            };
        },
        childViewOptions: function () {
            return {
                sessionId: this.options.sessionId,
            };
        },
    });

    // return the string grid-area attribute
    // takes the form of  [x-coord] / [y-Coord] / [width] / [height]
    var getGridAttributes = function (tile) {
        if (!tile) {
            return null;
        }
        var rowStart = tile.gridY + 1;
        var colStart = tile.gridX + 1;
        var rowEnd = rowStart + tile.gridHeight;
        var colEnd = colStart + tile.gridWidth;

        return rowStart + " / " + colStart + " / " +
            rowEnd + " / " + colEnd;
    };
    // generate the case tile's style block and insert
    var generateCaseTileStyles = function (tiles) {
        var templateString,
            caseTileStyle,
            caseTileStyleTemplate,
            tileModels;

        tileModels = _.chain(tiles || [])
            .map(function (tile, idx) {
                if (tile === null || tile === undefined) {
                    return null;
                }
                return {
                    id: 'grid-style-' + idx,
                    gridStyle: getGridAttributes(tile),
                    fontStyle: tile.fontSize,
                };
            })
            .filter(function (tile) {
                return tile !== null;
            }).value();

        templateString = $("#case-tile-style-template").html();
        caseTileStyleTemplate = _.template(templateString);
        caseTileStyle = caseTileStyleTemplate({
            models: tileModels,
        });

        // need to remove this attribute so the grid style is re-evaluated
        $("#case-tiles-style").html(caseTileStyle).data("css-polyfilled", false);
        $("#inner-tiles-container-style").data("css-polyfilled", false);
    };

    // Dynamically generate the CSS style to display multiple tiles per line
    var makeOuterGridStyle = function (numRows, numColumns, numCasesPerRow) {
        var outerGridTemplateString,
            outerGridStyle,
            outerGridStyleTemplate,
            outerGridModel;

        var widthPercentage = 100 / numCasesPerRow;
        var widthHeightRatio = numRows / numColumns;
        var heightPercentage = widthPercentage * widthHeightRatio;

        outerGridModel = {
            widthPercentage: widthPercentage,
            heightPercentage: heightPercentage,
        };
        outerGridTemplateString = $("#case-grid-style-template").html();
        outerGridStyleTemplate = _.template(outerGridTemplateString);
        outerGridStyle = outerGridStyleTemplate({
            model: outerGridModel,
        });
        // need to remove this attribute so the grid style is re-evaluated
        $("#outer-tiles-container-style").html(outerGridStyle).data("css-polyfilled", false);
    };

    // Dynamically generate the CSS style for the grid polyfill to use for the case tile
    // useUniformUnits - true if the grid's cells should have the same height as width
    var makeInnerGridStyle = function (numRows, numColumns, numCasesPerRow, useUniformUnits) {
        var templateString,
            view,
            template,
            model,
            widthPixels,
            heightPixels,
            fullWidth;

        fullWidth = 800;
        widthPixels = ((1 / numColumns) / numCasesPerRow) * fullWidth;
        if (useUniformUnits) {
            heightPixels = widthPixels;
        } else {
            heightPixels = widthPixels / 2;
        }

        model = {
            numRows: numRows,
            numColumns: numColumns,
            widthPixels: widthPixels,
            heightPixels: heightPixels,
        };
        templateString = $("#grid-inner-style-template").html();
        template = _.template(templateString);
        view = template({
            model: model,
        });
        // need to remove this attribute so the grid style is re-evaluated
        $("#inner-tiles-container-style").html(view).data("css-polyfilled", false);

        // If we have multiple cases per line, need to generate the outer grid style as well
        if (numCasesPerRow > 1) {
            makeOuterGridStyle(numRows, numColumns, numCasesPerRow);
        }
    };

    Views.CaseView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#case-view-item-template",
        className: "formplayer-request",

        events: {
            "click": "rowClick",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("menu:show:detail", this.options.model.get('id'), 0);
        },

        templateHelpers: function () {
            var appId = Util.currentUrlToObject().appId;
            return {
                data: this.options.model.get('data'),
                styles: this.options.styles,
                resolveUri: function (uri) {
                    return FormplayerFrontend.request('resourceMap', uri, appId);
                },
            };
        },
    });

    Views.CaseTileView = Views.CaseView.extend({
        template: "#case-tile-view-item-template",
    });

    Views.CaseListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#case-view-list-template",
        childViewContainer: ".js-case-container",
        childView: Views.CaseView,

        initialize: function (options) {
            this.styles = options.styles;
            this.hasNoItems = options.collection.length === 0;
        },

        childViewOptions: function () {
            return {
                styles: this.options.styles,
            };
        },

        ui: {
            actionButton: '#double-management',
            searchButton: '#case-list-search-button',
            paginators: '.page-link',
        },

        events: {
            'click @ui.actionButton': 'caseListAction',
            'click @ui.searchButton': 'caseListSearch',
            'click @ui.paginators': 'paginateAction',
            'keypress': 'keyAction',
        },

        caseListAction: function () {
            FormplayerFrontend.trigger("menu:select", "action 0");
        },

        caseListSearch: function (e) {
            e.preventDefault();
            var searchText = $('#searchText').val();
            FormplayerFrontend.trigger("menu:search", searchText);
        },

        keyAction: function (event) {
            if (event.which === 13 || event.keyCode === 13) {
                this.caseListSearch(event);
            }
        },

        paginateAction: function (e) {
            var pageSelection = $(e.currentTarget).data("id");
            FormplayerFrontend.trigger("menu:paginate", pageSelection);
        },

        templateHelpers: function () {
            return {
                title: this.options.title,
                headers: this.options.headers,
                widthHints: this.options.widthHints,
                action: this.options.action,
                currentPage: this.options.currentPage,
                pageCount: this.options.pageCount,
                styles: this.options.styles,
                breadcrumbs: this.options.breadcrumbs,
                templateName: "case-list-template",
                useGrid: this.options.numEntitiesPerRow > 1,
                useTiles: false,
                hasNoItems: this.hasNoItems,
            };
        },
    });

    Views.CaseTileListView = Views.CaseListView.extend({
        childView: Views.CaseTileView,
        initialize: function (options) {
            Views.CaseTileListView.__super__.initialize.apply(this, arguments);
            var gridPolyfillPath = FormplayerFrontend.request('gridPolyfillPath');
            generateCaseTileStyles(options.tiles);
            makeInnerGridStyle(options.maxHeight,
                options.maxWidth,
                options.numEntitiesPerRow || 1,
                options.useUniformUnits);
            $.getScript(gridPolyfillPath);
        },

        templateHelpers: function () {
            var dict = Views.CaseTileListView.__super__.templateHelpers.apply(this, arguments);
            dict['useTiles'] = true;
            return dict;
        },
    });

    Views.GridCaseTileViewItem = Views.CaseTileView.extend({
        tagName: "div",
        className: "formplayer-request case-tile-grid-item",
        template: "#case-tile-view-item-template",
    });

    Views.GridCaseTileListView = Views.CaseTileListView.extend({
        initialize: function () {
            Views.GridCaseTileListView.__super__.initialize.apply(this, arguments);
        },
        childView: Views.GridCaseTileViewItem,
    });

    Views.BreadcrumbView = Marionette.ItemView.extend({
        tagName: "li",
        template: "#breadcrumb-item-template",
        className: "breadcrumb-text",
        events: {
            "click": "crumbClick",
        },

        crumbClick: function (e) {
            e.preventDefault();
            var crumbId = this.options.model.get('id');
            FormplayerFrontend.trigger("breadcrumbSelect", crumbId);
        },
    });

    Views.BreadcrumbListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#breadcrumb-list-template",
        childView: Views.BreadcrumbView,
        childViewContainer: "ol",
        events: {
            'click .js-home': 'onClickHome',
        },
        onClickHome: function() {
            FormplayerFrontend.trigger('navigateHome');
        },
    });

    Views.DetailView = Marionette.ItemView.extend({
        tagName: "tr",
        className: "",
        template: "#detail-view-item-template",
    });

    Views.DetailListView = Marionette.CompositeView.extend({
        tagName: "table",
        className: "table module-table module-table-casedetail",
        template: "#detail-view-list-template",
        childView: Views.DetailView,
        childViewContainer: "tbody",
    });

    Views.DetailTabView = Marionette.ItemView.extend({
        tagName: "li",
        template: "#detail-view-tab-item-template",
        events: {
            "click": "tabClick",
        },
        initialize: function (options) {
            this.index = options.model.get('id');
            this.showDetail = options.showDetail;
        },
        tabClick: function (e) {
            e.preventDefault();
            this.options.showDetail(this.index);
        },
    });

    Views.DetailTabListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#detail-view-tab-list-template",
        childView: Views.DetailTabView,
        childViewContainer: "ul",
        childViewOptions: function () {
            return {
                showDetail: this.options.showDetail,
            };
        },
    });
})
;
