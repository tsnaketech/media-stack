# Bazarr : sous-titres des films et séries

Bazarr utilise l’image LinuxServer `lscr.io/linuxserver/bazarr:latest` dans la
stack partagée, avec le port Web `6767` et la route Traefik `bazarr.arr.local`.
Les URL de cet hôte figurent dans le README de `/opt`.

## Stockage et droits

La configuration et la base persistent dans `shared/data/bazarr`, exclu de Git.
Les bibliothèques sont montées sous `/movies` et `/tv`, comme dans Radarr et
Sonarr : aucune traduction de chemins n’est nécessaire. Bazarr doit pouvoir
écrire les fichiers de sous-titres à côté des vidéos ; ses montages sont donc en
lecture/écriture. Jellyfin conserve ses propres montages en lecture seule.

`BAZARR_MOVIES_DIR` et `BAZARR_TV_DIR` définissent les chemins hôtes. Ils doivent
exister et correspondre aux bibliothèques des applications arr. Les droits sont
ceux de `PUID:PGID` ; les ACL de l’utilisateur 1000 sont utilisées sur cet hôte.
L’installation vérifie la création/suppression d’un fichier temporaire dans
chaque racine. Voir aussi le [guide des droits](../../docs/permissions.md).

## Réglages dans le `.env`

```dotenv
BAZARR_PORT=6767
BAZARR_SETUP_ENABLED=true
BAZARR_USERNAME=admin
BAZARR_PASSWORD='your-random-password'
BAZARR_RADARR_URL=http://radarr:7878
BAZARR_RADARR_API_KEY=''
BAZARR_SONARR_URL=http://sonarr:8989
BAZARR_SONARR_API_KEY=''
BAZARR_LANGUAGE_PROFILE='Français'
BAZARR_MOVIES_DIR=/media/movies
BAZARR_TV_DIR=/media/tv
```

Générer un mot de passe avec `openssl rand -hex 24`. Le `.env` local est protégé
en mode `600`. Les UID/GID et le fuseau sont natifs de l’image ; les variables
`BAZARR_*` sont appliquées par `scripts/configure-bazarr.py` sur l’hôte. Il lit la
clé API de Bazarr avec son Python et son parseur YAML embarqués, sans ajouter de
dépendance sur l’hôte.

Les clés arr vides sont détectées depuis leurs volumes de configuration locaux.
Une autre URL exige une clé explicite. Le script active les deux connexions,
prépare le profil de sous-titres français et en fait le défaut pour les futurs
imports de films/séries. Il conserve les autres langues et profils. Le profil
est indépendant des profils de qualité **1080p Français**/**2160p Français** de
Profilarr : il concerne les sous-titres, pas la langue audio des vidéos.

Un mot de passe renseigné configure l’authentification par formulaire et vérifie
la connexion ; une valeur vide conserve l’authentification existante.

## Démarrage

Depuis la racine du dépôt :

```sh
mkdir -p shared/data/bazarr
sudo chown 1000:1000 shared/data/bazarr
python3 scripts/stack-compose.py shared up -d bazarr
python3 scripts/configure-bazarr.py
```

Le script est aussi exécuté par `scripts/stacks.sh up`, après démarrage des
applications arr. `BAZARR_SETUP_ENABLED=false` désactive cette configuration sans
supprimer les connexions existantes. Un `docker compose up` direct ne suffit pas
pour appliquer les variables personnalisées.

## Fournisseurs de sous-titres

Dans **Settings → Providers**, choisir les fournisseurs et renseigner leurs
comptes/clés si nécessaire. L’installation n’en active aucun sans configuration.
Les téléchargements de sous-titres ne pourront donc fonctionner qu’après cette
étape. Les sous-titres intégrés déjà présents peuvent être reconnus par Bazarr.

Vérifier ensuite les langues attribuées aux films/séries et leurs sous-titres
manquants. Les réglages de score et de synchronisation restent accessibles dans
l’interface. Bazarr n’a pas besoin d’être ajouté à Prowlarr ni de recevoir un
client qBittorrent.

## Vérification

```sh
python3 scripts/stack-compose.py shared ps bazarr
python3 scripts/stack-compose.py shared logs --since=5m --tail=50 bazarr
python3 scripts/configure-bazarr.py
```

Les contrôles vérifient l’API Bazarr, les versions Radarr/Sonarr accessibles et la
connexion par formulaire. Sauvegarder `shared/data/bazarr` avec le `.env` privé.

Documentation : [image LinuxServer](https://docs.linuxserver.io/images/docker-bazarr/),
[guide Bazarr](https://wiki.bazarr.media/Getting-Started/Setup-Guide/).
