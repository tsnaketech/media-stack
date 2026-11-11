# Authentification des applications arr

## Réglages actuels

Prowlarr, Sonarr, Radarr, Lidarr utilisent :

```json
{
  "authenticationMethod": "forms",
  "authenticationRequired": "disabledForLocalAddresses"
}
```

`Forms` correspond à **Forms (Login Page)**. La seconde option dispense
les adresses considérées locales par l'application de se connecter : il est
normal de ne pas voir le formulaire depuis le LAN. Derrière un reverse proxy,
le comportement dépend aussi de l'adresse client vue par l'application et de
sa gestion des en-têtes transmis ; ce réglage ne garantit pas une protection
externe si le proxy est considéré comme un client local.

Ce paramétrage concerne les cinq applications arr ; Shelfmark, qBittorrent,
Navidrome, Calibre-Web, Audiobookshelf et Arcane ont leurs propres mécanismes
d'authentification.

## Configuration déclarative via .env et Compose

Les réglages sont désormais définis dans les fichiers `.env` des stacks
`indexer`, `music`, `tv`, `movie` :

```dotenv
ARR_AUTH_METHOD=Forms
ARR_AUTH_REQUIRED=DisabledForLocalAddresses
```

Les `.env.example` contiennent les mêmes valeurs pour une nouvelle installation.
Le `.env` sert à l'interpolation de Compose ; le bloc `environment` transmet
ensuite les variables natives à l'application. Exemple Sonarr :

```yaml
environment:
  PUID: ${PUID:-1000}
  PGID: ${PGID:-1000}
  TZ: ${TZ:-Europe/Paris}
  SONARR__AUTH__METHOD: ${ARR_AUTH_METHOD:-Forms}
  SONARR__AUTH__REQUIRED: ${ARR_AUTH_REQUIRED:-DisabledForLocalAddresses}
```

Chaque application utilise son propre préfixe :

| Stack | Préfixe natif |
|---|---|
| `indexer` / Prowlarr | `PROWLARR__AUTH__` |
| `music` / Lidarr | `LIDARR__AUTH__` |
| `tv` / Sonarr | `SONARR__AUTH__` |
| `movie` / Radarr | `RADARR__AUTH__` |

Ces variables ne sont transmises ni à qBittorrent ni à Navidrome. Les ancres YAML
conservent les variables communes PUID/PGID/TZ lors des surcharges par service.
Les valeurs par défaut du Compose s'appliquent si une variable du `.env` est
absente ou vide. Les variables du shell de lancement peuvent aussi remplacer
celles du `.env` lors de l'interpolation.

Pour modifier un réglage, éditer le `.env` de la stack puis recréer le service :

```sh
cd /opt/media-stack/stacks
python3 scripts/stack-compose.py tv config --quiet
python3 scripts/stack-compose.py tv up -d sonarr
```

Un simple `restart` ne prend pas en compte un changement d'environnement.
Les variables natives priment sur les réglages persistés : modifier le `.env`
plutôt que la page de paramètres pour ces deux champs. Les comptes et clés API existants restent dans les données persistantes ; ces
deux variables natives ne créent pas de compte administrateur à elles seules.
Le hook décrit ci-dessous permet de fournir les identifiants séparément.

Références : [Sonarr](https://wiki.servarr.com/sonarr/environment-variables),
[Radarr](https://wiki.servarr.com/radarr/environment-variables),
[Prowlarr](https://wiki.servarr.com/prowlarr/environment-variables),
[Lidarr](https://wiki.servarr.com/lidarr/environment-variables).

## Nom d'utilisateur et mot de passe dans .env

Chaque stack arr accepte également :

```dotenv
ARR_AUTH_USERNAME='admin'
ARR_AUTH_PASSWORD='un-mot-de-passe-personnel'
```

Ces deux variables sont propres au dépôt. Les applications arr ne proposent pas
les équivalents natifs pour ces identifiants. Compose les transmet au service arr
concerné ; son hook `post_start` lance `scripts/configure-arr-auth.sh`.
Le script attend l'API, lit sa clé dans `/config/config.xml`, applique les
identifiants puis vérifie le nom d'utilisateur enregistré. Il ne les affiche pas.

- Un mot de passe vide conserve le compte existant, même si le nom est renseigné.
- Un mot de passe renseigné exige un nom d'utilisateur et remplace les identifiants
  actuels de l'application. Une valeur vide ne permet pas de supprimer un mot de passe.
- Les noms existants ont été récupérés. Les API ne permettent pas de récupérer
  les mots de passe existants : ils restent vides dans les `.env`, sauf celui de
  Radarr, déjà connu et migré sans changement.

Après édition du `.env` avec un éditeur local, recréer le service :

```sh
cd /opt/media-stack/stacks
python3 scripts/stack-compose.py movie config --quiet
python3 scripts/stack-compose.py movie up -d radarr
```

Compose 2.30 ou plus récent est nécessaire pour le hook. Les images actuelles
contiennent bash, curl et jq, utilisés par le script. Un changement du `.env`
modifie l'environnement et entraîne une recréation avec `up -d`. Un simple
redémarrage par le moteur Docker ne relance pas le hook ; les identifiants déjà
appliqués restent dans la base persistante. Le hook s'exécute après le démarrage :
il ne constitue pas un verrou empêchant l'application de servir avant sa fin.

Les `.env` sont exclus de Git et protégés en mode `600`. Ils contiennent des
secrets en clair, également visibles aux administrateurs Docker dans
l'environnement des conteneurs. Ne pas publier les sorties de `docker inspect`
ou de `docker compose config` sans `--quiet`. Utiliser des valeurs entre
apostrophes dans `.env` préserve notamment les caractères `$` sans interpolation.
Pour revenir à un ancien mot de passe, le renseigner explicitement dans `.env`
puis relancer `up -d`.

Référence : [hooks de cycle de vie Compose](https://docs.docker.com/compose/how-tos/lifecycle/).

## Configuration initiale via API

La configuration initiale a été effectuée via les API locales, en conservant les autres
réglages et les comptes existants :

1. Lire la clé API dans le `config.xml` local de l'application, sans l'afficher.
2. Lire l'objet de configuration avec `GET /api/<version>/config/host`.
3. Modifier uniquement les champs d'authentification dans cet objet.
4. Renvoyer l'objet complet avec `PUT` sur le même endpoint et l'en-tête
   `X-Api-Key`. Envoyer l'objet complet préserve ses autres propriétés.
5. Relire l'objet avec `GET` pour confirmer les valeurs enregistrées.

| Application | Port | Version API |
|---|---|---|
| Prowlarr | 9696 | `v1` |
| Lidarr | 8686 | `v1` |
| Sonarr | 8989 | `v3` |
| Radarr | 7878 | `v3` |

Les clés API et mots de passe ne doivent pas être copiés dans la documentation
ou les journaux. Les hôtes autorisés ont été conservés. Certaines applications
exigent une liste d'hôtes non vide pour permettre l'exemption des adresses locales.

## Cas de Radarr

Radarr utilisait `Authentication Method = None`. Son API refusait l'activation
de Forms sans nom d'utilisateur ni mot de passe. Un compte `admin` avec un mot
de passe aléatoire a donc été configuré ; les identifiants sont stockés dans :

```text
/opt/media-stack/stacks/movie/data/.radarr-credentials.json
```

Ce fichier est une copie historique en mode `600`, exclue de Git. Le fichier
`movie/.env` est désormais la source de configuration ; une modification
ultérieure ne met pas cette copie à jour. Pour consulter la copie initiale :

```sh
cat /opt/media-stack/stacks/movie/data/.radarr-credentials.json
```

## Consulter depuis l'interface

Les deux champs sont désormais pilotés par l'environnement. Les indications
ci-dessous décrivent les réglages équivalents dans l'interface ; une modification
locale ne remplace pas les valeurs fournies par Compose.

Dans chaque application : **Settings → General → Security** (afficher les
réglages avancés si nécessaire), choisir **Authentication Method → Forms
(Login Page)** et **Authentication Required → Disabled for Local Addresses**,
puis enregistrer. Sur une première configuration, renseigner également les
identifiants demandés. Après un changement de mot de passe dans l'interface,
mettre aussi à jour le `.env` si un mot de passe y est renseigné, faute de quoi
le hook réappliquera celui du `.env` au prochain démarrage via Compose.

## Accès local via Traefik

L'exemption locale peut fonctionner par IP et échouer par FQDN si l'application
ne fait pas confiance au proxy. Les applications arr refusent l'exemption tant
que l'en-tête `X-Forwarded-For` n'a pas été validé par leur middleware de proxies
connus ; le fait que le proxy soit lui-même dans un réseau privé ne suffit pas.

Les cinq stacks acceptent `ARR_TRUSTED_PROXIES` dans leur `.env`. Compose transmet
cette liste à `<APPLICATION>__SERVER__TRUSTEDNETWORKS`. La liste contient les
adresses des relais réellement utilisés, au format CIDR, séparées par des virgules.
Les adresses de ce déploiement restent uniquement dans les `.env` exclus de Git ;
les `.env.example` laissent cette variable vide.

Le routage actuel via les ports publiés peut faire apparaître la passerelle
Docker comme pair immédiat : les `.env` déclarent donc les adresses du proxy et
des passerelles concernées en `/32`, et non un réseau global de confiance.
Ces relais doivent être administrés et autorisés à transmettre l'adresse cliente.
Ne pas mettre `0.0.0.0/0` ni supprimer les en-têtes pour contourner le contrôle.

Après modification de cette liste, recréer le service avec `up -d` pour appliquer
l'environnement. Si Traefik ou les réseaux Docker sont recréés avec d'autres
adresses, vérifier la liste à nouveau. Le DNS local doit toujours pointer sur
l'hôte qui héberge Traefik.

Vérifications effectuées sur Prowlarr, Lidarr, Sonarr et Radarr :

- Accès via leur FQDN sans cookie : HTTP 200 pour le client local.
- Adresse cliente locale transmise depuis Traefik : HTTP 200.
- Adresse cliente externe de test transmise depuis Traefik : HTTP 302 vers le login.

Références : [traitement des proxies Sonarr](https://github.com/Sonarr/Sonarr/blob/develop/src/NzbDrone.Host/ForwardedHeadersConfigurator.cs)
et [condition d'exemption locale](https://github.com/Sonarr/Sonarr/blob/develop/src/Sonarr.Http/Authentication/UiAuthorizationHandler.cs).

## Allowed Hosts dans .env

Les cinq stacks arr acceptent `ARR_ALLOWED_HOSTS`. Exemple pour Sonarr :

```dotenv
ARR_ALLOWED_HOSTS='localhost;127.0.0.1;sonarr;sonarr.arr.local'
```

Compose transmet cette valeur à `SONARR__SERVER__ALLOWEDHOSTS` (ou au préfixe
natif de Prowlarr, Radarr ou Lidarr). Utiliser des points-virgules pour
séparer les noms et ne pas ajouter de protocole, port ou chemin. Inclure le nom
Docker si l'application est appelée ainsi par Prowlarr. Pour l'accès direct par
IP du serveur, ajouter également cette IP dans le `.env` local.

Il s'agit des noms utilisés dans l'en-tête HTTP `Host`, pas des adresses clientes
ni des réseaux autorisés à éviter le formulaire. La confiance dans les proxies
se règle séparément avec `ARR_TRUSTED_PROXIES`.

Les listes effectives existantes ont été reprises dans les `.env` sans les
anciens noms homelab. Les `.env.example` ne contiennent que des valeurs génériques,
pas l'adresse privée du serveur. Si la variable est absente ou vide, Compose
utilise les noms par défaut propres à chaque application.

Après modification, recréer le service concerné avec `docker compose up -d`.
Les valeurs d'environnement priment sur le champ correspondant de l'interface.

Le hook des [racines média](media-roots.md) est indépendant du hook des
identifiants : il peut enregistrer une racine même si `ARR_AUTH_PASSWORD` est vide.
