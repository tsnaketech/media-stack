# Seerr : demandes de films et séries

Seerr fournit un portail de demandes et transmet les demandes approuvées à
Radarr et Sonarr. Il ne télécharge pas les fichiers directement : les clients
qBittorrent déjà configurés dans ces deux applications assurent cette partie.

## Configuration et démarrage

Copier `shared/.env.example` vers `shared/.env` s'il n'existe pas, puis adapter les valeurs.
Les commentaires et variables suivent les conventions des autres stacks :
utilisateur, fuseau horaire, DNS, adresse d'écoute, port et niveau des journaux
(`SEERR_LOG_LEVEL`, transmis à Seerr sous le nom `LOG_LEVEL`).
L'image officielle utilise UID/GID `1000:1000` ; `PUID` et `PGID` sont ici utilisés
par la directive Compose `user`, pas transmis comme variables natives Seerr.

Depuis la racine du dépôt :

```sh
mkdir -p shared/data/seerr
# Adapter 1000:1000 aux valeurs du .env si nécessaire.
sudo chown 1000:1000 shared/data/seerr
python3 scripts/stack-compose.py shared config --quiet
python3 scripts/stack-compose.py shared up -d
python3 scripts/stack-compose.py shared ps
python3 scripts/stack-compose.py shared logs --since=5m --tail=80
```

Le service utilise le réseau `media-shared`, créé par la stack partagée. Les paramètres et la base
restent dans `shared/data/seerr`, exclus de Git et à sauvegarder. Aucun volume
contenant les films ou séries n'est nécessaire pour ce portail.

L'interface utilise le port publié `5055` par défaut. Pour les URL propres à
l'hôte actuel, consulter le README du parent `/opt`, qui n'est pas destiné à GitHub.
La route Traefik externe est `seerr.arr.local` ; le DNS des postes clients doit
faire pointer ce nom vers l'hôte de Traefik. Modifier `SEERR_PORT` impose aussi
d'adapter cette route si elle utilise le port publié.

## Premier accès

1. Pour un serveur externe sans bootstrap, ouvrir l’interface et suivre l’assistant pour connecter Jellyfin, Emby ou Plex
   et créer le compte administrateur. Utiliser l'adresse réelle du serveur média,
   accessible depuis le conteneur ; `localhost` désignerait Seerr lui-même.
2. Sélectionner et synchroniser les bibliothèques du serveur média.
3. Appliquer la configuration du `.env` avec le script ci-dessous. Radarr et
   Sonarr seront ajoutés automatiquement avec leur profil et leur racine.
4. Vérifier ces connexions dans Settings → Services.
5. Définir les permissions de demandes et d'approbation des utilisateurs.

Si les racines ont été personnalisées dans les `.env` des applications arr,
utiliser les valeurs correspondantes. Ne sélectionner le mode 4K que pour une
instance 4K distincte. Aucun média ni téléchargement de test n'est demandé
pendant l'installation de cette stack.

Seerr possède sa propre authentification liée aux comptes du portail/serveur
média ; les variables `ARR_AUTH_*` des autres stacks ne le configurent pas.
Il n'est pas ajouté à la liste des applications Prowlarr ni aux clients
qBittorrent : ces échanges sont délégués à Radarr et Sonarr.

Documentation : [installation officielle](https://docs.seerr.dev/getting-started/docker/),
[connexion aux services](https://docs.seerr.dev/using-seerr/settings/services/).

## Configuration via `shared/.env`

Les variables `TZ`, `LOG_LEVEL` et `PORT` sont natives. Les variables `SEERR_*`
ci-dessous sont propres au script hôte `scripts/configure-seerr.py` ; Compose les
transmet explicitement, sans exposer les secrets des autres services. Seerr ne
les applique pas directement. Python 3 est nécessaire sur l’hôte uniquement ; le
script utilise le Node.js déjà présent dans l’image pour tester les connexions.

Les sections du `.env.example` regroupent les réglages :

| Groupe | Variables principales |
| --- | --- |
| Application | `SEERR_SETUP_ENABLED`, `SEERR_APPLICATION_TITLE`, `SEERR_APPLICATION_URL` |
| Interface et catalogue | `SEERR_LOCALE`, `SEERR_DISCOVER_REGION`, `SEERR_STREAMING_REGION` |
| Connexion des utilisateurs | `SEERR_LOCAL_LOGIN`, `SEERR_MEDIA_SERVER_LOGIN` |
| Radarr | `SEERR_CONFIGURE_RADARR`, `SEERR_RADARR_URL`, `SEERR_RADARR_PROFILE`, `SEERR_RADARR_ROOT_FOLDER` |
| Sonarr | `SEERR_CONFIGURE_SONARR`, `SEERR_SONARR_URL`, `SEERR_SONARR_PROFILE`, `SEERR_SONARR_ROOT_FOLDER` |
| Serveur média optionnel | `SEERR_MEDIA_SERVER_TYPE`, `SEERR_MEDIA_SERVER_URL`, `SEERR_MEDIA_SERVER_API_KEY` |

Exemple :

```dotenv
SEERR_SETUP_ENABLED=true
SEERR_LOCALE=fr
SEERR_RADARR_PROFILE='1080p Français'
SEERR_RADARR_ROOT_FOLDER=/movies
SEERR_SONARR_PROFILE='1080p Français'
SEERR_SONARR_ROOT_FOLDER=/tv
```

Les noms des profils et les dossiers doivent déjà exister dans Radarr/Sonarr.
Les clés `SEERR_RADARR_API_KEY` et `SEERR_SONARR_API_KEY` vides sont détectées
localement depuis leurs volumes de configuration. Pour une URL différente de
`http://radarr:7878` ou `http://sonarr:8989`, renseigner explicitement sa clé.
Les URL doivent être accessibles depuis le conteneur Seerr. Le script résout les
identifiants des profils par leur nom, sans identifiants numériques codés en dur.

`SEERR_RADARR_DEFAULT` et `SEERR_SONARR_DEFAULT` désignent les serveurs par défaut
pour les demandes normales. Les entrées 4K existantes sont conservées. Les
options `*_SYNC_ENABLED`, `*_PREVENT_SEARCH`, `SEERR_RADARR_MINIMUM_AVAILABILITY`,
`SEERR_SONARR_SERIES_TYPE` et `SEERR_SONARR_SEASON_FOLDERS` pilotent le traitement
des futures demandes. `*_PREVENT_SEARCH=false` autorise la recherche lors d’une
demande ; la configuration elle-même ne crée aucune demande.

Depuis la racine du dépôt, après modification du `.env` :

```sh
python3 scripts/configure-seerr.py
```

Le script est aussi appelé à la fin de `scripts/stacks.sh up`, après la création
des profils français. Un `docker compose up` direct ne suffit pas à appliquer
ces variables personnalisées. `SEERR_SETUP_ENABLED=false` désactive cette étape ;
`SEERR_CONFIGURE_RADARR=false` ou `SEERR_CONFIGURE_SONARR=false` laisse la connexion
correspondante hors gestion par le script, sans la supprimer.

Le script teste les accès depuis Seerr et valide les profils/racines avant de
modifier les réglages. Il fusionne `settings.json` pendant un arrêt bref de
Seerr, puis redémarre le service et vérifie sa configuration chargée. L’API de
réglages n’est pas utilisable avant la création du premier administrateur ; ce
mode permet de préparer les connexions sans désactiver l’authentification.

Les comptes, sessions, permissions, notifications, état de l’assistant et champs
non pilotés sont conservés. Les clés API ne sont pas affichées. Une sauvegarde
privée est créée dans `shared/data/seerr/backups/env-settings-*.json` ; en cas
d’échec après écriture, le script restaure les anciens réglages et redémarre
Seerr. Les relances identiques ne créent pas de doublons ni d’arrêt supplémentaire.
Le `.env` fait autorité pour les champs exposés : une modification dans l’interface
sera réappliquée à la prochaine exécution du script.

## Jellyfin ou Emby optionnel

```dotenv
SEERR_MEDIA_SERVER_TYPE=jellyfin
SEERR_MEDIA_SERVER_URL='http://media-server:8096'
SEERR_MEDIA_SERVER_API_KEY='your-server-api-key'
SEERR_MEDIA_SERVER_EXTERNAL_URL='https://media.example.test'
SEERR_MEDIA_SERVER_LIBRARY_IDS='library-id-1,library-id-2'
```

Utiliser `emby` pour un serveur Emby. Créer une clé API dans l’administration du
serveur média. Le script récupère son nom, son identifiant et ses bibliothèques
films/séries. Les identifiants peuvent être relevés dans l’administration du
serveur ; la sélection est ensuite vérifiable dans Settings → Jellyfin/Emby.
Une URL média vide conserve la configuration existante. Une liste de bibliothèques
vide conserve la sélection antérieure pour le même serveur ; les nouvelles
bibliothèques restent désactivées. L’API doit répondre à `/System/Info` et
`/Library/VirtualFolders`. L’accès Plex reste à configurer dans l’assistant.

Sans bootstrap Jellyfin, ces variables préparent la connexion au serveur média ;
terminer alors la connexion administrateur et l’assistant dans l’interface. Aucun mot de passe Jellyfin/Emby ni compte administrateur
artificiel n’est écrit dans la base des utilisateurs.

Le français de l’interface (`SEERR_LOCALE=fr`) et les régions du catalogue ne
sélectionnent pas la langue audio des téléchargements : celle-ci est imposée par
le profil **1080p Français** dans Radarr/Sonarr.

## Jellyfin intégré à la stack

Le Compose partagé inclut désormais Jellyfin. Les scripts
`configure-jellyfin.py` puis `configure-seerr.py` préparent ses bibliothèques,
identifient son administrateur et terminent l’assistant Seerr si
`SEERR_BOOTSTRAP_WITH_JELLYFIN=true`. Dans ce mode, utiliser les identifiants
Jellyfin du `.env` avec le bouton de connexion Jellyfin de Seerr. Voir le
[guide Jellyfin](jellyfin.md) pour les variables et l’ordre des commandes.

Le mode manuel décrit ci-dessus reste disponible pour Plex ou un serveur média
externe en désactivant ce bootstrap. Les valeurs des profils par défaut Seerr
restent indépendantes de la [liste de profils Profilarr](profilarr.md#plusieurs-profils-dans-le-env).
