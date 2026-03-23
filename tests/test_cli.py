"""Tests for the CLI structure and commands."""

from unittest.mock import patch

from click.testing import CliRunner

from engram.cli import _step4_data_sources, cli


def test_cli_help():
    """Verify engram --help lists all expected commands."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Engram" in result.output
    for cmd in ("init", "server", "mcp", "ingest", "status"):
        assert cmd in result.output


def test_server_command_exists():
    """Verify engram server --help works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["server", "--help"])
    assert result.exit_code == 0
    assert "Start the FastAPI REST API server" in result.output


def test_mcp_command_calls_server():
    """Verify engram mcp calls the MCP server main function."""
    runner = CliRunner()
    with patch("engram.cli.asyncio") as mock_asyncio:
        result = runner.invoke(cli, ["mcp"])
        assert result.exit_code == 0
        mock_asyncio.run.assert_called_once()


def test_ingest_command_lists_exports():
    """Verify engram ingest queries for registered exports."""
    runner = CliRunner()
    with patch("engram.cli.asyncio") as mock_asyncio:
        mock_asyncio.run.return_value = []
        result = runner.invoke(cli, ["ingest"])
        assert result.exit_code == 0
        assert "Processing registered data exports" in result.output


def test_status_command_stub():
    """Verify engram status prints stub message."""
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.output


def test_init_wizard_aborts_without_docker():
    """Mock failed DB connection, verify wizard stops with helpful message."""
    runner = CliRunner()

    with patch("engram.cli.check_postgres", return_value=False):
        result = runner.invoke(cli, ["init"], input="n\n")
        assert result.exit_code == 0
        assert "docker compose up -d" in result.output.lower() or "Docker" in result.output


def test_init_data_sources_skip():
    """Verify the data sources step handles the skip case gracefully."""
    runner = CliRunner()
    # Invoke the step function directly via a click command wrapper
    import click

    @click.command()
    def _run_step4():
        count = _step4_data_sources("postgresql+asyncpg://fake/db")
        click.echo(f"CONFIGURED={count}")

    result = runner.invoke(_run_step4, input="5\n")
    assert result.exit_code == 0
    assert "Skip for now" in result.output
    assert "Skipping data source setup" in result.output
    assert "CONFIGURED=0" in result.output
