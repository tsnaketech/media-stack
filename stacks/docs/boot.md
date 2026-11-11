# Démarrage automatique et raccordement VPN

Docker doit être activé au démarrage (`systemctl is-enabled docker`). Les
conteneurs utilisent `restart: unless-stopped`. Le contrôle supplémentaire
ci-dessous rétablit le raccordement VPN après le démarrage ou le redémarrage
du service Docker.

## Installation

Après avoir initialisé et configuré les applications, depuis la racine du dépôt :

```sh
sudo python3 stacks/scripts/install-vpn-boot.py
```

L’installateur vérifie puis installe
`/etc/systemd/system/media-stack-vpn.service`, l’active et l’exécute immédiatement.
Il ne redémarre ni Docker ni la machine. Il peut être relancé après une mise à
jour ou un déplacement du dépôt pour actualiser les chemins absolus.
Python 3, Bash, `flock`, systemd et Docker Compose sont nécessaires.

## Fonctionnement

Le service attend Docker et le réseau, vérifie `/dev/net/tun` et l’existence des
sources des montages utilisés par Gluetun et ses trois clients. Les chemins
sous `/media` et `/downloads` nécessitent que ces points soient réellement
montés : aucun répertoire de remplacement n’est créé sur le disque du système.
Les chemins personnalisés hors de ces emplacements doivent exister.

Il lance `vpn-up.sh`, attend que Gluetun soit sain, puis démarre qBittorrent,
MeTube et JDownloader. Un client dont l’espace réseau diffère de celui de
Gluetun est recréé. Le script vérifie aussi la liaison de qBittorrent à `tun0`
et contrôle à nouveau les trois espaces réseau. Les extensions déclarées dans
le `.env` racine sont chargées par le mécanisme habituel.

Une exécution manuelle et une exécution automatique sont sérialisées par un
verrou. En cas d’échec, systemd réessaie après 30 secondes. Après réussite, le
service reste `active (exited)` : il n’effectue pas de surveillance continue et
ne relance pas toute la configuration applicative. Au prochain démarrage de
Docker, il démarrera les trois clients, même s’ils avaient été arrêtés à la main.

## Vérification et maintenance

```sh
systemctl is-enabled media-stack-vpn.service
systemctl status media-stack-vpn.service
journalctl -u media-stack-vpn.service -b --no-pager
sudo systemctl restart media-stack-vpn.service
```

Pour désactiver cette automatisation :

```sh
sudo systemctl disable --now media-stack-vpn.service
```

Cela ne stoppe pas les conteneurs. Pour réactiver, relancer l’installateur.
Après une recréation manuelle de Gluetun, utiliser `vpn-up.sh` ou redémarrer ce
service pour raccorder les clients.

Sur Proxmox, le démarrage du LXC lui-même reste une configuration de l’hôte.
Pour le conteneur 104, vérifier `pct config 104` et activer si nécessaire
`pct set 104 -onboot 1`. Les montages de stockage et TUN doivent également être
disponibles avant le démarrage des applications ; voir les guides de permissions
et de configuration VPN.
