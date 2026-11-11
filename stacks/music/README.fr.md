# Stack musique : Lidarr et Navidrome

[English](README.md) | **Français**

Exécuter ces commandes sur l'hôte Docker, depuis `/opt/media-stack/stacks/music`.
Docker Engine et le plugin Docker Compose sont nécessaires.

## Préparation

Conserver le fichier `.env` existant. S'il est absent, copier `.env.example`
vers `.env`. Adapter `PUID` et `PGID` à l'utilisateur qui gère la musique
(`id -u` et `id -g`). Les chemins par défaut sont `/media/music` pour la
bibliothèque et `/downloads` pour le volume partagé de téléchargements ; ils
peuvent être remplacés avec `MUSIC_DIR` et `SHARED_DOWNLOADS_DIR` dans `.env`.
Les téléchargements musicaux sont dans `/downloads/music` côté conteneur.

Avec les valeurs par défaut, préparer les dossiers :

```sh
sudo mkdir -p data/lidarr data/navidrome /media/music /downloads/music
# Remplacer 1000:1000 par les valeurs de PUID:PGID choisies.
sudo chown 1000:1000 data/lidarr data/navidrome /media/music /downloads/music
```

Adapter les chemins si les variables ont été modifiées. Pour une bibliothèque
existante, vérifier également les permissions des fichiers et sous-dossiers :
Lidarr doit pouvoir écrire, Navidrome doit pouvoir lire. Les commandes ci-dessus
ne changent pas récursivement les propriétaires des fichiers existants.

## Démarrage et vérification

```sh
python3 ../scripts/stack-compose.py music config --quiet
python3 ../scripts/stack-compose.py music pull
python3 ../scripts/stack-compose.py music up -d
python3 ../scripts/stack-compose.py music ps
python3 ../scripts/stack-compose.py music logs --tail=100 lidarr navidrome
```

Accéder à Lidarr sur `http://IP_DU_SERVEUR:8686` et à Navidrome sur
`http://IP_DU_SERVEUR:4533`. Configurer l'authentification de Lidarr et créer
le premier administrateur Navidrome.

Dans Lidarr, ajouter `/music` comme dossier racine. Navidrome lit ce même
dossier en lecture seule. Pour les téléchargements automatiques, configurer
également un indexeur et un client de téléchargement dans Lidarr : aucun
client n'est inclus dans cette stack. Le client doit partager le dossier de
téléchargements, avec un chemin cohérent avec `/downloads` dans Lidarr.

Cette stack fonctionne directement par ses ports et ne dépend pas de Traefik
ou d'Arcane. Exécuter `../scripts/vpn-up.sh` en premier pour préparer le réseau `media-shared`. Le démarrage effectif doit être vérifié sur l'hôte Docker.

## Services partagés

Voir [indexer](../indexer/README.fr.md) pour Prowlarr et
[download](../download/README.fr.md) pour qBittorrent. Le montage des
téléchargements utilise désormais `SHARED_DOWNLOADS_DIR=/downloads`
(par défaut), exposé sous `/downloads`. La catégorie musique utilise
`/downloads/music`. L’ancienne variable `DOWNLOADS_DIR` n’est plus utilisée.

Les chemins racines conteneur sont configurables dans `.env` ; voir le
[guide des racines média](../docs/media-roots.md).

Les connexions qBittorrent de cet hôte sont désormais configurées ; voir le
[récapitulatif des clients et catégories](../docs/download-clients.md).

## Classer les pistes par album dans Lidarr

Dans **Settings → Media Management → Track Naming**, activer **Rename Tracks**.
Dans le format de nommage, le texte avant le premier `/` définit le dossier
de l’album. Le format utilisé ici commence par `{Album Title} ({Release Year})/`.
Par exemple, les pistes de *Lunatic* sont rangées dans
`/music/Booba/Lunatic (2010)/` dans Lidarr.

La commande suivante active le renommage pour les prochains imports et applique
le format déjà configuré aux pistes existantes d’un album. Elle déplace et renomme
les fichiers de la bibliothèque via Lidarr. Exécuter depuis `/opt/media-stack/stacks/music`
avec Docker Compose et Python 3. Remplacer les identifiants Lidarr `2` (Booba)
et `10` (Lunatic) pour traiter un autre album.

```sh
python3 - 2 10 <<'PY'
import importlib
import sys
from pathlib import Path

artist_id, album_id = map(int, sys.argv[1:])
root = Path.cwd().parent
sys.path.insert(0, str(root / "scripts"))
clients = importlib.import_module("configure-download-clients")
lidarr = clients.app_api(root, "lidarr", "127.0.0.1")

album = lidarr.call(f"album/{album_id}")
if album["artistId"] != artist_id:
    raise SystemExit("Cet album ne correspond pas à l’artiste indiqué.")

naming = lidarr.call("config/naming")
if not naming["renameTracks"]:
    naming["renameTracks"] = True
    lidarr.call(f"config/naming/{naming['id']}", "PUT", naming)

renames = lidarr.call(f"rename?artistId={artist_id}")
tracks = [entry for entry in renames if entry["albumId"] == album_id]
if not tracks:
    raise SystemExit("Aucune piste de cet album à renommer.")

for entry in tracks:
    print(f"{entry['existingPath']} → {entry['newPath']}")

command = lidarr.call("command", "POST", {
    "name": "RenameFiles",
    "artistId": artist_id,
    "files": [entry["trackFileId"] for entry in tracks],
})
print(f"Tâche Lidarr {command['id']} lancée pour {len(tracks)} pistes.")
PY
```

Vérifier la fin de la tâche dans **System → Tasks**, puis ouvrir le dossier
de l’album dans la bibliothèque. La commande utilise la clé API locale via
le script du dépôt.

[Documentation du nommage Lidarr](https://github.com/Servarr/Wiki/blob/master/lidarr/settings.md)
