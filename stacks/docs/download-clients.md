# Clients qBittorrent de la stack

## Script de configuration

Depuis la racine du dépôt, avec Python 3 et les services démarrés :

```sh
python3 scripts/configure-download-clients.py
```

Le script retrouve la racine du dépôt depuis son propre emplacement ; il peut
également être lancé depuis un autre dossier. Aucun paquet Python supplémentaire
n'est nécessaire. Il lit les clés API locales dans les `data/*/config.xml` :
utiliser un compte disposant de ces droits, généralement root sur cet hôte.

Il configure Prowlarr, Lidarr, Radarr, Sonarr et Shelfmark, crée uniquement
les catégories absentes, puis teste les connexions. Il ne lance aucun téléchargement,
ne modifie pas le mot de passe du serveur qBittorrent et ne supprime aucun fichier.
Les chemins et options des catégories existantes sont conservés.

Les clients déjà présents sont conservés et testés. Pour cibler une partie de
la stack ou appliquer explicitement de nouveaux identifiants :

```sh
python3 scripts/configure-download-clients.py --apps sonarr radarr
python3 scripts/configure-download-clients.py --apps sonarr --update-existing
python3 scripts/configure-download-clients.py --help
```

`--update-existing` remplace la connexion, les identifiants et la catégorie du
client ciblé. Les autres paramètres, dont priorité et nettoyage, sont conservés.
En présence de plusieurs clients qBittorrent dans une même application, le script
refuse de choisir à l'aveugle. Aucune entrée supplémentaire n'est alors créée.
Les nouvelles connexions désactivent la suppression automatique des torrents
terminés ou échoués.

### Identifiants et réseau

Le fichier privé par défaut est `download/.qbittorrent-credentials.json`. Sur une
nouvelle installation, définir d'abord un mot de passe permanent dans qBittorrent,
puis enregistrer ces identifiants existants sans les mettre dans une commande :

```sh
python3 scripts/configure-download-clients.py --init-credentials
python3 scripts/configure-download-clients.py
```

La saisie du mot de passe est masquée ; le fichier est créé en mode `600` et
n'écrase pas un fichier existant. Il est exclu de Git. Une copie différente peut
être fournie avec `--credentials /chemin/vers/fichier-prive.json`.
Les variables déjà exportées `QBITTORRENT_USERNAME` et `QBITTORRENT_PASSWORD`
peuvent remplacer ce fichier ; les deux doivent être présentes. Le script ne
charge pas les `.env` automatiquement et n'utilise pas `ARR_AUTH_PASSWORD`
comme mot de passe du client qBittorrent.

`--api-host` désigne l'hôte joignable depuis le script (par défaut `127.0.0.1`,
ports publiés habituels). `--client-url` est l'URL vue par les conteneurs, par
défaut `http://qbittorrent:8080`. `--root` permet de choisir un autre dossier de
déploiement contenant les données locales. Le chemin de la catégorie `books`
doit être visible sous `/downloads` dans Shelfmark.

Si Shelfmark impose une authentification, exporter `SHELFMARK_API_KEY` avec une
clé administrateur déjà configurée sur ce service. Elle est transmise par
`X-API-Key` et n'est pas affichée. Le script ne désactive pas l'authentification.
La liaison Shelfmark → Prowlarr est ajoutée si elle est absente ; une liaison
existante est conservée, sauf avec `--update-existing`.

Le script renvoie `0` si tout réussit, `1` en cas d'échec. Il continue les autres
applications lorsqu'une seule échoue et affiche leur bilan sans réponse API brute
ni identifiants. Les changements déjà réussis ne sont pas annulés ; corriger le
problème et relancer la commande sans risque de créer de doublon.

## Connexions configurées sur cet hôte

Les applications utilisent le même service Docker `qbittorrent:8080` et le même
volume de téléchargements, exposé sous `/downloads`. Chaque outil possède sa
propre connexion et une catégorie dédiée :

| Application | Catégorie | Destination attendue |
|---|---|---|
| Prowlarr | `prowlarr` | `/downloads/prowlarr` |
| Lidarr | `music` | `/downloads/music` |
| Radarr | `movies` | `/downloads/movies` |
| Sonarr | `tv` | `/downloads/tv` |
| Shelfmark | `books` | `/downloads/books` |

Certaines catégories utilisent un chemin relatif (`music`, `movies`, `tv`,
`books`) au dossier par défaut de qBittorrent ; cela évite de modifier les
catégories déjà configurées. Conserver un dossier de téléchargement par défaut
cohérent avec `/downloads` et les volumes des applications.

Les clients ont été enregistrés et testés depuis les applications. Les clients
arr sont activés et les doublons ne sont pas créés. La suppression automatique
des torrents terminés ou échoués n'a pas été activée lors de leur création.
Les réglages de gestion automatique et d'utilisation des chemins de catégories
en mode manuel de qBittorrent ont été conservés.

## Shelfmark

La rubrique des clients de Shelfmark sélectionne qBittorrent avec :

- URL interne `http://qbittorrent:8080` ;
- catégorie ebooks `books` ;
- dossier de téléchargements `/downloads/books`.

La liaison Prowlarr est également renseignée avec `http://prowlarr:9696` et sa
clé API. Le test qBittorrent a été réalisé après enregistrement des paramètres.
La destination finale de livraison Shelfmark reste `/books`, qui correspond au
dossier de réception configuré dans la stack book.

## Ce qui reste séparé

La connexion à qBittorrent dans Prowlarr sert aux téléchargements lancés depuis
Prowlarr et ne configure pas les autres applications. Prowlarr synchronise les
indexeurs avec les applications arr, pas leurs clients de téléchargement.
Les indexeurs et les comptes requis pour les sources restent à configurer.
Aucun téléchargement n'a été lancé pour vérifier ces connexions.

Navidrome, Calibre-Web et Audiobookshelf lisent les bibliothèques ; aucun client
qBittorrent n'est nécessaire pour cette fonction. Arcane et Traefik ne sont pas
non plus des consommateurs de téléchargements.

## Persistance et identifiants

Les connexions sont enregistrées dans les bases et configurations locales des
applications, sous `data/`, exclues de Git. Un nouveau clone sans ces données
ne recrée pas automatiquement ces connexions au seul démarrage de Compose :
exécuter le script après avoir configuré les services et les identifiants, ou
restaurer les données locales sauvegardées.

Le mot de passe du client qBittorrent est distinct de `ARR_AUTH_PASSWORD`, qui
sert à se connecter à l'interface de chaque application arr. Les identifiants
qBittorrent utilisés sont sauvegardés localement dans le fichier privé
`download/.qbittorrent-credentials.json`. Si le mot de passe qBittorrent change,
mettre à jour les connexions des applications et la copie privée.

## Transport VPN

qBittorrent partage le réseau de Gluetun. Son nom Docker et son port interne
restent `qbittorrent:8080` grâce à un alias sur Gluetun. Après une modification
ou recréation du VPN, lancer `./scripts/vpn-up.sh` avant les tests clients.
Voir [le guide VPN](../vpn/README.md).

La catégorie générique `other`, destinée à `/downloads/other`, est également
créée si elle manque à chaque exécution du script, y compris avec `--apps`.
Une catégorie `other` déjà présente conserve son chemin.

## Premier compte sans data

`python3 scripts/initialize.py prepare` crée les identifiants privés et prépare
la configuration de qBittorrent lorsqu’elle n’existe pas. Le démarrage vérifie
le compte par l’API native ; l’authentification locale est exigée dès la création. Les variables
`QBITTORRENT_INIT_*` ne réinitialisent jamais un compte existant. Voir le
[guide d’initialisation](initialization.md).
