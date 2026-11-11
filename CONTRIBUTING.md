# Contribuer

Les stacks média sont dans `stacks/`. Modifier la stack concernée sans déplacer ses données
persistantes. Utiliser deux espaces pour le YAML, quatre pour Python, et conserver
les scripts Shell exécutables avec des fins de ligne LF.

Chaque Compose doit déclarer `x-common-keys: &common-keys`, même pour une stack
à un seul service. Chaque service hérite de ces réglages avec `<<: *common-keys`.
Y regrouper les propriétés communes (redémarrage, DNS, journaux) ; conserver les
surcharges spécifiques dans le service sans modifier les valeurs effectives.

Pour un nouveau réglage, fournir une valeur documentée dans `.env.example`, une
référence explicite dans Compose et les explications utiles dans le README de la
stack. Les secrets réels restent uniquement dans `.env` ou les données locales.
Ne pas ajouter `data/`, bases SQLite, téléchargements, journaux ou identifiants.

Avant une proposition de changement :

```sh
cd stacks
./scripts/stacks.sh validate
bash -n scripts/stacks.sh
bash -n scripts/configure-arr-auth.sh
bash -n scripts/configure-arr-root.sh
bash -n scripts/configure-arr-media.sh
STACK_EXTENSIONS_DIR= python3 -m unittest discover -s tests -v
python3 -c 'import ast; from pathlib import Path; [ast.parse(p.read_text()) for p in Path("scripts").glob("*.py")]'
```

Les tests du hook média requièrent Bash, Python 3 et jq ; ils simulent les API
sans contacter les services en cours.

Pour une modification de volumes, réseau ou démarrage, vérifier également le
service concerné sur un hôte Docker et indiquer le résultat. Les tests HTTP
s'exécutent après démarrage avec `python3 scripts/check-services.py`.
La CI vérifie les fichiers Compose sans utiliser les `.env` ni les données locales.

Les commits doivent décrire une action précise, par exemple
`tv: documenter la catégorie de téléchargement`. Une pull request explique le
comportement changé, les validations réalisées et les étapes d'application si
une intervention sur les données ou les permissions est nécessaire.
