# Services média

[English](README.md) | **Français**

Stacks Docker Compose pour les services de recherche, de téléchargement et de
lecture d'un homelab. Chaque domaine possède sa stack, ses exemples de réglages
et ses données locales. Ce répertoire appartient au dépôt dont la racine est
`/opt/media-stack` ; les médias et téléchargements sont des volumes externes configurables.

## Organisation

```text
.
├── vpn/              # Gluetun pour qBittorrent, MeTube et JDownloader
├── indexer/          # Prowlarr et FlareSolverr
├── download/         # qBittorrent, SABnzbd, qui, JOAL, MeTube et JDownloader
├── shared/           # Jellyfin, Seerr, Profilarr et Bazarr
├── music/            # Lidarr et Navidrome
├── movie/            # Radarr
├── tv/               # Sonarr
├── audiobook/        # Audiobookshelf
├── book/             # Calibre-Web et Shelfmark Lite
├── scripts/          # Gestion des stacks, tests HTTP et hook d'authentification
└── docs/             # Installation, droits, authentification, préparation GitHub
```

Les workflows CI se trouvent dans `.github/workflows/` à la racine du dépôt.

Dans chaque stack, `docker-compose.yml` et `.env.example` sont versionnables.
Le fichier `.env` et le dossier `data/` restent locaux et sont exclus de Git.
La [stack VPN](vpn/README.fr.md) est requise pour qBittorrent et incluse par défaut.
Utiliser `./scripts/stacks.sh up` : le VPN doit être sain avant qBittorrent.
Arcane et Traefik sont des stacks externes optionnelles ; ils ne sont pas requis
pour utiliser les interfaces directement par leurs ports.

## Installation dans un nouvel environnement

Le [guide d’initialisation sans data](docs/initialization.md) rassemble les
prérequis, montages, secrets, comptes externes et étapes manuelles.

```sh
python3 scripts/initialize.py prepare
# Fill VPN settings and verify storage paths in the generated .env files.
python3 scripts/initialize.py check
python3 scripts/initialize.py up
```

L’initialisation ne remplace pas les données ou comptes existants. Son test
isolé démarre avec des données neuves et des ports distincts :

```sh
python3 scripts/test-initialization.py
sudo python3 scripts/test-initialization.py --docker --pull
```

Les limites du test (VPN réel, fournisseurs et assistants manuels) sont explicitées
dans le guide ; les étapes échouées sont signalées sans masquer les autres erreurs.

## Démarrage

Prérequis : Docker Engine, Docker Compose **2.30+**, Bash ; Python 3 pour les tests
HTTP et la configuration automatique des applications ; jq est également nécessaire.
Exécuter depuis `/opt/media-stack/stacks` :

```sh
# Conserver les fichiers .env existants.
for stack in vpn indexer download shared music movie tv audiobook book; do
  test -f "$stack/.env" || cp "$stack/.env.example" "$stack/.env"
  chmod 600 "$stack/.env"
done
./scripts/stacks.sh validate
```

Renseigner d’abord la clé WireGuard dans `vpn/.env` et préparer TUN selon le
[guide VPN](vpn/README.fr.md). Le script VPN utilise le fichier privé
`download/.qbittorrent-credentials.json` ; voir le [guide des clients](docs/download-clients.md).

Adapter ensuite les chemins et UID/GID dans les `.env` :

| Variable | Usage |
|---|---|
| `DNS_PRIMARY`, `DNS_SECONDARY` | DNS des conteneurs, par défaut `1.1.1.1` et `1.0.0.1` |
| `PUID`, `PGID` | Utilisateur des applications, par défaut `1000:1000` |
| `SHARED_DOWNLOADS_DIR` | Même dossier hôte pour toutes les stacks concernées |
| `LIBRARY_DIR` | Bibliothèque de la stack, par exemple `/media/tv` |
| `MUSIC_DIR` | Bibliothèque musicale hôte pour Lidarr et Navidrome |
| `ARR_IMPORT_EXTRA_FILES`, `ARR_EXTRA_FILE_EXTENSIONS` | Activation et extensions des fichiers supplémentaires à importer |
| `ARR_ROOT_FOLDER` | Racine média dans le conteneur, enregistrée automatiquement dans l’application arr |
| `NAVIDROME_ROOT_FOLDER`, `CALIBRE_ROOT_FOLDER`, `AUDIOBOOKSHELF_ROOT_FOLDER`, `SHELFMARK_ROOT_FOLDER` | Racines conteneur des autres outils ; voir le guide des médias |
| `ARR_AUTH_METHOD`, `ARR_AUTH_REQUIRED` | Méthode et obligation de connexion des applications arr |
| `ARR_ALLOWED_HOSTS` | Noms HTTP autorisés, séparés par des points-virgules |
| `ARR_TRUSTED_PROXIES` | Relais de confiance pour les adresses clientes transmises par un proxy |
| `ARR_AUTH_USERNAME`, `ARR_AUTH_PASSWORD` | Identifiants appliqués par le hook ; mot de passe vide = compte conservé |

Préparer les dossiers et leurs permissions avant le démarrage ; voir le
[guide d'installation](docs/deployment.md) et le [guide des droits](docs/permissions.md).
Sur une nouvelle installation, créer les comptes et ajouter les bibliothèques
ou fournir les identifiants arr dans les `.env`. Les sources de téléchargement
et indexeurs ne sont pas fournis automatiquement.

```sh
./scripts/stacks.sh up       # Démarre les stacks puis configure Profilarr, Jellyfin et Seerr
./scripts/stacks.sh status
./scripts/stacks.sh logs
python3 scripts/check-services.py
# Configure and test download clients after setting up qBittorrent credentials.
python3 scripts/configure-download-clients.py
```

Ports Web par défaut : Prowlarr `9696`, qBittorrent `8080`, SABnzbd `8085`, MeTube `8081`, [JDownloader](download/docs/jdownloader.md) `5800`, Lidarr `8686`,
Navidrome `4533`, Radarr `7878`, Sonarr `8989`,
Audiobookshelf `13378`, Calibre-Web `8083`, Shelfmark `8084`, Seerr `5055`, Profilarr `6868`, Jellyfin `8096`, Bazarr `6767`, qui `7476` et JOAL `8088` (chemin d’interface dans le `.env`).

## Infrastructure optionnelle

Traefik, Arcane, Dozzle et Homepage résident à la racine du dépôt,
un niveau au-dessus de `stacks/`.
Pour les inclure explicitement :

```sh
./scripts/stacks.sh status --with-infra
./scripts/stacks.sh validate --with-vpn
# INFRA_ROOT contains traefik/, arcane/, dozzle/ and homepage/.
INFRA_ROOT=/opt/media-stack ./scripts/stacks.sh validate --with-infra
python3 scripts/check-services.py --with-infra --proxy-domain arr.local
```

Sans `--proxy-domain`, les tests HTTP ne nécessitent pas de reverse proxy.
`--host` permet de tester une autre adresse. Les routes Traefik et le DNS local
se gèrent dans l'infrastructure externe.

## Documentation et contributions


- [Installation et exploitation de l'hôte actuel](docs/deployment.md)
- [Profils et formats avec Profilarr](shared/docs/profilarr.md)
- [Portail Seerr](shared/docs/seerr.md)
- [Serveur média Jellyfin](shared/docs/jellyfin.md)
- [Proxy FlareSolverr](indexer/docs/flaresolverr.md)
- [Interface qui](download/docs/qui.md)
- [Service JOAL](download/docs/joal.md)
- [Sous-titres Bazarr](shared/docs/bazarr.md)
- [Passage de TUN au LXC Proxmox](docs/proxmox-tun.md)
- [Clients qBittorrent et catégories](docs/download-clients.md)
- [Import des fichiers supplémentaires](docs/media-management.md)
- [Racines média et volumes dans les .env](docs/media-roots.md)
- [Permissions Proxmox / LXC / Docker](docs/permissions.md)
- [Authentification et identifiants dans les .env](docs/authentication.md)
- [Préparation et publication GitHub](docs/github.md)
- [Contribuer](../CONTRIBUTING.md)

Les bases, médias, mots de passe, clés API et configurations générées ne font
pas partie du dépôt. Les sauvegardes des données locales restent nécessaires.


Le [client Usenet SABnzbd](download/sabnzbd.md) est disponible dans `download`.
Renseigner un fournisseur et un indexeur NZB avant de l’utiliser.

Les [applications Prowlarr](indexer/prowlarr-apps.md) sont configurées par
`python3 scripts/configure-prowlarr-apps.py`, avec `fullSync` par défaut et
variables `PROWLARR_APPS_*` / `PROWLARR_APP_<APP>_*` dans `indexer/.env`.

Les téléchargements utilisent le montage Proxmox `/downloads`. Voir le
[guide du stockage des téléchargements](docs/downloads-storage.md) pour les
ACL, la migration et les contrôles avant démarrage.

[MeTube](download/docs/metube.md) fournit une interface yt-dlp dans la stack
`download`, avec les vidéos dans `METUBE_VIDEO_DIR` (`/downloads/youtube/videos` par défaut),
et l’audio et les fichiers temporaires sous `SHARED_DOWNLOADS_DIR/youtube`.
