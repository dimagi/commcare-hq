import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import 'reports/js/bootstrap5/base';
import $ from 'jquery';
import initialPageData from "hqwebapp/js/initial_page_data";
import { Map, MapItem } from "geospatial/js/models";
import { getAsyncHQReport } from 'campaign/js/standard_hq_report';

let mobileWorkerMapsInitialized = false;

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
    $('a[data-bs-toggle="tab"]').on('shown.bs.tab', tabSwitch);
});

function tabSwitch(e) {
    const tabContentId = $(e.target).attr('href');

    // Only load mobile worker map widgets when tab is clicked to prevent weird map sizing behaviour
    if (!mobileWorkerMapsInitialized && tabContentId === '#mobile-workers-tab-content') {
        mobileWorkerMapsInitialized = true;
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
    }
}

let MapWidget = function (mapWidgetConfig) {
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

let ReportWidget = function (reportWidgetConfig) {
    let self = this;
    self.id = reportWidgetConfig.id;
    self.title = reportWidgetConfig.title;
    self.reportConfigurationId = reportWidgetConfig.report_configuration_id;
    self.urlRoot = reportWidgetConfig.url_root;
    self.domain = initialPageData.get('domain');
    
    // Make sure urlRoot ends with a slash
    if (self.urlRoot && !self.urlRoot.endsWith('/')) {
        self.urlRoot += '/';
    }
    
    self.datespan = undefined;

    self.init = function () {
        const $widgetFilters = $(`#report-widget-filters-${self.id}`);
        const reportOptions = {
            "widgetFilters": $widgetFilters,
            "filterForm": $widgetFilters.find('form'),
            "reportContent": $(`#report-container-${self.id}`),
            "domain": self.domain,
            "needsFilters": true,
            "urlRoot": self.urlRoot,
            "datespan": self.datespan,
            "slug": "configurable",  // Required for async report loading
            "async": true,
            "subReportSlug": self.reportConfigurationId,  // Used as reportId in async_configurable_report.js
            "reportConfigurationId": self.reportConfigurationId,  // Used as reportId in async_configurable_report.js
            "type": "configurable",  // Required to use async_configurable_report.js
        };
        getAsyncHQReport(reportOptions);
    };
}
