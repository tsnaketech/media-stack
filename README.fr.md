# Media Stack

[English](README.md) | **Français**

Configuration Docker Compose d’un homelab média, avec ses outils de recherche,
de téléchargement, de lecture et d’administration. Les exemples utilisent
`/opt/media-stack` comme racine du dépôt ; adapter ce chemin au déploiement.

## Organisation

```text
media-stack/
├── stacks/      # Neuf stacks média, scripts et tests
├── homepage/      # Tableau de bord
├── dozzle/        # Journaux Docker et proxy de lecture
├── traefik/       # Reverse proxy
├── arcane/        # Administration des conteneurs
├── docs/          # Organisation et migration du projet
├── .github/       # Validation continue
└── README.md
```

Les réglages de chaque stack figurent dans son `.env.example`. Copier ces modèles
dans les fichiers `.env` locaux et adapter les chemins, comptes et secrets.

## Installation et gestion

Depuis la racine du projet, préparer les stacks média.

```sh
python3 stacks/scripts/initialize.py prepare
python3 stacks/scripts/initialize.py check
python3 stacks/scripts/initialize.py up
```

Préparer également les fichiers privés et réseaux de l’infrastructure avant de
l’inclure dans les commandes. Le guide décrit les modèles Traefik et Homepage.

```sh
./stacks/scripts/stacks.sh validate --with-infra
./stacks/scripts/stacks.sh status --with-infra
python3 stacks/scripts/check-services.py --with-infra --proxy-domain arr.local
```

Les bibliothèques utilisent `/media` et les téléchargements `/downloads`. Les
montages Proxmox, ACL et valeurs `.env` doivent correspondre à l’environnement.

## Accès locaux

Le modèle `README.local.md.example` permet de créer `README.local.md` avec les URL
de son hôte. Cet annuaire peut aussi être conservé hors du dépôt, dans le dossier d’exploitation local.
Les données applicatives, fichiers `.env`, routes actives, rapports et sauvegardes
restent exclus de Git.

## Documentation

- [Démarrage automatique et raccordement VPN](stacks/docs/boot.md)
- [Doublons vidéo et rapports CSV/HTML](stacks/docs/video-duplicates.md)

- [Installation, droits et configuration des services](stacks/README.fr.md)
- [Organisation et migration vers cette racine](docs/project-layout.md)
- [Préparation Git et fichiers privés](stacks/docs/github.md)
- [Initialisation dans un autre environnement](stacks/docs/initialization.md)
- [Extensions de déploiement externes](docs/extensions.md)
- [Contribuer](CONTRIBUTING.md)
- [Homepage](homepage/README.fr.md)
- [Dozzle](dozzle/README.fr.md)
