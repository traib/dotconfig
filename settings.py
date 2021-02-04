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
    linux: Optional[str] = None
    darwin: Optional[str] = None
    windows: Optional[str] = None

    def inside_repository(self) -> pathlib.Path:
        assert self.save != ''
        return SCRIPT_DIR.joinpath(self.save)

    def outside_repository(self) -> Optional[pathlib.Path]:
        load = getattr(self, platform.system().lower())
        return None if not load else pathlib.Path(os.path.expandvars(load))


@dataclasses.dataclass(frozen=True)
class Command:
    args: tuple[str]

    def __init__(self, *args):
        object.__setattr__(self, 'args', args)

    def on_current_platform(self) -> tuple[str]:
        assert len(self.args) > 0
        return (shutil.which(self.args[0]),) + self.args[1:]


class CategoryDescription(NamedTuple):
    locations: tuple[Location]
    before_restore: tuple[Command] = ()
    after_restore: tuple[Command] = ()

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
        after_restore=(
            Command(
                'code', '--install-extension', 'vscodevim.vim',
                '--install-extension', 'ms-python.python'
            ),
        ),
    )

    ZSH = CategoryDescription(
        before_restore=(
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

    def copyfile_ignore_same(src: pathlib.Path, dst: pathlib.Path):
        try:
            shutil.copyfile(src, dst)
        except shutil.SameFileError as error:
            print(error, file=sys.stderr)

    def symlink_force(dst: pathlib.Path, src: pathlib.Path):
        with tempfile.TemporaryDirectory(
            dir=SCRIPT_DIR.joinpath('tmp')
        ) as tmp_dir:
            tmp_symlink = pathlib.Path(tmp_dir).joinpath('symlink')
            tmp_symlink.symlink_to(dst)
            tmp_symlink.replace(src)

    def backup(args):
        for category in categories(args.categories):
            if category.is_not_enabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for location in category.locations:
                src = location.outside_repository()
                dst = location.inside_repository()
                if not src:
                    continue
                print()
                print('(src="{}",\n dst="{}")'.format(src, dst))

                if args.dry_run:
                    continue

                dst.parent.mkdir(parents=True, exist_ok=True)
                copyfile_ignore_same(src, dst)

    def restore(args, copyfile=copyfile_ignore_same):
        for category in categories(args.categories):
            if category.is_not_enabled():
                continue
            print()
            print(category)
            print('=' * len(str(category)))

            for command in category.before_restore:
                command = command.on_current_platform()
                print()
                print(command)

                if args.dry_run:
                    continue

                print(
                    subprocess.check_output(
                        command, stderr=subprocess.STDOUT, text=True
                    )
                )

            for location in category.locations:
                src = location.inside_repository()
                dst = location.outside_repository()
                if not dst:
                    continue
                print()
                print('(src="{}",\n dst="{}")'.format(src, dst))

                if args.dry_run:
                    continue

                dst.parent.mkdir(parents=True, exist_ok=True)
                copyfile(src, dst)

            for command in category.after_restore:
                command = command.on_current_platform()
                print()
                print(command)

                if args.dry_run:
                    continue

                print(
                    subprocess.check_output(
                        command, stderr=subprocess.STDOUT, text=True
                    )
                )

    def install(args):
        restore(args, copyfile=symlink_force)

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

    backupparser = subparsers.add_parser('backup')
    backupparser.set_defaults(handler=backup)
    backupparser.add_argument('--dry-run', action='store_true')
    backupparser.add_argument(
        'categories',
        nargs='*',
        choices=[''] + [category.name.lower() for category in Category],
        default=''
    )

    restoreparser = subparsers.add_parser('restore')
    restoreparser.set_defaults(handler=restore)
    restoreparser.add_argument('--dry-run', action='store_true')
    restoreparser.add_argument(
        'categories',
        nargs='*',
        choices=[''] + [category.name.lower() for category in Category],
        default=''
    )

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
