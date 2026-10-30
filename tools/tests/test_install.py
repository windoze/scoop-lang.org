"""Run the piped installer against a local release archive and isolated user homes."""

import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[2] / "install.sh"


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="scoop installer ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.user_home = self.root / "user home"
        self.user_home.mkdir()
        self.commands = self.root / "commands"
        self.commands.mkdir()
        self.package = self.root / "package"
        self.package.mkdir()
        files = {
            "VERSION": "1.2.3\n",
            "bin/scoop": '#!/bin/sh\nprintf "scoop 1.2.3 (test)\\n"\n',
            "src/scoop.core/Cone.toml": '[cone]\nname = "scoop.core"\n',
            "vendor/library/source.c": "/* Vendored source. */\n",
            "commands/scoop-example": "example command",
            "post-install.sh": """#!/bin/sh
printf '%s\\n' "$*" >> "$HOME/post-install-arguments"
if [ "${TEST_POST_INSTALL_FAIL:-0}" != 0 ]; then exit 23; fi
mkdir -p "$HOME/.scoop/lib/test-target" "$HOME/.scoop/docs"
printf 'compiled library' > "$HOME/.scoop/lib/test-target/scoop.core.slib"
printf 'API documentation' > "$HOME/.scoop/docs/index.html"
""",
        }
        for relative, content in files.items():
            path = self.package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        (self.package / "bin/scoop").chmod(0o755)
        self.archive = self.root / "release.tar.xz"
        with tarfile.open(self.archive, "w:xz") as archive:
            archive.add(self.package, arcname=".")
        self.write_command(
            "curl",
            """#!/usr/bin/env python3
import json, os, shutil, sys
from pathlib import Path
arguments = sys.argv[1:]
with open(os.environ["TEST_CURL_LOG"], "a") as log:
    log.write(json.dumps(arguments) + "\\n")
if os.environ.get("TEST_DOWNLOAD_FAIL"):
    sys.exit(22)
if "-w" in arguments:
    print("https://github.com/windoze/scoop/releases/tag/v1.2.3", end="")
else:
    output = arguments[arguments.index("-o") + 1]
    shutil.copyfile(os.environ["TEST_RELEASE_ARCHIVE"], output)
""",
        )
        self.write_command(
            "uname",
            '#!/bin/sh\ncase "$1" in -s) printf "%s\\n" "$TEST_OS" ;; -m) printf "%s\\n" "$TEST_ARCH" ;; esac\n',
        )
        self.environment = dict(os.environ)
        for name in ("ZDOTDIR", "XDG_CONFIG_HOME", "ENV", "BASH_ENV"):
            self.environment.pop(name, None)
        self.environment.update(
            HOME=str(self.user_home),
            TMPDIR=str(self.root),
            SHELL="/bin/bash",
            PATH=str(self.commands) + os.pathsep + os.environ["PATH"],
            TEST_RELEASE_ARCHIVE=str(self.archive),
            TEST_CURL_LOG=str(self.root / "curl.jsonl"),
            TEST_OS="Linux",
            TEST_ARCH="x86_64",
        )

    def write_command(self, name, content):
        command = self.commands / name
        command.write_text(content)
        command.chmod(0o755)

    def install(self, *arguments, success=True):
        result = subprocess.run(
            ["sh", "-s", "--", *arguments],
            input=INSTALLER.read_text(),
            text=True,
            capture_output=True,
            env=self.environment,
            check=False,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def downloads(self):
        return [json.loads(line) for line in (self.root / "curl.jsonl").read_text().splitlines()]

    def test_piped_install_upgrade_and_path_are_repeatable(self):
        for relative in (
            "packages/cache",
            "commands/scoop-custom",
            "lib/old-target/old.slib",
        ):
            path = self.user_home / ".scoop" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("existing data")
        (self.user_home / ".bashrc").write_text("# My shell settings\n")
        for _ in range(2):
            self.install("--", "--jobs", "2")
        install = self.user_home / ".scoop"
        self.assertEqual((install / "VERSION").read_text(), "1.2.3\n")
        self.assertTrue((install / "docs/index.html").is_file())
        self.assertTrue((install / "lib/test-target/scoop.core.slib").is_file())
        self.assertFalse((install / "lib/old-target/old.slib").exists())
        for relative in ("packages/cache", "commands/scoop-custom"):
            self.assertEqual((install / relative).read_text(), "existing data")
        self.assertEqual(
            (self.user_home / "post-install-arguments").read_text(),
            "--jobs 2\n--jobs 2\n",
        )
        for rc in (".bashrc", ".profile"):
            content = (self.user_home / rc).read_text()
            self.assertEqual(content.count("# Scoop programming language"), 1)
        self.assertTrue(
            (self.user_home / ".bashrc").read_text().startswith("# My shell settings\n")
        )
        result = subprocess.run(
            ["sh", "-c", '. "$HOME/.bashrc"; . "$HOME/.bashrc"; printf "%s" "$PATH"'],
            env=self.environment,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.split(os.pathsep).count(str(install / "bin")), 1)
        self.assertIn(
            "https://github.com/windoze/scoop/releases/download/v1.2.3/scoop-1.2.3-x86_64-unknown-linux-gnu.tar.xz",
            self.downloads()[1],
        )

    def test_versioned_macos_install_uses_zdotdir(self):
        self.environment.update(
            TEST_OS="Darwin",
            TEST_ARCH="arm64",
            SHELL="/bin/zsh",
            ZDOTDIR=str(self.root / "zsh config"),
        )
        self.install("--version", "1.2.3")
        self.assertTrue((self.root / "zsh config/.zshrc").is_file())
        self.assertFalse((self.user_home / ".bashrc").exists())
        requests = self.downloads()
        self.assertEqual(len(requests), 1)
        self.assertIn(
            "https://github.com/windoze/scoop/releases/download/v1.2.3/scoop-1.2.3-aarch64-apple-darwin.tar.xz",
            requests[0],
        )

    def test_rosetta_selects_the_native_macos_package(self):
        self.environment.update(TEST_OS="Darwin", TEST_ARCH="x86_64")
        self.write_command("sysctl", "#!/bin/sh\nprintf '1\\n'\n")
        self.install("--version", "v1.2.3")
        self.assertTrue(
            any("aarch64-apple-darwin.tar.xz" in argument for argument in self.downloads()[0])
        )

    def test_fish_config_and_empty_shell(self):
        self.environment.update(
            SHELL="/usr/bin/fish", XDG_CONFIG_HOME=str(self.root / "fish config")
        )
        self.install("--version", "v1.2.3")
        fish = self.root / "fish config/fish/config.fish"
        self.assertIn('fish_add_path --path "$HOME/.scoop/bin"', fish.read_text())
        self.environment["SHELL"] = ""
        self.install("--version", "v1.2.3")
        self.assertTrue((self.user_home / ".profile").is_file())

    def test_existing_bash_login_configuration_is_kept(self):
        profile = self.user_home / ".bash_profile"
        profile.write_text("# Existing login settings\n")
        self.install("--version", "v1.2.3")
        self.assertTrue(profile.read_text().startswith("# Existing login settings\n"))
        self.assertIn(".scoop/bin", profile.read_text())
        self.assertFalse((self.user_home / ".profile").exists())

    def test_download_failure_leaves_existing_installation_and_rc(self):
        old = self.user_home / ".scoop/bin/scoop"
        old.parent.mkdir(parents=True)
        old.write_text("old version")
        self.environment["TEST_DOWNLOAD_FAIL"] = "1"
        self.install("--version", "v1.2.3", success=False)
        self.assertEqual(old.read_text(), "old version")
        self.assertFalse((self.user_home / ".bashrc").exists())

    def test_post_install_failure_does_not_modify_path_or_claim_success(self):
        self.environment["TEST_POST_INSTALL_FAIL"] = "1"
        result = self.install("--version", "v1.2.3", success=False)
        self.assertEqual(result.returncode, 23)
        self.assertFalse((self.user_home / ".bashrc").exists())
        self.assertNotIn("Scoop is installed", result.stdout)
        self.assertIn("rerun", result.stderr)

    def test_unsupported_architecture_and_invalid_version_fail_before_download(self):
        self.environment["TEST_ARCH"] = "aarch64"
        self.install(success=False)
        self.assertFalse((self.root / "curl.jsonl").exists())
        self.environment["TEST_ARCH"] = "x86_64"
        self.install("--version", "v1/invalid", success=False)
        self.assertFalse((self.root / "curl.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
