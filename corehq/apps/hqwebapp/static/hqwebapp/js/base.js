// This exists to provide a default entry point for hqwebapp/base, which
// will be used on all pages that don't define their own entry point,
// to provide behavior like bootstrap widget interactions.
// It's convenient to have a single module that works for both
// bootstrap 3 and bootstrap 5. Once that migration is complete,
// hqwebapp/base can be updated to use commcarehq.js as its entry point.
import "commcarehq";
