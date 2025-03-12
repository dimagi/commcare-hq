import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import 'reports/js/bootstrap5/base';
import $ from 'jquery';
import initialPageData from "hqwebapp/js/initial_page_data";
import { Map } from "geospatial/js/models";


let mobileWorkerMapsInitialized = false;

$(function () {
    // Only init case map widgets since this is the default tab
    const mapWidgetConfigs = initialPageData.get('map_widgets');
    for (const mapWidgetConfig of mapWidgetConfigs.cases) {
        const mapWidget = new MapWidget(mapWidgetConfig);
        mapWidget.initializeMap();
    }
    $('a[data-bs-toggle="tab"]').on('shown.bs.tab', tabSwitch);
});

function tabSwitch(e) {
    const tabContentId = $(e.target).attr('href');

    // Only load mobile worker map widgets when tab is clicked to prevent weird map sizing behaviour
    if (!mobileWorkerMapsInitialized && tabContentId === '#mobile-workers-tab-content') {
        mobileWorkerMapsInitialized = true;
        const mapWidgetConfigs = initialPageData.get('map_widgets');
        for (const mapWidgetConfig of mapWidgetConfigs.mobile_workers) {
            const mapWidget = new MapWidget(mapWidgetConfig);
            mapWidget.initializeMap();
        }
    }
}

var MapWidget = function (mapWidgetConfig) {
    let self = this;
    self.id = mapWidgetConfig.id;
    self.caseType = mapWidgetConfig.case_type;
    self.gpsPropName = mapWidgetConfig.gps_prop_name;
    self.title = mapWidgetConfig.title;

    self.mapInstance;

    self.initializeMap = function () {
        const containerName = `map-container-${self.id}`;
        self.mapInstance = new Map(false, false);
        self.mapInstance.initMap(containerName);
    };
};