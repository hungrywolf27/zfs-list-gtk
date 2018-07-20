# zfs-list-gtk
A simple GUI that lists ZFS filesystems and snapshots in a Gtk TreeView widget.

Written in Python. Developed and tested on Ubuntu 18.04 only.

## Features
- Snapshots can be expanded and collapsed
- Sortable by clicking column headers. Human-readable sizes are sorted correctly.
- Use `-o` to display any properties supported by `zfs list` (default is `name,used,avail,refer,mountpoint`)
- Refresh button
- Column widths and window size are saved on exit
- Can easily be extended to pass selected filesystem(s) or snapshot(s) to external script.

## Usage
`zfs-list-gtk.py [-o property[,...]] [filesystem]`
