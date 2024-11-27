import {
  type RouteConfig,
  layout,
  index,
  route,
} from "@remix-run/route-config";

export default [
  layout("routes/_oh/route.tsx", [
    index("routes/_oh._index/route.tsx"),
    route("app", "routes/_oh.app/route.tsx", [
      index("routes/_oh.app._index/route.tsx"),
      route("browser", "routes/_oh.app.browser.tsx"),
      route("jupyter", "routes/_oh.app.jupyter.tsx"),
    ]),
  ]),

  route("oauth", "routes/oauth.github.callback.tsx"),
] satisfies RouteConfig;
