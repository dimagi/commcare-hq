/*globals DOMPurify, Marionette */

hqDefine("cloudcare/js/formplayer/menus/views", function () {
    const kissmetrics = hqImport("analytix/js/kissmetrix"),
        constants = hqImport("cloudcare/js/formplayer/constants"),
        FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
        initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        toggles = hqImport("hqwebapp/js/toggles"),
        formplayerUtils = hqImport("cloudcare/js/formplayer/utils/utils"),
        cloudcareUtils = hqImport("cloudcare/js/utils"),
        markdown = hqImport("cloudcare/js/markdown");

    const MenuView = Marionette.View.extend({
        tagName: function () {
            if (this.model.collection.layoutStyle === 'grid') {
                return 'div';
            } else {
                return 'tr';
            }
        },
        className: "formplayer-request",
        attributes: function () {
            const displayText = this.options.model.attributes.displayText;
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
            let id = "#menu-view-row-template";
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
                const model = this.model;
                FormplayerFrontend.trigger("menu:select", model.get('index'));
            }
        },
        audioPlay: function (e) {
            e.preventDefault();
            const $playBtn = $(e.originalEvent.srcElement).closest('.js-module-audio-play');
            const $pauseBtn = $playBtn.parent().find('.js-module-audio-pause');
            $pauseBtn.removeClass('hide');
            $playBtn.addClass('hide');
            const $audioElem = $playBtn.parent().find('.js-module-audio');
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
            const $pauseBtn = $(e.originalEvent.srcElement).closest('.js-module-audio-pause');
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
            const imageUri = this.options.model.get('imageUri');
            const audioUri = this.options.model.get('audioUri');
            const navState = this.options.model.get('navigationState');
            const appId = formplayerUtils.currentUrlToObject().appId;
            return {
                navState: navState,
                imageUrl: imageUri ? FormplayerFrontend.getChannel().request('resourceMap', imageUri, appId) : "",
                audioUrl: audioUri ? FormplayerFrontend.getChannel().request('resourceMap', audioUri, appId) : "",
                menuIndex: this.menuIndex,
            };
        },
    });

    const MenuListView = Marionette.CollectionView.extend({
        tagName: "div",
        childView: MenuView,
        childViewContainer: ".menus-container",
        getTemplate: function () {
            let id = "#menu-view-list-template";
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
    const getGridAttributes = function (tile) {
        if (!tile) {
            return null;
        }
        const rowStart = tile.gridY + 1;
        const colStart = tile.gridX + 1;
        const rowEnd = rowStart + tile.gridHeight;
        const colEnd = colStart + tile.gridWidth;

        return rowStart + " / " + colStart + " / " +
            rowEnd + " / " + colEnd;
    };
    // use the field alignment from xml template only if valid
    const getValidFieldAlignment = function (alignment) {
        return constants.ALLOWED_FIELD_ALIGNMENTS.includes(alignment) ? alignment : 'start';
    };
    // generate the case tile's style block and insert
    const buildCellLayout = function (tiles, styles, prefix) {
        const tileModels = _.chain(tiles || [])
            .map(function (tile, idx) {
                if (tile === null || tile === undefined) {
                    return null;
                }
                const style = styles[idx] || {};
                return {
                    id: prefix + '-grid-style-' + idx,
                    gridStyle: getGridAttributes(tile),
                    fontStyle: tile.fontSize,
                    verticalAlign: getValidFieldAlignment(style.verticalAlign),
                    horizontalAlign: getValidFieldAlignment(style.horizontalAlign),
                };
            })
            .filter(function (tile) {
                return tile !== null;
            }).value();

        const templateString = $("#cell-layout-style-template").html();
        const caseTileStyleTemplate = _.template(templateString);
        const caseTileStyle = caseTileStyleTemplate({
            models: tileModels,
        });
        return caseTileStyle;
    };

    // Dynamically generate the CSS style for the grid polyfill to use for the case tile
    // useUniformUnits - true if the grid's cells should have the same height as width
    const buildCellGridStyle = function (numRows, numColumns, useUniformUnits, prefix) {
        let heightString;

        if (useUniformUnits) {
            const heightPercentage = 100 / numColumns;
            heightString = heightPercentage + "cqw";
        } else {
            heightString = "auto";
        }

        const model = {
            numRows: numRows,
            numColumns: numColumns,
            heightString: heightString,
            prefix: prefix,
        };
        const templateString = $("#cell-grid-style-template").html();
        const template = _.template(templateString);
        const view = template({
            model: model,
        });
        return view;
    };

    // Dynamically generate the CSS style to display multiple tiles per line
    const buildCellContainerStyle = function (numCasesPerRow) {
        const caseListLayoutString = $("#cell-container-style-template").html();
        const caseListLayoutTemplate = _.template(caseListLayoutString);
        const caseListLayout = caseListLayoutTemplate({
            casesPerRow: numCasesPerRow,
        });
        return caseListLayout;
    };

    const CaseView = Marionette.View.extend({
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
            const self = this;
            self.isMultiSelect = this.options.isMultiSelect;
            FormplayerFrontend.on("multiSelect:updateCases", function (action, caseIds) {
                if (_.contains(caseIds, self.model.get('id'))) {
                    self.ui.selectRow.prop("checked", action === constants.MULTI_SELECT_ADD);
                }
            });
        },

        className: "formplayer-request case-row",

        attributes: function () {
            let modelId = this.model.get('id');
            return {
                "tabindex": "0",
                "id": `row-${modelId}`,
            };
        },

        rowClick: function (e) {
            if (!(
                e.target.classList.contains('module-case-list-column-checkbox') ||  // multiselect checkbox
                e.target.classList.contains("select-row-checkbox") ||               // multiselect select all
                $(e.target).is('a')                                                 // actual link, as in markdown
            )) {
                e.preventDefault();
                let modelId = this.model.get('id');
                if (!this.model.collection.hasDetails) {
                    if (this.isMultiSelect) {
                        let action = this.isChecked() ? constants.MULTI_SELECT_ADD : constants.MULTI_SELECT_REMOVE;
                        FormplayerFrontend.trigger("multiSelect:updateCases", action, [modelId]);
                    } else {
                        FormplayerFrontend.trigger("menu:select", modelId);
                    }
                    return;
                }
                FormplayerFrontend.trigger("menu:show:detail", modelId, 0, this.isMultiSelect);
            }
        },

        rowKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.rowClick(e);
            }
        },

        selectRowAction: function (e) {
            const action = e.target.checked ? constants.MULTI_SELECT_ADD : constants.MULTI_SELECT_REMOVE;
            FormplayerFrontend.trigger("multiSelect:updateCases", action, [this.model.get('id')]);
        },

        isChecked: function () {
            return this.ui.selectRow.prop("checked");
        },

        templateContext: function () {
            const appId = formplayerUtils.currentUrlToObject().appId;
            return {
                data: this.options.model.get('data'),
                styles: this.options.styles,
                isMultiSelect: this.options.isMultiSelect,
                renderMarkdown: markdown.render,
                resolveUri: function (uri) {
                    return FormplayerFrontend.getChannel().request('resourceMap', uri, appId);
                },
            };
        },
    });

    const CaseViewUnclickable = CaseView.extend({
        events: {},
        className: "",
        rowClick: function () {},
    });

    const CaseTileView = CaseView.extend({
        tagName: "div",
        className: "formplayer-request list-cell-wrapper-style",
        template: _.template($("#case-tile-view-item-template").html() || ""),
        templateContext: function () {
            const dict = CaseTileView.__super__.templateContext.apply(this, arguments);
            dict['prefix'] = this.options.prefix;
            return dict;
        },
    });

    const CaseTileGroupedView = CaseTileView.extend({
        tagName: "div",
        className: "formplayer-request list-cell-wrapper-style case-tile-group",
        template: _.template($("#case-tile-grouped-view-item-template").html() || ""),
        templateContext: function () {
            const dict = CaseTileGroupedView.__super__.templateContext.apply(this, arguments);
            dict['groupHeaderRows'] = this.options.groupHeaderRows;

            const data = this.options.model.get('data');
            const headerRowIndices = this.options.headerRowIndices;
            dict['indexedHeaderData'] = headerRowIndices.reduce((acc, index) => {
                acc[index] = data[index];
                return acc;
            }, {});

            dict['indexedRowDataList'] = this.getIndexedRowDataList();

            return dict;
        },

        getIndexedRowDataList: function () {
            let indexedRowDataList = [];
            for (let model of this.options.groupModelsList) {
                let indexedRowData = model.get('data')
                    .reduce((acc, data, i) => {
                        if (!this.options.headerRowIndices.includes(i) &&
                            this.options.styles[i].widthHint !== 0) {
                            acc[i] = data;
                        }
                        return acc;
                    }, {});
                if (Object.keys(indexedRowData).length !== 0) {
                    indexedRowDataList.push(indexedRowData);
                }
            }
            return indexedRowDataList;
        },
    });

    const PersistentCaseTileView = CaseTileView.extend({
        className: "formplayer-request",
        rowClick: function (e) {
            e.preventDefault();
            if (this.options.hasInlineTile) {
                FormplayerFrontend.trigger("menu:show:detail", this.options.model.get('id'), 0, false, true);
            }
        },
    });

    const CaseListViewUI = function () {
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

    const CaseListViewEvents = function () {
        return {
            'click @ui.actionButton': 'caseListAction',
            'click @ui.searchButton': 'caseListSearch',
            'click @ui.paginators': 'paginateAction',
            'click @ui.paginationGoButton': 'paginationGoAction',
            'click @ui.columnHeader': 'columnSortAction',
            'keypress @ui.columnHeader': 'columnSortAction',
            'change @ui.casesPerPageLimit': 'onPerPageLimitChange',
            'keypress @ui.searchTextBox': 'searchTextKeyAction',
            'keypress @ui.paginationGoTextBox': 'paginationGoKeyAction',
            'keypress @ui.paginators': 'paginateKeyAction',
        };
    };

    const CaseListView = Marionette.CollectionView.extend({
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
            const self = this;
            var sidebarNoItemsText = gettext("Please perform a search.");
            self.styles = options.styles;
            self.hasNoItems = options.collection.length === 0 || options.triggerEmptyCaseList;
            self.noItemsText = options.triggerEmptyCaseList ? sidebarNoItemsText : this.options.collection.noItemsText;
            self.headers = options.triggerEmptyCaseList ? [] : this.options.headers;
            self.redoLast = options.redoLast;
            if (sessionStorage.selectedValues !== undefined) {
                const parsedSelectedValues = JSON.parse(sessionStorage.selectedValues)[sessionStorage.queryKey];
                self.selectedCaseIds = parsedSelectedValues !== undefined && parsedSelectedValues !== '' ? parsedSelectedValues.split(',') : [];
            } else {
                self.selectedCaseIds = [];
            }
            const user = FormplayerFrontend.currentUser;
            const displayOptions = user.displayOptions;
            const appPreview = displayOptions.singleAppMode;
            const addressFieldPresent = !!_.find(this.styles, function (style) { return style.displayFormat === constants.FORMAT_ADDRESS; });

            self.showMap = addressFieldPresent && !appPreview && !self.hasNoItems && toggles.toggleEnabled('CASE_LIST_MAP');
            self.smallScreenEnabled = cloudcareUtils.watchSmallScreenEnabled(enabled => self.smallScreenEnabled = enabled);
        },

        ui: CaseListViewUI(),

        events: CaseListViewEvents(),

        caseListAction: function (e) {
            const index = $(e.currentTarget).data().index,
                selection = "action " + index;
            if (selection === this.redoLast) {
                FormplayerFrontend.trigger("menu:select");
            } else {
                FormplayerFrontend.trigger("menu:select", selection);
            }
        },

        caseListSearch: function (e) {
            e.preventDefault();
            const searchText = $('#searchText').val();
            FormplayerFrontend.trigger("menu:search", searchText);
        },

        searchTextKeyAction: function (event) {
            // Pressing Enter in the search box activates it.
            if (event.which === 13 || event.keyCode === 13) {
                this.caseListSearch(event);
            }
        },

        paginateAction: function (e) {
            const pageSelection = $(e.currentTarget).data("id");
            FormplayerFrontend.trigger("menu:paginate", pageSelection, this.selectedCaseIds);
            kissmetrics.track.event("Accessibility Tracking - Pagination Interaction");
        },

        onPerPageLimitChange: function (e) {
            e.preventDefault();
            const casesPerPage = this.ui.casesPerPageLimit.val();
            FormplayerFrontend.trigger("menu:perPageLimit", casesPerPage, this.selectedCaseIds);
        },

        paginationGoAction: function (e) {
            e.preventDefault();
            const goText = Number(this.ui.paginationGoText.val());
            const pageNo = formplayerUtils.paginationGoPageNumber(goText, this.options.pageCount);
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
            if (e.type === 'click' || (e.type === 'keypress' && e.keyCode === 13)) {
                const columnSelection = $(e.currentTarget).data("id") + 1;
                FormplayerFrontend.trigger("menu:sort", columnSelection);
            }
        },

        _allCaseIds: function () {
            const caseIds = [];
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

        selectAllAction: function (e) {
            const action = e.target.checked ? constants.MULTI_SELECT_ADD : constants.MULTI_SELECT_REMOVE;
            FormplayerFrontend.trigger("multiSelect:updateCases", action, this._allCaseIds());
        },

        reconcileMultiSelectUI: function () {
            const self = this;

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
                hqRequire(["hqwebapp/js/bootstrap3/alert_user"], function (alertUser) {
                    alertUser.alert_user(errorMessage, 'danger');
                });
            }
        },

        columnStyle: function () {
            const self = this;
            if (self.showMap) {
                return "display: grid;grid-template-columns: [tiles] 7fr [map] 5fr;grid-template-rows: auto";
            } else {
                return "display: grid;grid-template-columns: [tiles] 100%;grid-template-rows: auto";
            }
        },

        fontAwesomeIcon: function (iconName) {
            return L.divIcon({
                html: `<i class='fa ${iconName} fa-4x'></i>`,
                iconSize: [12, 12],
                className: 'marker-pin',
            });
        },

        loadMap: function () {
            const token = initialPageData.get("mapbox_access_token");

            try {
                const locationIcon = this.fontAwesomeIcon("fa-map-marker");
                const selectedLocationIcon = this.fontAwesomeIcon("fa-star");
                const homeLocationIcon = this.fontAwesomeIcon("fa-street-view");

                const lat = 30;
                const lon = 15;
                const zoom = 3;
                const addressMap = L.map(
                    'module-case-list-map', {
                        zoomControl: false,
                    }).setView([lat, lon], zoom);

                L.control.zoom({
                    position: 'bottomright',
                }).addTo(addressMap);

                L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=' + token, {
                    id: 'mapbox/streets-v11',
                    attribution: '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> ©' +
                             ' <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
                    tileSize: 512,
                    zoomOffset: -1,
                }).addTo(addressMap);

                const addressIndex = _.findIndex(this.styles, function (style) { return style.displayFormat === constants.FORMAT_ADDRESS; });
                const popupIndex = _.findIndex(this.styles, function (style) { return style.displayFormat === constants.FORMAT_ADDRESS_POPUP; });
                L.mapbox.accessToken = token;

                const allCoordinates = [];
                const markers = [];
                this.options.collection.models
                    .forEach(model => {
                        const addressCoordinates = model.attributes.data[addressIndex];
                        if (addressCoordinates) {
                            let markerCoordinates = addressCoordinates.split(" ").slice(0,2);
                            if (markerCoordinates.length > 1) {
                                const rowId = `row-${model.id}`;
                                const popupText = markdown.render(model.attributes.data[popupIndex]);
                                let marker = L.marker(markerCoordinates, {icon: locationIcon});
                                markers.push(marker);
                                marker = marker.addTo(addressMap);
                                if (popupIndex >= 0) {
                                    marker = marker.bindPopup(popupText);
                                }

                                marker.on('click', () => {
                                    // tiles
                                    $(`.list-cell-wrapper-style[id!='${rowId}']`)
                                        .removeClass("highlighted-case");
                                    // rows
                                    $(`.case-row[id!='${rowId}']`)
                                        .removeClass("highlighted-case");
                                    $(`#${rowId}`)
                                        .addClass("highlighted-case");
                                    markers.forEach(m => m.setIcon(locationIcon));
                                    marker.setIcon(selectedLocationIcon);

                                    $([document.documentElement, document.body]).animate({
                                        // -50 Stay clear of the breadcrumbs
                                        scrollTop: $(`#${rowId}`).offset().top - 50,
                                    }, 500);

                                    addressMap.panTo(markerCoordinates);
                                });
                                allCoordinates.push(markerCoordinates);
                            }
                        }
                    });

                if (sessionStorage.locationLat) {
                    const homeCoordinates = [sessionStorage.locationLat, sessionStorage.locationLon];
                    L.marker(homeCoordinates, { icon: homeLocationIcon })
                        .bindPopup(gettext("Your location"))
                        .addTo(addressMap);
                    allCoordinates.push(homeCoordinates);
                }
                addressMap.fitBounds(allCoordinates, {maxZoom: 14});
            } catch (error) {
                console.error(error);
            }
        },

        onAttach() {
            const self = this;
            if (self.showMap) {
                self.loadMap();
            }
        },

        templateContext: function () {
            const paginateItems = formplayerUtils.paginateOptions(this.options.currentPage, this.options.pageCount);
            const casesPerPage = parseInt($.cookie("cases-per-page-limit")) || 10;
            const boldSortedCharIcon = (header) => {
                const headerWords = header.trim().split(' ');
                const lastChar = headerWords.pop();

                return lastChar === "Λ" || lastChar === "V"
                    ? `${headerWords.join(' ')} <b>${lastChar}</b>`
                    : header;
            };
            let description = this.options.description;
            let title = this.options.title;
            if (this.options.sidebarEnabled && this.options.collection.queryResponse) {
                description = this.options.collection.queryResponse.description;
                title = this.options.collection.queryResponse.title;
            }
            return {
                startPage: paginateItems.startPage,
                title: title.trim(),
                description: description === undefined ? "" : DOMPurify.sanitize(markdown.render(description.trim())),
                headers: this.headers.map(boldSortedCharIcon),
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
                useTiles: false,
                hasNoItems: this.hasNoItems,
                noItemsText: this.noItemsText,
                sortIndices: this.options.sortIndices,
                selectedCaseIds: this.selectedCaseIds,
                isMultiSelect: false,
                showMap: this.showMap,
                columnStyle: this.columnStyle(),
                sidebarEnabled: this.options.sidebarEnabled,
                smallScreenEnabled: this.smallScreenEnabled,
                triggerEmptyCaseList: this.options.triggerEmptyCaseList,

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

    const registerContinueListener = function (self, options) {
        self.maxSelectValue = options.multiSelectMaxSelectValue;
        // Remove any event handling left over from previous instances of MultiSelectCaseListView.
        // Only one of these views is supported on the page at any given time.
        FormplayerFrontend.off("multiSelect:updateCases").on("multiSelect:updateCases", function (action, caseIds) {
            if (action === constants.MULTI_SELECT_ADD) {
                self.selectedCaseIds = _.union(self.selectedCaseIds, caseIds);
            } else {
                self.selectedCaseIds = _.difference(self.selectedCaseIds, caseIds);
            }
            self.reconcileMultiSelectUI();
        });
    };

    const MultiSelectCaseListView = CaseListView.extend({
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
            const options = MultiSelectCaseListView.__super__.childViewOptions.apply(this);
            options.isMultiSelect = true;
            return options;
        },

        initialize: function (options) {    // eslint-disable-line no-unused-vars
            MultiSelectCaseListView.__super__.initialize.apply(this, arguments);
            registerContinueListener(this, options);
        },

        templateContext: function () {
            const context = MultiSelectCaseListView.__super__.templateContext.apply(this);
            context.isMultiSelect = true;
            return context;
        },

        onRender: function () {
            this.reconcileMultiSelectUI();
        },
    });

    // Return an object of case tile CSS styles that defines:
    // - layout of the content within a case list tile
    // - shape and size of the tile's layout grid
    // - the tile's visual style and its outer boundary
    // - layout of the case tiles on the outer, visible grid
    const buildCaseTileStyles = function (tiles, styles, numRows, numColumns, numEntitiesPerRow, useUniformUnits, prefix) {
        const caseTileStyles = {};
        caseTileStyles.cellLayoutStyle = buildCellLayout(tiles, styles, prefix);
        caseTileStyles.cellGridStyle = buildCellGridStyle(numRows, numColumns, useUniformUnits, prefix);
        if (numEntitiesPerRow > 1) {
            caseTileStyles.cellContainerStyle = buildCellContainerStyle(numEntitiesPerRow);
            caseTileStyles.cellWrapperStyle = $("#cell-wrapper-style-template");
        }
        return caseTileStyles;
    };

    const CaseTileListView = CaseListView.extend({
        ui: _.extend(CaseListViewUI(), {
            selectAllCheckbox: "#select-all-tile-checkbox",
            continueButton: "#multi-select-continue-btn",
            continueButtonText: "#multi-select-btn-text",
        }),
        childView: CaseTileView,

        initialize: function (options) {
            CaseTileListView.__super__.initialize.apply(this, arguments);

            const numEntitiesPerRow = options.numEntitiesPerRow || 1;
            const numRows = options.maxHeight;
            const numColumns = options.maxWidth;
            const useUniformUnits = options.useUniformUnits;

            const caseTileStyles = buildCaseTileStyles(options.tiles, options.styles, numRows, numColumns,
                numEntitiesPerRow, useUniformUnits, 'list');

            const gridPolyfillPath = FormplayerFrontend.getChannel().request('gridPolyfillPath');

            $("#list-cell-layout-style").html(caseTileStyles.cellLayoutStyle).data("css-polyfilled", false);
            $("#list-cell-grid-style").html(caseTileStyles.cellGridStyle).data("css-polyfilled", false);
            // If we have multiple cases per line, need to generate the outer grid style as well
            if (caseTileStyles.cellWrapperStyle && caseTileStyles.cellContainerStyle) {
                $("#list-cell-wrapper-style").html(caseTileStyles.cellWrapperStyle).data("css-polyfilled", false);
                $("#list-cell-container-style").html(caseTileStyles.cellContainerStyle).data("css-polyfilled", false);
            }

            $.getScript(gridPolyfillPath);

            registerContinueListener(this, options);
        },

        childViewOptions: function () {
            const dict = CaseTileListView.__super__.childViewOptions.apply(this, arguments);
            dict.prefix = 'list';
            dict.isMultiSelect = this.options.isMultiSelect;
            return dict;
        },

        templateContext: function () {
            const dict = CaseTileListView.__super__.templateContext.apply(this, arguments);
            dict.useTiles = true;
            dict.isMultiSelect = this.options.isMultiSelect;
            return dict;
        },

        events: _.extend(CaseListViewEvents(), {
            'click @ui.selectAllCheckbox': 'selectAllAction',
            'keypress @ui.selectAllCheckbox': 'selectAllAction',
            'click @ui.continueButton': 'continueAction',
            'keypress @ui.continueButton': 'continueAction',
        }),

        onRender: function () {
            if (this.options.isMultiSelect) {
                this.reconcileMultiSelectUI();
            }
        },
    });

    const CaseTileGroupedListView = CaseTileListView.extend({
        childView: CaseTileGroupedView,

        initialize: function () {
            CaseTileGroupedListView.__super__.initialize.apply(this, arguments);

            let clonedModels = this.options.collection.models.map((model) => model.clone());
            this.groupedModels = _.groupBy(clonedModels, (model) => model.get("groupKey"));
            for (let groupKey in this.groupedModels) {
                let models = this.groupedModels[groupKey];
                if (models.length > 1) {
                    // Only one childView will be created per group.
                    // The model for the first child is used, so subsequent models in the group need to be removed.
                    this.options.collection.remove(models.slice(1));
                }
            }

            let groupHeaderRows = this.options.collection.groupHeaderRows;
            // select the indices of the tile fields that are part of the header rows
            this.headerRowIndices = this.options.collection.tiles
                .map((tile, index) => ({tile: tile, index: index}))
                .filter((tile) => tile.tile && tile.tile.gridY < groupHeaderRows)
                .map((tile) => tile.index);
        },

        childViewOptions: function (model) {
            const dict = CaseTileGroupedListView.__super__.childViewOptions.apply(this, arguments);
            dict.groupHeaderRows = this.options.collection.groupHeaderRows;
            dict.groupModelsList = this.groupedModels[model.get("groupKey")];
            dict.headerRowIndices = this.headerRowIndices;
            return dict;
        },
    });

    const CaseListDetailView = CaseListView.extend({
        template: _.template($("#case-view-list-detail-template").html() || ""),
        childView: CaseViewUnclickable,
    });

    const BreadcrumbView = Marionette.View.extend({
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
            const crumbId = this.options.model.get('id');
            FormplayerFrontend.trigger("breadcrumbSelect", crumbId);
        },
        crumbKeyAction: function (e) {
            if (e.keyCode === 13) {
                this.crumbClick(e);
            }
        },
    });

    const BreadcrumbListView = Marionette.CollectionView.extend({
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

    const LanguageOptionView = Marionette.View.extend({
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
            const lang = e.target.id;
            $.publish('formplayer.change_lang', lang);
        },
    });

    const printBehavior = Marionette.Behavior.extend({
        ui: {
            selectPrint: ".print-button",
        },
        events: {
            "keydown @ui.selectPrint": "printKeyAction",
            "click @ui.selectPrint": "print",
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

    const MenuDropdownView = Marionette.CollectionView.extend({
        template: _.template($("#menu-dropdown-template").html() || ""),
        childView: LanguageOptionView,
        childViewContainer: 'ul',
        ui: {
            dropdownMenu: "#menu-dropdown",
        },
        behaviors: {
            print: printBehavior,
        },
        childViewOptions: function () {
            return {
                languageOptionsEnabled: Boolean(this.options.collection),
            };
        },
        templateContext: function () {
            const languageOptionsEnabled = Boolean(this.options.collection);
            return {
                languageOptionsEnabled: languageOptionsEnabled,
            };
        },
        events: {
            "keydown": "expandDropdown",
        },
        expandDropdown: function (e) {
            if (e.keyCode === 13 || e.keyCode === 32) {
                e.preventDefault();
                $(this.ui.dropdownMenu).toggleClass("open");
            }
        },
    });

    const DetailView = Marionette.View.extend({
        tagName: "tr",
        className: "",
        template: _.template($("#detail-view-item-template").html() || ""),
        templateContext: function () {
            const appId = formplayerUtils.currentUrlToObject().appId;
            return {
                resolveUri: function (uri) {
                    return FormplayerFrontend.getChannel().request('resourceMap', uri, appId);
                },
            };
        },
    });

    const DetailListView = Marionette.CollectionView.extend({
        tagName: "table",
        className: "table module-table module-table-case-detail",
        template: _.template($("#detail-view-list-template").html() || ""),
        childView: DetailView,
    });

    const DetailTabView = Marionette.View.extend({
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

    const DetailTabListView = Marionette.CollectionView.extend({
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

    const CaseDetailFooterView = Marionette.View.extend({
        tagName: "div",
        className: "",
        events: {
            "click #select-case": "selectCase",
        },
        getTemplate: function () {
            let id = "#module-case-detail";
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
        MenuDropdownView: function (options) {
            return new MenuDropdownView(options);
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
        CaseTileGroupedListView: function (options) {
            return new CaseTileGroupedListView(options);
        },
        DetailListView: function (options) {
            return new DetailListView(options);
        },
        DetailTabListView: function (options) {
            return new DetailTabListView(options);
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
