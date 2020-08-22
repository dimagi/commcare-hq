/*global FormplayerFrontend, Util, Marionette */

hqDefine("cloudcare/js/formplayer/menus/views", function () {
    var MenuView = Marionette.LayoutView.extend({
        tagName: function () {
            if (this.model.collection.layoutStyle === 'grid') {
                return 'div';
            } else {
                return 'tr';
            }
        },
        className: "formplayer-request",
        events: {
            "click": "rowClick",
            "click .js-module-audio-play": "audioPlay",
            "click .js-module-audio-pause": "audioPause",
        },

        initialize: function (options) {
            this.menuIndex = options.menuIndex;
        },

        getTemplate: function () {
            if (this.model.collection.layoutStyle === FormplayerFrontend.Constants.LayoutStyles.GRID) {
                return "#menu-view-grid-item-template";
            } else {
                if (this.model.get('audioUri')) {
                    return "#menu-view-row-audio-template";
                } else {
                    return "#menu-view-row-template";
                }
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
                imageUrl: imageUri ? FormplayerFrontend.getChannel().request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.getChannel().request('resourceMap', audioUri, appId) : "",
                menuIndex: this.menuIndex,
            };
        },
    });

    var MenuTableView = Marionette.CollectionView.extend({
        childView: MenuView,
        tagName: "tbody",
    });

    var MenuListView = Marionette.LayoutView.extend({
        tagName: "div",
        regions: {
            body: {
                el: "table",
            },
        },
        onShow: function () {
            this.getRegion('body').show(new MenuTableView({
                collection: this.collection,
            }));
        },
        getTemplate: function () {
            if (this.collection.layoutStyle === FormplayerFrontend.Constants.LayoutStyles.GRID) {
                return "#menu-view-grid-template";
            } else {
                return "#menu-view-list-template";
            }
        },
        templateHelpers: function () {
            return {
                title: this.options.title,
                environment: FormplayerFrontend.getChannel().request('currentUser').environment,
            };
        },
        childViewOptions: function (model, index) {
            return {
                sessionId: this.options.sessionId,
                menuIndex: index,
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
    var buildCellLayout = function (tiles, prefix) {
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
                    id: prefix + '-grid-style-' + idx,
                    gridStyle: getGridAttributes(tile),
                    fontStyle: tile.fontSize,
                };
            })
            .filter(function (tile) {
                return tile !== null;
            }).value();

        templateString = $("#cell-layout-style-template").html();
        caseTileStyleTemplate = _.template(templateString);
        caseTileStyle = caseTileStyleTemplate({
            models: tileModels,
        });
        return caseTileStyle;
    };

    // Dynamically generate the CSS style to display multiple tiles per line
    var buildCellContainerStyle = function (numRows, numColumns, numCasesPerRow) {
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
        outerGridTemplateString = $("#cell-container-style-template").html();
        outerGridStyleTemplate = _.template(outerGridTemplateString);
        outerGridStyle = outerGridStyleTemplate({
            model: outerGridModel,
        });
        return outerGridStyle;
    };

    // Dynamically generate the CSS style for the grid polyfill to use for the case tile
    // useUniformUnits - true if the grid's cells should have the same height as width
    var buildCellGridStyle = function (numRows, numColumns, numCasesPerRow, useUniformUnits, prefix) {
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
            prefix: prefix,
        };
        templateString = $("#cell-grid-style-template").html();
        template = _.template(templateString);
        view = template({
            model: model,
        });
        return view;
    };

    var CaseView = Marionette.LayoutView.extend({
        tagName: "tr",
        template: "#case-view-item-template",

        events: {
            "click": "rowClick",
        },

        className: "formplayer-request",

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("menu:show:detail", this.model.get('id'), 0, false);
        },

        templateHelpers: function () {
            var appId = Util.currentUrlToObject().appId;
            return {
                data: this.options.model.get('data'),
                styles: this.options.styles,
                resolveUri: function (uri) {
                    return FormplayerFrontend.getChannel().request('resourceMap', uri, appId);
                },
            };
        },
    });

    var CaseViewUnclickable = CaseView.extend({
        events: {},
        className: "",
        rowClick: function () {},
    });

    var CaseTileView = CaseView.extend({
        template: "#case-tile-view-item-template",
        templateHelpers: function () {
            var dict = CaseTileView.__super__.templateHelpers.apply(this, arguments);
            dict['prefix'] = this.options.prefix;
            return dict;
        },
    });

    var PersistentCaseTileView = CaseTileView.extend({
        rowClick: function (e) {
            e.preventDefault();
            if (this.options.hasInlineTile) {
                FormplayerFrontend.trigger("menu:show:detail", this.options.model.get('id'), 0, true);
            }
        },
    });

    var CaseListContainerView = Marionette.CollectionView.extend({
        childView: CaseView,
        tagName: "tbody",

        childViewOptions: function () {
            return {
                styles: this.options.styles,
            };
        },
    });

    var CaseListView = Marionette.LayoutView.extend({
        tagName: "div",
        template: "#case-view-list-template",

        regions: {
            body: {
                el: ".js-case-container",
            },
        },
        onShow: function () {
            this.getRegion('body').show(new CaseListContainerView({
                collection: this.collection,
                styles: this.styles,
            }));
        },

        initialize: function (options) {
            this.styles = options.styles;
            this.hasNoItems = options.collection.length === 0;
        },

        ui: {
            actionButton: '#double-management',
            searchButton: '#case-list-search-button',
            paginators: '.page-link',
            columnHeader: '.header-clickable',
        },

        events: {
            'click @ui.actionButton': 'caseListAction',
            'click @ui.searchButton': 'caseListSearch',
            'click @ui.paginators': 'paginateAction',
            'click @ui.columnHeader': 'columnSortAction',
            'keypress': 'keyAction',
        },

        caseListAction: function (e) {
            var index = $(e.currentTarget).data().index;
            FormplayerFrontend.trigger("menu:select", "action " + index);
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

        columnSortAction: function (e) {
            var columnSelection = $(e.currentTarget).data("id") + 1;
            FormplayerFrontend.trigger("menu:sort", columnSelection);
        },

        templateHelpers: function () {
            return {
                title: this.options.title,
                headers: this.options.headers,
                widthHints: this.options.widthHints,
                actions: this.options.actions,
                currentPage: this.options.currentPage,
                pageCount: this.options.pageCount,
                styles: this.options.styles,
                breadcrumbs: this.options.breadcrumbs,
                templateName: "case-list-template",
                useGrid: this.options.numEntitiesPerRow > 1,
                useTiles: false,
                hasNoItems: this.hasNoItems,
                sortIndices: this.options.sortIndices,
                columnSortable: function (index) {
                    return this.sortIndices.indexOf(index) > -1;
                },
                columnVisible: function (index) {
                    return !(this.widthHints && this.widthHints[index] === 0);
                },
            };
        },
    });

    // Return a two- or three-length array of case tile CSS styles
    //
    // styles[0] - the grid layout of the cells within a case list tile
    // styles[1] - the layout of the grid itself, IE how many rows/columns each tile should have and their size
    // styles[2] (optional) - If showing multiple cases per line, sets the style of how to layout the case tiles in the
    //                        outer grid
    var buildCaseTileStyles = function (tiles, numRows, numColumns, numEntitiesPerRow, useUniformUnits, prefix) {
        var cellLayoutStyle = buildCellLayout(tiles, prefix);
        var cellGridStyle = buildCellGridStyle(numRows,
            numColumns,
            numEntitiesPerRow,
            useUniformUnits,
            prefix);
        if (numEntitiesPerRow > 1) {
            var cellContainerStyle = buildCellContainerStyle(numRows, numColumns, numEntitiesPerRow);
            return [cellLayoutStyle, cellGridStyle, cellContainerStyle];
        } else {
            return [cellLayoutStyle, cellGridStyle];
        }
    };

    var CaseTileListView = CaseListView.extend({
        childView: CaseTileView,
        initialize: function (options) {
            CaseTileListView.__super__.initialize.apply(this, arguments);

            var numEntitiesPerRow = options.numEntitiesPerRow || 1;
            var numRows = options.maxHeight;
            var numColumns = options.maxWidth;
            var useUniformUnits = options.useUniformUnits;

            var caseTileStyles = buildCaseTileStyles(options.tiles, numRows, numColumns,
                numEntitiesPerRow, useUniformUnits, 'list');

            var gridPolyfillPath = FormplayerFrontend.getChannel().request('gridPolyfillPath');

            $("#list-cell-layout-style").html(caseTileStyles[0]).data("css-polyfilled", false);
            $("#list-cell-grid-style").html(caseTileStyles[1]).data("css-polyfilled", false);
            // If we have multiple cases per line, need to generate the outer grid style as well
            if (caseTileStyles.length > 2) {
                $("#list-cell-container-style").html(caseTileStyles[2]).data("css-polyfilled", false);
            }

            $.getScript(gridPolyfillPath);
        },

        childViewOptions: function () {
            var dict = CaseTileListView.__super__.childViewOptions.apply(this, arguments);
            dict.prefix = 'list';
            return dict;
        },

        templateHelpers: function () {
            var dict = CaseTileListView.__super__.templateHelpers.apply(this, arguments);
            dict.useTiles = true;
            return dict;
        },
    });

    var GridCaseTileViewItem = CaseTileView.extend({
        tagName: "div",
        className: "formplayer-request list-cell-container-style",
    });

    var GridCaseTileListView = CaseTileListView.extend({
        initialize: function () {
            GridCaseTileListView.__super__.initialize.apply(this, arguments);
        },
        childView: GridCaseTileViewItem,
    });

    var CaseListDetailView = CaseListView.extend({
        template: "#case-view-list-detail-template",
        childView: CaseViewUnclickable,
    });

    var BreadcrumbView = Marionette.LayoutView.extend({
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

    var BreadcrumbContainerView = Marionette.CollectionView.extend({
        childView: BreadcrumbView,
        tagName: "ol",
    });

    var BreadcrumbListView = Marionette.LayoutView.extend({
        tagName: "div",
        template: "#breadcrumb-list-template",
        regions: {
            body: {
                el: '.not-home',
            },
        },
        // TODO: in 3, replace onShow with onRender and show with showChildView (see CollectionView docs on
        // rendering tables)
        onShow: function () {
            this.getRegion('body').show(new BreadcrumbContainerView({
                collection: this.collection,
            }));
        },
        events: {
            'click .js-home': 'onClickHome',
        },
        onClickHome: function () {
            FormplayerFrontend.trigger('navigateHome');
        },
    });

    var DetailView = Marionette.LayoutView.extend({
        tagName: "tr",
        className: "",
        template: "#detail-view-item-template",
        templateHelpers: function () {
            var appId = Util.currentUrlToObject().appId;
            return {
                resolveUri: function (uri) {
                    return FormplayerFrontend.getChannel().request('resourceMap', uri, appId);
                },
            };
        },
    });

    var DetailListView = Marionette.CollectionView.extend({
        childView: DetailView,
        tagName: "tbody",
    });

    var DetailTabView = Marionette.LayoutView.extend({
        tagName: "li",
        className: function () {
            return this.options.model.get('active') ? 'active' : '';
        },
        template: "#detail-view-tab-item-template",
        events: {
            "click": "tabClick",
        },
        initialize: function (options) {
            this.index = options.model.get('id');
            this.active = options.model.get('active');
            this.showDetail = options.showDetail;
        },
        tabClick: function (e) {
            e.preventDefault();
            this.options.showDetail(this.index);
        },
    });

    var DetailTabListView = Marionette.CollectionView.extend({
        tagName: "ul",
        className: "nav nav-tabs",
        childView: DetailTabView,
        childViewOptions: function () {
            return {
                showDetail: this.options.showDetail,
            };
        },
        onRender: function () {
            this.$el.attr("role", "tablist");
        },
    });

    return {
        buildCaseTileStyles: buildCaseTileStyles,
        BreadcrumbListView: function (options) {
            return new BreadcrumbListView(options);
        },
        CaseListDetailView: function (options) {
            return new CaseListDetailView(options);
        },
        CaseListView: function (options) {
            return new CaseListView(options);
        },
        CaseTileListView: function (options) {
            return new CaseTileListView(options);
        },
        DetailListView: function (options) {
            return new DetailListView(options);
        },
        DetailTabListView: function (options) {
            return new DetailTabListView(options);
        },
        GridCaseTileListView: function (options) {
            return new GridCaseTileListView(options);
        },
        MenuListView: function (options) {
            return new MenuListView(options);
        },
        PersistentCaseTileView: function (options) {
            return new PersistentCaseTileView(options);
        },
    };
})
;
