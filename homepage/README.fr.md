# Homepage

[English](README.md) | **Français**

Tableau de bord du homelab dans `/opt/media-stack/homepage`.
Les URL de l’hôte figurent dans [l’annuaire local](../README.local.md), ignoré par Git.
Le port par défaut est `3002`.

## Configuration commune

Copier `config.example/*.yaml` dans `config/`, puis adapter les URL et les noms DNS.
Les fichiers sources restent dans le répertoire commun :

- `.env` : UID/GID, image, port et `HOMEPAGE_ALLOWED_HOSTS`.
- `config/services.yaml` : services communs et états Docker.
- `config/settings.yaml` : langue, thème et disposition.
- `config/docker.yaml` : connexion au proxy Docker de Dozzle.
- `config/widgets.yaml` et `config/bookmarks.yaml` : widgets et favoris.

`config/` reste ignoré par Git et est monté en lecture seule. Le lanceur prépare
`../runtime/homepage/` avec le propriétaire du conteneur pour les fichiers générés
et journaux. Le renderer utilise Node et le parseur YAML déjà fourni par l’image.

## Ajouts facultatifs

Une surcharge peut monter un dossier externe en lecture seule sous
`/app/config-extra`. Son `services.yaml` contient uniquement les entrées
supplémentaires, regroupées sous les noms des sections communes ou de nouvelles
sections. Sans ce dossier, Homepage utilise uniquement les services communs.

Au démarrage, le script fusionne les deux listes dans
`runtime/homepage/services.yaml`. Il surveille ensuite les dossiers sources :
les changements se propagent automatiquement. Un nom de service en double dans
une même section est refusé ; une modification invalide conserve le dernier
résultat valide. Ne pas modifier directement le YAML généré.
Les autres configurations communes sont accessibles par des liens dans le runtime.

## Gestion

Dozzle doit d’abord créer son réseau et le proxy Docker. Depuis la racine :

```sh
python3 stacks/scripts/stack-compose.py dozzle up -d
python3 stacks/scripts/stack-compose.py homepage config --quiet
python3 stacks/scripts/stack-compose.py homepage up -d
python3 stacks/scripts/stack-compose.py homepage logs --tail=60
```

Une modification du `.env` ou des montages nécessite une recréation.
Sauvegarder `.env`, `config/` et les ajouts externes ; le runtime est régénérable.
Les noms d’hôte autorisés doivent figurer dans `HOMEPAGE_ALLOWED_HOSTS`.
L’interface est destinée au LAN et ne configure pas d’authentification.
