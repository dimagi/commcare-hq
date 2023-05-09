/*globals DOMPurify, Marionette */

hqDefine("cloudcare/js/formplayer/menus/views", function () {
    var kissmetrics = hqImport("analytix/js/kissmetrix"),
        constants = hqImport("cloudcare/js/formplayer/constants"),
        FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        toggles = hqImport("hqwebapp/js/toggles"),
        utils = hqImport("cloudcare/js/formplayer/utils/utils");

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
            if (this.model.collection.layoutStyle === constants.LayoutStyles.GRID) {
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
            var appId = utils.currentUrlToObject().appId;
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
            if (this.collection.layoutStyle === constants.LayoutStyles.GRID) {
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
            heightPixels = "auto";
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

    // Dynamically generate the CSS style to display multiple tiles per line
    var buildCellWrapperStyle = function (numRows, numColumns, numCasesPerRow) {
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
        outerGridTemplateString = $("#cell-wrapper-style-template").html();
        outerGridStyleTemplate = _.template(outerGridTemplateString);
        outerGridStyle = outerGridStyleTemplate({
            model: outerGridModel,
        });
        return outerGridStyle;
    };

    var CaseView = Marionette.View.extend({
        tagName: "tr",
        template: _.template($("#case-view-item-template").html() || ""),

        ui: {
            selectRow: ".select-row-checkbox",
        },

        events: {
            "click": "rowClick",
            "keydown": "rowKeyAction",
            'click @ui.selectRow': 'selectRowAction',
            'keypress @ui.selectRow': 'selectRowAction',
        },

        initialize: function () {
            var self = this;
            self.isMultiSelect = this.options.isMultiSelect;
            FormplayerFrontend.on("multiSelect:updateCases", function (action, caseIds) {
                if (_.contains(caseIds, self.model.get('id'))) {
                    self.ui.selectRow.prop("checked", action === constants.MULTI_SELECT_ADD);
                }
            });
        },

        className: "formplayer-request",

        attributes: function () {
            return {
                "tabindex": "0",
            };
        },

        rowClick: function (e) {
            if (!(e.target.classList.contains('module-case-list-column-checkbox') || e.target.classList.contains("select-row-checkbox"))) {
                e.preventDefault();
                FormplayerFrontend.trigger("menu:show:detail", this.model.get('id'), 0, this.isMultiSelect);
            }
        },

        rowKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.rowClick(e);
            }
        },

        selectRowAction: function (e) {
            var action = e.target.checked ? constants.MULTI_SELECT_ADD : constants.MULTI_SELECT_REMOVE;
            FormplayerFrontend.trigger("multiSelect:updateCases", action, [this.model.get('id')]);
        },

        isChecked: function () {
            return this.ui.selectRow.prop("checked");
        },

        templateContext: function () {
            var appId = utils.currentUrlToObject().appId;
            return {
                data: this.options.model.get('data'),
                styles: this.options.styles,
                isMultiSelect: this.options.isMultiSelect,
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
            var dict = CaseTileView.__super__.templateContext.apply(this, arguments),
                md = window.markdownit();
            dict['prefix'] = this.options.prefix;
            dict['renderMarkdown'] = function (datum) {
                return md.render(DOMPurify.sanitize(datum || ""));
            };
            return dict;
        },
    });

    var PersistentCaseTileView = CaseTileView.extend({
        rowClick: function (e) {
            e.preventDefault();
            if (this.options.hasInlineTile) {
                FormplayerFrontend.trigger("menu:show:detail", this.options.model.get('id'), 0, false, true);
            }
        },
    });

    var CaseListViewUI = function () {
        return {
            actionButton: '.case-list-action-button button',
            searchButton: '#case-list-search-button',
            searchTextBox: '.module-search-container',
            paginators: '.js-page',
            paginationGoButton: '#pagination-go-button',
            paginationGoTextBox: '.module-go-container',
            columnHeader: '.header-clickable',
            paginationGoText: '#goText',
            casesPerPageLimit: '.per-page-limit',
        };
    };

    var CaseListViewEvents = function () {
        return {
            'click @ui.actionButton': 'caseListAction',
            'click @ui.searchButton': 'caseListSearch',
            'click @ui.paginators': 'paginateAction',
            'click @ui.paginationGoButton': 'paginationGoAction',
            'click @ui.columnHeader': 'columnSortAction',
            'change @ui.casesPerPageLimit': 'onPerPageLimitChange',
            'keypress @ui.searchTextBox': 'searchTextKeyAction',
            'keypress @ui.paginationGoTextBox': 'paginationGoKeyAction',
            'keypress @ui.paginators': 'paginateKeyAction',
        };
    };

    var CaseListView = Marionette.CollectionView.extend({
        tagName: "div",
        template: _.template($("#case-view-list-template").html() || ""),

        childViewContainer: ".js-case-container",
        childView: CaseView,
        childViewOptions: function () {
            return {
                styles: this.options.styles,
                isMultiSelect: false,
            };
        },

        initialize: function (options) {
            var self = this;
            self.styles = options.styles;
            self.hasNoItems = options.collection.length === 0;
            self.redoLast = options.redoLast;
            if (sessionStorage.selectedValues !== undefined) {
                let parsedSelectedValues = JSON.parse(sessionStorage.selectedValues)[sessionStorage.queryKey];
                self.selectedCaseIds = parsedSelectedValues !== undefined && parsedSelectedValues !== '' ? parsedSelectedValues.split(',') : [];
            } else {
                self.selectedCaseIds = [];
            }
        },

        ui: CaseListViewUI(),

        events: CaseListViewEvents(),

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
            FormplayerFrontend.trigger("menu:paginate", pageSelection, this.selectedCaseIds);
            kissmetrics.track.event("Accessibility Tracking - Pagination Interaction");
        },

        onPerPageLimitChange: function (e) {
            e.preventDefault();
            var casesPerPage = this.ui.casesPerPageLimit.val();
            FormplayerFrontend.trigger("menu:perPageLimit", casesPerPage, this.selectedCaseIds);
        },

        paginationGoAction: function (e) {
            e.preventDefault();
            var goText = Number(this.ui.paginationGoText.val());
            var pageNo = utils.paginationGoPageNumber(goText, this.options.pageCount);
            FormplayerFrontend.trigger("menu:paginate", pageNo - 1, this.selectedCaseIds);
            kissmetrics.track.event("Accessibility Tracking - Pagination Go To Page Interaction");
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

        _allCaseIds: function () {
            var caseIds = [];
            this.children.each(function (childView) {
                caseIds.push(childView.model.get('id'));
            });
            return caseIds;
        },

        continueAction: function () {
            FormplayerFrontend.trigger("menu:select", this.selectedCaseIds);
            if (/search_command\.m\d+/.test(sessionStorage.queryKey)) {
                kissmetrics.track.event('Completed Case Search', {
                    'Split Screen Case Search': toggles.toggleEnabled('SPLIT_SCREEN_CASE_SEARCH'),
                });
            }
        },

        templateContext: function () {
            var paginateItems = utils.paginateOptions(this.options.currentPage, this.options.pageCount);
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
                noItemsText: this.options.collection.noItemsText,
                sortIndices: this.options.sortIndices,
                selectedCaseIds: this.selectedCaseIds,
                isMultiSelect: false,
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

    var MultiSelectCaseListView = CaseListView.extend({
        ui: _.extend(CaseListViewUI(), {
            selectAllCheckbox: "#select-all-checkbox",
            continueButton: "#multi-select-continue-btn",
            continueButtonText: "#multi-select-btn-text",
        }),

        events: _.extend(CaseListViewEvents(), {
            'click @ui.selectAllCheckbox': 'selectAllAction',
            'keypress @ui.selectAllCheckbox': 'selectAllAction',
            'click @ui.continueButton': 'continueAction',
            'keypress @ui.continueButton': 'continueAction',
        }),

        childViewOptions: function () {
            var options = MultiSelectCaseListView.__super__.childViewOptions.apply(this);
            options.isMultiSelect = true;
            return options;
        },

        initialize: function (options) {    // eslint-disable-line no-unused-vars
            MultiSelectCaseListView.__super__.initialize.apply(this, arguments);
            var self = this;
            self.maxSelectValue = options.multiSelectMaxSelectValue;
            // Remove any event handling left over from previous instances of MultiSelectCaseListView.
            // Only one of these views is supporteed on the page at any given time.
            FormplayerFrontend.off("multiSelect:updateCases").on("multiSelect:updateCases", function (action, caseIds) {
                if (action === constants.MULTI_SELECT_ADD) {
                    self.selectedCaseIds = _.union(self.selectedCaseIds, caseIds);
                } else {
                    self.selectedCaseIds = _.difference(self.selectedCaseIds, caseIds);
                }
                self.reconcileMultiSelectUI();
            });
        },

        templateContext: function () {
            var context = MultiSelectCaseListView.__super__.templateContext.apply(this);
            context.isMultiSelect = true;
            return context;
        },

        onRender: function () {
            this.reconcileMultiSelectUI();
        },

        selectAllAction: function (e) {
            var action = e.target.checked ? constants.MULTI_SELECT_ADD : constants.MULTI_SELECT_REMOVE;
            FormplayerFrontend.trigger("multiSelect:updateCases", action, this._allCaseIds());
        },

        reconcileMultiSelectUI: function () {
            var self = this;

            self.verifySelectedCaseIdsLessThanMaxSelectValue();

            // Update states of row checkboxes
            self.children.each(function (childView) {
                childView.ui.selectRow.prop("checked", self.selectedCaseIds.indexOf(childView.model.id) !== -1);
            });

            // Update state of Continue button
            self.ui.continueButtonText.text(self.selectedCaseIds.length);
            self.ui.continueButton.prop("disabled", !self.selectedCaseIds.length);

            // Reconcile state of "select all" checkbox
            self.ui.selectAllCheckbox.prop("checked", !_.difference(self._allCaseIds(), self.selectedCaseIds).length);
        },

        verifySelectedCaseIdsLessThanMaxSelectValue: function () {
            if (this.selectedCaseIds.length > this.maxSelectValue) {
                let errorMessage = _.template(gettext("You have selected more than the maximum selection limit " +
                    "of <%= value %> . Please uncheck some values to continue."))({ value: this.maxSelectValue });
                hqRequire(["hqwebapp/js/alert_user"], function (alertUser) {
                    alertUser.alert_user(errorMessage, 'danger');
                });
            }
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
            var cellWrapperStyle = buildCellWrapperStyle(numRows, numColumns, numEntitiesPerRow);
            return [cellLayoutStyle, cellGridStyle, cellWrapperStyle];
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
                $("#list-cell-wrapper-style").html(caseTileStyles[2]).data("css-polyfilled", false);
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
        className: "formplayer-request list-cell-wrapper-style",
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
            'keydown .lang': 'onKeyActionChangeLang',
        },
        initialize: function (options) {
            this.languageOptionsEnabled = options.languageOptionsEnabled;
        },
        templateContext: function () {
            return {
                languageOptionsEnabled: this.languageOptionsEnabled,
            };
        },
        onKeyActionChangeLang: function (e) {
            if (e.keyCode === 13) {
                this.onChangeLang(e);
            }
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
        ui: {
            dropdownMenu: "#form-menu-dropdown",
            selectPrint: "#print-header.dropdown-header",
        },
        childViewOptions: function () {
            return {
                languageOptionsEnabled: Boolean(this.options.collection),
            };
        },
        templateContext: function () {
            var languageOptionsEnabled = Boolean(this.options.collection);
            return {
                languageOptionsEnabled: languageOptionsEnabled,
            };
        },
        events: {
            "keydown": "expandDropdown",
            "keydown @ui.selectPrint": "printKeyAction",
            "click @ui.selectPrint": "print",
        },
        expandDropdown: function (e) {
            if (e.keyCode === 13 || e.keyCode === 32) {
                e.preventDefault();
                $(this.ui.dropdownMenu).toggleClass("open");
            }
        },
        printKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.print();
            }
        },
        print: function () {
            window.print();
        },
    });

    var DetailView = Marionette.View.extend({
        tagName: "tr",
        className: "",
        template: _.template($("#detail-view-item-template").html() || ""),
        templateContext: function () {
            var appId = utils.currentUrlToObject().appId;
            return {
                resolveUri: function (uri) {
                    return FormplayerFrontend.getChannel().request('resourceMap', uri, appId);
                },
            };
        },
    });

    var DetailListView = Marionette.CollectionView.extend({
        tagName: "table",
        className: "table module-table module-table-case-detail",
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
            this.onTabClick = options.onTabClick;
        },
        tabClick: function (e) {
            e.preventDefault();
            this.options.onTabClick(this.index);
        },
    });

    var DetailTabListView = Marionette.CollectionView.extend({
        tagName: "div",
        template: _.template($("#detail-view-tab-list-template").html() || ""),
        childView: DetailTabView,
        childViewContainer: "ul",
        childViewOptions: function () {
            return {
                onTabClick: this.options.onTabClick,
            };
        },
    });

    var CaseDetailFooterView = Marionette.View.extend({
        tagName: "div",
        className: "",
        events: {
            "click #select-case": "selectCase",
        },
        getTemplate: function () {
            var id = "#module-case-detail";
            if (this.isPersistentDetail) {
                return _.template("");
            } else if (this.isMultiSelect) {
                id = "#module-case-detail-multi-select";
            }
            return _.template($(id).html() || "");
        },
        initialize: function (options) {
            this.isPersistentDetail = options.model.get('isPersistentDetail');
            this.isMultiSelect = options.isMultiSelect;
            this.caseId = options.caseId;
        },
        selectCase: function () {
            if (this.isMultiSelect) {
                FormplayerFrontend.trigger("multiSelect:updateCases", constants.MULTI_SELECT_ADD, [this.caseId]);
            } else {
                FormplayerFrontend.trigger("menu:select", this.caseId);
                if (/search_command\.m\d+/.test(sessionStorage.queryKey)) {
                    kissmetrics.track.event('Completed Case Search', {
                        'Split Screen Case Search': toggles.toggleEnabled('SPLIT_SCREEN_CASE_SEARCH'),
                    });
                }
            }
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
        CaseDetailFooterView: function (options) {
            return new CaseDetailFooterView(options);
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
        MultiSelectCaseListView: function (options) {
            return new MultiSelectCaseListView(options);
        },
        PersistentCaseTileView: function (options) {
            return new PersistentCaseTileView(options);
        },
    };
})
;
