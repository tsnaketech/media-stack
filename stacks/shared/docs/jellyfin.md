# Jellyfin : lecture des films, séries et musique

Jellyfin utilise directement `lscr.io/linuxserver/jellyfin:latest` dans le
Compose partagé. Il rejoint `media-shared`
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

L’image LinuxServer exécute `jellyfin-abyss/init/abyss-spotlight.sh` via
`/custom-cont-init.d` à chaque démarrage. Le hook copie les ressources locales
vers `/usr/share/jellyfin/web/ui/` et injecte une seule balise de chargement
Spotlight dans `index.html`. Aucun téléchargement n’est requis au démarrage.
Les fichiers, leur licence, leur commit amont et leurs empreintes sont dans
`shared/jellyfin-abyss/assets/` et `SOURCE.json`.

Le script `configure-jellyfin.py` applique les imports locaux dans cet ordre :

```css
/* ABYSS THEME START */
@import url("/web/ui/abyss.css");
@import url("/web/ui/abyss-je.css");
/* ABYSS THEME END */
```

`abyss-je.css` ajoute les styles de compatibilité Jellyfin Enhanced. Le fichier
amont indique une cible v11.3 ; l’extension installée est plus récente, donc
certaines règles peuvent ne plus cibler tous ses éléments. Les personnalisations
existantes sont conservées, y compris celles placées dans un ancien bloc géré.
Pour les nouvelles règles de couleur ou d’arrondi, les ajouter après le bloc.

Le compte administrateur utilise le thème sombre et l’ordre d’accueil recommandé :
Continuer la lecture, À suivre, Mes médias, Ajouts récents. Les préférences
précédentes restent sauvegardées une fois dans `config/abyss-before.json`.

Depuis la racine du projet :

```sh
python3 stacks/scripts/stack-compose.py shared pull jellyfin
python3 stacks/scripts/stack-compose.py shared up -d --no-deps jellyfin
python3 stacks/scripts/configure-jellyfin.py
```

`JELLYFIN_IMAGE` choisit l’image LinuxServer. Il n’y a plus d’image dérivée à
construire. `PUID` et `PGID` contrôlent l’utilisateur applicatif ; l’initialisation
s6 doit démarrer en root, sans `user`, `init: true` ou `cap_drop: ALL` ajoutés au
service. Les polices référencées par le CSS restent téléchargées par le navigateur.
Après application, recharger avec `Ctrl+F5`. Les clients utilisant Jellyfin Web
bénéficient du thème ; les applications TV natives peuvent avoir leur propre interface.

## Migration d’une ancienne installation

LinuxServer attend les XML directement dans `/config` et utilise `/config/data`
comme répertoire de données. Une ancienne installation issue de l’image officielle
ne peut pas être reprise en changeant uniquement l’image.

Arrêter Jellyfin et sauvegarder son dossier de configuration avant la migration :

```sh
cd /opt/media-stack
docker stop jellyfin
backup_dir="/srv/backups/jellyfin-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
cp -a stacks/shared/data/jellyfin/config "$backup_dir/config"
python3 stacks/scripts/migrate-jellyfin-layout.py stacks/shared/data/jellyfin/config --offline
python3 stacks/scripts/stack-compose.py shared up -d --no-deps jellyfin
python3 stacks/scripts/configure-jellyfin.py
```

Exécuter cette procédure avec les droits nécessaires sur les fichiers locaux.
`--offline` confirme l’arrêt du serveur et l’existence d’une sauvegarde vérifiée.
Le script conserve les identifiants et les médias, déplace la base vers
`config/data/data/jellyfin.db` et adapte les chemins internes des racines en base.
Des liens conservent les anciens chemins des images, plugins et racines.
Le cache est monté sous `/config/cache` et `/cache` pour garder les anciens
chemins de transcodage. Une installation vierge ne nécessite pas cette migration.

Après migration, vérifier les comptes, identifiants de bibliothèques, images,
plugins et connexions Seerr/arr. Les fichiers médias restent en lecture seule.

[Installation Abyss](https://github.com/AumGupta/abyss-jellyfin/blob/main/SETUP.md#docker)

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
