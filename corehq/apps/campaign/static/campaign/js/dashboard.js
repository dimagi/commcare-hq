import "commcarehq";
import 'hqwebapp/js/htmx_base';
import Alpine from 'alpinejs';
import 'reports/js/bootstrap5/base';
import $ from 'jquery';
import { RadialGauge } from 'canvas-gauges';
import initialPageData from "hqwebapp/js/initial_page_data";
import { Map, MapItem } from "geospatial/js/bootstrap5/models";
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
        this.id = null;
        this.type = null;
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

let activeTab = 'cases';

$(function () {
    // Only init case map widgets since this is the default tab
    const widgetConfigs = initialPageData.get('map_report_widgets');
    for (const widgetConfig of widgetConfigs.cases) {
        if (widgetConfig.widget_type === 'DashboardMap') {
            const mapWidget = new MapWidget(widgetConfig);
            mapWidget.initializeMap();
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
    $(widgetModalSelector).on('htmx:configRequest', widgetHtmxConfigRequestHandler);

    $('#delete-widget-confirmation-modal').on('htmx:afterRequest', afterDeleteWidgetRequest);
});

function tabSwitch(e) {
    const tabContentId = $(e.target).attr('href');
    activeTab = getActiveTab(tabContentId);

    // Only load mobile worker map widgets when tab is clicked to prevent weird map sizing behaviour
    if (!mobileWorkerWidgetsInitialized && tabContentId === '#mobile-workers-tab-content') {
        mobileWorkerWidgetsInitialized = true;
        const widgetConfigs = initialPageData.get('map_report_widgets');
        for (const widgetConfig of widgetConfigs.mobile_workers) {
            if (widgetConfig.widget_type === 'DashboardMap') {
                const mapWidget = new MapWidget(widgetConfig);
                mapWidget.initializeMap();
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

var getActiveTab = function (tabContentId) {
    if (tabContentId === '#mobile-workers-tab-content') {
        return 'mobile_workers';
    }
    return 'cases';
};

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
            orientation: 'landscape',
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
    if ($(triggerSource).data('source') === 'add-widget-dropdown') {
        $modalTitleElement.text(addWidgetText);
    } else {
        $modalTitleElement.text(editWidgetText);
    }
};

var widgetHtmxConfigRequestHandler = function (event) {
    const requestMethod = event.detail.verb;
    if (requestMethod === 'post') {
        event.detail.parameters['dashboard_tab'] = activeTab;
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
