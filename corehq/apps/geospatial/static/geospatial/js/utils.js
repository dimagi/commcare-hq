
hqDefine('geospatial/js/utils', [
    'mapbox-gl',
    'underscore',
], function (
    mapboxgl,
    _,
) {

    const DEFAULT_MARKER_OPACITY = 1.0;
    const MAX_URL_LENGTH = 4500;

    var getRandomRGBColor = function () { // TODO: Ensure generated colors looks different!
        var r = Math.floor(Math.random() * 256); // Random value between 0 and 255 for red
        var g = Math.floor(Math.random() * 256); // Random value between 0 and 255 for green
        var b = Math.floor(Math.random() * 256); // Random value between 0 and 255 for blue

        return `rgba(${r},${g},${b},${DEFAULT_MARKER_OPACITY})`;
    };

    var uuidv4 = function () {
        // https://stackoverflow.com/questions/105034/how-do-i-create-a-guid-uuid/2117523#2117523
        return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
            (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16),
        );
    };

    var getTodayDate = function () {
        const todayDate = new Date();
        return todayDate.toLocaleDateString();
    };

    var createMapPopup = function (coordinates, popupDiv, openEventFunc, closeEventFunc) {
        popupDiv.setAttribute("data-bind", "template: 'select-case'");
        const popup = new mapboxgl.Popup({ offset: 25, anchor: "bottom" })
            .setLngLat(coordinates)
            .setDOMContent(popupDiv);
        if (openEventFunc) {
            popup.on('open', openEventFunc);
        }
        if (closeEventFunc) {
            popup.on('close', closeEventFunc);
        }
        return popup;
    };

    var setQueryParam = function (paramName, paramVal) {
        const url = new URL(window.location.href);
        url.searchParams.set(paramName, paramVal);
        return updateUrl(url);
    };

    var clearQueryParam = function (paramName) {
        const url = new URL(window.location.href);
        url.searchParams.delete(paramName);
        return updateUrl(url);
    };

    var fetchQueryParam = function (paramName) {
        const url = new URL(window.location.href);
        return url.searchParams.get(paramName);
    };

    function updateUrl(url) {
        if (url.href.length > MAX_URL_LENGTH) {
            return false;
        }
        window.history.replaceState({ path: url.href }, '', url.href);
        return true;
    }

    function downloadCsv(items, headers, cols, fileName) {
        let csvStr = "";
        csvStr = (headers).join(',');
        csvStr += '\n';

        _.forEach(items, function (itemToExport) {
            let dataToExport = [];
            for (const col of cols) {
                dataToExport.push(itemToExport[col]);
            }
            csvStr += dataToExport.join(',');
            csvStr += '\n';
        });

        // Download CSV file
        const hiddenElement = document.createElement('a');
        hiddenElement.href = 'data:text/csv;charset=utf-8,' + encodeURI(csvStr);
        hiddenElement.target = '_blank';
        hiddenElement.download = `${fileName} (${getTodayDate()}).csv`;
        hiddenElement.click();
        hiddenElement.remove();
    }

    return {
        getRandomRGBColor: getRandomRGBColor,
        uuidv4: uuidv4,
        getTodayDate: getTodayDate,
        createMapPopup: createMapPopup,
        setQueryParam: setQueryParam,
        clearQueryParam: clearQueryParam,
        fetchQueryParam: fetchQueryParam,
        downloadCsv: downloadCsv,
    };
});
