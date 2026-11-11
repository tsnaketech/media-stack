# FlareSolverr : proxy de résolution pour Prowlarr

FlareSolverr utilise l’image officielle
`ghcr.io/flaresolverr/flaresolverr:latest` dans la stack indexer. Prowlarr le
joint avec `http://flaresolverr:8191`. Le port publié est limité à l’adresse de
boucle locale du LXC ; aucune route Traefik n’est créée pour cette API.

## Configuration

Les réglages sont regroupés dans `indexer/.env` et `.env.example` :

```dotenv
FLARESOLVERR_PORT=8191
FLARESOLVERR_BIND_IP=127.0.0.1
FLARESOLVERR_LOG_LEVEL=info
FLARESOLVERR_LOG_HTML=false
FLARESOLVERR_SETUP_ENABLED=true
FLARESOLVERR_URL=http://flaresolverr:8191
FLARESOLVERR_REQUEST_TIMEOUT=60
FLARESOLVERR_TAG=flaresolverr
FLARESOLVERR_INDEXERS=''
```

Le délai est exprimé en secondes, entre 1 et 180. `LOG_LEVEL` et `LOG_HTML` sont
transmis nativement au conteneur. Les variables de configuration Prowlarr sont
appliquées par le script Python de l’hôte, sans installer Python dans Prowlarr.
Les données persistantes utilisent `indexer/data/flaresolverr`, exclu de Git.
Les fichiers temporaires du navigateur utilisent un `tmpfs` limité à 256 Mio.

Depuis la racine du dépôt :

```sh
python3 scripts/stack-compose.py indexer up -d flaresolverr
python3 scripts/configure-flaresolverr.py
python3 scripts/stack-compose.py indexer ps flaresolverr
```

Le script lit la clé API locale de Prowlarr, crée le tag et le proxy, puis lance
le test natif Prowlarr. Les relances réutilisent le proxy existant sans doublon.
`scripts/stacks.sh up` l’exécute également. `FLARESOLVERR_SETUP_ENABLED=false`
désactive cette configuration automatique sans supprimer le proxy existant.

## Choix des indexeurs

Dans Prowlarr, Settings → Indexer Proxies contient le proxy **FlareSolverr**.
Ajouter le tag **flaresolverr** aux indexeurs qui doivent l’utiliser. Prowlarr
n’appelle le solveur que lorsqu’il détecte une protection Cloudflare.

Pour appliquer les tags depuis le `.env`, renseigner les noms exacts :

```dotenv
FLARESOLVERR_INDEXERS='"First indexer","Second indexer"'
```

Relancer ensuite le script. Une liste vide conserve les tags des indexeurs ;
les tags existants restent en place. Un nom inconnu provoque une erreur avant
modification des indexeurs. Retirer un nom de la liste ne retire pas son tag
existant : supprimer celui-ci dans l’interface pour désactiver ce routage.
Aucun indexeur n’est ajouté ni aucun téléchargement lancé par l’installation.

FlareSolverr ne fournit pas d’accès aux indexeurs et ne garantit pas la résolution
de toutes les protections ou CAPTCHA. Le test de connexion vérifie le navigateur
et l’intégration Prowlarr ; tester ensuite chaque indexeur concerné dans Prowlarr.

## Vérification

```sh
curl --fail http://127.0.0.1:8191/
python3 scripts/stack-compose.py indexer logs --since=5m --tail=50 flaresolverr
```

Cette adresse est accessible depuis le LXC, pas depuis le navigateur d’un autre
poste. Ne pas publier cette API sans authentification sur Internet. Les journaux
HTML restent désactivés pour éviter d’y enregistrer les pages et cookies.

Documentation : [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr).
