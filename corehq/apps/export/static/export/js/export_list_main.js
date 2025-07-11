import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import noopMetrics from "analytix/js/noopMetrics";
import utils from "hqwebapp/js/bootstrap5/main";
import createModels from "export/js/create_export";
import listModels from "export/js/export_list";
import "hqwebapp/js/select_2_ajax_widget";  // for case owner & user filters in DashboardFeedFilterForm

$(function () {
    var $createExport = $("#create-export"),
        isOData = initialPageData.get('is_odata', true);

    if ($createExport.length) {
        $createExport.koApplyBindings(createModels.createExportModel({
            model_type: initialPageData.get("model_type", true),
            drilldown_fetch_url: initialPageData.reverse('get_app_data_drilldown_values'),
            drilldown_submit_url: initialPageData.reverse('submit_app_data_drilldown_form'),
            page: {
                is_daily_saved_export: initialPageData.get('is_daily_saved_export', true),
                is_feed: initialPageData.get('is_feed', true),
                is_deid: initialPageData.get('is_deid', true),
                is_odata: isOData,
                model_type: initialPageData.get('model_type', true),
            },
        }));
        $('#createExportOptionsModal').on('show.bs.modal', function () {
            noopMetrics.track.event("Clicked New Export");

            if (isOData) {
                noopMetrics.track.event("[BI Integration] Clicked + Add Odata Feed button");
            }

            const exportAction = getExportAction();
            const metricsMessage = `${exportAction} Export - Clicked Add Export Button`;
            noopMetrics.track.event(metricsMessage, {
                domain: initialPageData.get('domain'),
            });
        });
    }

    if (isOData) {
        noopMetrics.track.event("[BI Integration] Visited feature page");
        noopMetrics.track.outboundLink(
            '#js-odata-track-learn-more',
            "[BI Integration] Clicked Learn More-Wiki",
        );
        noopMetrics.track.outboundLink(
            '#js-odata-track-learn-more-preview',
            "[BI Integration] Clicked Learn More-Feature Preview",
        );
    }

    var modelType = initialPageData.get("model_type");
    $("#export-list").koApplyBindings(listModels.exportListModel({
        modelType: modelType,
        isDeid: initialPageData.get('is_deid'),
        isDailySavedExport: initialPageData.get('is_daily_saved_export', true),
        isFeed: initialPageData.get('is_feed', true),
        isOData: isOData,
        headers: {
            my_export_type: initialPageData.get('my_export_type'),
            shared_export_type: initialPageData.get('shared_export_type'),
            export_type_caps_plural: initialPageData.get('export_type_caps_plural'),
        },
        urls: {
            commitFilters: initialPageData.reverse("commit_filters"),
            getExportsPage: initialPageData.reverse("get_exports_page"),
            poll: initialPageData.reverse("get_saved_export_progress"),
            toggleEnabled: initialPageData.reverse("toggle_saved_export_enabled"),
            update: initialPageData.reverse("update_emailed_export_data"),
        },
        exportOwnershipEnabled: initialPageData.get("export_ownership_enabled"),
    }));

    if (modelType === 'form') {
        noopMetrics.track.event('Visited Export Forms Page');
    } else if (modelType === 'case') {
        noopMetrics.track.event('Visited Export Cases Page');
    }

    // Analytics: Send noopMetrics event when user closes alert bubble
    $('#alert-export-deep-links').on('click', function () {
        noopMetrics.track.event("Dismissed alert bubble - Deep links in exports");
    });
});

function getExportAction() {
    const modelType = initialPageData.get('model_type', true);
    if (modelType) {
        return utils.capitalize(modelType);
    }

    const isDailySavedExport = initialPageData.get('is_daily_saved_export', true);
    const isExcelExport = initialPageData.get('is_feed', true);
    const isOData = initialPageData.get('is_odata', true);

    if (isDailySavedExport) {
        // NOTE: Currently, excel exports are considered daily exports,
        // but if this was not intentional, this code should be separated
        return (isExcelExport ? 'Excel Dashboard' : 'Daily Saved');
    } else if (isOData) {
        return 'PowerBI';
    }
}
