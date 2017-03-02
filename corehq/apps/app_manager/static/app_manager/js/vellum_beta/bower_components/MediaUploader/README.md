# Media Uploader component

by Biyeun Buczyk, extracted from CommCare HQ.

YUI files built with http://yuilibrary.com/yui/configurator/

See Vellum and CommCare HQ for usage examples.

## Guess at original build procedure

NOTE: tried this procedure with YUI 3.17.2, both with and without the "loader"
rollup. The result was broken so either there is a regression beteen 3.16.0 and
3.17.2 or this procedure is incomplete.

Go to http://yuilibrary.com/yui/configurator/

Options:

    File Type: Raw
    Combine Files: Yes

Selected Modules (this is a guess):

    node-core
    uploader

Getting the files:

- Copy the Output Console into yui-config.html
- Use download the JS files (URLs abbreviated for readability)

    curl "http://yui.yahooapis.com/combo?.../yui-base/yui-base.js&..." > yui-base.js
    curl "http://yui.yahooapis.com/combo?.../uploader/uploader.js" > yui-uploader.js

## Components added later to fix Firefox blocked content errors

Procedure: load Vellum in Chrome and watch the network pane (with caching
disabled) in developer tools for requests to yui.yahooapis.com. Then download
the content into local files:

    curl "http://yui.yahooapis.com/combo?3.16.0/widget-base/assets/skins/sam/widget-base.css&3.16.0/cssbutton/cssbutton-min.css" > yui-combo.css
    curl http://yui.yahooapis.com/3.16.0/build/loader/loader.js > yui-loader.js

NOTE while the CSS is probably necessary, the loader should not be.
TODO figure out why the loader is being requested and make it not happen.
