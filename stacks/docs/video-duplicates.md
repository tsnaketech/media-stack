# Rechercher les doublons vidéo

`scripts/find-video-duplicates.py` analyse les fichiers sans modifier les vidéos,
leurs noms ou les métadonnées Jellyfin. Il produit des rapports **CSV et HTML**,
avec un cache SQLite pour éviter de retraiter les fichiers inchangés.

## Utilisation

Depuis la racine du dépôt, avec Python 3 et FFmpeg/FFprobe installés sur l’hôte :

```sh
python3 stacks/scripts/find-video-duplicates.py /path/to/videos \
  --output reports/video-duplicates
```

Pour utiliser les outils déjà présents dans Jellyfin LinuxServer :

```sh
sudo python3 stacks/scripts/find-video-duplicates.py /media/movies \
  --container jellyfin --read-uid 1000 \
  --output reports/video-duplicates
```

Les chemins des vidéos doivent être identiques sur l’hôte et dans le conteneur.
Le conteneur doit déjà être démarré. L’image doit fournir `nice`, `ionice`, FFmpeg
et FFprobe ; `--ffmpeg-dir` adapte le répertoire des binaires, et
`--container-user` adapte l’UID/GID utilisé (par défaut `1000:1000`). Les processus
de décodage y sont lancés avec une priorité basse et un thread de codec.

Le script analyse un fichier à la fois par défaut. `--workers 2` permet deux
traitements simultanés sur un hôte disposant des ressources nécessaires (maximum
4). Les travailleurs sont des processus séparés ; le cache est écrit uniquement
par le processus principal. Réduire à un travailleur pendant une lecture vidéo
si le serveur manque de ressources.

`--read-uid` sert à l’inventaire, au hachage et à la lecture par FFmpeg/FFprobe
sur l’hôte. Avec `--container`, le décodage utilise plutôt `--container-user`.
Root est nécessaire pour adopter temporairement un autre UID ; les
rapports sont écrits avec l’identité qui lance le script. Aucune ACL n’est changée.

Plusieurs racines peuvent être analysées dans une même commande pour détecter
les copies entre dossiers. Les liens symboliques sont ignorés. Les liens
physiques sont signalés séparément et un seul exemplaire est analysé.

Pour commencer par les copies exactes uniquement :

```sh
python3 stacks/scripts/find-video-duplicates.py /path/to/videos \
  --exact-only --output reports/video-duplicates
```

Ce mode ne nécessite pas FFmpeg. Il calcule SHA-256 pour les groupes de fichiers
de même taille. Les colonnes techniques restent vides si elles ne sont pas
déjà disponibles dans le cache.

## Comparaison visuelle et limites

L’analyse complète relève durée, résolution et codec, puis extrait **12 images**
entre 5 % et 95 % de chaque vidéo. `--frames` accepte de 8 à 24 images. Chaque
image est réduite en niveaux de gris pour calculer une empreinte perceptuelle
dHash de 64 bits. Les images sombres ou quasi uniformes sont écartées.

Les paires comparées ont des durées proches : écart maximal de 2 secondes ou
2 % de la plus courte durée. Au moins six positions exploitables sont nécessaires.
Le classement utilise la proportion d’images dont les empreintes sont proches,
ainsi que leur distance moyenne. Le pourcentage affiché mesure des images
ressemblantes ; il ne représente pas une probabilité de doublon.

Un SHA-256 identique confirme une copie exacte. Une ressemblance visuelle demande
une vérification : génériques communs, images statiques et montages peuvent
induire des erreurs. Les versions coupées, décalées, fortement recadrées ou
retouchées peuvent échapper à cette première méthode. Aucun exemplaire à supprimer
n’est choisi automatiquement.

## Rapports et cache

Chaque exécution crée un dossier daté avec :

- `index.html` : tableau autonome, filtrable, utilisable sans serveur ni Internet ;
- `duplicates.csv` : paires candidates avec chemins, tailles, durées, résolutions,
  codecs, scores et colonne `decision` à renseigner ;
- `hardlinks.csv` : chemins qui désignent déjà le même fichier sur disque ;
- `errors.csv` : fichiers ou répertoires non analysés, et erreurs de lecture.

Les CSV utilisent le point-virgule et UTF-8 avec BOM pour Excel. Conserver le
dossier complet pour que les liens du HTML vers les CSV fonctionnent. Un groupe
relie des paires candidates ; tous ses membres ne sont pas nécessairement
équivalents entre eux. Un rapport vide signifie seulement qu’aucun candidat n’a
été trouvé avec les critères appliqués. Le code de sortie vaut `2` en présence
d’erreurs : consulter `errors.csv` avant de conclure.

Le cache `fingerprints.sqlite` reste dans le répertoire de sortie, sauf choix
explicite avec `--cache`. Il est invalidé lorsque taille, dates de modification
ou de changement, inode, nombre d’images ou version de l’algorithme changent.
Les résultats de chaque fichier terminé sont conservés même si le processus est
interrompu. Relancer la même commande pour reprendre grâce au cache ; éviter les
analyses concurrentes et les fichiers en cours de téléchargement.

Les rapports sont nouveaux à chaque exécution : les décisions saisies dans un
ancien CSV ne sont pas écrasées ni automatiquement importées. Cache et rapports
contiennent les chemins des vidéos. Les placer dans un répertoire ignoré par Git,
comme `reports/`, ou hors du dépôt. Les fichiers générés sont privés (`600`) et
les nouveaux dossiers de rapports sont créés en `700`.
