#!/bin/sh
# Download and prepare the Scoop programming language toolchain.
set -eu

scoop_error() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

scoop_add_path() {
    scoop_rc=$1
    scoop_path_line=$2
    mkdir -p "$(dirname "$scoop_rc")"
    if [ ! -f "$scoop_rc" ] || ! grep -Fqx "$scoop_path_line" "$scoop_rc"; then
        printf '\n# Scoop programming language\n%s\n' "$scoop_path_line" >> "$scoop_rc"
        printf 'Updated %s\n' "$scoop_rc"
    fi
}

scoop_install() {
    scoop_tag=
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --version)
                [ "$#" -ge 2 ] || scoop_error '--version requires a release version'
                scoop_tag=$2
                shift 2
                ;;
            --)
                shift
                break
                ;;
            -h|--help)
                printf '%s\n' \
                    'Usage: sh install.sh [--version VERSION] [-- POST_INSTALL_OPTIONS...]' \
                    'Install the latest stable Scoop release into ~/.scoop.' \
                    'Examples:' \
                    '  curl -fsSL https://scoop-lang.org/install.sh | sh' \
                    '  sh install.sh --version v1.2.3 -- --jobs 2' \
                    '  sh install.sh -- --all-targets'
                return 0
                ;;
            *) scoop_error "unknown option: $1 (use --help)" ;;
        esac
    done

    [ -n "${HOME:-}" ] || scoop_error 'HOME must be set'
    for scoop_command in curl tar mktemp; do
        command -v "$scoop_command" >/dev/null 2>&1 || scoop_error "$scoop_command is required"
    done
    scoop_system=$(uname -s)
    scoop_machine=$(uname -m)
    case "$scoop_system/$scoop_machine" in
        Darwin/arm64|Darwin/aarch64) scoop_host=aarch64-apple-darwin ;;
        Darwin/x86_64)
            [ "$(sysctl -n hw.optional.arm64 2>/dev/null || true)" = 1 ] || \
                scoop_error 'the macOS release requires Apple Silicon'
            scoop_host=aarch64-apple-darwin
            ;;
        Linux/x86_64|Linux/amd64) scoop_host=x86_64-unknown-linux-gnu ;;
        MINGW*|MSYS*|CYGWIN*)
            scoop_error 'on Windows, use the release archive and post-install.ps1; see https://scoop-lang.org/docs/install.html'
            ;;
        *) scoop_error "unsupported host: $scoop_system/$scoop_machine" ;;
    esac

    scoop_releases=https://github.com/windoze/scoop/releases
    if [ -z "$scoop_tag" ]; then
        scoop_latest=$(curl -fsSLI --retry 3 -o /dev/null -w '%{url_effective}' "$scoop_releases/latest")
        scoop_tag=${scoop_latest##*/}
    fi
    case "$scoop_tag" in
        v[0-9]*) ;;
        [0-9]*) scoop_tag=v$scoop_tag ;;
        *) scoop_error "invalid release version: $scoop_tag" ;;
    esac
    case "$scoop_tag" in
        *[!A-Za-z0-9.+-]*) scoop_error "invalid release version: $scoop_tag" ;;
    esac
    scoop_version=${scoop_tag#v}
    scoop_archive=scoop-$scoop_version-$scoop_host.tar.xz
    scoop_download_dir=$(mktemp -d "${TMPDIR:-$HOME}/scoop-install.XXXXXX")
    trap 'rm -rf "$scoop_download_dir"' 0
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    printf 'Downloading Scoop %s for %s...\n' "$scoop_version" "$scoop_host"
    curl -fSL --retry 3 "$scoop_releases/download/$scoop_tag/$scoop_archive" \
        -o "$scoop_download_dir/$scoop_archive"
    mkdir "$scoop_download_dir/package"
    tar -xJf "$scoop_download_dir/$scoop_archive" -C "$scoop_download_dir/package"
    [ -f "$scoop_download_dir/package/post-install.sh" ] || scoop_error 'archive is missing post-install.sh'

    scoop_install_root=$HOME/.scoop
    mkdir -p "$scoop_install_root"
    # Replace distribution files so an upgrade cannot reuse an old target's slibs.
    # Keep package caches, build results and user-supplied external commands.
    for scoop_component in bin lib include src vendor native libexec docs share tooling; do
        rm -rf "${scoop_install_root:?}/${scoop_component:?}"
    done
    cp -Rp "$scoop_download_dir/package/." "$scoop_install_root/"
    printf 'Building system libraries and API documentation...\n'
    if sh "$scoop_install_root/post-install.sh" "$@"; then
        "$scoop_install_root/bin/scoop" --version
    else
        scoop_exit=$?
        printf 'Installation preparation failed. Fix the reported error, then rerun:\n  sh "%s/post-install.sh"\n' \
            "$scoop_install_root" >&2
        return "$scoop_exit"
    fi

    # Expand the user's variables when the rc file is sourced.
    # shellcheck disable=SC2016
    scoop_path_line='case ":$PATH:" in *":$HOME/.scoop/bin:"*) ;; *) export PATH="$HOME/.scoop/bin:$PATH" ;; esac'
    scoop_shell=${SHELL:-sh}
    case "${scoop_shell##*/}" in
        zsh) scoop_add_path "${ZDOTDIR:-$HOME}/.zshrc" "$scoop_path_line" ;;
        bash)
            scoop_add_path "$HOME/.bashrc" "$scoop_path_line"
            if [ -f "$HOME/.bash_profile" ]; then
                scoop_login_rc=$HOME/.bash_profile
            elif [ -f "$HOME/.bash_login" ]; then
                scoop_login_rc=$HOME/.bash_login
            else
                scoop_login_rc=$HOME/.profile
            fi
            scoop_add_path "$scoop_login_rc" "$scoop_path_line"
            ;;
        fish)
            # shellcheck disable=SC2016
            scoop_add_path "${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish" \
                'fish_add_path --path "$HOME/.scoop/bin"'
            ;;
        *) scoop_add_path "$HOME/.profile" "$scoop_path_line" ;;
    esac
    printf '\nScoop is installed in %s.\nOpen a new shell to use it.\n' "$scoop_install_root"
    # shellcheck disable=SC2016
    printf 'For this shell (sh, bash or zsh):\n  export PATH="$HOME/.scoop/bin:$PATH"\n'
}

# Keep execution at the end so curl | sh reads the whole script before installing.
scoop_install "$@"
