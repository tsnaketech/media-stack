# VPN : Gluetun

[English](README.md) | **Français**

Cette stack dédiée utilise le projet [passteque/gluetun](https://github.com/passteque/gluetun)
et son image `qmcgaw/gluetun:latest`. Le changement de dépôt GitHub conserve les
noms officiels des images Docker. Elle utilise le réseau externe `media-shared`, le volume
`data:/gluetun`, la capacité `NET_ADMIN` et le périphérique `/dev/net/tun`.
L’image fournit son propre contrôle de santé. Gluetun publie les ports 8080 de
qBittorrent, 8081 de MeTube et 5800 de JDownloader ; son serveur de contrôle reste sur la boucle locale du conteneur.

## État de cette installation

Gluetun est démarré avec **Proton VPN Plus / WireGuard**. Le filtre de pays est
`SERVER_COUNTRIES=Belgium` et les serveurs compatibles P2P sont sélectionnés.
Le contrôle de santé et les journaux ont confirmé une sortie en Belgique.
Le périphérique TUN est accessible depuis Docker. Les secrets restent dans le
`.env` privé ; la sélection du pays utilise les noms anglais attendus par Gluetun.

La stack est nécessaire à qBittorrent, MeTube et JDownloader. `scripts/stacks.sh` inclut désormais le VPN
par défaut ; `--with-vpn` reste accepté pour compatibilité.

## Fichiers et variables

- `docker-compose.yml` : service et réseau Docker ;
- `.env.example` : modèle versionnable avec commentaires en anglais ;
- `.env` : fournisseur, protocole et secrets locaux, protégé en mode `600` ;
- `data/` : état Gluetun et éventuels fichiers de configuration VPN, hors Git.

Depuis la racine du dépôt :

```sh
test -f vpn/.env || cp vpn/.env.example vpn/.env
chmod 600 vpn/.env
./scripts/stacks.sh validate --with-vpn
```

Le modèle utilise `VPN_SERVICE_PROVIDER=protonvpn` et `VPN_TYPE=wireguard`.
Voir le [guide Proton VPN](protonvpn.md) pour obtenir la clé et activer le tunnel.
Les paramètres `custom` et OpenVPN ci-dessous restent disponibles pour une autre
configuration explicite.

### WireGuard

Renseigner `WIREGUARD_PRIVATE_KEY` et `WIREGUARD_ADDRESSES` selon le fournisseur.
Pour un endpoint personnalisé, fournir également `WIREGUARD_PUBLIC_KEY`,
`WIREGUARD_ENDPOINT_IP` et `WIREGUARD_ENDPOINT_PORT`. La clé prépartagée est
optionnelle. Utiliser les paramètres délivrés par le fournisseur, sans générer
une clé de remplacement arbitraire.

Une configuration peut aussi être placée dans `data/wireguard/wg0.conf` : ses
champs prennent priorité sur les variables correspondantes. Ce fichier contient
des secrets et doit rester dans le stockage ignoré par Git.

### OpenVPN

Choisir `VPN_TYPE=openvpn`, puis renseigner `OPENVPN_USER` et
`OPENVPN_PASSWORD` si le fournisseur les exige. Pour le fournisseur `custom`,
placer son fichier dans `data/custom.ovpn` et définir :

```dotenv
VPN_SERVICE_PROVIDER=custom
VPN_TYPE=openvpn
OPENVPN_CUSTOM_CONFIG=/gluetun/custom.ovpn
```

Les fichiers de certificats référencés doivent également être accessibles sous
`/gluetun`. Pour un fournisseur intégré, laisser `OPENVPN_CUSTOM_CONFIG` vide.

## Prérequis du LXC

La [procédure complète Proxmox/TUN](../docs/proxmox-tun.md) détaille le chargement
du module, la sauvegarde de `104.conf`, les deux lignes de configuration, le
redémarrage et les contrôles de présence du périphérique.

Sur Proxmox, préparer le passage de `/dev/net/tun` vers le LXC hébergeant Docker,
puis redémarrer le LXC lorsque l’interruption de ses services est acceptable.
Le périphérique doit être accessible avant de créer le conteneur Docker :

```sh
test -c /dev/net/tun && ls -l /dev/net/tun
```

Le Compose transmet uniquement ce périphérique avec `NET_ADMIN` ; aucun mode
Docker `privileged` n’est demandé. La configuration Proxmox et le redémarrage
sont des opérations à effectuer sur l’hôte.

## Activation et vérification

Une fois le fournisseur, les secrets et TUN configurés :

```sh
./scripts/vpn-up.sh
python3 scripts/stack-compose.py vpn ps
python3 scripts/stack-compose.py vpn logs --since=5m --tail=80
```

Le contrôle de santé doit être positif. Vérifier également l’adresse de sortie
et la résolution DNS depuis le conteneur avant de lui confier des applications.
Pour démarrer toutes les stacks avec cette option :

```sh
./scripts/stacks.sh up --with-vpn
./scripts/stacks.sh status --with-vpn
```

## Contrôler le VPN depuis qBittorrent

Exécuter ces commandes dans le LXC hébergeant Docker. Elles vérifient le réseau
de qBittorrent ; un test lancé directement sur le LXC ne vérifie pas son tunnel.
MeTube et JDownloader partagent aussi ce tunnel. SABnzbd et les autres services ne sont pas
automatiquement protégés par Gluetun.

### Santé et raccordement

```sh
docker inspect gluetun --format '{{.State.Health.Status}}'
docker exec gluetun readlink /proc/self/ns/net
docker exec qbittorrent readlink /proc/self/ns/net
```

Gluetun doit être `healthy`. Les deux identifiants `net:[...]` doivent être
identiques : les conteneurs partagent alors le même espace réseau. La santé seule
ne prouve pas que qBittorrent utilise ce réseau. En cas de différence, relancer
`./scripts/vpn-up.sh` depuis la racine `stacks`, puis refaire les contrôles.

### Adresse publique et route

```sh
docker exec qbittorrent curl -fsS --max-time 15 https://ipinfo.io/json
docker exec qbittorrent ip route get 1.1.1.1
```

L’adresse publique doit correspondre à la sortie VPN. Avec le filtre actuel
`SERVER_COUNTRIES=Belgium`, le pays attendu est `"country": "BE"`. L’adresse peut
changer lors des reconnexions ; ne pas la figer. La géolocalisation est indicative,
et une panne du service IPinfo ne suffit pas à conclure à une panne du VPN.
La route doit contenir `dev tun0`.

Dans **qBittorrent → Options → Avancé → Interface réseau**, vérifier également
la valeur `tun0`. Le script de configuration applique cette liaison pour les
connexions torrent.

### Blocage de la sortie Internet directe

Après avoir confirmé que la requête via le VPN fonctionne :

```sh
docker exec qbittorrent curl -fsS \
  --interface eth0 --connect-timeout 3 --max-time 5 \
  https://1.1.1.1/cdn-cgi/trace
```

Cette requête force l’interface Docker `eth0`, hors tunnel. Elle doit échouer,
généralement par expiration du délai (`curl: (28)`). Une réponse réussie nécessite
de vérifier le pare-feu avant de reprendre les téléchargements. Une autre erreur
peut avoir une cause différente : elle ne démontre pas à elle seule le blocage.

Ce contrôle ne coupe pas le VPN et ne simule pas sa déconnexion ; il vérifie le
blocage du chemin direct au moment du test. Les exceptions LAN déclarées dans
`FIREWALL_OUTBOUND_SUBNETS` restent autorisées.

### DNS et diagnostic

```sh
docker exec qbittorrent cat /etc/resolv.conf
python3 scripts/stack-compose.py vpn logs --since=5m --tail=80
docker exec gluetun iptables -S OUTPUT
```

Le résolveur attendu dans cette installation est `nameserver 127.0.0.1`, celui de
Gluetun. Cela vérifie la configuration DNS, sans constituer un test externe de
fuite DNS. La politique de sortie du pare-feu doit afficher `-P OUTPUT DROP`,
avec des autorisations pour le tunnel, son serveur et les réseaux locaux prévus.
Les journaux peuvent contenir des adresses réseau : les relire avant de les partager.

## Raccordement des applications

La protection VPN s’applique aux applications qui partagent l’espace réseau de
Gluetun. Pour une application d’un autre Compose, le mécanisme est
`network_mode: "container:gluetun"`. Préparer alors les ports publiés sur Gluetun,
le démarrage après Gluetun et les adresses utilisées par les autres applications.
qBittorrent, MeTube et JDownloader sont raccordés au VPN ; les autres applications conservent leur réseau
habituel. L’alias Docker `qbittorrent` appartient à Gluetun : les connexions
existantes vers `http://qbittorrent:8080` restent utilisables.

Le pare-feu intégré de Gluetun fournit son mécanisme de coupure du trafic hors
tunnel. `FIREWALL_INPUT_PORTS=8080,8081,5800` autorise les trois interfaces Web. Renseigner uniquement le
CIDR du LAN dans `FIREWALL_OUTBOUND_SUBNETS` pour les réponses locales : cette
exception permet aussi les connexions vers ce LAN hors VPN. Les proxies HTTP et
Shadowsocks sont désactivés dans ce modèle.

Documentation : [Gluetun](https://github.com/passteque/gluetun),
[configuration par fournisseur](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers),
[raccordement d’un conteneur](https://github.com/qdm12/gluetun-wiki/blob/main/setup/connect-a-container-to-gluetun.md).

## Redémarrer sans perdre le raccordement

Depuis la racine `stacks`, utiliser :

```sh
./scripts/vpn-up.sh
# Or start the whole homelab, with VPN first:
./scripts/stacks.sh up
```

Le script crée le réseau externe s’il manque, attend un Gluetun sain, puis recrée
qBittorrent, MeTube et JDownloader si leurs espaces réseau diffèrent. Relancer ce script après toute
recréation de Gluetun : un simple `restart qbittorrent` ne suffit pas à rejoindre
un nouveau conteneur VPN. Ne pas arrêter Gluetun pendant un téléchargement.

`configure-qbittorrent-vpn.py` utilise les identifiants privés existants pour lier
les torrents à `tun0` et désactiver UPnP et le port aléatoire. Le pare-feu Gluetun
et cette liaison bloquent le trafic torrent lorsque le tunnel disparaît.
Les ports de pairs 6881 ne sont plus publiés sur l’hôte. La redirection de port
Proton reste désactivée ; les connexions sortantes fonctionnent sans elle.

`QBITTORRENT_WEB_BIND_IP` et `QBITTORRENT_WEB_PORT` dans `vpn/.env` pilotent
la publication Web. Les scripts résolvent le port publié depuis le modèle
Compose effectif ; le port interne reste 8080.
Le réseau externe survit à `compose down` ; ne pas le supprimer tant que
les autres stacks l’utilisent. Les sauvegardes d’exploitation restent hors de Git.

### Première installation sans identifiants qBittorrent

Après configuration de TUN et de `vpn/.env`, démarrer une première fois :

```sh
docker network inspect media-shared >/dev/null 2>&1 || docker network create media-shared
python3 scripts/stack-compose.py vpn up -d --wait --wait-timeout 120
python3 scripts/stack-compose.py download up -d --no-deps qbittorrent
```

Choisir le mot de passe permanent depuis l’interface Web, puis enregistrer les
identifiants avec `python3 scripts/configure-download-clients.py --init-credentials`.
Terminer par `./scripts/vpn-up.sh` pour appliquer et vérifier la liaison `tun0`.

## MeTube via Gluetun

MeTube partage le même tunnel que qBittorrent. `METUBE_WEB_BIND_IP` et
`METUBE_PORT` dans `vpn/.env` pilotent la publication de son port interne 8081.
Le pare-feu autorise l’entrée Web sur 8081. Son alias réseau est `metube`.
Le script `scripts/vpn-up.sh` reconnecte les trois clients après recréation du VPN.
Voir [la procédure de vérification MeTube](../download/docs/metube.md#raccordement-vpn).
