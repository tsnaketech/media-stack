# Applications Prowlarr

Le script `scripts/configure-prowlarr-apps.py` ajoute et configure Lidarr, Radarr,
Sonarr dans **Prowlarr → Settings → Apps**. Il utilise l’API native ;
les entrées restent dans `indexer/data/prowlarr/prowlarr.db`, pas dans `config.xml`.

## Exécution

Depuis la racine `stacks` :

```sh
python3 scripts/configure-prowlarr-apps.py
```

Il est également exécuté par `./scripts/stacks.sh up`, après le démarrage des
applications et la configuration du proxy FlareSolverr. Python 3 et la bibliothèque
standard suffisent. Le compte exécutant le script doit lire les configurations
locales contenant les clés API. Les réponses et clés ne sont pas affichées.

## Variables dans indexer/.env

```dotenv
PROWLARR_APPS_SETUP_ENABLED=true
PROWLARR_APPS_PROWLARR_URL=http://prowlarr:9696
PROWLARR_APPS_SYNC_LEVEL=fullSync
PROWLARR_APP_SONARR_ENABLED=true
PROWLARR_APP_SONARR_URL=http://sonarr:8989
PROWLARR_APP_SONARR_API_KEY=
PROWLARR_APP_SONARR_SYNC_LEVEL=
```

Les mêmes quatre variables existent pour `LIDARR`, `RADARR` et `SONARR`.
L’URL Prowlarr doit être accessible depuis les applications. Les URL des
applications doivent être accessibles depuis Prowlarr.

Une clé vide est lue automatiquement dans le `config.xml` du service local.
Pour une URL personnalisée, fournir une clé explicite afin de ne pas transmettre
la clé locale à une destination différente. Le `.env` privé reste hors Git.

Le niveau par application, s’il est renseigné, remplace le niveau global :

- `fullSync` : Prowlarr pilote l’ajout, les mises à jour et les suppressions de ses
  indexeurs synchronisés. Les modifier dans Prowlarr, car des changements locaux
  peuvent être remplacés.
- `addOnly` : synchronisation des ajouts et suppressions, sans mise à jour continue
  des paramètres des indexeurs déjà présents.
- `disabled` : désactive la synchronisation pour cette application.

`*_ENABLED=false` ignore la gestion de l’entrée ; il ne la supprime pas et ne
change pas son niveau existant. `PROWLARR_APPS_SETUP_ENABLED=false` ignore tout
le script.

## Conservation et contrôles

Le script identifie les entrées par type et URL, refuse les doublons ou collisions
de noms, et conserve les noms personnalisés, tags, catégories et autres options.
Il applique les URL, clés et niveaux déclarés, puis vérifie leur enregistrement.
Les connexions sont toutes testées avant les écritures. Relancer ne crée pas de
doublons ; une erreur pendant les écritures peut toutefois laisser un résultat
partiel, à corriger puis relancer.

La commande globale `ApplicationIndexerSync` est ensuite lancée et attendue ;
elle peut aussi traiter d’autres applications déjà présentes dans Prowlarr.
Une commande terminée ne garantit pas que tous les indexeurs distants sont
fonctionnels : vérifier **System → Events** et **Settings → Indexers** dans chaque
application. Seuls les indexeurs compatibles avec les catégories et tags sont
transmis. Aucun indexeur ni téléchargement n’est créé par ce script.
