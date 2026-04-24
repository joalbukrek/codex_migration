from setuptools import find_namespace_packages, setup


setup(
    name="cli-anything-codex-migrator",
    version="0.1.0",
    description="CLI-Anything harness for migrating Codex Desktop local sessions between macOS user paths.",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    package_data={"cli_anything.codex_migrator": ["SKILL.md"]},
    install_requires=["click>=8.0"],
    entry_points={
        "console_scripts": [
            "cli-anything-codex-migrator=cli_anything.codex_migrator._cli:cli",
            "codex_migration=cli_anything.codex_migrator._cli:cli",
        ],
    },
    python_requires=">=3.9",
)
