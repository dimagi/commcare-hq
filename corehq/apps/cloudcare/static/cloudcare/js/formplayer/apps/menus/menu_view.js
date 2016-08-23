/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette) {
    MenuList.MenuView = Marionette.ItemView.extend({
        tagName: "tr",
        className: "formplayer-request",
        events: {
            "click": "rowClick",
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
            var model = this.model;
            FormplayerFrontend.trigger("menu:select", model.get('index'));
        },
        templateHelpers: function () {
            var imageUri = this.options.model.get('imageUri');
            var audioUri = this.options.model.get('audioUri');
            var navState = this.options.model.get('navigationState');
            var appId = this.model.collection.appId;
            return {
                navState: navState,
                imageUrl: imageUri ? FormplayerFrontend.request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.request('resourceMap', audioUri, appId) : "",
            };
        },
    });

    MenuList.MenuListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#menu-view-list-template",
        childView: MenuList.MenuView,
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

    MenuList.CaseView = Marionette.ItemView.extend({
        tagName: "tr",
        getTemplate: function () {
            if (_.isNull(this.options.tiles)) {
                return "#case-view-item-template";
            } else {
                return "#case-tile-view-item-template";
            }
        },

        className: "formplayer-request",
        events: {
            "click": "rowClick",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("menu:show:detail", this, 0);
        },

        templateHelpers: function () {
            var appId = this.model.collection.appId;
            return {
                data: this.options.model.get('data'),
                styles: this.options.styles,
                tiles: this.options.tiles,
                resolveUri: function (uri) {
                    return FormplayerFrontend.request('resourceMap', uri, appId);
                },
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
            tileStyle,
            tileStyleTemplate,
            tileModels;

        tileModels = _.chain(tiles || [])
            .filter(function(tile) { return tile !== null; })
            .map(function(tile, idx) {
                return {
                    id: 'grid-style-' + idx,
                    gridStyle: getGridAttributes(tile),
                    fontStyle: tile.fontSize,
                };
            }).value();

        templateString = $("#case-tile-style-template").html();
        tileStyleTemplate = _.template(templateString);
        tileStyle = tileStyleTemplate({
            models: tileModels,
        });

        // need to remove this attribute so the grid style is re-evaluated
        $("#case-tiles-style").html(tileStyle).data("css-polyfilled", false);
    };

    MenuList.CaseListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#case-view-list-template",
        childView: MenuList.CaseView,
        childViewContainer: ".case-container",

        initialize: function (options) {
            this.tiles = options.tiles;
            this.styles = options.styles;
            generateCaseTileStyles(options.tiles);
        },

        childViewOptions: function () {
            return {
                styles: this.options.styles,
                tiles: this.options.tiles,
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
        },

        caseListAction: function () {
            FormplayerFrontend.trigger("menu:select", "action 0");
        },

        caseListSearch: function (e) {
            e.preventDefault();
            var searchText = $('#searchText').val();
            FormplayerFrontend.trigger("menu:search", searchText);
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
                tiles: this.options.tiles,
                breadcrumbs: this.options.breadcrumbs,
            };
        },
    });

    MenuList.BreadcrumbView = Marionette.ItemView.extend({
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

    MenuList.BreadcrumbListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#breadcrumb-list-template",
        childView: MenuList.BreadcrumbView,
        childViewContainer: "ol",
    });

    MenuList.DetailView = Marionette.ItemView.extend({
        tagName: "tr",
        className: "row",
        template: "#detail-view-item-template",
    });

    MenuList.DetailListView = Marionette.CompositeView.extend({
        tagName: "table",
        className: "table table-hover table-striped table-bordered",
        template: "#detail-view-list-template",
        childView: MenuList.DetailView,
        childViewContainer: "tbody",
    });

    MenuList.DetailTabView = Marionette.ItemView.extend({
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

    MenuList.DetailTabListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#detail-view-tab-list-template",
        childView: MenuList.DetailTabView,
        childViewContainer: "ul",
        childViewOptions: function () {
            return {
                showDetail: this.options.showDetail,
            };
        },
    });
})
;
