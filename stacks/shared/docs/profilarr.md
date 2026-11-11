# Profilarr : profils de qualité et formats personnalisés

Profilarr centralise les profils et formats destinés à Radarr et Sonarr.
Cette stack utilise les images stables officielles `profilarr:latest` et
`profilarr-parser:latest` depuis GHCR. Le parser permet de tester les formats et
profils ; il reste sur le réseau privé de la stack, sans port publié sur l'hôte.

## Configuration et démarrage

Les réglages sont regroupés dans `shared/.env.example` : utilisateur, fuseau horaire,
DNS, port, origines HTTP et authentification. Copier ce fichier vers `.env`
uniquement si ce dernier n'existe pas. Les paramètres persistants et les bases
restent dans `shared/data/profilarr`, exclu de Git.

Depuis la racine du dépôt :

```sh
mkdir -p shared/data/profilarr
# Adapter 1000:1000 aux valeurs PUID/PGID choisies.
sudo chown 1000:1000 shared/data/profilarr
python3 scripts/stack-compose.py shared config --quiet
python3 scripts/stack-compose.py shared up -d
python3 scripts/stack-compose.py shared ps
python3 scripts/stack-compose.py shared logs --since=5m --tail=80
```

Le port Web par défaut est `6868`. Consulter le README de `/opt` pour les URL
réelles de l'hôte actuel. La route Traefik externe est `profilarr.arr.local` et
nécessite une entrée DNS locale correspondante.

`PROFILARR_ORIGIN` définit une seule URL publique canonique complète dans la
version installée. Utiliser cette adresse pour la connexion et les formulaires.
La valeur locale est `http://profilarr.arr.local` ; une liste séparée par des
virgules provoque une boucle de redirection avec cette version. Pour utiliser
uniquement l'accès direct, remplacer cette valeur par l'URL privée et son port
dans le `.env`, puis recréer le conteneur. Les adresses privées restent hors Git.

## Première configuration

1. Définir les identifiants dans `shared/.env` comme indiqué ci-dessous, ou
   créer le compte depuis l’interface si `PROFILARR_PASSWORD` est vide.
   `PROFILARR_AUTH=on` conserve la connexion obligatoire.
2. Lancer `python3 scripts/configure-profilarr.py` pour relier automatiquement
   Radarr et Sonarr. Le réseau `media-shared` permet ces accès.
3. Choisir la base de profils souhaitée dans l'interface, puis sélectionner les
   profils et formats utiles à la bibliothèque.
4. Examiner les changements avant d'effectuer la première synchronisation.

Le script peut lier la base Dictionarry au premier démarrage lorsque la gestion
des profils français et `PROFILARR_DATABASE_SETUP_ENABLED` sont activées.
Aucune synchronisation vers Radarr/Sonarr, recherche, mise à niveau de médias
ou modification de leurs profils existants n’est déclenchée par cette installation.
Les paramètres média pilotés par les `.env` des stacks arr sont réappliqués par
leurs scripts de démarrage : éviter de les gérer simultanément avec une autre
source sans choisir laquelle doit faire autorité.

Profilarr ne reçoit pas de client qBittorrent et n'est pas une application à
ajouter dans Prowlarr. Il ne monte pas les bibliothèques média : il configure
Radarr et Sonarr via leurs API.

Documentation : [dépôt officiel et installation](https://github.com/Dictionarry-Hub/profilarr).

## Identifiants locaux depuis le `.env`

Le hook Compose `post_start` exécute `scripts/configure-profilarr-auth.sh` dans
Profilarr avec PUID/PGID. Bash et curl sont présents dans l’image ; Python n’est
pas nécessaire. Le script utilise les formulaires de création, de connexion et
de changement de mot de passe de l’application, qui assure le hachage et la
validation. Ces variables sont propres au script :

```dotenv
PROFILARR_USERNAME=admin
PROFILARR_PASSWORD='mot-de-passe-au-moins-8-caracteres'
PROFILARR_CURRENT_PASSWORD=''
```

Générer un mot de passe sous Linux avec `openssl rand -hex 24`. Le placer dans
`shared/.env`, exclu de Git et protégé en mode `600`, puis appliquer depuis la
racine du dépôt :

```sh
python3 scripts/stack-compose.py shared up -d profilarr
```

Un mot de passe cible vide conserve le compte existant. Sinon, le script crée
le premier compte ou vérifie les identifiants déjà configurés. Pour changer le
mot de passe, conserver le nom d’utilisateur existant, renseigner l’ancien dans
`PROFILARR_CURRENT_PASSWORD` et le nouveau dans `PROFILARR_PASSWORD`, puis lancer
la commande ci-dessus. Après succès, vider `PROFILARR_CURRENT_PASSWORD` et
relancer la commande. Le renommage d’un compte existant n’est pas pris en charge.
Des identifiants inconnus provoquent une erreur sans réinitialiser le compte ni
modifier directement la base de données.

Le script attend le démarrage et vérifie la connexion après application. Aucun
mot de passe n’est affiché ni transmis comme argument de commande. Les fichiers
temporaires sont privés et supprimés en fin d’exécution. Après modification du
`.env`, utiliser la commande Compose ci-dessus : un simple redémarrage ne relance
pas `post_start`. Une erreur du hook est signalée par Compose, mais l’application
peut rester démarrée : vérifier le résultat de la commande. L’authentification
doit rester activée avec `PROFILARR_AUTH=on`.

## Connexions automatiques à Radarr et Sonarr

Le script Python standard de l’hôte `scripts/configure-profilarr.py` récupère les
réglages résolus par Compose et lit les clés API dans les volumes `/config` de
Radarr et Sonarr. Python n’est pas requis dans les conteneurs. Il utilise la
session Profilarr et ses formulaires/API, sans écrire directement dans sa base.
Les identifiants et les réponses contenant des secrets ne sont jamais affichés.

Dans `shared/.env` :

```dotenv
PROFILARR_SETUP_ENABLED=true
PROFILARR_RADARR_URL=http://radarr:7878
PROFILARR_SONARR_URL=http://sonarr:8989
PROFILARR_RADARR_API_KEY=''
PROFILARR_SONARR_API_KEY=''
```

Les clés vides sont détectées automatiquement ; les renseigner uniquement pour
une instance dont la configuration locale n’est pas accessible. Adapter aussi
l’URL correspondante. Les deux applications doivent être démarrées et joignables
depuis Profilarr. Le compte local doit être configuré par le hook d’authentification.
Les URL représentent les destinations vues depuis le conteneur, pas depuis l’hôte.

Depuis la racine du dépôt :

```sh
python3 scripts/configure-profilarr.py
# Après rotation des clés API, mettre à jour explicitement les entrées existantes.
python3 scripts/configure-profilarr.py --update-existing
```

`scripts/stacks.sh up` appelle automatiquement ce script après le démarrage de
toutes les stacks. Un `docker compose up` direct ne lance pas ce script hôte.
`PROFILARR_SETUP_ENABLED=false` désactive cette étape. Les relances conservent les
connexions existantes, sans doublon ; une destination différente sous le même nom
provoque une erreur. L’option `--update-existing` renouvelle les clés enregistrées
en conservant le nom, les tags, l’URL externe et l’intervalle de bibliothèque.

Chaque connexion est testée depuis Profilarr avant son ajout. La création utilise
le comportement natif de Profilarr : si son option « appliquer les profils de
délai par défaut » est activée, ceux-ci sont appliqués aux applications lors de
l’ajout. Cette option est activée sur cet hôte. Les profils de qualité, formats,
renommages et synchronisations restent à sélectionner selon les langues et
qualités souhaitées. Le script ne choisit pas ces préférences. Les formulaires
utilisés ont été vérifiés avec Profilarr 2.3.1 ; après une mise à niveau majeure,
contrôler le résultat du script avant de supposer la configuration appliquée.

## Politique 1080p et audio français

Le profil local **1080p Français** est défini dans
`shared/profiles/french-1080p.json`. Il est créé dans la couche utilisateur de
Dictionarry : les mises à jour communautaires conservent ces réglages locaux.
Il accepte WEB-DL, WEBRip et Blu-ray en 1080p. Le format **Audio français requis**
utilise la condition native de langue française, avec un score de `10000` et un
minimum obligatoire de `10000`. Aucun autre format ne contribue au score : une
release sans français ne peut donc pas franchir ce seuil. Radarr reçoit également
la langue de profil `French`. Sonarr v4 utilise le format personnalisé.

FRENCH, VFF et VFQ sont acceptés. MULTI est accepté lorsque les informations
analysées identifient le français ; le seul mot MULTI ne garantit pas sa présence.
VO ou VOSTFR seules sont refusées. La décision dépend des informations du titre
et de l’indexeur, pas d’une inspection des pistes audio avant téléchargement.
Les versions dont la langue est inconnue peuvent être refusées. Les profils ne
fournissent pas d’indexeurs ni de releases francophones.

Dans `shared/.env` :

```dotenv
PROFILARR_FRENCH_PROFILES_ENABLED=true
PROFILARR_FRENCH_APPLY_EXISTING=true
```

Depuis la racine du dépôt :

```sh
python3 scripts/configure-profilarr.py
python3 scripts/configure-french-profiles.py
```

Le second script crée les éléments via les formulaires Profilarr, teste 12 cas
avec son parser, synchronise Radarr/Sonarr et vérifie les paramètres réellement
exportés. Il est aussi appelé par `scripts/stacks.sh up`. La synchronisation des
profils est ensuite programmée chaque jour à 05:00, selon le fuseau de Profilarr.
Les réglages de nommage et d’import média restent gérés par les scripts arr.

`PROFILARR_FRENCH_APPLY_EXISTING=true` attribue ce profil aux films et séries déjà
présents ; sa valeur d’exemple est `false` pour préserver une autre installation.
Les relances ne créent pas de doublons. Les remplacements automatiques sont
désactivés dans ce profil ; aucune recherche ni commande de téléchargement n’est
lancée par le script. Les fichiers déjà présents restent en place.

Des instantanés privés des anciens profils et attributions ainsi qu’une copie
SQLite cohérente de Profilarr sont conservés dans
`shared/data/profilarr/backups/french-policy-*`, exclus de Git. En cas de retour
arrière, remettre les anciens identifiants de profils des instantanés via les API
Radarr/Sonarr et désactiver l’application automatique avant de relancer les stacks.
Ne pas remplacer une base SQLite pendant que l’application tourne.

Pour les nouveaux ajouts manuels, sélectionner **1080p Français** dans Radarr ou
Sonarr. Les connexions Seerr et leurs profils par défaut sont préparés par
`scripts/configure-seerr.py` depuis les variables `SEERR_*` du `.env` partagé.
Voir le [guide Seerr](seerr.md#configuration-via-sharedenv). Avec le Jellyfin de la stack et `SEERR_BOOTSTRAP_WITH_JELLYFIN=true`, les scripts
terminent aussi l’authentification initiale et l’assistant via les API natives.

## Plusieurs profils dans le `.env`

La liste utilise une syntaxe CSV : chaque nom est entouré de guillemets doubles,
et l’ensemble d’apostrophes pour conserver ces guillemets dans Docker Compose :

```dotenv
PROFILARR_PROFILES='"1080p Français","2160p Français"'
PROFILARR_DEFAULT_PROFILE='1080p Français'
```

La ligne sans apostrophes extérieures n’est pas un fichier `.env` valide pour
Compose. Le script utilise un lecteur CSV, sans exécuter la valeur comme du code.
Les noms vides, doublons et noms sans définition locale sont refusés.

Les deux définitions sont versionnées dans `shared/profiles/french-1080p.json` et
`shared/profiles/french-2160p.json`. Elles imposent la même condition d’audio français,
avec des qualités WEB-DL/WEBRip/Blu-ray respectivement en 1080p et 2160p. Les deux
profils sont synchronisés dans Radarr et Sonarr, chaque jour à 05:00. Pour ajouter
un autre profil, créer sa définition `french-*.json`, puis ajouter son nom exact à
la liste. Le script gère ici des profils exigeant le français.

```sh
python3 scripts/configure-french-profiles.py
```

`PROFILARR_DEFAULT_PROFILE` doit appartenir à la liste. Avec
`PROFILARR_FRENCH_APPLY_EXISTING=true`, les films/séries utilisant un ancien profil
non sélectionné sont migrés vers ce défaut. Une attribution existante à l’un des
profils sélectionnés est conservée : une sélection 2160p ne redevient pas 1080p à
chaque déploiement. Aucun fichier ni recherche n’est déclenché par cette migration.

Seerr conserve un profil par défaut pour chaque connexion :

```dotenv
SEERR_RADARR_PROFILE='1080p Français'
SEERR_SONARR_PROFILE='1080p Français'
```

Les administrateurs/utilisateurs autorisés peuvent choisir un autre profil dans
les options avancées des demandes. Changer les valeurs `SEERR_*` ci-dessus pour
modifier les défauts, puis exécuter `python3 scripts/configure-seerr.py`.

## Jeton API TMDB dans le `.env`

Le jeton de lecture TMDB peut être géré avec :

```dotenv
PROFILARR_TMDB_API_TOKEN='your-tmdb-api-read-access-token'
```

Utiliser l’**API Read Access Token** fourni dans les paramètres API du compte
TMDB, sans le préfixe `Bearer`. Ce jeton n’est pas une clé API v3 courte. Le
script accepte aussi un préfixe `Bearer` collé par erreur et le retire.

Depuis la racine du dépôt :

```sh
python3 scripts/configure-profilarr.py
```

La variable est personnalisée : le script hôte transmet le jeton au formulaire
Settings → General de Profilarr. Il valide le jeton auprès de TMDB via Profilarr
avant l’enregistrement, puis vérifie le jeton enregistré. Les autres réglages
(journaux, sauvegardes, interface et comportement) sont conservés. Le jeton n’est
pas affiché ni passé comme argument de commande. Une valeur vide laisse le jeton
actuel inchangé ; pour l’effacer volontairement, utiliser l’interface Profilarr.

Cette étape est aussi exécutée par `scripts/stacks.sh up` lorsque
`PROFILARR_SETUP_ENABLED=true`. Le `.env` est exclu de Git ; ne mettre aucun jeton
réel dans `.env.example`.

## Initialisation de la base de politiques

Si les profils français sont activés, `configure-profilarr.py` utilise
`PROFILARR_DATABASE_SETUP_ENABLED`, `PROFILARR_DATABASE_NAME` et
`PROFILARR_DATABASE_URL` pour lier une base absente et attendre son cache.
Les modifications locales sont autorisées sur une base nouvellement créée pour
y enregistrer les politiques du dépôt. Une base déjà désactivée n’est pas
réactivée : l’étape française affiche un diagnostic et conserve les profils
existants. Voir le [parcours d’initialisation](../../docs/initialization.md).
