# JOAL : service et interface Web

JOAL est un simulateur de client BitTorrent pour les annonces aux trackers.
L’installation utilise l’image officielle `anthonyraymond/joal:2.1.37` dans le
Compose partagé, avec sa configuration de release et un dossier de torrents vide.
Aucun torrent qBittorrent ni fichier de téléchargement n’est importé automatiquement.

## Stockage et initialisation

Le volume `download/data/joal` contient :

- `config.json`, provenant de la release officielle ;
- `clients/`, avec ses définitions de clients ;
- `torrents/`, initialement vide.

Le script `scripts/prepare-joal.py` télécharge l’archive de la version de l’image
si les fichiers de configuration manquent. Il extrait seulement la configuration
et les définitions, sans écraser les fichiers présents ni importer de torrents.
`scripts/stacks.sh up` le lance avant de démarrer les stacks. Le stockage reste
exclu de Git. L’application fonctionne avec l’utilisateur `PUID:PGID`.

## Variables du `.env`

```dotenv
JOAL_IMAGE_TAG=2.1.37
JOAL_PORT=8088
JOAL_UI_PATH='yourAlphanumericPath'
JOAL_UI_SECRET_TOKEN='your-random-token'
JOAL_JAVA_OPTIONS='-Xms64m -Xmx256m -Duser.home=/data'
```

Générer un chemin avec `openssl rand -hex 8` et un token avec
`openssl rand -hex 24`. Le chemin doit contenir uniquement des caractères
alphanumériques. Le token sert à l’authentification de l’interface. Les options
Web sont passées aux arguments natifs de JOAL ; la mémoire maximale Java est
limitée à 256 Mio par défaut. L’image et l’archive utilisent la même version.

Depuis la racine du dépôt :

```sh
python3 scripts/prepare-joal.py
python3 scripts/stack-compose.py download config --quiet
python3 scripts/stack-compose.py download up -d joal
```

## Accès à l’interface

L’interface se trouve à l’adresse :

```text
http://IP_DU_SERVEUR:8088/<JOAL_UI_PATH>/ui/
http://joal.arr.local/<JOAL_UI_PATH>/ui/
```

Remplacer le composant de chemin par la valeur du `.env` et saisir le token
`JOAL_UI_SECRET_TOKEN` dans l’interface. La racine `/` peut renvoyer `404` : c’est
le comportement attendu. La route Traefik transmet le chemin sans le modifier.
Les URL complètes de cet hôte sont dans le README local de `/opt`.

Le contrôle de santé Docker vérifie l’écoute du port ; l’installation vérifie
aussi que l’interface répond en HTTP. Aucun volume média n’est monté dans JOAL.
JOAL commence à traiter les fichiers de son dossier `torrents/` au démarrage ;
l’installation n’en ajoute aucun. Sa configuration métier reste dans
`download/data/joal/config.json`, indépendamment du client réel qBittorrent.

## Vérification et sauvegarde

```sh
python3 scripts/stack-compose.py download ps joal
python3 scripts/stack-compose.py download logs --since=5m --tail=50 joal
```

Sauvegarder `download/data/joal` et le `.env` privé. Ne pas publier les secrets ou
les fichiers de torrents contenant des identifiants de trackers. Modifier les
variables Web nécessite de recréer le service avec `up -d`.

Documentation : [JOAL](https://github.com/anthonyraymond/joal).
