#!/usr/bin/env python3
"""Basic Click + nfo integration demo.

Shows NfoGroup auto-logging every command invocation with configurable
terminal output formats.

Usage:
    # Default (color format):
    python demo_basic.py greet World

    # Markdown rendering (requires rich):
    python demo_basic.py greet World --nfo-format markdown

    # TOON compact + SQLite persistence:
    python demo_basic.py greet World --nfo-format toon --nfo-sink sqlite:demo.db

    # Table format:
    python demo_basic.py process --count 5 --nfo-format table
"""

import time
from typing import Any

import click

from nfo.click import NfoGroup, nfo_options


@click.group(cls=NfoGroup)
@nfo_options
def cli(**kwargs):
    """Demo CLI with automatic nfo logging."""
    pass


@cli.command()
@click.argument("name")
def greet(name):
    """Greet someone."""
    click.echo(f"Hello, {name}!")


@cli.command()
@click.option("--count", default=10, help="Number of steps")
def process(count):
    """Run a processing loop."""
    for i in range(count):
        click.echo(f"  Step {i + 1}/{count}")
        time.sleep(0.01)
    click.echo("Done!")


@cli.command()
@click.argument("path")
@click.option("--force", is_flag=True, help="Force deploy")
def deploy(path, force):
    """Deploy to a target path."""
    if force:
        click.echo(f"Force deploying to {path}...")
    else:
        click.echo(f"Deploying to {path}...")
    time.sleep(0.1)
    click.echo("Deploy complete.")


@cli.command()
def fail():
    """Command that fails (demonstrates error logging)."""
    raise RuntimeError("Something went wrong!")


if __name__ == "__main__":
    cli()
