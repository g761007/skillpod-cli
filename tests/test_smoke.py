from skillpod import __version__
from skillpod.cli import app


def test_version_string() -> None:
    assert isinstance(__version__, str)
    assert __version__


def test_cli_app_is_typer() -> None:
    import typer

    assert isinstance(app, typer.Typer)
