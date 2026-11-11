# Première installation sans données applicatives

Ce guide est le point d’entrée pour porter le dépôt dans un autre environnement.
Il complète les procédures de [montage et droits](permissions.md),
[stockage des téléchargements](downloads-storage.md) et [TUN Proxmox](proxmox-tun.md).
Un démarrage de conteneurs ne signifie pas que les abonnements, catalogues et
bibliothèques sont utilisables : les étapes externes ci-dessous restent nécessaires.

## Prérequis

- Linux avec Docker Engine accessible, Docker Compose **2.30+**, Bash et Python
  **3.10+**. Docker doit pouvoir télécharger les images publiées.
- Accès au dépôt en écriture et possibilité de préparer les dossiers avec les
  UID/GID choisis. Exécuter l’initialisation comme root, ou avec l’utilisateur
  correspondant aux UID/GID des applications. Le script ne change pas récursivement
  les propriétaires des bibliothèques existantes.
- Stockage média et téléchargements présents avant Docker. Les chemins par défaut
  sont `/media` et `/downloads` : le contrôle exige qu’ils soient de vrais montages.
  Un stockage local est possible avec des chemins explicites différents, par
  exemple `/srv/media` et `/srv/downloads`.
- `/dev/net/tun` transmis à Docker et capacité `NET_ADMIN` disponible pour Gluetun.
  qBittorrent et MeTube utilisent son réseau ; ils nécessitent un tunnel sain.
- Compte VPN et configuration délivrée par le fournisseur. Pour Proton/WireGuard,
  la clé privée est un secret externe, jamais généré par l’initialisation.
- Ports disponibles et noms de conteneurs libres, ou appartenant à ce même dépôt.
  Les noms Docker sont fixes : deux installations de production ne peuvent pas
  partager le même moteur sans adapter leurs noms, ports et réseaux.

Traefik et Arcane sont optionnels et extérieurs au dépôt `stacks`.
L’option `--with-infra` suppose leurs Compose, secrets et réseaux externes déjà
préparés dans `INFRA_ROOT` (parent du dépôt par défaut). Sans eux,
les interfaces restent accessibles par les ports directs. Le script n’installe
pas Docker, ne modifie pas Proxmox et ne crée pas de comptes externes.

## 1. Préparer le stockage

Sur le LXC Proxmox, préparer `mp0` pour la bibliothèque et `mp1` pour les
téléchargements selon les guides liés plus haut. Vérifier les ACL pour l’UID des
applications et la traversée pour Docker. Le mapping habituel du LXC non privilégié
associe UID 1000 à UID 101000 sur Proxmox ; il peut différer ailleurs.

Pour une nouvelle installation utilisant des dossiers locaux, créer les bases
et sous-dossiers avec les propriétaires choisis. Exemple **sur des dossiers neufs** :

```sh
mkdir -p /srv/media/{movies,tv,music,books,audiobooks} /srv/downloads
chown 1000:1000 /srv/media/{movies,tv,music,books,audiobooks} /srv/downloads
```

Pour un partage existant, conserver ses propriétaires et utiliser les ACL plutôt
que cette commande. Ne pas appliquer de `chown -R` générique au stockage partagé.

## 2. Préparer les fichiers et comptes

Depuis la racine `stacks` :

```sh
python3 scripts/initialize.py prepare
# Alternative with explicit storage locations:
python3 scripts/initialize.py prepare \
  --library-root /srv/media --downloads-root /srv/downloads
```

`prepare` copie uniquement les `.env.example` dont le `.env` manque. Il génère
des mots de passe pour les services ne possédant encore aucune donnée, crée les
dossiers locaux de données et les sous-dossiers de téléchargements lorsque leur
base est accessible. Les `.env` sont protégés en mode `600` ; aucun secret n’est
affiché. Il ne lance aucun conteneur.

L’option de stockage met à jour les chemins hôtes des stacks concernées. Vérifier
leurs valeurs avant de poursuivre. Un `.env` existant n’est pas remplacé ; une
valeur secrète vide peut être remplie seulement si le service n’a pas encore de
données. Les mots de passe existants ne sont pas tournés automatiquement.

Pour qBittorrent sans configuration, le script prépare un mot de passe PBKDF2
compatible et `download/.qbittorrent-credentials.json` avant le premier démarrage. L’authentification localhost est exigée dès cette
configuration. Le démarrage vérifie le compte via l’API native ; un marqueur
limite cette vérification initiale aux configurations nouvellement créées.
Les variables `QBITTORRENT_INIT_USERNAME` et `QBITTORRENT_INIT_PASSWORD` ne servent
qu’à cette création. Une configuration existante n’est jamais réécrite. Si son
fichier d’identifiants manque, renseigner les identifiants actuels avec :

```sh
python3 scripts/configure-download-clients.py --init-credentials
```

Cette dernière commande ne change pas le compte de qBittorrent. Conserver le
fichier JSON et les `.env` dans une sauvegarde privée ; ne pas les committer.

## 3. Réglages propres au nouvel environnement

| Élément | Fichier ou emplacement | Action |
|---|---|---|
| UID/GID et fuseau | `.env` de chaque stack | Adapter `PUID`, `PGID`, `TZ` de façon cohérente |
| Bibliothèques | `.env` média, shared et download | Vérifier `LIBRARY_DIR`, `MUSIC_DIR`, `JELLYFIN_*_DIR`, `BAZARR_*_DIR`, `METUBE_VIDEO_DIR` |
| Téléchargements | `.env` de download et des applications arr/book | Même `SHARED_DOWNLOADS_DIR` partout |
| VPN | `vpn/.env` | Fournisseur, protocole, clé WireGuard ou identifiants OpenVPN, pays |
| Accès Web VPN | `vpn/.env` | Ports/adresses de qBittorrent et MeTube, entrées 8080/8081 du pare-feu |
| Exceptions réseau | `vpn/.env` | Uniquement les sous-réseaux LAN nécessaires dans `FIREWALL_OUTBOUND_SUBNETS` |
| DNS des conteneurs | `.env` des stacks concernées | `DNS_PRIMARY`, `DNS_SECONDARY` ; les clients VPN utilisent le DNS Gluetun |
| Noms HTTP autorisés | `.env` des applications arr/indexer | Adapter `ARR_ALLOWED_HOSTS` et les éventuels proxies de confiance |
| URL publiques | `shared/.env` | Adapter URL Jellyfin, Seerr, origine Profilarr et autres noms de domaine |
| Connect Jellyfin | `shared/.env` | Adapter les correspondances si les chemins dans les conteneurs changent |
| Indexeurs | Interface Prowlarr | Ajouter les sources, comptes, catégories et éventuel tag FlareSolverr |
| Usenet | `download/.env` et Prowlarr | Fournisseur SABnzbd et indexeur NZB ; facultatifs pour les torrents |
| Sous-titres | Interface Bazarr | Choisir les fournisseurs et renseigner leurs accès |
| Profilarr | `shared/.env`, puis interface | Accès au dépôt de profils, base activée et synchronisée, profils sélectionnés |
| Calibre-Web | Interface | Fournir une véritable base Calibre `metadata.db`, puis changer le compte initial |
| Audiobookshelf/Navidrome | Interfaces | Créer les premiers comptes et choisir les bibliothèques |
| Routage HTTPS | DNS/Traefik hors dépôt | Créer les enregistrements DNS, adapter les routes et configurer TLS si utilisé |

Les indexeurs, cookies MeTube, comptes et réglages ajoutés uniquement dans une
interface ne réapparaissent pas sans leur `data/` ou sauvegarde. Les variables
`.env.example` documentent les réglages pris en charge par les scripts ; toutes
les options de toutes les applications ne sont pas gérées automatiquement.

## 4. Contrôler puis démarrer

```sh
python3 scripts/initialize.py check
python3 scripts/initialize.py up
# Equivalent entry point:
./scripts/stacks.sh up
# Optional infrastructure outside this repository:
python3 scripts/initialize.py up --with-infra
```

`check` ne crée pas de données. Il valide les Compose, l’existence des sources de
montage, l’accès des applications au stockage, la cohérence des téléchargements,
les collisions de noms/ports et les prérequis VPN. Il ne prouve ni la validité d’un
abonnement, ni le fonctionnement du tunnel : ces contrôles se font au démarrage.

`up` prépare les fichiers, effectue les contrôles, attend Gluetun sain, démarre
les stacks et attend les API arr. Il applique ensuite les scripts de configuration :
catégories et clients qBittorrent, qui, applications Prowlarr, FlareSolverr,
Jellyfin/Connect, Bazarr, Profilarr et Seerr. Les fonctions déjà configurées sont
conservées selon les règles documentées de chaque script.

Les étapes de configuration indépendantes sont toutes tentées. Si une étape
échoue, la commande retourne un code non nul et liste les scripts concernés ;
elle n’annule pas les étapes réussies et n’annonce pas une installation complète.
Corriger le diagnostic puis relancer. Aucun téléchargement de contenu n’est lancé.

Profilarr lie/synchronise la base déclarée si elle manque et si la gestion des
profils français est activée. Une base déjà désactivée reste désactivée. Un cache
indisponible, un dépôt inaccessible ou un schéma non pris en charge bloque cette
étape avec un diagnostic. Vérifier la base dans Profilarr ; ne pas désactiver la
validation de langue pour masquer l’erreur. Seerr doit référencer des profils
réellement présents dans Radarr/Sonarr.

Les tâches manuelles du tableau restent à terminer, en particulier les comptes
initiaux : Calibre-Web utilise initialement `admin` / `admin123`, à changer dès
la première connexion. Navidrome et Audiobookshelf doivent recevoir leur premier
administrateur avant ouverture à d’autres utilisateurs. Vérifier les accès aux bibliothèques pour chaque nouveau compte Jellyfin.

## 5. Tester sans toucher à la production

```sh
# Data-free fixture, generated accounts and idempotent preparation; no service started:
python3 scripts/test-initialization.py
# Native core integration in a separate Docker project:
sudo python3 scripts/test-initialization.py --docker
# Allow downloading missing application images:
sudo python3 scripts/test-initialization.py --docker --pull
# Setup-script unit tests:
STACK_EXTENSIONS_DIR= python3 -m unittest discover -s tests -v
```

Le test copie uniquement les sources et modèles dans un dossier temporaire,
jamais les `.env`, clés VPN, fichiers d’identifiants ou données de production.
Il prépare deux fois la copie et vérifie que les comptes ne changent pas.

Avec `--docker`, quatre applications réelles démarrent avec des données vides :
qBittorrent, Prowlarr, Radarr et Jellyfin. Le projet, les noms de conteneurs, le
réseau et les dossiers sont uniques ; les ports sont alloués dynamiquement et
liés uniquement à `127.0.0.1`. Le réseau de test est un bridge distinct, sans clé
VPN ; il peut accéder à Internet pour les besoins natifs des applications.

Le test vérifie l’authentification qBittorrent, les catégories, les hooks natifs
Radarr, son client de téléchargement, le Full Sync Prowlarr, l’assistant initial
Jellyfin, ses bibliothèques et la connexion Connect. Une seconde application des
réglages ne doit pas créer de doublons. Aucun torrent, indexeur ou téléchargement
n’est ajouté. Le projet et ses volumes temporaires sont supprimés à la fin. Si Docker empêche
le nettoyage, le script signale le projet et conserve son dossier temporaire en
mode privé pour inspection et nettoyage manuel, sans viser les autres stacks.

**Limites du test** : il ne démarre pas toutes les images du homelab et ne valide
pas un abonnement VPN, les recherches sur un indexeur, un téléchargement YouTube,
le fournisseur Usenet, les politiques Profilarr distantes ou les assistants
manuels. Il ne garantit donc pas que toutes les combinaisons d’images `latest`
et de stockage fonctionneront du premier coup. Le test complet du VPN reste
celui du [guide Gluetun](../vpn/README.md), dans l’environnement cible.

## Vérification finale et sauvegarde

```sh
./scripts/stacks.sh status
python3 scripts/check-services.py
# If local DNS and reverse proxy have been configured:
python3 scripts/check-services.py --proxy-domain YOUR_LOCAL_DOMAIN
```

Tester aussi un import autorisé et sa visibilité dans Jellyfin, les permissions
des nouveaux fichiers, les alertes des applications et un redémarrage du LXC.
Sauvegarder ensuite `.env`, identifiants et données applicatives de façon cohérente,
puis tester une restauration. Les [guides spécifiques](../README.md) complètent
ce parcours sans devoir copier les anciennes données pour créer les comptes neufs.
