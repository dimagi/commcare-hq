import "commcarehq";
import "hqwebapp/js/htmx_and_alpine";
import 'reports/js/bootstrap5/base';
import $ from 'jquery';
import initialPageData from "hqwebapp/js/initial_page_data";
import { Map, MapItem } from "geospatial/js/models";
import html2pdf from "html2pdf.js";


let mobileWorkerMapsInitialized = false;

$(function () {
    // Only init case map widgets since this is the default tab
    const widgetConfigs = initialPageData.get('map_report_widgets');
    for (const widgetConfig of widgetConfigs.cases) {
        if (widgetConfig.widget_type === 'DashboardMap') {
            const mapWidget = new MapWidget(widgetConfig);
            mapWidget.initializeMap();
        }
    }
    $('a[data-bs-toggle="tab"]').on('shown.bs.tab', tabSwitch);
    $('#print-to-pdf').on('click', printActiveTabToPdf);
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
            }
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