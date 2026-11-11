# Jellyfin : lecture des films, séries et musique

Jellyfin utilise l’image dérivée `media-stack/jellyfin-abyss:local`, construite
depuis l’image officielle dans le Compose partagé. Il rejoint `media-shared`
et publie `8096/tcp` et `7359/udp` par défaut.
Consulter `/opt/media-stack/README.local.md` pour les URL de cet hôte. Le FQDN
Traefik `jellyfin.arr.local` nécessite une entrée dans le DNS local.

## Stockage et droits

- `shared/data/jellyfin/config` conserve la configuration et les bases.
- `shared/data/jellyfin/cache` conserve le cache et les fichiers de transcodage.
- `/media/movies`, `/media/tv` et `/media/music` sont montés en lecture seule.

Les chemins hôtes sont pilotés par `JELLYFIN_MOVIES_DIR`, `JELLYFIN_TV_DIR` et
`JELLYFIN_MUSIC_DIR`. Les répertoires doivent déjà exister ; Compose ne les crée
pas. Jellyfin fonctionne avec `PUID:PGID` via la directive `user`. Sur un LXC non
privilégié, vérifier les ACL de lecture et de traversée pour cet utilisateur.
Les ACL existantes de l’utilisateur 1000 sont utilisées sur cet hôte.

Les médias ne sont pas modifiés. Les métadonnées restent dans la configuration
Jellyfin ; `SaveLocalMetadata=false` évite d’écrire à côté des fichiers. Aucun
périphérique GPU n’est transmis par cette configuration.

## Variables et installation

Dans `shared/.env` :

```dotenv
JELLYFIN_SETUP_ENABLED=true
JELLYFIN_ADMIN_USERNAME=admin
JELLYFIN_ADMIN_PASSWORD='your-random-password'
JELLYFIN_SERVER_NAME=Homelab
JELLYFIN_PUBLIC_URL='http://jellyfin.arr.local'
JELLYFIN_MOVIES_NAME=Films
JELLYFIN_TV_NAME='Séries'
JELLYFIN_MUSIC_NAME=Musique
SEERR_BOOTSTRAP_WITH_JELLYFIN=true
```

Générer un mot de passe sous Linux : `openssl rand -hex 24`. Utiliser au moins
12 caractères. Le `.env` local est exclu de Git et protégé en mode `600`.

Depuis la racine du dépôt :

```sh
mkdir -p stacks/shared/data/jellyfin/{config,cache}
sudo chown 1000:1000 stacks/shared/data/jellyfin/{config,cache}
python3 stacks/scripts/stack-compose.py shared up -d jellyfin seerr
python3 stacks/scripts/configure-jellyfin.py
python3 stacks/scripts/configure-seerr.py
```

Le script Python s’exécute sur l’hôte. Il suit les API de l’assistant natif pour
créer le premier administrateur, configurer le serveur en français et terminer
l’assistant. Il crée trois bibliothèques et une clé dédiée **Homelab Seerr**,
puis enregistre automatiquement dans le `.env` :

- `JELLYFIN_API_KEY` ;
- `SEERR_MEDIA_SERVER_URL=http://jellyfin:8096` et sa clé API ;
- `SEERR_MEDIA_SERVER_EXTERNAL_URL` depuis l’URL publique Jellyfin ;
- `SEERR_MEDIA_SERVER_LIBRARY_IDS` avec les identifiants Films et Séries.

Les relances vérifient le compte, les bibliothèques et la clé existants sans les
dupliquer. Un nom de bibliothèque déjà utilisé avec un autre chemin/type provoque
une erreur, sans remplacement. Le script ne réinitialise pas un compte existant :
si son mot de passe change dans Jellyfin, mettre à jour le `.env` pour les relances.
Les scans initiaux lisent les médias et récupèrent leurs métadonnées.

## Connexion de Seerr

Avec `SEERR_BOOTSTRAP_WITH_JELLYFIN=true`, le script utilise l’authentification
Jellyfin native de Seerr pour créer/identifier le premier administrateur. Le
script Seerr applique ensuite les bibliothèques et les connexions Radarr/Sonarr,
puis termine l’assistant via son API administrateur. Aucune base d’utilisateurs
n’est modifiée directement. Le serveur média doit autoriser ce compte en tant
qu’administrateur.

Dans Seerr, utiliser la connexion **Jellyfin** avec les identifiants
`JELLYFIN_ADMIN_USERNAME` et `JELLYFIN_ADMIN_PASSWORD`. Les demandes utilisent les
profils par défaut définis par `SEERR_RADARR_PROFILE` et `SEERR_SONARR_PROFILE`.
La musique reste accessible dans Jellyfin mais ne constitue pas une bibliothèque
de demandes Seerr.

`scripts/stacks.sh up` lance ces scripts dans l’ordre après le démarrage des
stacks. Pour un serveur média externe, désactiver `SEERR_BOOTSTRAP_WITH_JELLYFIN`
et ajuster les variables `SEERR_MEDIA_SERVER_*` décrites dans le [guide Seerr](seerr.md).
`JELLYFIN_SETUP_ENABLED=false` désactive la configuration automatique de Jellyfin.

## Vérification et sauvegarde

```sh
python3 scripts/stack-compose.py shared ps jellyfin seerr
python3 scripts/stack-compose.py shared logs --since=5m --tail=80 jellyfin
python3 scripts/check-services.py
```

Sauvegarder `shared/data/jellyfin/config`, le `.env` privé et les données Seerr.
Le cache peut être régénéré. Les journaux, les clés et les bases restent hors Git.
Les ports et chemins sont indépendants des profils de téléchargement : voir le
[guide des profils français](profilarr.md#plusieurs-profils-dans-le-env).

Documentation : [conteneur officiel Jellyfin](https://jellyfin.org/docs/general/installation/container/).

## Connexions des applications arr

Lidarr, Radarr et Sonarr actualisent Jellyfin via leurs connexions
natives **Settings → Connect**. Voir le [guide Connect](arr-connect.md) pour
les variables `JELLYFIN_CONNECT_*`, la clé dédiée et les correspondances de chemins.

## Thème Abyss et Spotlight

L’image locale `media-stack/jellyfin-abyss:local` est construite à partir de
l’image officielle Jellyfin. Son Dockerfile ajoute le CSS Abyss et les trois
fichiers Spotlight, puis charge Spotlight dans l’interface Web.
Les sources et leur licence sont dans `shared/jellyfin-abyss/`. Le commit amont
et les empreintes des fichiers sont enregistrés dans `SOURCE.json`.

Le script `configure-jellyfin.py` applique le CSS local via l’API Branding et
configure le thème sombre du compte administrateur. Il utilise l’ordre d’accueil
recommandé par Abyss pour Continuer la lecture, À suivre, Mes médias et Ajouts
récents. Les réglages précédents sont sauvegardés une fois dans
`shared/data/jellyfin/config/abyss-before.json`.

Depuis la racine du projet, reconstruire l’image après une mise à jour de
Jellyfin, puis vérifier la configuration.

```sh
python3 stacks/scripts/stack-compose.py shared build --pull jellyfin
python3 stacks/scripts/stack-compose.py shared up -d --no-deps jellyfin
python3 stacks/scripts/configure-jellyfin.py
```

`JELLYFIN_BASE_IMAGE` choisit l’image officielle de base et `JELLYFIN_IMAGE`
le nom de l’image dérivée. Les fichiers du thème sont embarqués dans l’image.
Les polices Google Sans et Material Icons référencées par le CSS sont chargées
par le navigateur depuis leurs fournisseurs.

Après l’installation, recharger l’interface Web avec `Ctrl+F5`.
Abyss et Spotlight s’appliquent aux clients qui utilisent cette interface Web.

[Installation Abyss](https://github.com/AumGupta/abyss-jellyfin/blob/main/SETUP.md)

## Dépôts d’extensions

`configure-jellyfin.py` enregistre le dépôt suivant via l’API Jellyfin
lors de la configuration. La commande est aussi appelée par `initialize.py up`
et `stacks.sh up`.

| Variable dans `shared/.env` | Dépôt |
|---|---|
| `JELLYFIN_ENHANCED_REPOSITORY` | Jellyfin Enhanced |

Les URL des manifestes figurent dans `shared/.env.example` et sont transmises
par le Compose au script de configuration. Une URL vide permet d’ignorer ce
dépôt. `JELLYFIN_PLUGIN_REPOSITORIES_ENABLED=false` désactive cette gestion.

Le script ajoute les sources absentes et vérifie leur enregistrement. Il
identifie les sources existantes par leur URL et conserve leur nom et leur
état d’activation. Les autres dépôts sont conservés, y compris Jellyfin Stable.
Une relance produit la même liste de dépôts.

Depuis la racine du projet, appliquer les valeurs du `.env` avec cette commande.

```sh
python3 stacks/scripts/configure-jellyfin.py
```

Pour une installation neuve, installer ensuite les extensions souhaitées depuis
**Tableau de bord → Extensions → Catalogue** et renseigner leurs clés dans leurs
pages de configuration. Les dépôts, extensions et réglages sont persistés dans
`shared/data/jellyfin/config`.
