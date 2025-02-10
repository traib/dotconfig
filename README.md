# dotconfig

### Installation

Sets up symlinks. Overwrites existing files, including copies.

    python settings.py install

Sets up copies. Overwrites existing files, including symlinks.

    python settings.py install --cp

Categories of settings can be selected individually.
They are set up in topological order, recursively installing their dependencies.

    python settings.py install zsh vscode

Dry-run is supported.

    python settings.py install --dry-run

All flags can be mixed and matched.

    python settings.py install --dry-run zsh


### Diff

It's useful to diff all settings before installation on a new system,
since it overwrites all matching files.

    python settings.py diff


#### Brewfile needs to be updated manually

If symlinked

    brew bundle dump --force --global

If not

    brew bundle dump --force --file=brew/Brewfile
