# Extensions de déploiement

Le dépôt contient les services communs et des modèles de configuration.
Les adaptations propres à un hôte peuvent rester dans un répertoire externe,
avec leurs stacks supplémentaires, surcharges Compose et réglages d’intégration.
Ce répertoire ne fait pas partie du dépôt Git ; aucune exclusion spécifique
n’est nécessaire dans `.gitignore`.

## Activer un répertoire externe

Dans le `.env` local à la racine du projet, déjà ignoré par Git :

```dotenv
# Optional absolute path to deployment extensions.
STACK_EXTENSIONS_DIR=/srv/stack-config
```

Sans cette variable, ou si le répertoire indiqué n’existe pas, la stack commune
fonctionne seule. Un répertoire présent doit contenir un manifeste `extensions.json`
valide ; une extension incomplète ou une valeur relative provoque une erreur.
`STACK_EXTENSIONS_DIR=` dans l’environnement désactive explicitement les extensions,
notamment pour les tests isolés.

## Structure du manifeste

Exemple minimal :

```json
{
  "stacks": {"sample": "stacks/sample"},
  "env_files": {"shared": ["settings/integrations.env"]},
  "compose_overrides": {"shared": ["compose-overrides/shared.yml"]}
}
```

Les chemins du manifeste sont relatifs au répertoire externe. Chaque stack
supplémentaire contient `docker-compose.yml`, `.env.example` et son `.env` local.
Les variables sont chargées depuis le `.env` principal, puis celui de la stack,
puis les fichiers d’environnement du manifeste. L’environnement du terminal reste
prioritaire. Les surcharges Compose sont appliquées après le fichier principal.
Les chemins relatifs des montages restent relatifs à la stack principale.
Utiliser des chemins absolus pour les fichiers d’une surcharge externe.

Les champs facultatifs alimentent les scripts de configuration :

| Champ | Valeur |
|---|---|
| `applications` | Nom → `[stack, port, version_api, champ_catégorie, catégorie]` pour les clients, Prowlarr et Connect |
| `connect_roots` | Nom → `[chemin_application, chemin_serveur]` |
| `plugin_repositories` | Liste de `[variable_env, nom, url_manifeste]` |
| `jellyfin_libraries` | Liste de `{key, enabled, name_variable, name, type, path, restricted}` ; `enabled` désigne une variable d’environnement |
| `management_exports` | Liste facultative ; sans manifeste, les stacks communes sont exportées automatiquement. Destination : `runtime/arcane/<stack>/` dans le dépôt principal pour les stacks communes, dans le dossier externe pour les stacks supplémentaires |
| `health_checks` | Nom → `[port, chemin_http]` |
| `secret_fields` | Stack → `{variable_mot_de_passe: service}` ; génération uniquement sans données existantes |
| `storage` | Stack → `{library_subdir, variable, downloads}` pour les racines de stockage explicites |
| `download_directories` | Sous-dossiers supplémentaires à préparer sous la racine des téléchargements |

Une bibliothèque supplémentaire avec `restricted: true` conserve les accès
explicites et limite les anciens accès globaux avant sa création. Vérifier
les autorisations lors de l’ajout de nouveaux utilisateurs.

## Gestion quotidienne

Depuis la racine du dépôt :

```sh
python3 stacks/scripts/stack-compose.py shared config --quiet
python3 stacks/scripts/stack-compose.py shared up -d
python3 stacks/scripts/stack-compose.py sample logs --tail=30
./stacks/scripts/stacks.sh validate --with-infra
python3 stacks/scripts/initialize.py check
```

`stacks.sh`, `vpn-up.sh`, `initialize.py` et les configurateurs utilisent le même
chargeur. Employer ce lanceur pour les opérations Compose : une commande directe
avec seulement le fichier public omet les surcharges. Une interface externe de
gestion Docker doit également charger la configuration effective complète.
Les exports des stacks communes restent dans le dossier local `runtime/arcane/`
du dépôt principal, ignoré par Git ; ceux des stacks supplémentaires restent
dans le dossier externe. Une configuration résolue peut contenir des secrets
et des surcharges locales : ne pas la versionner. Les exports
`management_exports` sont actualisés lors de la résolution par les
configurateurs ou le lanceur Compose. Après modification des `.env` ou surcharges,
exécuter le lanceur avec `config --quiet` avant de lancer le projet depuis cette interface.
La commande `config` sans `--quiet` peut afficher des secrets résolus.

Sauvegarder séparément le dépôt, le dossier externe et les données applicatives.
Les bases natives des services partagés restent dans leurs dossiers `data/` ignorés
par Git et peuvent conserver leurs intégrations locales.

## Surcharge Traefik par fichier

Le dossier dynamique commun reste monté en lecture seule dans
`/etc/traefik/dynamic`. Une surcharge peut ajouter un fichier externe à cet endroit
sans remplacer le dossier. Le modèle `traefik/config/dynamic.example/extensions.yml`
fournit un emplacement neutre à copier avec les autres configurations actives.
Ce fichier doit exister dans le dossier commun avant le démarrage, car le montage
parent est en lecture seule. Il reste sans réglage propre au déploiement.
Après remplacement atomique d’un fichier source monté individuellement, recréer
le service pour renouveler son montage.

## Homepage : ajouts aux services communs

Le fichier commun `homepage/config/services.yaml` reste la source principale.
Une surcharge peut monter un dossier externe contenant uniquement des ajouts
sous `/app/config-extra`. Le script livré avec Homepage fusionne ces entrées dans
`runtime/homepage/services.yaml`, ignoré par Git, et surveille les deux dossiers.
Sans extension, il génère le tableau de bord commun seul. Voir le
[guide Homepage](../homepage/README.md).
