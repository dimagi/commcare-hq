# Sidecar

Sidecar embeds independently developed web apps in CommCare HQ. A sidecar app is
hosted outside HQ and displayed in an iframe within a project space, where it
can call HQ's APIs as the logged-in user.

Sidecar is behind the `SIDECAR` domain toggle.

## Registering an app

Apps are registered as `SidecarApp`s in the Django admin. Each app belongs to a
project, is identified within it by a slug, and has the URL of the page to load
in the iframe. HQ shows the app on its own page in the project, linked from the
"Data" tab.

## The allowlist

Each app lists the HQ API endpoints it may call, as pairs of an HTTP method and
a path prefix relative to the project. Requests that don't match an entry are
refused. Apps can only reach HQ's APIs, never its other pages.

```json
[
  { "method": "GET", "path": "/api/case/v2/" },
  { "method": "PUT", "path": "/api/case/v2/" }
]
```

## Messaging

The app has no direct access to HQ. Instead, it sends each API request as a
message to the HQ page that contains it, using the browser's cross-window
messaging. HQ's page checks that the message came from the app's iframe and
origin, and that the request is on the allowlist. It then makes the request
itself and sends the response back to the app the same way.

A request is a message posted to `window.parent`, targeted at HQ's origin:

```js
window.parent.postMessage(
  {
    id: 1, // any value, echoed in the reply
    method: "PUT",
    path: "/api/case/v2/<case_id>/", // relative to /a/<project>
    query: {}, // optional, URL query parameters
    body: { properties: { status: "reviewed" } }, // optional, sent as JSON
  },
  "https://www.commcarehq.org",
);
```

HQ replies with a message of the form `{ id, status, body }`, where `body` is
the parsed JSON response, or `null` if there is none. The app should only accept
replies from `window.parent` with HQ's origin, and use `id` to match each reply
to its request.

```js
window.addEventListener("message", (event) => {
  if (event.source !== window.parent || event.origin !== "https://www.commcarehq.org") {
    return;
  }
  const { id, status, body } = event.data;
  console.log(`Request ${id} returned ${status}`, body);
});
```

## Auth

The app never holds a session cookie, token, or any other credential. HQ's page
makes requests with the logged-in user's session, so the user's usual
permissions apply, and an app can never do more than the user could.

Most HQ APIs normally reject session logins, to protect against cross-site
request forgery. In Sidecar projects, the APIs accept the session if the request
also carries HQ's CSRF token, which other websites cannot read. Since sidecar
requests come from HQ javascript, we do have that protection.

## Threat model

A sidecar app is third-party code. We limit its access by sandboxing the iframe,
mediating and limiting the requests it makes to HQ, and not passing credentials
to the app. Still, sidecar apps have full access to whatever APIs are granted to
them, and since they are fundamentally outside of our control, they must come
from a trustworthy source.

The sandbox lets apps download files to the user's computer, such as data
exports. A malicious app could use this to deliver harmful files while the user
is on an HQ page.
