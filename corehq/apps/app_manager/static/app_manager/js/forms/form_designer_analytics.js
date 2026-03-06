/*
    This file uses AMD because it is ultimately imported by Vellum,
    which is still on AMD.
*/
import google from "analytix/js/google";
import noopMetrics from "analytix/js/noopMetrics";

function workflow(message) {
    noopMetrics.track.event(message);
}

function usage(label, group, message) {
    google.track.event(label, group, message);
}

function fbUsage(group, message) {
    usage("Form Builder", group, message);
}

export default {
    fbUsage: fbUsage,
    usage: usage,
    workflow: workflow,
};
