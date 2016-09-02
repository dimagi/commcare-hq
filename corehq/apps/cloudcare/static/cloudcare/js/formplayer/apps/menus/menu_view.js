/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette) {
    MenuList.MenuView = Marionette.ItemView.extend({
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
        template: "#case-view-item-template",

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
                resolveUri: function (uri) {
                    return FormplayerFrontend.request('resourceMap', uri, appId);
                },
            };
        },
    });

    MenuList.CaseTileView = MenuList.CaseView.extend({
        tagName: "tr",
        template: "#case-tile-view-item-template",
        className: "formplayer-request grid-wrapper",

        templateHelpers: function () {
            var appId = this.model.collection.appId;
            return {
                data: this.options.model.get('data'),
                styles: this.options.styles,
                tiles: this.options.tiles,
                numEntitiesToDisplayPerRow: this.options.numEntitiesToDisplayPerRow,
                resolveUri: function (uri) {
                    return FormplayerFrontend.request('resourceMap', uri, appId);
                },
            };
        },
    });

    MenuList.CaseTileGridViewItem = MenuList.CaseTileView.extend({
        tagName: "div",
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
            .filter(function (tile) {
                return tile !== null;
            })
            .map(function (tile, idx) {
                return {
                    id: 'grid-style-' + idx,
                    gridStyle: getGridAttributes(tile),
                    fontStyle: tile.fontSize,
                };
            }).value();

        templateString = $("#case-tile-style-template").html();
        caseTileStyleTemplate = _.template(templateString);
        caseTileStyle = caseTileStyleTemplate({
            models: tileModels,
        });

        // need to remove this attribute so the grid style is re-evaluated
        $("#case-tiles-style").html(caseTileStyle).removeAttr("data-css-polyfilled");
    };

    var generateCaseTileContainerStyles = function (numCases, numCasesPerRow) {
        var templateString,
            caseTileContainerStyle,
            caseTileContainerStyleTemplate,
            containerModel;

        containerModel = {
            numCasesPerRow: numCasesPerRow,
            numRows: Math.ceil(numCases / numCasesPerRow),
        };
        templateString = $("#case-tile-container-style-template").html();
        caseTileContainerStyleTemplate = _.template(templateString);
        caseTileContainerStyle = caseTileContainerStyleTemplate({
            model: containerModel,
        });

        // need to remove this attribute so the grid style is re-evaluated
        $("#case-tiles-container-style").html(caseTileContainerStyle).removeAttr("data-css-polyfilled");
        $("#case-tiles-style").removeAttr("data-css-polyfilled");
    };

    MenuList.CaseListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#case-view-list-template",
        childViewContainer: ".case-container",
        childView: MenuList.CaseView,

        initialize: function (options) {
            this.styles = options.styles;
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
                breadcrumbs: this.options.breadcrumbs,
            };
        },
    });

    MenuList.CaseTileListView = MenuList.CaseListView.extend({
        template: "#case-view-tile-list-template",
        childView: MenuList.CaseTileView,
        initialize: function (options) {
            this.styles = options.styles;
            this.tiles = options.tiles;
            this.numCases = options.collection.length;
            this.numEntitiesPerRow = options.numEntitiesPerRow;
            generateCaseTileStyles(options.tiles);
        },

        childViewOptions: function () {
            return {
                styles: this.options.styles,
                tiles: this.options.tiles,
            };
        },

        templateHelpers: function () {
            return {
                title: this.options.title,
                action: this.options.action,
                currentPage: this.options.currentPage,
                pageCount: this.options.pageCount,
                styles: this.options.styles,
                tiles: this.options.tiles,
                breadcrumbs: this.options.breadcrumbs,
                numEntitiesPerRow: this.options.numEntitiesPerRow,
                numCases: this.options.numCases,
            };
        },
    });

    MenuList.CaseTileGridView = MenuList.CaseTileListView.extend({
        childView: MenuList.CaseTileGridViewItem,

        initialize: function (options) {
            this.styles = options.styles;
            this.tiles = options.tiles;
            this.numCases = options.collection.length;
            this.numEntitiesPerRow = options.numEntitiesPerRow;
            generateCaseTileStyles(options.tiles);
            generateCaseTileContainerStyles(this.numCases, this.numEntitiesPerRow);
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
