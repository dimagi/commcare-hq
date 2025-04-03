import "commcarehq";
import 'hqwebapp/js/htmx_base';
import Alpine from 'alpinejs';
import 'reports/js/bootstrap5/base';
import $ from 'jquery';
import { RadialGauge } from 'canvas-gauges';
import initialPageData from "hqwebapp/js/initial_page_data";
import { Map, MapItem } from "geospatial/js/bootstrap5/models";
// import 'userreports/js/bootstrap5/base';  // Errors with `TypeError: dataTablesConfig.HQReportDataTables is not a function`
import dataTablesConfig from 'reports/js/bootstrap5/datatables_config';
import filtersMain from 'reports/js/filters/bootstrap5/main';
import chartsMain from 'reports/js/charts/main';
import html2pdf from "html2pdf.js";

Alpine.store('deleteWidgetModel', {
    id: null,
    type: null,
    title: null,
    swapTargetSelector: null,  // element css selector that should be removed post deletion
    setData(id, type, title) {
        this.id = id;
        this.type = type;
        this.title = title;
        this.swapTargetSelector = `[data-htmx-swap-target=${type}-${id}]`;
    },
    resetData() {
        this.widgetId = null;
        this.widgetType = null;
        this.title = null;
        this.swapTargetSelector = null;
    },
});

Alpine.start();

let mobileWorkerWidgetsInitialized = false;

const widgetModalSelector = '#widget-modal';
const modalTitleSelector = '.modal-title';
const addWidgetText = gettext('Add Widget');
const editWidgetText = gettext('Edit Widget');
let $modalTitleElement = null;

$(function () {
    // Only init widgets on "cases" tab since this is the default tab
    const widgetConfigs = initialPageData.get('map_report_widgets');
    for (const widgetConfig of widgetConfigs.cases) {
        if (widgetConfig.widget_type === 'DashboardMap') {
            const mapWidget = new MapWidget(widgetConfig);
            mapWidget.initializeMap();
        } else if (widgetConfig.widget_type === 'DashboardReport') {
            const reportWidget = new ReportWidget(widgetConfig);
            reportWidget.init();
        }
    }

    const gaugeWidgetConfigs = initialPageData.get('gauge_widgets');
    for (const gaugeWidgetConfig of gaugeWidgetConfigs.cases) {
        if (gaugeWidgetConfig.value) {
            new RadialGauge({
                renderTo: `gauge-widget-${ gaugeWidgetConfig.id }`,
                value: gaugeWidgetConfig.value,
                maxValue: gaugeWidgetConfig.max_value,
                majorTicks: gaugeWidgetConfig.major_ticks,
                valueDec: 0
            }).draw();
        }
    }

    $('a[data-bs-toggle="tab"]').on('shown.bs.tab', tabSwitch);
    $('#print-to-pdf').on('click', printActiveTabToPdf);

    $modalTitleElement = $(widgetModalSelector).find(modalTitleSelector);
    $(widgetModalSelector).on('hidden.bs.modal', onHideWidgetModal);
    $(widgetModalSelector).on('show.bs.modal', onShowWidgetModal);
    $(widgetModalSelector).on('htmx:beforeSwap', htmxBeforeSwapWidgetForm);

    $('#delete-widget-confirmation-modal').on('htmx:afterRequest', afterDeleteWidgetRequest);
});

function tabSwitch(e) {
    const tabContentId = $(e.target).attr('href');

    // Only load mobile worker widgets when tab is clicked to prevent weird map sizing behaviour
    if (!mobileWorkerWidgetsInitialized && tabContentId === '#mobile-workers-tab-content') {
        mobileWorkerWidgetsInitialized = true;
        const widgetConfigs = initialPageData.get('map_report_widgets');
        for (const widgetConfig of widgetConfigs.mobile_workers) {
            if (widgetConfig.widget_type === 'DashboardMap') {
                const mapWidget = new MapWidget(widgetConfig);
                mapWidget.initializeMap();
            } else if (widgetConfig.widget_type === 'DashboardReport') {
                const reportWidget = new ReportWidget(widgetConfig);
                reportWidget.init();
            }
        }

        const gaugeWidgetConfigs = initialPageData.get('gauge_widgets');
        for (const gaugeWidgetConfig of gaugeWidgetConfigs.mobile_workers) {
            new RadialGauge({
                renderTo: `gauge-widget-${ gaugeWidgetConfig.id }`,
                value: gaugeWidgetConfig.value,
                maxValue: gaugeWidgetConfig.max_value,
                majorTicks: gaugeWidgetConfig.major_ticks,
                valueDec: 0
            }).draw();
        }
    }
}

function printActiveTabToPdf() {
    const activeTabId = $('.nav-tabs .nav-link.active').attr('href');
    const elementToPrint = document.querySelector(activeTabId);
    const pdfExportErrorElement =  document.querySelector('#pdf-export-error');

    pdfExportErrorElement.classList.add('d-none');

    // Hide the map controls as they're not needed in the PDF
    const mapControlElements = elementToPrint.querySelectorAll('.mapboxgl-control-container');
    mapControlElements.forEach((element) => {
        element.style.visibility = 'hidden';
    });

    const dateString = new Date().toISOString().split('T')[0];
    const opt = {
        margin: [10, 10, 10, 10],
        filename: `campaign-dashboard-${dateString}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: {
            scale: 2,
            logging: false,
            letterRendering: true,
        },
        jsPDF: {
            unit: 'mm',
            format: 'a4',
            orientation: 'portrait',
        },
    };

    html2pdf().from(elementToPrint).set(opt).save().catch(() => {
        pdfExportErrorElement.classList.remove('d-none');
    }).finally(() => {
        mapControlElements.forEach((element) => {
            element.style.visibility = 'visible';
        });
    });
}

var MapWidget = function (mapWidgetConfig) {
    let self = this;
    self.id = mapWidgetConfig.id;
    self.caseType = mapWidgetConfig.case_type;
    self.gpsPropName = mapWidgetConfig.geo_case_property;
    self.title = mapWidgetConfig.title;

    self.mapInstance;

    self.initializeMap = function () {
        const containerName = `map-container-${self.id}`;
        self.mapInstance = new Map(false, false);
        self.mapInstance.initMap(containerName, null, true);

        const $filterForm = $(`#map-widget-filters-${self.id}`).find('form');
        $filterForm.on('submit', function (e) {
            e.preventDefault();
            const formDataString = $filterForm.serialize();
            fetchMapData(formDataString);
        });

        fetchMapData();
    };

    function fetchMapData(queryStr) {
        let url = initialPageData.reverse('api_cases_with_gps');
        if (queryStr) {
            url += `?${queryStr}`;
        }
        $.ajax({
            method: 'GET',
            url: url,
            data: {
                // TODO: Add ability to paginate on UI
                page: 1,
                limit: 100,
                case_type: self.caseType,
                gps_prop_name: self.gpsPropName,
            },
            success: function (data) {
                loadCases(data.items);
            },
            error: function () {
                $(`#error-alert-${self.id}`).removeClass('d-none');
            },
        });
    }

    function loadCases(caseData) {
        self.mapInstance.removeItemTypeFromSource('case');
        self.mapInstance.caseMapItems([]);
        let features = [];
        let caseMapItems = [];
        for (const caseItem of caseData) {
            const parsedData = {
                id: caseItem.id,
                coordinates: caseItem.coordinates,
                link: caseItem.name,
                name: caseItem.name,
                itemType: 'case',
                isSelected: false,
                customData: {},
            };
            const caseMapItem = new MapItem(parsedData, self.mapInstance);
            caseMapItems.push(caseMapItem);
            features.push(caseMapItem.getGeoJson());
        }
        self.mapInstance.caseMapItems(caseMapItems);
        self.mapInstance.addDataToSource(features);
        self.mapInstance.fitMapBounds(caseMapItems);
    }
};

var ReportWidget = function (config) {
    let self = this;

    self.init = function () {

        // Copied from `userreports/js/bootstrap5/base.js`
        $(function () {
            var chartSpecs = initialPageData.get('charts');
            var updateCharts = function (data) {
                if (chartSpecs !== null && chartSpecs.length > 0) {
                    var isReportBuilderReport = initialPageData.get('created_by_builder');
                    if (data.iTotalRecords > 25 && isReportBuilderReport) {
                        $("#chart-warning").removeClass("hide");
                        charts.clear($("#chart-container"));
                    } else {
                        $("#chart-warning").addClass("hide");
                        charts.render(chartSpecs, data.aaData, $("#chart-container"));
                    }
                }
            };

            var mapSpec = initialPageData.get('map_config');
            var updateMap = function (data) {
                if (mapSpec) {
                    mapSpec.mapboxAccessToken = initialPageData.get('MAPBOX_ACCESS_TOKEN');
                    maps.render(mapSpec, data.aaData, $("#map-container"));
                }
            };

            var paginationNotice = function (data) {
                if (mapSpec) {  // Only show warning for map reports
                    if (data.aaData !== undefined && data.iTotalRecords !== undefined) {
                        if (data.aaData.length < data.iTotalRecords) {
                            $('#info-message').html(
                                gettext('Showing the current page of data. Switch pages to see more data.'),
                            );
                            $('#report-info').removeClass('hide');
                        } else {
                            $('#report-info').addClass('hide');
                        }
                    }
                }
            };

            var errorCallback = function (jqXHR, textStatus, errorThrown) {
                $('#error-message').html(errorThrown);
                $('#report-error').removeClass('hide');
            };

            var successCallback = function (data) {
                if (data.error || data.error_message) {
                    const message = data.error || data.error_message;
                    $('#error-message').html(message);
                    $('#report-error').removeClass('hide');
                } else {
                    $('#report-error').addClass('hide');
                }
                if (data.warning) {
                    $('#warning-message').html(data.warning);
                    $('#report-warning').removeClass('hide');
                } else {
                    $('#report-warning').addClass('hide');
                }
            };

            var reportTables = dataTablesConfig.HQReportDataTables({
                dataTableElem: '#report_table_' + initialPageData.get('report_slug'),
                defaultRows: initialPageData.get('table_default_rows'),
                startAtRowNum: initialPageData.get('table_start_at_row'),
                showAllRowsOption: initialPageData.get('table_show_all_rows'),
                aaSorting: [],
                aoColumns: initialPageData.get('render_aoColumns'),
                autoWidth: initialPageData.get('header_auto_width'),
                customSort: initialPageData.get('custom_sort'),
                // HACK! Using request param "bs=5" to set Bootstrap 5
                // TODO: Create a new view in corehq/apps/campaign/views.py for dashboard reports
                ajaxSource: initialPageData.get('url') + '?bs=5',
                ajaxMethod: initialPageData.get('ajax_method'),
                ajaxParams: function () {
                    return $('#paramSelectorForm').serializeArray();
                },
                fixColumns: initialPageData.get('left_col_is_fixed'),
                fixColsNumLeft: initialPageData.get('left_col_fixed_num'),
                fixColsWidth: initialPageData.get('left_col_fixed_width'),
                successCallbacks: [successCallback, updateCharts, updateMap, paginationNotice],
                errorCallbacks: [errorCallback],
            });
            $('#paramSelectorForm').submit(function (event) {
                $('#reportHint').remove();
                $('#reportContent').removeClass('d-none');
                event.preventDefault();
                reportTables.render();
            });
            // after we've registered the event that prevents the default form submission
            // we can enable the submit button
            $("#apply-filters").prop('disabled', false);

            $(function () {
                $('.header-popover').popover({  /* todo B5: js-popover */
                    trigger: 'hover',
                    placement: 'bottom',
                    container: 'body',
                });
            });

            // filter init
            $(function () {
                filtersMain.init();
                chartsMain.init();
            });
        });

    };
};

var htmxBeforeSwapWidgetForm = function (event) {
    $('#widget-modal-spinner').addClass('d-none');

    const requestMethod = event.detail.requestConfig.verb;
    const responseStatus = event.detail.xhr.status;
    if (requestMethod === 'post' && responseStatus === 200) {
        // If form is saved successfully, show success message and reload the page
        const contentType = event.detail.xhr.getResponseHeader("Content-Type");
        if (contentType && contentType.includes('application/json')) {
            const response = JSON.parse(event.detail.xhr.response);
            if (response.success) {
                $('#widget-success-message').removeClass('d-none');
                event.detail.shouldSwap = false;
                $('#widget-form').text('');
                window.location.reload();
            }
        }
    }
};

var onHideWidgetModal = function () {
    $('#widget-modal-spinner').removeClass('d-none');
    $('#widget-form').text('');
};

var onShowWidgetModal = function (event) {
    const triggerSource = event.relatedTarget;
    if (triggerSource.id === 'edit-widget-btn') {
        $modalTitleElement.text(editWidgetText);
    } else {
        $modalTitleElement.text(addWidgetText);
    }
};

// TODO Use alert_js instead after geospatial bootstrap5 migration
var afterDeleteWidgetRequest = function (event) {
    const responseStatus = event.detail.xhr.status;
    if (responseStatus === 200) {
        $(event.currentTarget).modal('hide');
        $('#delete-widget-alert').removeClass('d-none');
        setTimeout(function () {
            $('#delete-widget-alert').addClass('d-none');
        }, 3000);
    }
};
