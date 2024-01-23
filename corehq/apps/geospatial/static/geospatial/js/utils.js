hqDefine('geospatial/js/utils', [], function () {

    const DEFAULT_MARKER_OPACITY = 1.0;

    var getRandomRGBColor = function () { // TODO: Ensure generated colors looks different!
        var r = Math.floor(Math.random() * 256); // Random value between 0 and 255 for red
        var g = Math.floor(Math.random() * 256); // Random value between 0 and 255 for green
        var b = Math.floor(Math.random() * 256); // Random value between 0 and 255 for blue

        return `rgba(${r},${g},${b},${DEFAULT_MARKER_OPACITY})`;
    };

    var uuidv4 = function () {
        // https://stackoverflow.com/questions/105034/how-do-i-create-a-guid-uuid/2117523#2117523
        return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
            (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
        );
    };

    var getTodayDate = function () {
        const todayDate = new Date();
        return todayDate.toLocaleDateString();
    };

    var createMapPopup = function (coordinates, popupDiv, openEventFunc, closeEventFunc) {
        popupDiv.setAttribute("data-bind", "template: 'select-case'");
        const popup = new mapboxgl.Popup({ offset: 25, anchor: "bottom" })  // eslint-disable-line no-undef
            .setLngLat(coordinates)
            .setDOMContent(popupDiv)
            .on('open', openEventFunc)
            .on('close', closeEventFunc);
        return popup;
    };

    return {
        getRandomRGBColor: getRandomRGBColor,
        uuidv4: uuidv4,
        getTodayDate: getTodayDate,
        createMapPopup: createMapPopup,
    };
});