# Téléchargements

[English](README.md) | **Français**

Cette stack regroupe **qBittorrent**, **SABnzbd**, **qui**, **JOAL**, **MeTube** et **JDownloader 2**.
Gluetun reste dans `../vpn` ; qBittorrent, MeTube et JDownloader partagent son espace réseau. Les autres
services rejoignent directement le réseau externe `media-shared`.

## Configuration

Les réglages de chaque outil sont regroupés dans `.env.example`. Le `.env`
privé conserve les valeurs locales, comptes et secrets ; le protéger en mode
`600`. `SHARED_DOWNLOADS_DIR=/downloads` désigne le montage Proxmox commun aux
clients et applications arr. Vérifier qu’il est monté avant le démarrage.

Les ports habituels restent : qBittorrent `8080`, MeTube `8081` et JDownloader `5800` (publiés par Gluetun), SABnzbd
`8085`, qui `7476`, JOAL `8088`. Les URL propres à l’hôte sont dans
`/opt/media-stack/README.local.md`. Les noms Docker restent identiques.

## Démarrage et contrôle

Avant une première installation, préparer les dossiers MeTube selon son
[guide](docs/metube.md#stockage), puis exécuter depuis la racine `stacks` :

```sh
./scripts/vpn-up.sh
python3 scripts/prepare-joal.py
python3 scripts/stack-compose.py download up -d
python3 scripts/stack-compose.py download ps
python3 scripts/stack-compose.py download logs --since=5m --tail=60
```

`./scripts/stacks.sh up` démarre aussi les autres stacks. Après leur démarrage :

```sh
python3 scripts/configure-qui.py
python3 scripts/configure-download-clients.py
```

Le fichier privé `.qbittorrent-credentials.json` est utilisé par ces scripts et
par la configuration VPN. Les comptes et torrents existants sont conservés.
Les données propres à chaque service sont sous `download/data/<service>` et
restent exclues de Git. Sauvegarder configurations et secrets séparément.

Voir les guides [JDownloader](docs/jdownloader.md), [MeTube](docs/metube.md), [SABnzbd](sabnzbd.md), [qui](docs/qui.md), [JOAL](docs/joal.md),
[VPN](../vpn/README.fr.md) et [stockage partagé](../docs/downloads-storage.md).
SABnzbd nécessite un fournisseur Usenet et un indexeur NZB ; son trafic ne passe
pas automatiquement par le VPN de qBittorrent.
