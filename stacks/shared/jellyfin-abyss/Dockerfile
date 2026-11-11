ARG JELLYFIN_BASE_IMAGE=jellyfin/jellyfin:latest
FROM ${JELLYFIN_BASE_IMAGE}

COPY assets/abyss.css assets/spotlight.html assets/spotlight.css assets/spotlight-loader.js /jellyfin/jellyfin-web/ui/
COPY assets/LICENSE /usr/share/doc/abyss-jellyfin/LICENSE

RUN test -f /jellyfin/jellyfin-web/index.html \
    && sed -i 's|</body>|<script src="ui/spotlight-loader.js" data-abyss-spotlight></script></body>|' /jellyfin/jellyfin-web/index.html \
    && grep -q data-abyss-spotlight /jellyfin/jellyfin-web/index.html
