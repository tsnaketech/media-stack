# MeTube

MeTube est l’interface Web de yt-dlp installée dans la stack `download` avec
l’image officielle `ghcr.io/alexta69/metube:latest`. Il rejoint `media-shared` et
partage le réseau de Gluetun, qui publie son port `8081`. Les URL propres à cet hôte figurent dans `/opt/media-stack/README.local.md`.

## Utilisation

Ouvrir `http://IP_DU_SERVEUR:8081` ou `http://metube.arr.local` après configuration
du DNS local. Coller l’URL d’une vidéo ou d’une playlist, choisir la qualité et
le format vidéo/audio, puis ajouter le téléchargement à la file.

Les fichiers sont conservés sur le serveur. Le lien d’un téléchargement terminé
permet de le récupérer dans le navigateur. Aucun contenu n’a été téléchargé pour
l’installation ; les vérifications portent sur l’interface et les droits d’écriture.

## Stockage

| Données | Chemin dans le conteneur | Chemin hôte par défaut |
|---|---|---|
| Vidéos | `/videos` | `/downloads/youtube/videos` |
| Audio | `/downloads/audio` | `/downloads/youtube/audio` |
| Fichiers temporaires | `/downloads/.tmp` | `/downloads/youtube/.tmp` |
| Historique, file et cookies | `/config` | `download/data/metube` |

Le chemin hôte est construit depuis `SHARED_DOWNLOADS_DIR`, commun aux clients.
Son sous-dossier `youtube` est monté pour l’audio et les fichiers temporaires.
`METUBE_VIDEO_DIR=/downloads/youtube/videos` fournit la destination des vidéos, montée sous
`/videos` en écriture. L’historique et les cookies
restent exclus de Git. Ils sont à sauvegarder comme les autres données privées.

Pour une première installation, créer les dossiers avec les UID/GID choisis
(1000:1000 par défaut), après vérification du montage Proxmox :

```sh
mountpoint /downloads
setpriv --reuid=1000 --regid=1000 --clear-groups \
  mkdir -p /downloads/youtube/audio /downloads/youtube/.tmp
mkdir -p download/data/metube
chown 1000:1000 download/data/metube
```

Le conteneur fonctionne directement avec cet utilisateur et `CHOWN_DIRS=false` :
les droits du partage sont gérés par les ACL, sans tentative de changement global
des propriétaires. Voir le [guide du stockage](../../docs/downloads-storage.md).

## Variables et gestion

Les variables `METUBE_*` sont regroupées dans `download/.env.example` et le `.env`
privé : thème, niveau des journaux, umask, téléchargements simultanés,
suppression des fichiers et options yt-dlp au format JSON. Par défaut, deux
travaux peuvent s’exécuter simultanément et retirer une entrée de l’historique
ne supprime pas son fichier. Les modifications libres d’options yt-dlp depuis
l’interface sont désactivées.

Depuis la racine `stacks` :

```sh
python3 scripts/stack-compose.py download config --quiet
./scripts/vpn-up.sh
python3 scripts/stack-compose.py download ps metube
python3 scripts/stack-compose.py download logs --since=5m --tail=60 metube
```

Après modification du `.env`, relancer `up -d --no-deps metube`. L’image fournit
son contrôle de santé. MeTube ne possède pas de connexion arr à configurer et
partage le tunnel VPN avec qBittorrent. Les vidéos sont écrites dans le dossier configuré.
L’interface n’a pas d’authentification native configurée ; l’accès actuel est prévu
sur le réseau local. YouTube peut demander des cookies ou limiter les requêtes :
consulter le [guide officiel](https://github.com/alexta69/metube/wiki/Using-browser-cookies)
en cas d’erreur, sans publier ses cookies.

Source : [MeTube](https://github.com/alexta69/metube).

## Raccordement VPN

MeTube utilise `network_mode: "container:gluetun"`, sans réseau, DNS ni ports
propres. Gluetun fournit le DNS et le pare-feu ; son alias Docker `metube` permet
aux autres conteneurs de joindre le service. Le port hôte et son adresse sont
définis par `METUBE_PORT` et `METUBE_WEB_BIND_IP` dans `vpn/.env`, et non dans
`download/.env`. Le port interne reste 8081 ; `FIREWALL_INPUT_PORTS` inclut 8081.

Après toute recréation de Gluetun, exécuter `./scripts/vpn-up.sh` : il attend un
VPN sain, puis reconnecte MeTube et qBittorrent au nouvel espace réseau. L’interface
reste accessible localement même si le tunnel est indisponible ; cela ne garantit
pas qu’un téléchargement puisse sortir sur Internet.

Contrôles depuis le LXC :

```sh
docker exec gluetun readlink /proc/self/ns/net
docker exec metube readlink /proc/self/ns/net
docker exec metube curl -fsS --max-time 15 https://ipinfo.io/json
docker exec metube curl -fsS --interface eth0 --connect-timeout 3 --max-time 5 \
  https://1.1.1.1/cdn-cgi/trace
```

Les espaces réseau doivent être identiques, l’adresse publique doit être celle
du VPN et le test forcé par `eth0` doit échouer alors que le test normal réussit.
Ce dernier test vérifie le blocage de la sortie directe, sans couper le tunnel.
Voir le [guide VPN](../../vpn/README.md) pour les diagnostics complémentaires.

## Destination des vidéos

Les nouveaux téléchargements vidéo sont écrits directement dans `/videos`,
correspondant à `METUBE_VIDEO_DIR` sur l’hôte (par défaut `/downloads/youtube/videos`). Les
fichiers temporaires restent sur `/downloads/youtube/.tmp` avant déplacement
vers la bibliothèque. Les fichiers audio restent sur `/downloads/youtube/audio`.
Les fichiers déjà présents dans l’ancien dossier ne sont pas déplacés.

Pour changer la destination, modifier `METUBE_VIDEO_DIR` dans `download/.env`,
préparer les droits d’écriture UID 1000 sur ce dossier, puis recréer MeTube :

```sh
python3 scripts/stack-compose.py download up -d --no-deps metube
```
