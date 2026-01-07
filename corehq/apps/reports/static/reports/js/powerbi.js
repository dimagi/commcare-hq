import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";

var self = {};

self.requestEmbedToken = function () {
    $.ajax({
        method: 'post',
        url: initialPageData.reverse('get_powerbi_embed_token'),
        data: {
            report_id: initialPageData.get("report_id"),
        },
        dataType: 'json',
        success: function (data) {
            $('#loadingDiv').addClass("hide");
            if (data.success) {
                self.embedReport(data.embedToken, data.embedUrl, data.reportId);
            } else {
                $('#errorMessage').removeClass("hide");
                document.getElementById('errorMessage').innerHTML = '<b>' + data.message + '</b>';
            }
        },
        error: function () {
            $('#loadingDiv').addClass("hide");
            var requestErrorMessage = gettext("An error occurred with the PowerBI embed token request. " +
                "Please ensure the configuration is correct and try again.");
            $('#errorMessage').removeClass("hide");
            document.getElementById("errorMessage").innerHTML = requestErrorMessage;
        },
    });
};

self.embedReport = function (embedToken, embedUrl, reportId) {
    // Load PowerBI JavaScript SDK from CDN, then embed the report
    $.getScript("https://cdn.jsdelivr.net/npm/powerbi-client@2.23.1/dist/powerbi.min.js", function () {
        self.initializeEmbed(embedToken, embedUrl, reportId);
    });
};

self.initializeEmbed = function (embedToken, embedUrl, reportId) {
    var containerDiv = document.getElementById("powerBIContainer");

    // Watch for iframe creation and add sandbox attribute
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.tagName === 'IFRAME') {
                    // Reset node with sandbox attrs
                    node.remove();
                    node.setAttribute('sandbox', 'allow-scripts allow-same-origin');
                    containerDiv.appendChild(node);
                    console.log('Sandbox attribute set on iframe:', node.getAttribute('sandbox'));
                    observer.disconnect();
                }
            });
        });
    });

    // Start observing the container for new iframes
    observer.observe(containerDiv, { childList: true, subtree: true });

    // PowerBI is now available on window from CDN
    var powerbi = window.powerbi;
    var models = window['powerbi-client'].models;

    // PowerBI embed configuration
    var embedConfig = {
        type: 'report',
        tokenType: models.TokenType.Embed,
        accessToken: embedToken,
        embedUrl: embedUrl,
        id: reportId,
        permissions: models.Permissions.Read,
        settings: {
            panes: {
                filters: {
                    visible: false,
                },
                pageNavigation: {
                    visible: true,
                },
            },
            background: models.BackgroundType.Transparent,
        },
    };

    // Embed the report
    var report = powerbi.embed(containerDiv, embedConfig);

    // Handle errors
    report.on('error', function (event) {
        console.error('PowerBI embed error:', event.detail);
        $('#errorMessage').removeClass("hide");
        document.getElementById('errorMessage').innerHTML =
            '<b>' + gettext("Error loading PowerBI report") + '</b>';
    });

    // Log when report is loaded
    report.on('loaded', function () {
        console.log('PowerBI report loaded successfully');
    });
};

$(document).ready(function () {
    self.requestEmbedToken();
});
