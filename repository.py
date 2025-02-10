import dataclasses
import enum
import os
import pathlib
import platform
import shutil
from typing import NamedTuple, Optional

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPOSITORY = SCRIPT_DIR.joinpath("repository")


@dataclasses.dataclass(frozen=True)
class Location:
    repo: str
    linux: Optional[str]
    darwin: Optional[str]
    windows: Optional[str]

    def __init__(self, repo, linux=None, darwin=None, windows=None):
        assert repo
        object.__setattr__(self, "repo", repo)
        object.__setattr__(self, "linux", linux)
        object.__setattr__(self, "darwin", darwin)
        object.__setattr__(self, "windows", windows)

    def inside_repository(self) -> pathlib.Path:
        return REPOSITORY.joinpath(self.repo)

    def outside_repository(self) -> Optional[pathlib.Path]:
        load = getattr(self, platform.system().lower())
        return None if not load else pathlib.Path(os.path.expandvars(load))


@dataclasses.dataclass(frozen=True)
class Command:
    args: tuple[str]

    def __init__(self, *args):
        assert args
        object.__setattr__(self, "args", args)

    def on_current_platform(self) -> tuple[str]:
        return (shutil.which(self.args[0]),) + self.args[1:]


class CategoryDescription(NamedTuple):
    prerequisites: tuple[str] = ()
    before_install: tuple[Command] = ()
    locations: tuple[Location] = ()
    after_install: tuple[Command] = ()

    def is_disabled(self) -> bool:
        return all(not location.outside_repository() for location in self.locations)


class Category(CategoryDescription, enum.Enum):
    BASH = CategoryDescription(
        prerequisites=("SH",),
        locations=(
            Location(
                repo="bash/bash_profile",
                linux="$HOME/.bash_profile",
                darwin="$HOME/.bash_profile",
                windows="$HOME/.bash_profile",
            ),
            Location(
                repo="bash/bashrc",
                linux="$HOME/.bashrc",
                darwin="$HOME/.bashrc",
                windows="$HOME/.bashrc",
            ),
        ),
    )

    BREW = CategoryDescription(
        locations=(
            # https://docs.brew.sh/Manpage#bundle-subcommand
            Location(
                repo="brew/Brewfile",
                linux="$HOME/.Brewfile",
                darwin="$HOME/.Brewfile",
                windows="$HOME/.Brewfile",
            ),
        ),
        after_install=(Command("brew", "bundle", "upgrade", "--global"),),
    )

    GIT = CategoryDescription(
        locations=(
            Location(
                repo="git/config",
                linux="$HOME/.gitconfig",
                darwin="$HOME/.gitconfig",
                windows="$HOME/.gitconfig",
            ),
        ),
    )

    SH = CategoryDescription(
        locations=(
            Location(
                repo="sh/inputrc",
                linux="$HOME/.inputrc",
                darwin="$HOME/.inputrc",
                windows="$HOME/.inputrc",
            ),
            Location(
                repo="sh/profile",
                linux="$HOME/.profile",
                darwin="$HOME/.profile",
                windows="$HOME/.profile",
            ),
        ),
    )

    VSCODE = CategoryDescription(
        locations=(
            # https://code.visualstudio.com/docs/getstarted/settings#_settings-file-locations
            Location(
                repo="vscode/",
                linux="$HOME/.config/Code/",
                darwin="$HOME/Library/Application Support/Code/",
                windows="%APPDATA%/Code/",
            ),
        ),
    )

    ZSH = CategoryDescription(
        prerequisites=("SH",),
        before_install=(
            Command(
                "curl",
                "--silent",
                "--show-error",
                "https://raw.githubusercontent.com/grml/grml-etc-core/master/etc/zsh/zshrc",
                "--output",
                REPOSITORY.joinpath("zsh/zshrc"),
            ),
        ),
        locations=(
            # https://wiki.archlinux.org/index.php/zsh#Startup/Shutdown_files
            Location(
                repo="zsh/zshrc.pre",
                linux="$HOME/.zshrc.pre",
                darwin="$HOME/.zshrc.pre",
            ),
            Location(repo="zsh/zshrc", linux="$HOME/.zshrc", darwin="$HOME/.zshrc"),
            Location(
                repo="zsh/zshrc.local",
                linux="$HOME/.zshrc.local",
                darwin="$HOME/.zshrc.local",
            ),
        ),
    )
