function add_report_links(slugs) {
    var url = window.location.href;
    var lastSlash = url.lastIndexOf('/');
    var previousSlash = url.lastIndexOf('/', lastSlash - 1);
    var content = '<div style="margin: 0 0 30px 120px;">';

    $('legend + div').remove();

    $.each(slugs, function() {
        content += '<a class="btn" style="margin-left: 10px" href="' +
                url.substring(0, previousSlash + 1) + this[0] + url.substring(lastSlash) +
                '">' + this[1] + '</a>';
    });

    content += '</div>';
    $('legend').after(content);
}
