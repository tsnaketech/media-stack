# Racines média dans les .env

## Chemin hôte et chemin conteneur

Le chemin hôte indique où les fichiers sont stockés sur le serveur.
La racine conteneur est le chemin visible par l'application. Exemple Sonarr :

```dotenv
# Host library directory
LIBRARY_DIR=/media/tv
# Media root inside the container
ARR_ROOT_FOLDER=/tv
```

Compose utilise ces deux valeurs pour monter la bibliothèque :

```yaml
volumes:
  - ${LIBRARY_DIR:-/media/tv}:${ARR_ROOT_FOLDER:-/tv}
```

Les commentaires des `.env.example` sont en anglais. Les `.env` actifs restent
locaux, exclus de Git ; aucun média n'est déplacé lors de leur préparation.

## Variables par outil

| Stack / outil | Chemin hôte | Racine conteneur dans .env | Valeur initiale |
|---|---|---|---|
| music / Lidarr | `MUSIC_DIR` | `ARR_ROOT_FOLDER` | `/music` |
| music / Navidrome | `MUSIC_DIR` | `NAVIDROME_ROOT_FOLDER` | `/music` |
| movie / Radarr | `LIBRARY_DIR` | `ARR_ROOT_FOLDER` | `/movies` |
| tv / Sonarr | `LIBRARY_DIR` | `ARR_ROOT_FOLDER` | `/tv` |
| audiobook / Audiobookshelf | `LIBRARY_DIR` | `AUDIOBOOKSHELF_ROOT_FOLDER` | `/audiobooks` |
| book / Calibre-Web | `LIBRARY_DIR` | `CALIBRE_ROOT_FOLDER` | `/books` |
| book / Shelfmark | `SHARED_DOWNLOADS_DIR` + `/books/ingest` | `SHELFMARK_ROOT_FOLDER` | `/books` |

Dans une stack, `ARR_ROOT_FOLDER` concerne uniquement son application arr.
Navidrome et Lidarr partagent le même dossier hôte, mais peuvent utiliser des
chemins conteneur différents.

Prowlarr gère les indexeurs et n'a pas de bibliothèque média. qBittorrent utilise
`SHARED_DOWNLOADS_DIR`, toujours exposé sous `/downloads` pour rester cohérent
avec ses clients. Ses catégories définissent les sous-dossiers de téléchargement ;
ce ne sont pas les bibliothèques finales des applications arr.

## Enregistrement automatique dans les applications arr

Le hook Compose `post_start` exécute `scripts/configure-arr-root.sh` pour
Lidarr, Radarr et Sonarr. Il attend l'API locale, vérifie la présence
du dossier monté puis ajoute la racine si son chemin n'est pas déjà enregistré.
La clé API est lue dans `/config/config.xml` et n'est pas affichée.

Un second démarrage ne crée pas de doublon et ne modifie pas les réglages d'une
racine existante. Aucun dossier existant n'est supprimé et aucun élément de
bibliothèque n'est déplacé ou réassigné automatiquement.

Lidarr exige aussi des profils de qualité et de métadonnées : lors de la création
d'une nouvelle racine, le hook utilise le premier profil disponible de chaque
catégorie et désactive la surveillance par défaut pour cette racine. Vérifier
ensuite ces choix dans l'interface avant d'activer des recherches automatiques.
Les paramètres d'une racine Lidarr déjà existante sont conservés.

## Autres applications

- Navidrome reçoit la racine via sa variable native `ND_MUSICFOLDER`.
- Shelfmark reçoit sa destination de livraison via sa variable native `INGEST_DIR`.
  Il s'agit d'un dossier de réception, pas d'une bibliothèque Calibre.
- Pour Calibre-Web et Audiobookshelf, la variable définit le point de montage
  accessible. La sélection de la bibliothèque dans l'interface reste nécessaire :
  choisir ce chemin dans Audiobookshelf ; sélectionner un dossier contenant une
  base Calibre `metadata.db` valide dans Calibre-Web. Aucun compte administrateur
  n'est créé pour ces applications et aucune base Calibre vide n'est fabriquée.

## Appliquer un changement

Depuis la racine du dépôt :

```sh
python3 scripts/stack-compose.py tv config --quiet
python3 scripts/stack-compose.py tv up -d
```

Le hook requiert Docker Compose 2.30+ et n'est exécuté que lors des démarrages
gérés par Compose. Les dossiers racines ajoutés restent dans les bases persistantes.
Un mot de passe vide dans `.env` n'empêche pas le hook des racines de fonctionner.

Changer une racine conteneur peut laisser les anciennes références dans la base
de l'application : migrer les éléments existants depuis l'interface avant de
retirer un ancien chemin. Garder les montages existants pendant une migration
qui le nécessite. Modifier le `.env` seul ne déplace pas les fichiers.
Les droits du dossier hôte et les restrictions `:ro` restent applicables.
