# SABnzbd

SABnzbd complète qBittorrent pour les téléchargements Usenet. Il est déclaré dans
`download/docker-compose.yml`, sur le réseau `media-shared`, sans raccordement à
Gluetun. Les connexions au fournisseur utilisent TLS par défaut.

## Démarrage

Depuis la racine `stacks` :

```sh
python3 scripts/stack-compose.py download config --quiet
python3 scripts/stack-compose.py download up -d --no-deps sabnzbd
python3 scripts/stack-compose.py download logs --tail=60 sabnzbd
```

Interface : `http://IP_DU_SERVEUR:8085` ou `http://sabnzbd.arr.local` si le DNS
local pointe vers Traefik. Les URL propres à l’hôte sont dans `/opt/media-stack/README.local.md`.
Les identifiants sont `SABNZBD_USERNAME` et `SABNZBD_PASSWORD` dans le `.env` privé.
Générer un mot de passe avec `openssl rand -hex 24`.

## Configuration par environnement

Le script `scripts/configure-sabnzbd.py` s’exécute avant l’application via
`/custom-cont-init.d`, avec Python et ConfigObj déjà présents dans l’image.
Il applique l’authentification, `SABNZBD_ALLOWED_HOSTS`, les dossiers et la limite
`SABNZBD_MIN_FREE_SPACE`. Mettre `SABNZBD_SETUP_ENABLED=false` pour laisser la
configuration manuelle prendre le relais. Les clés API existantes sont conservées.

Pour connecter un fournisseur Usenet, renseigner `SABNZBD_SERVER_HOST`,
`SABNZBD_SERVER_PORT`, `SABNZBD_SERVER_SSL`, `SABNZBD_SERVER_USERNAME`,
`SABNZBD_SERVER_PASSWORD` et `SABNZBD_SERVER_CONNECTIONS`, puis relancer
`python3 scripts/stack-compose.py download up -d --no-deps sabnzbd`.
Le fournisseur géré s’appelle `env-provider` ; vider le host conserve une entrée
existante. Les autres serveurs configurés manuellement sont conservés.

## Stockage et intégrations

Le volume `SHARED_DOWNLOADS_DIR:/downloads` est commun aux applications arr.
Les téléchargements utilisent `/downloads/usenet/incomplete` et
`/downloads/usenet/complete`, avec les catégories `movies`, `tv`, `music`
et `books`. Aucune tâche n’est ajoutée par l’installation.

Le dossier hôte par défaut `/downloads` utilise le disque du LXC. La limite
libre de 2 Go réduit le risque de saturation sans garantir l’espace nécessaire
à une décompression. Prévoir un stockage plus grand avant les premiers travaux,
en conservant des chemins cohérents dans tous les clients.

L’installation ne fournit ni abonnement Usenet ni indexeur NZB. Après leur choix,
ajouter l’indexeur dans Prowlarr et le client SABnzbd dans les applications :
hôte `sabnzbd`, port `8080`, clé API disponible dans Configuration → Général,
catégorie propre à chaque application. qBittorrent reste disponible.

Références : [image LinuxServer](https://docs.linuxserver.io/images/docker-sabnzbd/),
[documentation SABnzbd](https://sabnzbd.org/wiki/).
