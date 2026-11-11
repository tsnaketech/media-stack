#!/usr/bin/env python3
"""Check media interfaces; reverse proxy and external infrastructure are optional."""
import argparse
import stack_extensions as extensions
import os
import ssl
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("HTTP_HOST", "127.0.0.1"))
    parser.add_argument("--proxy-domain", default=os.environ.get("PROXY_DOMAIN"))
    parser.add_argument("--with-infra", action="store_true", help="Also check Arcane, Traefik, Homepage and Dozzle")
    args = parser.parse_args()
    services = {
        "jdownloader": (5800, "/"),
        "lidarr": (8686, "/"), "navidrome": (4533, "/"),
        "metube": (8081, "/"), "sabnzbd": (8085, "/"), "prowlarr": (9696, "/"), "qbittorrent": (8080, "/"), "qui": (7476, "/health"),
        "bazarr": (6767, "/"), "radarr": (7878, "/"),
        "books": (8083, "/"), "audiobookshelf": (13378, "/"),
        "shelfmark": (8084, "/"), "sonarr": (8989, "/"),
        "jellyfin": (8096, "/health"), "seerr": (5055, "/"), "profilarr": (6868, "/"),
    }
    services.update(extensions.settings().get("health_checks", {}))
    if args.with_infra:
        services.update(arcane=(3552, "/"), traefik=(8888, "/dashboard/"), homepage=(3002, "/"), dozzle=(9999, "/"))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    failed = False
    for name, (port, path) in services.items():
        scheme = "https" if name == "jdownloader" else "http"
        # Only this local GUI currently uses a self-signed certificate.
        service_opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                          urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
                          if name == "jdownloader" else opener)
        targets = [("direct", f"{scheme}://{args.host}:{port}{path}", {})]
        if args.proxy_domain and name != "traefik":
            targets.append(("proxy", f"{scheme}://{args.host}/", {"Host": f"{name}.{args.proxy_domain}"}))
        for kind, url, headers in targets:
            try:
                with service_opener.open(urllib.request.Request(url, headers=headers), timeout=10) as response:
                    code = response.status
            except urllib.error.HTTPError as error:
                code = error.code
            except (OSError, urllib.error.URLError) as error:
                print(f"{name:16} {kind:6} ERROR {error}")
                failed = True
                continue
            print(f"{name:16} {kind:6} HTTP {code}")
            failed |= code not in (200, 301, 302, 303, 307, 308, 401, 403)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
