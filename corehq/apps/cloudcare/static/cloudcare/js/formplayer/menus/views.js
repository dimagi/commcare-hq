/*global Marionette */

hqDefine("cloudcare/js/formplayer/menus/views", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        Util = hqImport("cloudcare/js/formplayer/utils/util");

    var MenuView = Marionette.View.extend({
        tagName: function () {
            if (this.model.collection.layoutStyle === 'grid') {
                return 'div';
            } else {
                return 'tr';
            }
        },
        className: "formplayer-request",
        attributes: function () {
            var displayText = this.options.model.attributes.displayText;
            return {
                "role": "link",
                "tabindex": "0",
                "aria-label": displayText,
            };
        },
        events: {
            "click": "rowClick",
            "click .js-module-audio-play": "audioPlay",
            "click .js-module-audio-pause": "audioPause",
            "keydown": "rowKeyAction",
        },

        initialize: function (options) {
            this.menuIndex = options.menuIndex;
        },

        getTemplate: function () {
            var id = "#menu-view-row-template";
            if (this.model.collection.layoutStyle === hqImport("cloudcare/js/formplayer/constants").LayoutStyles.GRID) {
                id = "#menu-view-grid-item-template";
            } else if (this.model.get('audioUri')) {
                id = "#menu-view-row-audio-template";
            }
            return _.template($(id).html() || "");
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
        rowKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.rowClick(e);
            }
        },
        templateContext: function () {
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

    var MenuListView = Marionette.CollectionView.extend({
        tagName: "div",
        childView: MenuView,
        childViewContainer: ".menus-container",
        getTemplate: function () {
            var id = "#menu-view-list-template";
            if (this.collection.layoutStyle === hqImport("cloudcare/js/formplayer/constants").LayoutStyles.GRID) {
                id = "#menu-view-grid-template";
            }
            return _.template($(id).html() || "");
        },
        templateContext: function () {
            return {
                title: this.options.title,
                environment: FormplayerFrontend.getChannel().request('currentUser').environment,
            };
        },
        childViewOptions: function (model) {
            return {
                sessionId: this.options.sessionId,
                menuIndex: this.collection.indexOf(model),
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

    var CaseView = Marionette.View.extend({
        tagName: "tr",
        template: _.template($("#case-view-item-template").html() || ""),

        events: {
            "click": "rowClick",
            "keydown": "rowKeyAction",
        },

        className: "formplayer-request",

        attributes: function () {
            return {
                "tabindex": "0",
            };
        },

        rowClick: function (e) {
            e.preventDefault();
            FormplayerFrontend.trigger("menu:show:detail", this.model.get('id'), 0, false);
        },

        rowKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.rowClick(e);
            }
        },

        templateContext: function () {
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
        template: _.template($("#case-tile-view-item-template").html() || ""),
        templateContext: function () {
            var dict = CaseTileView.__super__.templateContext.apply(this, arguments);
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

    var CaseListView = Marionette.CollectionView.extend({
        tagName: "div",
        template: _.template($("#case-view-list-template").html() || ""),

        childViewContainer: ".js-case-container",
        childView: CaseView,
        childViewOptions: function () {
            return {
                styles: this.options.styles,
            };
        },

        initialize: function (options) {
            this.styles = options.styles;
            this.hasNoItems = options.collection.length === 0;
            this.redoLast = options.redoLast;
        },

        ui: {
            actionButton: '.caselist-action-button button',
            searchButton: '#case-list-search-button',
            searchTextBox: '.module-search-container',
            paginators: '.js-page',
            paginationGoButton: '#pagination-go-button',
            paginationGoTextBox: '.module-go-container',
            columnHeader: '.header-clickable',
            paginationGoText: '#goText',
            casesPerPageLimit: '.per-page-limit',
        },

        events: {
            'click @ui.actionButton': 'caseListAction',
            'click @ui.searchButton': 'caseListSearch',
            'click @ui.paginators': 'paginateAction',
            'click @ui.paginationGoButton': 'paginationGoAction',
            'click @ui.columnHeader': 'columnSortAction',
            'change @ui.casesPerPageLimit': 'onPerPageLimitChange',
            'keypress @ui.searchTextBox': 'searchTextKeyAction',
            'keypress @ui.paginationGoTextBox': 'paginationGoKeyAction',
            'keypress @ui.paginators': 'paginateKeyAction',
        },

        caseListAction: function (e) {
            var index = $(e.currentTarget).data().index,
                selection = "action " + index;
            if (selection === this.redoLast) {
                FormplayerFrontend.trigger("menu:select");
            } else {
                FormplayerFrontend.trigger("menu:select", selection);
            }
        },

        caseListSearch: function (e) {
            e.preventDefault();
            var searchText = $('#searchText').val();
            FormplayerFrontend.trigger("menu:search", searchText);
        },

        searchTextKeyAction: function (event) {
            // Pressing Enter in the search box activates it.
            if (event.which === 13 || event.keyCode === 13) {
                this.caseListSearch(event);
            }
        },

        paginateAction: function (e) {
            var pageSelection = $(e.currentTarget).data("id");
            FormplayerFrontend.trigger("menu:paginate", pageSelection);
        },

        onPerPageLimitChange: function (e) {
            e.preventDefault();
            var casesPerPage = this.ui.casesPerPageLimit.val();
            FormplayerFrontend.trigger("menu:perPageLimit", casesPerPage);
        },

        paginationGoAction: function (e) {
            e.preventDefault();
            var goText = Number(this.ui.paginationGoText.val());
            var pageNo = paginationGoPageNumber(goText, this.options.pageCount);
            FormplayerFrontend.trigger("menu:paginate", pageNo - 1);
        },

        paginateKeyAction: function (e) {
            // Pressing Enter on a pagination control activates it.
            if (event.which === 13 || event.keyCode === 13) {
                e.stopImmediatePropagation();
                this.paginateAction(e);
            }
        },

        paginationGoKeyAction: function (e) {
            // Pressing Enter in the go box activates it.
            if (event.which === 13 || event.keyCode === 13) {
                e.stopImmediatePropagation();
                this.paginationGoAction(e);
            }
        },

        columnSortAction: function (e) {
            var columnSelection = $(e.currentTarget).data("id") + 1;
            FormplayerFrontend.trigger("menu:sort", columnSelection);
        },

        templateContext: function () {
            var paginateItems = paginateOptions(this.options.currentPage, this.options.pageCount);
            var casesPerPage = parseInt($.cookie("cases-per-page-limit")) || 10;
            return {
                startPage: paginateItems.startPage,
                title: this.options.title,
                headers: this.options.headers,
                widthHints: this.options.widthHints,
                actions: this.options.actions,
                currentPage: this.options.currentPage,
                endPage: paginateItems.endPage,
                pageCount: paginateItems.pageCount,
                rowRange: [10, 25, 50, 100],
                limit: casesPerPage,
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
                pageNumLabel: _.template(gettext("Page <%-num%>")),
            };
        },
    });

    // this method takes current page number on which user has clicked and total possible pages
    // and calculate the range of page numbers (start and end) that has to be shown on pagination widget.
    var paginateOptions = function (currentPage, totalPages) {
        var maxPages = 5;
        // ensure current page isn't out of range
        if (currentPage < 1) {
            currentPage = 1;
        } else if (currentPage > totalPages) {
            currentPage = totalPages;
        }
        var startPage, endPage;
        if (totalPages <= maxPages) {
            // total pages less than max so show all pages
            startPage = 1;
            endPage = totalPages;
        } else {
            // total pages more than max so calculate start and end pages
            var maxPagesBeforeCurrentPage = Math.floor(maxPages / 2);
            var maxPagesAfterCurrentPage = Math.ceil(maxPages / 2) - 1;
            if (currentPage <= maxPagesBeforeCurrentPage) {
                // current page near the start
                startPage = 1;
                endPage = maxPages;
            } else if (currentPage + maxPagesAfterCurrentPage >= totalPages) {
                // current page near the end
                startPage = totalPages - maxPages + 1;
                endPage = totalPages;
            } else {
                // current page somewhere in the middle
                startPage = currentPage - maxPagesBeforeCurrentPage;
                endPage = currentPage + maxPagesAfterCurrentPage;
            }
        }
        return {
            startPage: startPage,
            endPage: endPage,
            pageCount: totalPages,
        };
    };

    var paginationGoPageNumber = function (pageNumber, pageCount) {
        if (pageNumber >= 1 && pageNumber <= pageCount) {
            return pageNumber;
        } else {
            return pageCount;
        }
    };

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

        templateContext: function () {
            var dict = CaseTileListView.__super__.templateContext.apply(this, arguments);
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
        template: _.template($("#case-view-list-detail-template").html() || ""),
        childView: CaseViewUnclickable,
    });

    var BreadcrumbView = Marionette.View.extend({
        tagName: "li",
        template: _.template($("#breadcrumb-item-template").html() || ""),
        className: "breadcrumb-text",
        attributes: function () {
            return {
                "role": "link",
                "tabindex": "0",
            };
        },
        events: {
            "click": "crumbClick",
            "keydown": "crumbKeyAction",
        },

        crumbClick: function (e) {
            e.preventDefault();
            var crumbId = this.options.model.get('id');
            FormplayerFrontend.trigger("breadcrumbSelect", crumbId);
        },
        crumbKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.crumbClick(e);
            }
        },
    });

    var BreadcrumbListView = Marionette.CollectionView.extend({
        tagName: "div",
        template: _.template($("#breadcrumb-list-template").html() || ""),
        childView: BreadcrumbView,
        childViewContainer: "ol",
        events: {
            'click .js-home': 'onClickHome',
            'keydown .js-home': 'onKeyActionHome',
        },
        onClickHome: function () {
            FormplayerFrontend.trigger('navigateHome');
        },
        onKeyActionHome: function (e) {
            if (e.keyCode === 13) {
                this.onClickHome();
            }
        },
    });

    var LanguageOptionView = Marionette.View.extend({
        tagName: "li",
        template: _.template($("#language-option-template").html() || ""),
        events: {
            'click': 'onChangeLang',
        },
        onChangeLang: function (e) {
            var lang = e.target.id;
            $.publish('formplayer.change_lang', lang);
        },
    });

    var FormMenuView = Marionette.CollectionView.extend({
        template: _.template($("#form-menu-template").html() || ""),
        tagName: 'li',
        childView: LanguageOptionView,
        childViewContainer: 'ul',
    });

    var DetailView = Marionette.View.extend({
        tagName: "tr",
        className: "",
        template: _.template($("#detail-view-item-template").html() || ""),
        templateContext: function () {
            var appId = Util.currentUrlToObject().appId;
            return {
                resolveUri: function (uri) {
                    return FormplayerFrontend.getChannel().request('resourceMap', uri, appId);
                },
            };
        },
    });

    var DetailListView = Marionette.CollectionView.extend({
        tagName: "table",
        className: "table module-table module-table-casedetail",
        template: _.template($("#detail-view-list-template").html() || ""),
        childView: DetailView,
    });

    var DetailTabView = Marionette.View.extend({
        tagName: "li",
        className: function () {
            return this.options.model.get('active') ? 'active' : '';
        },
        template: _.template($("#detail-view-tab-item-template").html() || ""),
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
        tagName: "div",
        template: _.template($("#detail-view-tab-list-template").html() || ""),
        childView: DetailTabView,
        childViewContainer: "ul",
        childViewOptions: function () {
            return {
                showDetail: this.options.showDetail,
            };
        },
    });

    return {
        buildCaseTileStyles: buildCaseTileStyles,
        BreadcrumbListView: function (options) {
            return new BreadcrumbListView(options);
        },
        FormMenuView: function (options) {
            return new FormMenuView(options);
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
        paginateOptions: paginateOptions,
        paginationGoPageNumber: paginationGoPageNumber,
    };
})
;
