import "commcarehq";
import $ from "jquery";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";

var self = {};

self.requestViz = function () {
    self.initViz('asdf');
    // $.ajax({
    //     method: 'post',
    //     url: initialPageData.reverse('get_tableau_server_ticket'),
    //     data: {
    //         viz_id: initialPageData.get("viz_id"),
    //     },
    //     dataType: 'json',
    //     success: function (data) {
    //         $('#loadingDiv').addClass("hide");
    //         if (data.success) {
    //             self.initViz(data.ticket);
    //         } else {
    //             $('#errorMessage').removeClass("hide");
    //             document.getElementById('errorMessage').innerHTML = '<b>' + data.message + '</b>';
    //         }
    //     },
    //     error: function () {
    //         $('#loadingDiv').addClass("hide");
    //         var requestErrorMessage = gettext("An error occured with the tableau server request, please ensure " +
    //             "the server configuration is correct and try again.");
    //         $('#errorMessage').removeClass("hide");
    //         document.getElementById("errorMessage").innerHTML = requestErrorMessage;
    //     },
    // });
};

self.initViz = function (ticket) {
    var containerDiv = document.getElementById("vizContainer");

    // Watch for iframe creation and add sandbox attribute before it loads
    // var observer = new MutationObserver(function (mutations) {
    //     mutations.forEach(function (mutation) {
    //         mutation.addedNodes.forEach(function (node) {
    //             if (node.tagName === 'IFRAME') {
    //                 // Set sandbox before browser loads iframe content
    //                 node.remove();
    //                 node.setAttribute('sandbox', 'allow-scripts');
    //                 containerDiv.appendChild(node);
    //                 // node.addAttribute('sandbox');
    //                 console.log('Sandbox attribute set on iframe:', node.getAttribute('sandbox'));
    //                 observer.disconnect();
    //             }
    //         });
    //     });
    // });

    // Start watching the container for new child elements
    // observer.observe(containerDiv, { childList: true, subtree: true });

    // TEST CODE: Simple iframe for testing sandbox behavior
    var iframe = document.createElement('iframe');
    iframe.srcdoc = `<script>
      console.log('script ran');
      alert('alert ran');
      window.top.location = 'https://example.com';
    </script>

    <form action='https://example.com' method='POST'>
      <button type='submit'>Submit form</button>
    </form>

    <a href='https://example.com' target='_top'>Navigate top</a>
  `;
    // iframe.sandbox = 'allow-scripts';
    iframe.style.width = '100%';
    iframe.style.height = '600px';
    containerDiv.appendChild(iframe);

    /* ORIGINAL TABLEAU CODE - commented out for testing
    var url = _.template("https://<%- validate_hostname %>/<% if (is_server) { %>trusted/<%- ticket %>/<% } %><%- view_url %>")({
        validate_hostname: initialPageData.get("validate_hostname"),
        is_server: initialPageData.get("server_type") === "server",
        ticket: ticket,
        view_url: initialPageData.get("view_url"),
    });

    $.getScript("https://" + initialPageData.get("validate_hostname") + "/javascripts/api/tableau-2.5.0.min.js", function () {
        new window.tableau.Viz(containerDiv, url, {
            hideTabs: true,
        });
    });
    */

    iframe = $(containerDiv).find('iframe')[0];  // Get DOM element, not jQuery object
    iframe.remove();
    iframe.setAttribute('sandbox', 'allow-scripts allow-top-navigation');
    containerDiv.appendChild(iframe);
};

$(document).ready(function () {
    self.requestViz();
});
