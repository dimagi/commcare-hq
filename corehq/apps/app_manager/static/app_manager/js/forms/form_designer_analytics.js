import google from "analytix/js/google";
import kissmetrics from "analytix/js/kissmetrix";

function workflow(message) {
    kissmetrics.track.event(message);
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
