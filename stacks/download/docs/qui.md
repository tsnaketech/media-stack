# qui : interface de gestion de qBittorrent

qui utilise l’image officielle `ghcr.io/autobrr/qui:latest` dans le Compose
partagé. Son interface est publiée sur le port `7476`, avec une route Traefik
`qui.arr.local`. Les URL de l’hôte actuel sont dans le README de `/opt`.

L’application rejoint `media-shared` et utilise l’API de qBittorrent à
`http://qbittorrent:8080`. Elle ne remplace pas qBittorrent. Son stockage persiste
dans `download/data/qui`, exclu de Git. Aucun dossier de téléchargement ni socket
Docker n’est monté dans qui.

## Variables du `.env`

```dotenv
QUI_PORT=7476
QUI_LOG_LEVEL=INFO
QUI_SESSION_SECRET='your-random-session-secret'
QUI_SESSION_COOKIE_SECURE=false
QUI_SETUP_ENABLED=true
QUI_USERNAME=admin
QUI_PASSWORD='your-random-password'
QUI_INSTANCE_NAME=qBittorrent
QUI_QBITTORRENT_URL=http://qbittorrent:8080
QUI_QBITTORRENT_USERNAME=''
QUI_QBITTORRENT_PASSWORD=''
```

Générer le secret de session avec `openssl rand -hex 32` et un mot de passe
avec `openssl rand -hex 24`. Les valeurs réelles restent dans le `.env` local,
protégé en mode `600`. Les options serveur/session sont transmises avec les
variables natives `QUI__*`. Activer le cookie sécurisé uniquement lorsque
l’interface est accessible en HTTPS, car il ne sera pas envoyé en HTTP.

Les autres variables sont appliquées par le script hôte. Si les identifiants
qBittorrent sont vides, il lit `download/.qbittorrent-credentials.json`. Une autre
URL exige des identifiants explicites, pour éviter d’envoyer les secrets locaux
à une destination différente.

## Démarrage et connexion

Depuis la racine du dépôt :

```sh
mkdir -p download/data/qui
sudo chown 1000:1000 download/data/qui
python3 scripts/stack-compose.py download up -d qui
python3 scripts/configure-qui.py
```

Le script crée le premier compte via l’API native, vérifie la connexion et ajoute
l’instance qBittorrent. Les relances conservent le compte et l’instance existants,
sans doublon. Il ne réinitialise pas un mot de passe inconnu et ne modifie aucun
torrent. Les fonctions de cross-seed et d’automatisation restent à configurer
volontairement dans l’interface.

Après rotation des identifiants qBittorrent, appliquer explicitement :

```sh
python3 scripts/configure-qui.py --update-existing
```

`QUI_SETUP_ENABLED=false` désactive cette configuration automatique. Le script
est aussi appelé par `scripts/stacks.sh up`. Pour modifier un mot de passe qui
existant, le changer dans l’interface puis mettre à jour le `.env` utilisé pour
les prochaines connexions du script. L’authentification reste activée.

## Vérification

```sh
python3 scripts/stack-compose.py download ps qui
curl --fail http://127.0.0.1:7476/health
```

Sauvegarder `download/data/qui` et le `.env` privé. Le dossier `/config` contient
la base et les réglages ; ne pas les publier sur GitHub.

Documentation : [qui](https://github.com/autobrr/qui),
[variables natives](https://getqui.com/docs/configuration/environment).
