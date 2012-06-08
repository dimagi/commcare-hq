FormDesigner 2.0
================

Installation/Usage
------------------
Using/Testing the FormDesigner is easy.  Clone the repo and serve it through a webserver.  Point your browser to index.html, or test.html (for Unit Tests), and you're off to the races.

The super easy way
~~~~~~~~~~~~~~~~~~
1. Clone the repo
2. Initialize submodule (http://github.com/dimagi/js-xpath.git):
        $ git submodule init
3. Update submodule:
        $ git submodule update
2. Download Mongoose: http://code.google.com/p/mongoose/
3. Place the mongoose exe file in the root of the repo and execute
4. Open browser and go to http://localhost:8080 (for tests go to http://localhost:8080/test.html)

That's it!

Usage as a Jquery-UI like plugin
--------------------------------
1. Clone the repo
2. Place all the subfolders in the same folder as the html file you're planning to run the plugin from.
e.g. if you host your webserver at c:\www with your index.html being at c:\www\index.html place the contents of the repo in that www folder.

Example Usage (assumes you already have jquery set up for the page):
    $(document).ready(function () {
           formdesigner.launch({
            rootElement: "#formdesigner",
            staticPrefix: "",
            langs: ""
        });
       });

formdesigner.launch causes the formdesigner to initialize itself fully in the element specified by rootElement.

Form Options:
 *  rootElement: "jQuery selector to FD Container",
 *  staticPrefix : "url prefix for static resources like css and pngs",
 *  saveUrl : "URL that the FD should post saved forms to",
 *  [form] : "string of the xml form that you wish to load"
 *  [formName] : "Default Form Name"
 *  iconUrl: URL pointing to jquery-ui icons.png

See index.html in this repo for a working example.

IMPORTANT!!: in css/jquery.fancybox-1.3.4.css change line 39 to the URL that points to fancybox.png



Contact: adewinter [at] dimagi dot C O M
