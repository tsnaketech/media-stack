# Indexeurs

[English](README.md) | **Français**

Cette stack regroupe **Prowlarr** et son proxy **FlareSolverr**. Ils partagent le
réseau externe `media-shared` avec les applications arr. Les noms Docker et ports
restent `prowlarr:9696` et `flaresolverr:8191` ; l’API FlareSolverr est publiée
uniquement sur la boucle locale de l’hôte par défaut.

## Configuration et démarrage

Copier `.env.example` vers `.env` uniquement si nécessaire, puis protéger ce
fichier avec `chmod 600 indexer/.env`. Les variables `ARR_AUTH_*` et
`ARR_ALLOWED_HOSTS` concernent Prowlarr. `PROWLARR_APPS_*` et
`PROWLARR_APP_<APP>_*` pilotent l’enregistrement des applications ;
`FLARESOLVERR_*` configure le proxy et ses tags.

Depuis la racine `stacks` :

```sh
./scripts/stacks.sh up
# Or operate on this stack after creating the external media-shared network:
python3 scripts/stack-compose.py indexer config --quiet
python3 scripts/stack-compose.py indexer up -d
python3 scripts/stack-compose.py indexer ps
python3 scripts/stack-compose.py indexer logs --since=5m --tail=60
```

Après démarrage des services concernés :

```sh
python3 scripts/configure-flaresolverr.py
python3 scripts/configure-prowlarr-apps.py
```

Voir les guides [applications Prowlarr](prowlarr-apps.md) et
[FlareSolverr](docs/flaresolverr.md). La synchronisation est `fullSync` par défaut.
Les indexeurs doivent être ajoutés dans Prowlarr avec les accès appropriés.

## Données et accès

Les configurations persistent dans `indexer/data/prowlarr` et
`indexer/data/flaresolverr`. Les scripts lisent la clé Prowlarr dans son
`config.xml`. Ne pas modifier directement sa base SQLite pendant l’exécution.
Les données et le `.env` privé sont exclus de Git ; les sauvegarder séparément.
Les URL propres à l’hôte sont dans `/opt/media-stack/README.local.md`.
