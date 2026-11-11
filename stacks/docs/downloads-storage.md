# Stockage des téléchargements dans le montage Proxmox

Le disque partagé est exposé au LXC sous `/downloads`. Les applications reçoivent
ce même dossier sous `/downloads` dans leurs conteneurs. Définir
`SHARED_DOWNLOADS_DIR=/downloads` dans les `.env` de `download`, `music`, `movie`,
`tv` et `book` : toutes les applications doivent voir les mêmes fichiers.
Les URL et clés API ne changent pas.

## Montage et droits

Sur Proxmox, définir le numéro du LXC et adapter le chemin de stockage illustratif :

```sh
CT_ID=YOUR_CT_ID
pct set "$CT_ID" -mp1 /srv/media/downloads,mp=/downloads
setfacl -R -m u:101000:rwX /srv/media/downloads
find /srv/media/downloads -type d -exec setfacl -m u:100000:--x,d:u:100000:--x,d:u:101000:rwx {} +
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
