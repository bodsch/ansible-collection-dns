"""rndc output parser."""

from __future__ import absolute_import, annotations

from typing import Any


class RndcOutputParser:
    """Parse rndc command output."""

    @staticmethod
    def parse_status(output: str) -> dict[str, Any]:
        """Parse rndc status output.

        Example output:
        version: BIND 9.16.x (...)
        running on hostname
        ...

        Args:
            output: rndc status command output

        Returns:
            Dict with parsed status information
        """
        lines: list[str] = output.split(sep="\n")
        status: dict[str, int | list[Any] | None] = {
            "version": None,
            "hostname": None,
            "zones_loaded": 0,
            "zones": [],
        }

        for line in lines:
            line: str = line.strip()

            if line.startswith("version:"):
                status["version"] = line[8:].strip()
            elif line.startswith("running on"):
                status["hostname"] = line[10:].strip()

        return status

    @staticmethod
    def parse_reload_response(output: str) -> dict[str, Any]:
        """Parse rndc reload response.

        Args:
            output: rndc reload command output

        Returns:
            Dict with reload result
        """
        return {
            "message": output.strip() if output.strip() else "reload successful",
            "zones": [],
        }

    @staticmethod
    def is_success(output: str, stderr: str) -> bool:
        """Determine if command was successful based on output/error.

        Args:
            output: stdout from rndc command
            stderr: stderr from rndc command

        Returns:
            True if output indicates success
        """
        error_indicators = ["error", "failed", "permission denied"]

        combined = (output + stderr).lower()
        return not any(indicator in combined for indicator in error_indicators)
