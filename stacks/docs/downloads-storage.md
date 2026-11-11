# Stockage des téléchargements dans le montage Proxmox

Le disque partagé est exposé au LXC sous `/downloads`. Les applications reçoivent
ce même dossier sous `/downloads` dans leurs conteneurs. Définir
`SHARED_DOWNLOADS_DIR=/downloads` dans les `.env` de `download`, `music`, `movie`,
`tv` et `book` : toutes les applications doivent voir les mêmes fichiers.
Les URL et clés API ne changent pas.

## Montage et droits

Sur Proxmox, pour le LXC 104 :

```sh
pct set 104 -mp1 /mnt/share/downloads,mp=/downloads
setfacl -R -m u:101000:rwX /mnt/share/downloads
find /mnt/share/downloads -type d -exec setfacl -m u:100000:--x,d:u:100000:--x,d:u:101000:rwx {} +
```

L’UID 101000 correspond à l’utilisateur 1000 des applications dans ce LXC non
privilégié. `rwX` autorise lecture/écriture et traversée des dossiers, sans rendre
les fichiers ordinaires exécutables. Le droit de traversée `--x` pour l’UID
100000 permet à root du LXC et au moteur Docker de résoudre les chemins, sans
accorder la lecture du contenu des dossiers. Les ACL par défaut donnent les
droits nécessaires aux nouveaux éléments. Les propriétaires sont conservés.
Ces identifiants supposent le mapping Proxmox par défaut.

Dans le LXC :

```sh
mountpoint /downloads
findmnt -T /downloads
df -h /downloads
setpriv --reuid=1000 --regid=1000 --clear-groups \
  sh -c 'touch /downloads/.permission-test && rm /downloads/.permission-test'
```

Vérifier le montage avant chaque démarrage : un dossier local nommé `/downloads`
ne suffit pas. En cas d’absence du partage, ne pas démarrer les clients.

## Migration d’un ancien dossier

Arrêter qBittorrent, SABnzbd et les applications susceptibles d’importer des
fichiers avant la copie. Sauvegarder leurs `.env`. Copier sans écraser les fichiers
existants différents ; conserver chemins relatifs et dates. Comparer les tailles
et empreintes SHA-256 avant de modifier les montages Docker. Conserver la source
jusqu’à validation des téléchargements et imports. Ne pas supprimer les torrents
ni leur état applicatif.

Après changement des `.env`, recréer les conteneurs concernés et utiliser
`scripts/vpn-up.sh` pour qBittorrent. Les chemins enregistrés dans les clients,
comme `/downloads/movies` ou `/downloads/usenet`, restent identiques : aucun
Remote Path Mapping supplémentaire n’est nécessaire.

Les dossiers `/media` et `/downloads` restent deux montages Docker distincts.
Leur présence sur un même disque hôte ne garantit pas les hardlinks entre les
deux montages ; un import peut nécessiter une copie et consommer de l’espace.

## Migration de cette installation

Le contenu de `/opt/downloads` a été copié vers `/downloads`, sans écrasement de
fichiers différents, puis vérifié par tailles et empreintes SHA-256. Les fichiers source de `/opt/downloads` ont été supprimés après validation, à la
demande de l’utilisateur. Les clients utilisent désormais le stockage partagé. Les `.env` précédents sont sauvegardés sous `/opt/media-stack/backups`.
