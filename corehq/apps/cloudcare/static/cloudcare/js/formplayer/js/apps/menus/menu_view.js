/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate.MenuList", function (MenuList, FormplayerFrontend, Backbone, Marionette) {
    MenuList.MenuView = Marionette.ItemView.extend({
        tagName: "tr",

        events: {
            "click": "rowClick",
        },

        getTemplate: function () {
            if (this.model.attributes.audioUri) {
                return "#menu-view-item-audio-template";
            } else {
                return "#menu-view-item-template";
            }
        },

        rowClick: function (e) {
            e.preventDefault();
            var model = this.model;
            FormplayerFrontend.trigger("menu:select", model.get('index'), model.collection.appId);
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
                title: this.options.collection.title,
            };
        },
    });

    var getGridAttributes = function (tile) {
        if (!tile) {
            return null;
        }
        var rowStart = tile.gridY + 1;
        var colStart = tile.gridX + 1;
        var rowEnd = rowStart + tile.gridHeight;
        var colEnd = colStart + tile.gridWidth;

        return "grid-area: " + rowStart + " / " + colStart + " / " +
            rowEnd + " / " + colEnd + ";";
    };

    function addStyleString(str) {
        var node = document.createElement('style');
        node.innerHTML = str;
        document.body.appendChild(node);
    }

    MenuList.CaseView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#case-view-item-template",

        getTemplate: function () {
            if (this.options.tiles) {
                return "#case-tile-view-item-template";
            } else {
                return "#case-view-item-template";
            }
        },

        initialize: function (options) {
            this.tiles = options.tiles;
            this.styles = options.styles;
            for(var i = 0; i < this.tiles.length; i++) {
                var tile = this.tiles[i];
                var styleString = getGridAttributes(tile);
                var tileId = "grid-style-" + i;
                var formattedString = "." + tileId + " { " + styleString + " } ";
                addStyleString(formattedString);
            }
        },


        events: {
            "click": "rowClick",
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("menu:show:detail", this);
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
                getGridStyle: function (index) {
                    var tile = this.tiles[index];
                    return getGridAttributes(tile);
                }
            };
        },
    });

    MenuList.CaseListView = Marionette.CompositeView.extend({
        tagName: "div",
        template: "#case-view-list-template",
        childView: MenuList.CaseView,
        childViewContainer: "div",

        initialize: function (options) {
            this.tiles = options.tiles;
            this.styles = options.styles;
        },

        childViewOptions: function () {
            return {
                styles: this.options.styles,
                tiles: this.options.tiles,
            };
        },

        ui: {
            button: '#double-management',
            paginators: '.page-link',
        },

        events: {
            'click @ui.button': 'caseListAction',
            'click @ui.paginators': 'paginateAction',
        },

        caseListAction: function () {
            FormplayerFrontend.trigger("menu:select", "action 0", this.options.collection.appId);
        },

        paginateAction: function (e) {
            var pageSelection = $(e.currentTarget).data("id");
            FormplayerFrontend.trigger("menu:paginate", pageSelection, this.options.collection.appId);
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
            };
        },
    });

    MenuList.DetailView = Marionette.ItemView.extend({
        tagName: "tr",
        template: "#detail-view-item-template",
    });

    MenuList.DetailListView = Marionette.CompositeView.extend({
        tagName: "table",
        className: "table table-hover",
        template: "#detail-view-list-template",
        childView: MenuList.DetailView,
        childViewContainer: "tbody",
    });
});