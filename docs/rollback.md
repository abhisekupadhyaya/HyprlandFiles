# Rollback and recovery

Every managed-file transaction prints `BACKUP=...` and its exact rollback command
**before writes**. Root snapshots live in `/var/lib/hyprlandfiles/backups`, user
snapshots in `~/.local/state/hyprlandfiles/backups`; both are mode 0700. Original
files, modes, ownership and symlinks use `cp -a`. Write-ahead manifests also allow
restoring a transaction interrupted halfway through. An incomplete transaction
blocks subsequent installation until explicitly restored.

Save work and log out through the desktop menu before rollback. The tool refuses
an authenticated graphical session; it never kills applications. From an
existing TTY/SSH, if only the idle login is running, hide it normally:

```sh
hf-desktop off
systemctl is-active greetd.service
# Continue when inactive; do not stop an authenticated GUI to force this.
sudo systemctl stop hf-desktopd.service
```

Stopping the controller is an explicit rollback action. It does not stop SSH,
networking, firewall or other server units. Keep your recovery connection open.
Restore the **user snapshots as that user** and the **root snapshots via sudo**,
in reverse chronological order within each store:

```sh
./install.sh rollback /exact/user/BACKUP/path
sudo python3 tools/installer.py rollback /exact/root/BACKUP/path
```

Use the paths printed on your own installation, not an example timestamp. If
checkout is unavailable, the installed tool also works while its payload remains:
`python3 /usr/local/share/hyprlandfiles/tools/installer.py rollback PATH`.
For a complete removal of managed files, run from a retained checkout and restore
all snapshots newest-first. The oldest root snapshot restores the original APT
source/pins and temporary greetd mask; later root snapshots undo runtime/login/
next-boot enablement. Do not restore a lower snapshot over a later one.

Rollback refuses any managed file changed since deployment, before restoring
anything. Preserve/merge the edit manually rather than adding a force option.
This includes a changed theme-current symlink after wallpaper selection: retain
your selected generation, inspect the recorded symlink and restore it to the
recorded expected target before rollback, or merge only that file explicitly.
Generated colour caches and package downloads remain; they are private local
state, never Git content. Empty directories may remain.

Installed packages are deliberately retained. Removing packages can remove
unrelated dependencies; review an APT simulation and get separate administrator
approval for removals. No automatic autoremove/purge exists. The runtime wheels
are journalled files and are restored with the rest of the runtime.

If a package/download stage failed, greetd may still be masked. Keep it masked
until the printed source-stage snapshot is rolled back or the reviewed
installation is repaired. Never unmask just to hide the installation failure.
No logind restart is required by rollback; restored lid policy takes effect at
next operator-chosen boot. Do not reboot with a closed lid until the restored
power policy is understood.


## Desktop appearance preferences

GTK/VS Code files installed by the main user phase are in its normal file
snapshot. The two desktop GSettings preferences have a separate per-key snapshot
(the full dconf database is not read or copied). The appearance phase prints:

```
python3 tools/appearance.py rollback /exact/appearance/preferences/SNAPSHOT
```

Run it as the desktop user without sudo. It restores original values or resets
originally unset keys, refuses later unrelated edits, and leaves other desktop
preferences alone. If the standalone appearance command also changed files,
that same rollback restores their permission-preserving file snapshot too. This
appearance-only rollback can run while applications remain open. For complete
uninstall rollback, restore these preferences before the main user/root snapshots.
