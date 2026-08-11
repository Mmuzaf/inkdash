"""Stamp the build with the git version.

PlatformIO's `!command` build flag is not expanded once the option is
interpolated into another section, so the version is injected here instead.
"""

import subprocess

Import("env")  # noqa: F821  provided by PlatformIO


def git_version() -> str:
    try:
        described = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        # A source archive rather than a checkout.
        return "dev"
    return described.stdout.strip().lstrip("v") or "dev"


env.Append(CPPDEFINES=[("INKDASH_VERSION", env.StringifyMacro(git_version()))])  # noqa: F821
