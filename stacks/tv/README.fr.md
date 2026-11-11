# Séries : Sonarr

[English](README.md) | **Français**

Les URL ci-dessous utilisent `IP_DU_SERVEUR`, à remplacer par l’adresse de votre hôte.

Interface : http://IP_DU_SERVEUR:8989 ou http://sonarr.arr.local après création
d'une entrée DNS vers `IP_DU_SERVEUR`. La stack utilise le réseau externe
`media-shared` préparé par `scripts/vpn-up.sh`.

## Volumes et permissions

| Hôte LXC | Sonarr | Usage |
|---|---|---|
| `./data/sonarr` | `/config` | Configuration et base locales |
| `/media/tv` | `/tv` | Bibliothèque finale des séries |
| `/downloads` | `/downloads` | Téléchargements partagés avec qBittorrent |

Les valeurs peuvent être remplacées avec `LIBRARY_DIR` et
`SHARED_DOWNLOADS_DIR` ; conserver le même chemin hôte des téléchargements
que dans la stack download. Les UID/GID par défaut sont `1000:1000`.
Le dossier `/media/series` existant n'est pas utilisé : cette stack utilise
`/media/tv`, exposé sous `/tv`. Ne pas mélanger les deux bibliothèques.

Pour les ACL à appliquer sur Proxmox, voir le [guide des droits](../docs/permissions.md).
La bibliothèque TV doit recevoir les mêmes ACL pour UID hôte `101000` que les
films. L'héritage doit être défini sur les dossiers existants.

## Commandes dans le LXC

```sh
cd /opt/media-stack/stacks
./scripts/vpn-up.sh
python3 scripts/stack-compose.py indexer up -d
python3 scripts/stack-compose.py tv config --quiet
python3 scripts/stack-compose.py tv up -d
python3 scripts/stack-compose.py tv ps
python3 scripts/stack-compose.py tv logs --since=5m --tail=80
```

La stack est incluse dans `scripts/stacks.sh` et Sonarr est testé par
`scripts/check-services.py`.

## Configuration applicative

- Créer les identifiants administrateur au premier accès.
- Le dossier racine `/tv` est déjà enregistré. Choisir les profils de qualité
  souhaités avant d'ajouter des séries.
- Dans qBittorrent, créer la catégorie `tv` avec le chemin `/downloads/tv`.
- Ajouter qBittorrent dans Settings → Download Clients : hôte `qbittorrent`,
  port `8080`, identifiants personnels et catégorie `tv`. Tester puis enregistrer.
- Sonarr est déjà enregistré dans Prowlarr avec synchronisation des ajouts.
  Pour vérifier Settings → Apps : URL Sonarr `http://sonarr:8989`,
  URL de Prowlarr `http://prowlarr:9696` et la clé API Sonarr disponible dans
  Settings → General. Ne pas créer une deuxième entrée si elle existe déjà.
- Ajouter ensuite les indexeurs proposant les catégories TV dans Prowlarr.
  Aucun indexeur ni aucune recherche de série n'est configuré automatiquement.

Documentation de l'image : https://docs.linuxserver.io/images/docker-sonarr/

Les chemins racines conteneur sont configurables dans `.env` ; voir le
[guide des racines média](../docs/media-roots.md).

Les connexions qBittorrent de cet hôte sont désormais configurées ; voir le
[récapitulatif des clients et catégories](../docs/download-clients.md).
