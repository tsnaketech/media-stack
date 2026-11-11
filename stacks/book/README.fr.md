# Livres : Calibre-Web et Shelfmark Lite

[English](README.md) | **Français**

Les URL ci-dessous utilisent `IP_DU_SERVEUR`, à remplacer par l’adresse de votre hôte.

- Calibre-Web : http://IP_DU_SERVEUR:8083, bibliothèque `/books` issue de `/media/books`.
- Shelfmark Lite : http://IP_DU_SERVEUR:8084 ou http://shelfmark.arr.local après
  création d'une entrée DNS vers `IP_DU_SERVEUR`.

## Volumes de Shelfmark

| Hôte LXC | Conteneur | Rôle |
|---|---|---|
| `./data/shelfmark` | `/config` | Configuration, base et cache persistants |
| `/downloads/books/ingest` | `/books` | Destination des ebooks récupérés |
| `/downloads` | `/downloads` | Même chemin que qBittorrent pour récupérer les fichiers |

`SHARED_DOWNLOADS_DIR` permet de remplacer `/downloads` ; utiliser la même
valeur dans la stack download. Les dossiers doivent appartenir à l'UID/GID de
Shelfmark, par défaut `1000:1000`. Le moteur Docker doit pouvoir y accéder.
Shelfmark ne monte pas la bibliothèque existante `/media/books` : les fichiers
reçus restent dans un dossier de réception distinct, en attendant leur import.

## Gestion

Depuis la racine du dépôt (`/opt/media-stack/stacks` sur cet hôte) :

```sh
./scripts/vpn-up.sh
python3 scripts/stack-compose.py indexer up -d
python3 scripts/stack-compose.py book config --quiet
python3 scripts/stack-compose.py book up -d shelfmark
python3 scripts/stack-compose.py book ps
python3 scripts/stack-compose.py book logs --since=5m --tail=80 shelfmark
curl -fsS http://127.0.0.1:8084/api/health
```

Le réseau externe `media-shared` est créé par `scripts/vpn-up.sh`. Calibre-Web
conserve son réseau actuel. Le healthcheck de Shelfmark contrôle également
que son coordinateur de téléchargements fonctionne.

## Première utilisation

1. Ouvrir Shelfmark et configurer son authentification dans les paramètres.
2. Configurer les sources souhaitées. Pour Prowlarr, utiliser
   `http://prowlarr:9696` et sa clé API ; des indexeurs proposant des ebooks
   doivent être ajoutés dans Prowlarr avant de pouvoir y trouver des résultats.
3. Configurer qBittorrent avec `http://qbittorrent:8080` et ses identifiants.
   Utiliser une catégorie dédiée, par exemple `books`, avec destination
   `/downloads/books`. Ce chemin est visible à l'identique dans les deux services.
4. Choisir les formats et langues souhaités, puis les fournisseurs de métadonnées.
   Certaines sources demandent un compte ou une clé API personnelle.
5. Tester les connexions dans l'interface avant le premier téléchargement.

Lite conserve l'interface web, la recherche et les intégrations aux clients.
Il retire le navigateur interne utilisé pour certaines sources de téléchargement
direct ; un résolveur externe compatible peut être nécessaire pour ces sources.
Aucun résolveur ni aucune source n'est ajouté automatiquement.

## Import dans Calibre-Web

Shelfmark livre les fichiers mais ne gère pas la bibliothèque Calibre et ne
surveille pas les nouvelles sorties d'auteurs. Les ebooks du dossier de réception
doivent être importés dans une bibliothèque Calibre valide (ou téléversés via
Calibre-Web si cette fonction est configurée). Copier un EPUB dans `/media/books`
ne suffit pas à mettre à jour `metadata.db`. Aucune modification automatique de
la bibliothèque existante n'est configurée ici.

Documentation : [Shelfmark](https://github.com/calibrain/shelfmark),
[Compose Lite officiel](https://github.com/calibrain/shelfmark/blob/main/compose/docker-compose.lite.yml).

Les chemins racines conteneur sont configurables dans `.env` ; voir le
[guide des racines média](../docs/media-roots.md).

Les connexions qBittorrent de cet hôte sont désormais configurées ; voir le
[récapitulatif des clients et catégories](../docs/download-clients.md).
