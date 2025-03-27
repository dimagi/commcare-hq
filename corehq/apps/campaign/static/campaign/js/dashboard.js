import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import 'reports/js/bootstrap5/base';
import $ from 'jquery';
import { RadialGauge } from 'canvas-gauges';
import initialPageData from "hqwebapp/js/initial_page_data";
import { Map, MapItem } from "geospatial/js/models";


let mobileWorkerWidgetsInitialized = false;

const widgetModalSelector = '#widget-modal';
const modalTitleSelector = '.modal-title';
const addWidgetText = gettext('Add Widget');
const editWidgetText = gettext('Edit Widget');
let $modalTitleElement = null;

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
        new RadialGauge({
            renderTo: `gauge-widget-${ gaugeWidgetConfig.id }`,
            value: gaugeWidgetConfig.value,
            maxValue: gaugeWidgetConfig.max_value,
            majorTicks: gaugeWidgetConfig.major_ticks,
            valueDec: 0
        }).draw();
    }
    $('a[data-bs-toggle="tab"]').on('shown.bs.tab', tabSwitch);

    $modalTitleElement = $(widgetModalSelector).find(modalTitleSelector);
    $(widgetModalSelector).on('hidden.bs.modal', onHideWidgetModal);
    $(widgetModalSelector).on('show.bs.modal', onShowWidgetModal);

    $(widgetModalSelector).on('htmx:afterSwap', htmxAfterSwapWidgetForm);
});

function tabSwitch(e) {
    const tabContentId = $(e.target).attr('href');

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

var htmxAfterSwapWidgetForm = function (event) {
    $('#widget-modal-spinner').addClass('d-none');

    const requestMethod = event.detail.requestConfig.verb;
    const responseStatus = event.detail.xhr.status;
    if (requestMethod === 'post' && responseStatus === 200) {
        setTimeout(function () {
            window.location.reload();
        }, 1000);
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
