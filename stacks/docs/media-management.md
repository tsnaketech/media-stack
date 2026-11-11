# Import des fichiers supplémentaires

Lidarr, Radarr et Sonarr proposent les champs **Import Extra Files**
et **Extra File Extensions**, dans Settings → Media Management.
Les stacks `music`, `movie`, `tv` les exposent dans leur `.env` :

```dotenv
# Extra-file import
# Enable importing companion files alongside the main media file.
ARR_IMPORT_EXTRA_FILES=true
# Comma-separated extensions without leading dots, for example: srt,nfo,jpg
ARR_EXTRA_FILE_EXTENSIONS='srt,nfo,jpg'
```

`true` coche l'option, `false` la décoche. La seconde variable définit les suffixes
à prendre en compte. Les `.env` et `.env.example` utilisent initialement `false`
et `srt`, conformément aux valeurs présentes lors de l'installation de ce hook.
Les autres outils ne proposent pas ces mêmes paramètres arr et ne reçoivent pas
ces variables.

## Application des réglages

Depuis la racine du dépôt, après avoir édité le `.env` :

```sh
python3 scripts/stack-compose.py tv config --quiet
python3 scripts/stack-compose.py tv up -d sonarr
```

Le hook `post_start` exécute `scripts/configure-arr-media.sh`. Il attend l'API,
lit `/api/v1/config/mediamanagement` pour Lidarr ou l'équivalent `v3` pour les
autres applications, puis applique :

```json
{
  "importExtraFiles": true,
  "extraFileExtensions": "srt,nfo,jpg"
}
```

L'objet complet de configuration est conservé : seuls ces deux champs sont
modifiés, puis relus pour vérification. Si les valeurs sont déjà correctes,
aucune écriture n'est faite. La clé API est lue dans le volume de configuration
et n'est pas affichée. Le script refuse les booléens invalides et les extensions
contenant des chemins ; il normalise espaces, points initiaux et majuscules.

Ces variables sont des conventions de ce dépôt, interprétées par le hook,
pas des paramètres d'environnement natifs des applications arr. Les valeurs
absentes ou vides prennent les valeurs de repli Compose (`false` et `srt`).
Un redémarrage effectué par Docker seul ne relance pas le hook, mais les réglages
appliqués restent enregistrés dans la base persistante de l'application.

L'option s'applique au processus d'import de l'application : elle ne copie pas
immédiatement des fichiers dans la bibliothèque et ne lance pas de téléchargement.
Vérifier la pertinence des extensions choisies pour chaque type de média et les
éventuels traitements spécifiques de l'application.
