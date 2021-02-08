import dataclasses
import enum
import os
import pathlib
import platform
import shutil
import sys
from typing import NamedTuple, Optional

assert sys.version_info >= (3, 9)

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent


@dataclasses.dataclass(frozen=True)
class Location:
    save: str
    linux: Optional[str]
    darwin: Optional[str]
    windows: Optional[str]

    def __init__(self, save, linux=None, darwin=None, windows=None):
        assert save
        object.__setattr__(self, 'save', save)
        object.__setattr__(self, 'linux', linux)
        object.__setattr__(self, 'darwin', darwin)
        object.__setattr__(self, 'windows', windows)

    def inside_repository(self) -> pathlib.Path:
        return SCRIPT_DIR.joinpath(self.save)

    def outside_repository(self) -> Optional[pathlib.Path]:
        load = getattr(self, platform.system().lower())
        return None if not load else pathlib.Path(os.path.expandvars(load))


@dataclasses.dataclass(frozen=True)
class Command:
    args: tuple[str]

    def __init__(self, *args):
        assert args
        object.__setattr__(self, 'args', args)

    def on_current_platform(self) -> tuple[str]:
        return (shutil.which(self.args[0]),) + self.args[1:]


class CategoryDescription(NamedTuple):
    prerequisites: tuple[str] = ()
    before_install: tuple[Command] = ()
    locations: tuple[Location] = ()
    after_install: tuple[Command] = ()

    def is_not_enabled(self) -> bool:
        return all(
            not location.outside_repository() for location in self.locations
        )


class Category(CategoryDescription, enum.Enum):

    BASH = CategoryDescription(
        prerequisites=("SH",),
        locations=(
            Location(
                save='bash/bash_profile',
                linux='$HOME/.bash_profile',
                darwin='$HOME/.bash_profile',
                windows='$HOME/.bash_profile'
            ),
            Location(
                save='bash/bashrc',
                linux='$HOME/.bashrc',
                darwin='$HOME/.bashrc',
                windows='$HOME/.bashrc'
            ),
        ),
    )

    SH = CategoryDescription(
        locations=(
            Location(
                save='sh/inputrc',
                linux='$HOME/.inputrc',
                darwin='$HOME/.inputrc',
                windows='$HOME/.inputrc'
            ),
            Location(
                save='sh/profile',
                linux='$HOME/.profile',
                darwin='$HOME/.profile',
                windows='$HOME/.profile'
            ),
        ),
    )

    VSCODE = CategoryDescription(
        locations=(
            # https://code.visualstudio.com/docs/getstarted/settings#_settings-file-locations
            Location(
                save='Code/User/keybindings.json',
                linux='$HOME/.config/Code/User/keybindings.json',
                darwin=
                '$HOME/Library/Application Support/Code/User/keybindings.json',
                windows='%APPDATA%/Code/User/keybindings.json'
            ),
            Location(
                save='Code/User/settings.json',
                linux='$HOME/.config/Code/User/settings.json',
                darwin=
                '$HOME/Library/Application Support/Code/User/settings.json',
                windows='%APPDATA%/Code/User/settings.json'
            ),
        ),
        after_install=(
            Command(
                'code', '--install-extension', 'vscodevim.vim',
                '--install-extension', 'ms-python.python'
            ),
        ),
    )

    ZSH = CategoryDescription(
        prerequisites=('SH',),
        before_install=(
            Command(
                'curl', '--silent', '--show-error',
                'https://raw.githubusercontent.com/grml/grml-etc-core/master/etc/zsh/zshrc',
                '--output', SCRIPT_DIR.joinpath('zsh/zshrc')
            ),
        ),
        locations=(
            # https://wiki.archlinux.org/index.php/zsh#Startup/Shutdown_files
            Location(
                save='zsh/zshenv',
                linux='$HOME/.zshenv',
                darwin='$HOME/.zshenv'
            ),
            Location(
                save='zsh/zshrc.pre',
                linux='$HOME/.zshrc.pre',
                darwin='$HOME/.zshrc.pre'
            ),
            Location(
                save='zsh/zshrc', linux='$HOME/.zshrc', darwin='$HOME/.zshrc'
            ),
            Location(
                save='zsh/zshrc.local',
                linux='$HOME/.zshrc.local',
                darwin='$HOME/.zshrc.local'
            ),
        ),
    )


if __name__ == '__main__':
    import argparse
    import contextlib
    import difflib
    import graphlib
    import io
    import subprocess
    import tempfile

    def as_categories(
        names: tuple[str], default=tuple(Category)
    ) -> tuple[Category]:
        return default if not names else tuple(
            Category[name.upper()] for name in names
        )

    def toposort(names: tuple[str]) -> tuple[Category]:
        visited = set()
        to_visit = list(as_categories(names))
        sorter = graphlib.TopologicalSorter()
        while to_visit:
            category = to_visit.pop()
            prerequisites = as_categories(category.prerequisites, default=())
            visited.add(category)
            sorter.add(category, *prerequisites)
            to_visit.extend(
                prerequisite for prerequisite in prerequisites
                if prerequisite not in visited
            )
        return sorter.static_order()

    def open_or_empty(path: pathlib.Path):
        if not path.is_file():
            return contextlib.nullcontext(io.StringIO())
        return open(path)

    def symlink_force(src: pathlib.Path, dst: pathlib.Path):
        with tempfile.TemporaryDirectory(
            dir=SCRIPT_DIR.joinpath('tmp')
        ) as tmp_dir:
            tmp_symlink = pathlib.Path(tmp_dir).joinpath('symlink')
            tmp_symlink.symlink_to(dst)
            tmp_symlink.replace(src)

    def install(args):
        for category in toposort(args.categories):
            if category.is_not_enabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for command in category.before_install:
                command = command.on_current_platform()
                print()
                print('run{}'.format(command))

                if args.dry_run:
                    continue

                print(
                    subprocess.check_output(
                        command, stderr=subprocess.STDOUT, text=True
                    )
                )

            for location in category.locations:
                src = location.outside_repository()
                dst = location.inside_repository()
                if not src:
                    continue
                print()
                print("symlink(src='{}', dst='{}')".format(src, dst))

                if args.dry_run:
                    continue

                dst.parent.mkdir(parents=True, exist_ok=True)
                symlink_force(src, dst)

            for command in category.after_install:
                command = command.on_current_platform()
                print()
                print('run{}'.format(command))

                if args.dry_run:
                    continue

                print(
                    subprocess.check_output(
                        command, stderr=subprocess.STDOUT, text=True
                    )
                )

    def diff(args):
        for category in toposort(args.categories):
            if category.is_not_enabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.inside_repository()
                dst = location.outside_repository()
                if not dst:
                    continue

                with open_or_empty(src) as src_file:
                    with open_or_empty(dst) as dst_file:
                        print()
                        print(
                            *difflib.unified_diff(
                                src_file.readlines(),
                                dst_file.readlines(),
                                fromfile=str(src),
                                tofile=str(dst),
                                n=0
                            )
                        )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subcommand', required=True)

    installparser = subparsers.add_parser('install')
    installparser.set_defaults(handler=install)
    installparser.add_argument('--dry-run', action='store_true')
    installparser.add_argument(
        'categories',
        nargs='*',
        choices=[''] + [category.name.lower() for category in Category],
        default=''
    )

    diffparser = subparsers.add_parser('diff')
    diffparser.set_defaults(handler=diff)
    diffparser.add_argument(
        'categories',
        nargs='*',
        choices=[''] + [category.name.lower() for category in Category],
        default=''
    )

    args = parser.parse_args()
    print(args)
    args.handler(args)
