"""Packaging shim — do not import.

This file exists only so setuptools can ship the top-level Agent Skill suite
(``skills/arenaforge-*``) inside the wheel as the ``arenaforge.skills_suite`` package (see
``pyproject.toml``). That lets ``arenaforge install`` locate and copy the suite after
a plain ``pip install`` via ``arenaforge.cli.commands.install_cmd.bundled_skills_root``.

It carries no runtime code and is never imported by ArenaForge. The ``arenaforge install``
command copies only ``arenaforge-*`` skill directories, so this module is never
propagated into a target coding-agent's skills directory.
"""
