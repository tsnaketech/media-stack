# Racine du projet

Les exemples utilisent `/opt/media-stack` comme racine du projet ; le dépôt peut
être cloné dans un autre répertoire.
Le dépôt Git couvre `stacks/`, `homepage/`, `dozzle/`, `traefik/`, `arcane/`
et leur documentation. Les commandes des stacks média restent dans
`stacks/scripts/`. La CI se trouve dans `.github/workflows/` et exécute ces
commandes depuis `stacks/`.

## Fichiers propres à l’hôte

| Configuration active | Modèle versionné |
|---|---|
| `README.local.md` | `README.local.md.example` |
| `<stack>/.env` | `<stack>/.env.example` |
| `homepage/config/` | `homepage/config.example/` |
| `traefik/config/dynamic/` | `traefik/config/dynamic.example/` |

Pour préparer l’infrastructure sur un autre hôte, copier les modèles et adapter
`SERVER_IP`, les noms DNS, les ports et le chemin privé JOAL. Les fichiers d’exemple
Homepage utilisent des icônes distantes ; leurs copies locales éventuelles
restent dans la configuration propre au déploiement.

```sh
cp homepage/.env.example homepage/.env
cp dozzle/.env.example dozzle/.env
cp arcane/.env.example arcane/.env
mkdir -p homepage/config traefik/config/dynamic
cp homepage/config.example/*.yaml homepage/config/
cp traefik/config/dynamic.example/*.yml traefik/config/dynamic/
cp README.local.md.example README.local.md
chmod 600 homepage/.env dozzle/.env arcane/.env README.local.md
```

Adapter les secrets Arcane et préparer les dossiers de données locaux avec
l’UID/GID applicatif choisi. Pour les valeurs par défaut de Homepage et Dozzle,
créer `dozzle/data` puis donner `homepage/config` et `dozzle/data` à `1000:1000`.
Arcane crée `arcane-network` et Traefik crée `proxy-network`. Démarrer ensuite Dozzle pour créer
`infra-observability`, puis Homepage.

## Données et références

Les bibliothèques sont montées sous `/media` et les téléchargements sous
`/downloads`. Les données applicatives se trouvent dans les dossiers
`data/` de leurs stacks. `backups/` et `reports/` conservent les fichiers
d’exploitation privés.

Lors d’un déplacement, conserver les noms des projets Compose, conteneurs et
réseaux, puis recréer les conteneurs pour actualiser leurs montages. Les chemins
des projets Arcane et son paramètre `projectsDirectory` doivent
correspondre au répertoire utilisé pour les Compose, ou aux exports complets
d’un déploiement externe. Arcane monte la racine au même emplacement dans son
conteneur pour que les chemins transmis au moteur Docker correspondent à l’hôte.

Les scripts exécutés à l’intérieur des conteneurs peuvent toujours utiliser
`/opt/configure-*.sh`. Ces chemins désignent leurs montages internes.

## Configurations de déploiement externes

Le mécanisme `STACK_EXTENSIONS_DIR` permet de conserver les adaptations locales
hors du dépôt. Les stacks supplémentaires, surcharges, rapports et sauvegardes
peuvent résider dans ce répertoire ; les fichiers natifs des services communs
restent dans leurs dossiers `data/` ignorés par Git.
Voir le [guide des extensions](extensions.md) pour les commandes de gestion.

Les exports Arcane des stacks communes restent dans `runtime/arcane/` à la racine
du projet. Ce dossier généré est ignoré par Git, car les Compose résolus peuvent
contenir des secrets et des surcharges locales. Les exports des stacks externes
restent dans le répertoire externe ; Arcane peut conserver leurs projets séparés.
