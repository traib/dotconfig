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
        self.save = save
        self.linux = linux
        self.darwin = darwin
        self.windows = windows

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
    locations: tuple[Location]
    before_install: tuple[Command] = ()
    after_install: tuple[Command] = ()

    def is_not_enabled(self) -> bool:
        return all(
            not location.outside_repository() for location in self.locations
        )


class Category(CategoryDescription, enum.Enum):

    VSCODE = CategoryDescription(
        locations=(
            Location(
                # https://code.visualstudio.com/docs/getstarted/settings#_settings-file-locations
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
    import io
    import subprocess
    import tempfile

    def categories(names: tuple[str]) -> tuple[Category]:
        return tuple(Category) if not names else (
            Category[name.upper()] for name in names
        )

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
        for category in categories(args.categories):
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
        for category in categories(args.categories):
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
