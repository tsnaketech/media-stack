# Services partagés

[English](README.md) | **Français**

Cette stack contient **Jellyfin**, **Seerr**, **Profilarr** avec son parser et
**Bazarr**. Prowlarr et FlareSolverr sont dans [indexer](../indexer/README.fr.md) ;
qBittorrent, SABnzbd, qui et JOAL sont dans [download](../download/README.fr.md).

## Configuration et démarrage

Les réglages sont regroupés dans `.env.example`. Conserver le `.env` privé
existant ; protéger les secrets avec `chmod 600 shared/.env`. Chaque service
conserve ses données dans `shared/data/<service>`.

Depuis la racine `stacks` :

```sh
./scripts/stacks.sh up
# Or operate on the shared services once media-shared exists:
python3 scripts/stack-compose.py shared config --quiet
python3 scripts/stack-compose.py shared up -d
python3 scripts/stack-compose.py shared ps
python3 scripts/stack-compose.py shared logs --since=5m --tail=60
```

Le réseau externe `media-shared` relie les stacks. Le réseau privé
`profilarr-internal` relie Profilarr à son parser sans publication de celui-ci.
Le script `scripts/vpn-up.sh` prépare le réseau externe avant le démarrage global.

## Guides et automatisation

- [Jellyfin](docs/jellyfin.md) : bibliothèques et lecture des médias, port `8096`.
- [Seerr](docs/seerr.md) : demandes et connexion Jellyfin/Radarr/Sonarr, port `5055`.
- [Profilarr](docs/profilarr.md) : profils et formats Radarr/Sonarr, port `6868`.
- [Bazarr](docs/bazarr.md) : sous-titres et connexions Radarr/Sonarr, port `6767`.
- [Connect arr vers Jellyfin](docs/arr-connect.md) : mise à jour des bibliothèques.

Les scripts correspondants sont dans `../scripts` et utilisent les variables
`JELLYFIN_*`, `SEERR_*`, `PROFILARR_*` et `BAZARR_*` transmises par le Compose.
Jellyfin monte les bibliothèques en lecture seule. Bazarr écrit dans les bibliothèques pour les sous-titres.

Ne pas publier `.env`, bases, journaux et données dans Git. Les URL contenant
l’adresse réelle de l’hôte sont regroupées dans `/opt/media-stack/README.local.md`.
