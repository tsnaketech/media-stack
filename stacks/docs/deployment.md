# Homelab média

Les URL ci-dessous utilisent `IP_DU_SERVEUR`, à remplacer par l’adresse de votre hôte.

Stacks Docker Compose pour un serveur média. Les exemples Proxmox utilisent
`/srv/media/library` → LXC `/media` ; adapter ce chemin au stockage disponible.
Les configurations et bases applicatives restent sur le disque local dans
`stacks/*/data/` et `arcane/data/`.

Arcane, Traefik, Dozzle et Homepage sont dans les répertoires correspondants
à la racine du dépôt. L’option `--with-infra` les inclut dans les commandes de gestion.
Pour les inclure dans une commande de gestion, ajouter `--with-infra`.

Pour une installation sans données applicatives existantes, commencer par le
[guide d’initialisation](initialization.md) et `scripts/initialize.py`. Il décrit
les étapes automatiques, les prérequis externes et la portée du test isolé.

## Accès

| Application | URL directe | Chemin de bibliothèque dans le conteneur |
|---|---|---|
| Lidarr | http://IP_DU_SERVEUR:8686 | `/music` |
| Navidrome | http://IP_DU_SERVEUR:4533 | `/music` |
| Prowlarr | http://IP_DU_SERVEUR:9696 | — |
| qBittorrent | http://IP_DU_SERVEUR:8080 | `/downloads` |
| Profilarr | http://IP_DU_SERVEUR:6868 | Aucun volume média requis |
| qui | http://IP_DU_SERVEUR:7476 | Interface du qBittorrent existant |
| JOAL | `http://IP_DU_SERVEUR:8088/<JOAL_UI_PATH>/ui/` | Configuration indépendante, torrents initialement vides |
| Jellyfin | http://IP_DU_SERVEUR:8096 | Films, séries et musique en lecture seule |
| Seerr | http://IP_DU_SERVEUR:5055 | Aucun volume média requis |
| Sonarr | http://IP_DU_SERVEUR:8989 | `/tv` |
| Bazarr | http://IP_DU_SERVEUR:6767 | Bibliothèques films/séries en écriture pour les sous-titres |
| Radarr | http://IP_DU_SERVEUR:7878 | `/movies` |
| Audiobookshelf | http://IP_DU_SERVEUR:13378 | `/audiobooks` |
| Shelfmark Lite | http://IP_DU_SERVEUR:8084 | destination `/books`, téléchargements `/downloads` |
| Calibre-Web | http://IP_DU_SERVEUR:8083 | `/books` |
| Arcane | http://IP_DU_SERVEUR:3552 | projets `/opt/media-stack/stacks` |
| Traefik | http://IP_DU_SERVEUR:8888/dashboard/ | — |

Les routes HTTP `<service>.arr.local` sont configurées dans Traefik ;
Calibre-Web utilise `books.arr.local`. Créer les entrées DNS correspondantes
vers `IP_DU_SERVEUR` dans le résolveur local ou le fichier hosts des clients.
Aucun certificat TLS n'est encore configuré. La route Excalidraw existante
pointe vers un autre hôte et n'est pas gérée par ces stacks.

## Exploitation

Depuis la racine du dépôt (`/opt/media-stack/stacks` dans les exemples), avec accès au moteur Docker :

```sh
./scripts/stacks.sh validate  # Valide les neuf stacks du dépôt
./scripts/stacks.sh up        # Démarre dans l'ordre des dépendances
./scripts/stacks.sh status    # Affiche l'état de chaque stack
./scripts/stacks.sh logs      # Journaux récents
python3 scripts/check-services.py --with-infra --proxy-domain arr.local  # Exemple de domaine local
```

Le réseau externe `media-shared`, créé par `scripts/vpn-up.sh`, relie Prowlarr,
qBittorrent, Lidarr et Radarr. Démarrer le VPN et les stacks indexer/download avant les applications, via
`scripts/stacks.sh up`.
Ne pas supprimer son réseau avec `down` tant qu'il est utilisé par une autre stack.
Les conteneurs redémarrent automatiquement avec Docker (`unless-stopped`).
Les fichiers `.env.example` documentent les réglages ; conserver les `.env`
existants. Après modification d'un Compose ou d'un environnement, relancer `up -d`.

## Première configuration

- Garder les comptes existants de Lidarr et Navidrome. Sur les nouvelles
  interfaces, configurer les comptes administrateurs et changer les mots de passe
  initiaux.
- qBittorrent : utilisateur initial `admin`, mot de passe temporaire dans
  `python3 scripts/stack-compose.py download logs qbittorrent`.
  Définir un mot de passe permanent avant de connecter les applications.
- Arcane : compte initial `arcane` / `arcane-admin`, changement demandé au premier
  accès. Ses secrets existants sont conservés dans `arcane/.env`.
- Calibre-Web : compte initial `admin` / `admin123`. Indiquer le dossier contenant
  une base Calibre `metadata.db`. Calibre-Web ne scanne pas automatiquement un
  simple dossier de fichiers EPUB/PDF ; une bibliothèque Calibre valide est requise.
- Audiobookshelf : créer l'administrateur puis une bibliothèque pointant vers
  `/audiobooks`. Le partage y est monté en lecture seule ; métadonnées et base
  restent dans `audiobook/data/`.
- Dans Lidarr, Radarr et Sonarr, sélectionner respectivement `/music`, `/movies`
  et `/tv` comme dossier racine. Importer les fichiers existants sans déclencher
  de recherche automatique si les indexeurs ne sont pas encore configurés.

Le [guide de la stack livres](../book/README.md) décrit Shelfmark Lite,
ses volumes et les connexions à Prowlarr et qBittorrent.

## Téléchargements et intégrations

Le même dossier hôte `/downloads` est exposé sous `/downloads` dans
qBittorrent et les applications arr. Créer une catégorie par application :
`music` → `/downloads/music`, `movies` → `/downloads/movies`,
`tv` → `/downloads/tv`. Les bibliothèques finales sont séparées.

Dans chaque application arr, ajouter qBittorrent avec hôte `qbittorrent`,
port `8080`, ses identifiants et la catégorie correspondante. Tester avant
l'enregistrement. Dans Prowlarr → Settings → Apps, ajouter les applications
avec leurs clés API et les URL internes `http://lidarr:8686`,
`http://radarr:7878`, `http://sonarr:8989`. URL interne de Prowlarr :
`http://prowlarr:9696`. Aucun indexeur n'est ajouté automatiquement.

## Permissions et sauvegardes

Le [guide des droits Proxmox / LXC / Docker](permissions.md) détaille les
commandes utilisées : mapping UID/GID, inspection et sauvegarde des ACL, droits
des bibliothèques, données locales, tests et diagnostic des erreurs.

Les applications utilisent par défaut UID/GID `1000:1000`. Dans ce LXC non
privilégié, UID 1000 correspond à UID 101000 sur Proxmox. Les ACL du partage
accordent l'accès à cet utilisateur ; elles doivent aussi couvrir les nouveaux
sous-dossiers. L'accès du moteur Docker à un montage et celui de l'application
aux fichiers sont deux vérifications distinctes.

Sauvegarder les dossiers `data/`, les Compose et les `.env` ; arrêter les
applications ou utiliser leurs fonctions de sauvegarde pour une copie cohérente
des bases SQLite. Ne pas committer les secrets, bases et téléchargements.
Le dashboard Traefik utilise le mode insecure existant ; aucun de ces ports
ne doit être publié sur Internet sans configuration d'accès adaptée.

Pour les séries, voir le [guide Sonarr](../tv/README.md).

Le [guide d’authentification](authentication.md) décrit les réglages Forms
et leur configuration déclarative dans les fichiers `.env` et Docker Compose.

Les identifiants arr peuvent aussi être fournis dans les `.env` avec
`ARR_AUTH_USERNAME` et `ARR_AUTH_PASSWORD`. Un mot de passe vide conserve le
compte existant ; un hook Compose applique les valeurs renseignées au démarrage.

## DNS des conteneurs

Les sept stacks média partagent les mêmes valeurs par défaut, modifiables dans
leur `.env` :

```dotenv
# DNS resolvers used by containers.
DNS_PRIMARY=1.1.1.1
DNS_SECONDARY=1.0.0.1
```

Compose transmet ces résolveurs avec la propriété `dns`. Sur les réseaux Docker
personnalisés, `/etc/resolv.conf` peut toujours afficher `127.0.0.11` : c'est le
résolveur embarqué de Docker, qui gère les noms des services puis transmet les
requêtes externes aux DNS configurés. Ne pas remplacer ce fichier à la main.

Après modification, recréer la stack avec `docker compose up -d`. Ces paramètres
concernent les conteneurs ; ils ne configurent pas le DNS des postes clients ni
les entrées locales `*.arr.local`. Si un conteneur doit résoudre ces noms privés,
utiliser un résolveur capable de les traiter plutôt qu'un DNS public.

## Stack VPN optionnelle

Gluetun est défini dans `vpn/`. Le modèle propose Proton VPN Plus/WireGuard ;
adapter `vpn/.env` au fournisseur, renseigner ses secrets avant le démarrage et
vérifier l’accès du LXC à `/dev/net/tun`. Contrôler ensuite la sortie VPN.

```sh
./stacks/scripts/stacks.sh validate --with-vpn
# Après configuration du fournisseur, des secrets et de TUN :
./scripts/stacks.sh up --with-vpn
```

L’option peut être combinée à `--with-infra`. Voir le [guide VPN](../vpn/README.md)
pour les protocoles et le raccordement futur des applications au tunnel.

La [procédure TUN pour Proxmox/LXC](proxmox-tun.md) détaille le prérequis du périphérique, sa vérification et le retour arrière.

## Démarrage du VPN et de qBittorrent

Utiliser `./scripts/stacks.sh up` pour démarrer le VPN avant les autres stacks.
Après toute recréation de Gluetun, `./scripts/vpn-up.sh` reconnecte qBittorrent
au nouvel espace réseau. Le port Web 8080 est publié par Gluetun ; les connexions
interapplications conservent `qbittorrent:8080`. Le DNS de qBittorrent vient de
Gluetun, et ne suit pas `DNS_PRIMARY`/`DNS_SECONDARY` de download.
