from path import Path
import sys
import tomlkit
import pytest

import tbump.git
import tbump.hooks
import tbump.main


def add_hook(test_repo: Path, name: str, cmd: str, after_push: bool = False) -> None:
    """ Patch the configuration file so that we can also test hooks.

    """
    cfg_path = test_repo / "pyproject.toml"
    parsed = tomlkit.loads(cfg_path.text())
    if after_push:
        key = "after_push"
    else:
        key = "before_commit"
    if key not in parsed["tool"]["tbump"]:
        parsed["tool"]["tbump"][key] = tomlkit.aot()
    hook_config = tomlkit.table()
    hook_config.add("cmd", cmd)
    hook_config.add("name", name)
    parsed["tool"]["tbump"][key].append(hook_config)
    from pprint import pprint
    pprint(parsed)

    cfg_path.write_text(tomlkit.dumps(parsed))
    tbump.git.run_git(test_repo, "add", ".")
    tbump.git.run_git(test_repo, "commit", "--message", "update hooks")


def add_before_hook(test_repo: Path) -> None:
    """ Patch config to add a working `before_commit` hook
    that runs tbump/test/data/before.py

    """
    add_hook(
        test_repo,
        "fake yarn",
        sys.executable + " before.py {current_version} {new_version}",
    )


def add_after_hook(test_repo: Path) -> None:
    """ Patch config to add a working `after_push` hook
    that runs tbump/test/data/after.py

    """
    add_hook(test_repo, "after hook", sys.executable + " after.py", after_push=True)


def add_crashing_hook(test_repo: Path) -> None:
    """ Patch config to add a `before_commit` hook
    that runs a command that fails
    """
    add_hook(test_repo, "crashing hook", sys.executable + " nosuchfile.py")


def test_working_hook(test_repo: Path) -> None:
    """
    Check that the configured hook runs and properly uses
    current and new version
    """
    add_before_hook(test_repo)
    tbump.main.main(["-C", test_repo, "1.2.41-alpha-2", "--non-interactive"])
    hook_stamp = test_repo / "before-hook.stamp"
    assert hook_stamp.text() == "1.2.41-alpha-1 -> 1.2.41-alpha-2"


def test_hook_fails(test_repo: Path) -> None:
    """
    Check that the proper exception is raised
    if the hooks exits with non-zero return code
    """
    add_before_hook(test_repo)
    add_crashing_hook(test_repo)
    with pytest.raises(tbump.hooks.HookError):
        tbump.main.run(["-C", test_repo, "1.2.41-alpha-2", "--non-interactive"])


def test_hooks_after_push(test_repo: Path) -> None:
    """
    Check that both `before_commit` and `after_push`
    hooks run when tbump is configured with both
    """
    add_before_hook(test_repo)
    add_after_hook(test_repo)
    tbump.main.main(["-C", test_repo, "1.2.41-alpha-2", "--non-interactive"])
    assert (test_repo / "before-hook.stamp").exists()
    assert (test_repo / "after-hook.stamp").exists()
