// A bind with no matching data node — Vellum records this as a parse warning
// in form.errors on load.
const ORPHAN_BIND_XML = `<?xml version="1.0" encoding="UTF-8" ?>
<h:html xmlns:h="http://www.w3.org/1999/xhtml"
    xmlns:orx="http://openrosa.org/jr/xforms"
    xmlns="http://www.w3.org/2002/xforms"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:jr="http://openrosa.org/javarosa"
    xmlns:vellum="http://commcarehq.org/xforms/vellum">
    <h:head>
        <h:title>T</h:title>
        <model>
            <instance>
                <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
                    xmlns="http://openrosa.org/formdesigner/ABC"
                    uiVersion="1"
                    version="1"
                    name="T">
                    <text />
                </data>
            </instance>
            <bind nodeset="/data/text" type="xsd:string" />
            <bind nodeset="/data/ghost" type="xsd:string" />
            <itext>
                <translation lang="en" default="">
                    <text id="text-label">
                        <value>text</value>
                    </text>
                </translation>
            </itext>
        </model>
    </h:head>
    <h:body>
        <input ref="/data/text">
            <label ref="jr:itext('text-label')" />
        </input>
    </h:body>
</h:html>`;

export default ORPHAN_BIND_XML;
