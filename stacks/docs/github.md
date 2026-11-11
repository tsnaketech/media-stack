# Préparer le dépôt Git

La racine Git est `/opt/media-stack`. Les stacks média sont dans `stacks/`
et l’infrastructure dans `arcane/`, `traefik/`, `homepage/` et `dozzle/`.
Le workflow GitHub Actions est placé dans `.github/workflows/validate.yml`.

## Fichiers suivis

Le dépôt contient les Compose, scripts, tests, guides et exemples de configuration.
Les exclusions couvrent les `.env`, identifiants, données applicatives, journaux,
bases SQLite, sauvegardes, rapports et configurations actives propres à l’hôte.

Les variantes publiables de Homepage et des routes Traefik sont dans
`config.example/` et `config/dynamic.example/`. Leurs valeurs `SERVER_IP` et
`changeThisPathBeforeUse` sont à adapter dans les copies locales. Le modèle
`README.local.md.example` accompagne l’annuaire privé `README.local.md`.

## Contrôle avant un commit

Depuis la racine du projet, inspecter les fichiers proposés et les changements.

```sh
git status --short --untracked-files=all
git diff
git ls-files --others --exclude-standard
git check-ignore README.local.md stacks/shared/.env stacks/download/.qbittorrent-credentials.json backups/ reports/
```

Pour ajouter les sources puis vérifier la sélection du prochain commit.

```sh
git add .
git diff --cached --stat
git diff --cached
```

Vérifier les nouveaux fichiers avant le premier commit. Les règles d’exclusion
s’appliquent aux fichiers qui ne sont pas encore suivis. Un fichier sensible
déjà enregistré nécessite un traitement de l’index et éventuellement de l’historique.

## Validation

```sh
./stacks/scripts/stacks.sh validate --with-infra
cd stacks
STACK_EXTENSIONS_DIR= python3 -m unittest discover -s tests -v
python3 scripts/test-initialization.py
```

La CI utilise les modèles et teste le cœur applicatif avec des données neuves,
dans un projet Docker isolé. Les prérequis des déploiements sont décrits dans
le [guide d’initialisation](initialization.md).
