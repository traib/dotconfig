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

    def is_disabled(self) -> bool:
        return all(
            not location.outside_repository() for location in self.locations
        )


class Category(CategoryDescription, enum.Enum):

    BASH = CategoryDescription(
        prerequisites=('SH',),
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

    GIT = CategoryDescription(
        locations=(
            Location(
                save='git/config',
                linux='$HOME/.gitconfig',
                darwin='$HOME/.gitconfig',
                windows='$HOME/.gitconfig'
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
                save='vscode/',
                linux='$HOME/.config/Code/',
                darwin='$HOME/Library/Application Support/Code/',
                windows='%APPDATA%/Code/'
            ),
        ),
        after_install=(
            Command(
                'code',
                '--install-extension',
                'vscodevim.vim',
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
    import shutil
    import subprocess
    import tempfile

    def as_categories(
        names: tuple[str], default=tuple(Category)
    ) -> tuple[Category]:
        return default if not names else tuple(
            Category[name.upper()] for name in names
        )

    def topological_sort(names: tuple[str]) -> tuple[Category]:
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
            tmp_symlink.symlink_to(src)
            tmp_symlink.replace(dst)

    def cp_force(src: pathlib.Path, dst: pathlib.Path):
        with tempfile.TemporaryDirectory(
            dir=SCRIPT_DIR.joinpath('tmp')
        ) as tmp_dir:
            tmp_cp = pathlib.Path(tmp_dir).joinpath('cp')
            shutil.copyfile(src, tmp_cp, follow_symlinks=False)
            tmp_cp.replace(dst)

    def install(args):
        for category in topological_sort(args.categories):
            if category.is_disabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for command in category.before_install:
                command = command.on_current_platform()
                print()
                print(f'run{command}')

                if args.dry_run:
                    continue

                print(
                    subprocess.check_output(
                        command, stderr=subprocess.STDOUT, text=True
                    )
                )

            for location in category.locations:
                operation = symlink_force if not args.cp else cp_force
                operation_name = 'symlink' if not args.cp else 'cp'

                src = location.inside_repository()
                dst = location.outside_repository()
                if not dst:
                    continue

                operation_paths = []

                if src.is_file():
                    operation_paths.append((src, dst))

                if src.is_dir():
                    for dirpath, _, filenames in os.walk(src):
                        if not filenames:
                            continue

                        for filename in filenames:
                            dir = pathlib.PurePath(dirpath)
                            rel = dir.relative_to(src).joinpath(filename)
                            operation_paths.append(
                                (src.joinpath(rel), dst.joinpath(rel))
                            )

                for src_path, dst_path in operation_paths:
                    print()
                    print(
                        f"{operation_name}(src='{src_path}', dst='{dst_path}')"
                    )

                    if args.dry_run:
                        continue

                    dst.parent.mkdir(parents=True, exist_ok=True)
                    operation(src_path, dst_path)

            for command in category.after_install:
                command = command.on_current_platform()
                print()
                print(f'run{command}')

                if args.dry_run:
                    continue

                print(
                    subprocess.check_output(
                        command, stderr=subprocess.STDOUT, text=True
                    )
                )

    def diff(args):
        for category in topological_sort(args.categories):
            if category.is_disabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.inside_repository()
                dst = location.outside_repository()
                if not dst:
                    continue

                diff_paths = []

                if src.is_file():
                    diff_paths.append((src, dst))

                if src.is_dir():
                    for dirpath, _, filenames in os.walk(src):
                        if not filenames:
                            continue

                        for filename in filenames:
                            dir = pathlib.PurePath(dirpath)
                            rel = dir.relative_to(src).joinpath(filename)
                            diff_paths.append(
                                (src.joinpath(rel), dst.joinpath(rel))
                            )

                for src_path, dst_path in diff_paths:
                    with open_or_empty(src_path) as src_file:
                        with open_or_empty(dst_path) as dst_file:
                            deltas = list(
                                difflib.unified_diff(
                                    src_file.readlines(),
                                    dst_file.readlines(),
                                    fromfile=str(src_path),
                                    tofile=str(dst_path),
                                    n=0
                                )
                            )
                            if deltas:
                                print()
                                print(''.join(deltas))

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subcommand', required=True)

    installparser = subparsers.add_parser('install')
    installparser.set_defaults(handler=install)
    installparser.add_argument('--dry-run', action='store_true')
    installparser.add_argument('--cp', action='store_true')
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
