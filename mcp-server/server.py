"""
MCP server for workbook-generator.

Exposes three tools:
  - generate_workbook        : build a workbook from explicit headers + rows
  - generate_sample_workbook : generate a workbook with randomised sample data
  - save_workbook            : write a base64 workbook to a file on disk

The server shells out to the fat JAR (workbook-tools-0.0.1-SNAPSHOT.jar) which
includes the McpHelper CLI shim.  Build the JAR first:

    mvn package          # from the repo root

Requires Python 3.11+ and:
    pip install mcp==1.3.0
"""

import asyncio
import base64
import json
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

# ---------------------------------------------------------------------------
# Path to the fat JAR (built with: mvn package)
# ---------------------------------------------------------------------------

JAR = Path(__file__).parent.parent / "target" / "workbook-tools-0.0.1-SNAPSHOT.jar"
JAVA_MAIN = "com.example.workbooktools.McpHelper"

# ---------------------------------------------------------------------------
# Helper: call the JAR
# ---------------------------------------------------------------------------


def _run_java(operation: str, payload: dict) -> bytes:
    """
    Invoke: java -cp <jar> McpHelper <operation> <json>
    Returns raw .xlsx bytes from stdout.
    Raises RuntimeError on non-zero exit.
    """
    if not JAR.exists():
        raise FileNotFoundError(
            f"JAR not found at {JAR}. Run 'mvn package' from the repo root first."
        )
    cmd = ["java", "-cp", str(JAR), JAVA_MAIN, operation, json.dumps(payload)]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")
        raise RuntimeError(f"JAR exited {result.returncode}: {err}")
    return result.stdout


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

app = Server("workbook-generator")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_workbook",
            description=(
                "Build an .xlsx workbook from explicit header and row data. "
                "Returns the workbook as a base64-encoded string."
            ),
            inputSchema={
                "type": "object",
                "required": ["headers", "rows"],
                "properties": {
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'Column headers, e.g. ["Name", "Qty", "Price"]',
                    },
                    "rows": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                        "description": "2-D array of string cell values (one inner array per row).",
                    },
                },
            },
        ),
        Tool(
            name="generate_sample_workbook",
            description=(
                "Build an .xlsx workbook filled with randomised sample data. "
                "Describe each column with a type (text | integer | decimal | date | choice) "
                "and its constraints. Pass a seed for reproducible output."
            ),
            inputSchema={
                "type": "object",
                "required": ["columns", "rowCount"],
                "properties": {
                    "columns": {
                        "type": "array",
                        "description": "Column specifications.",
                        "items": {
                            "type": "object",
                            "required": ["type", "header"],
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["text", "integer", "decimal", "date", "choice"],
                                },
                                "header": {"type": "string"},
                                "min": {
                                    "description": "Min value (number) or ISO-8601 start date (date type)."
                                },
                                "max": {
                                    "description": "Max value (number) or ISO-8601 end date (date type)."
                                },
                                "options": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Fixed choices for 'choice' columns.",
                                },
                                "words": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Custom word list for 'text' columns.",
                                },
                                "blankProbability": {
                                    "type": "number",
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                    "description": "Fraction of cells to leave blank (0.0–1.0).",
                                },
                            },
                        },
                    },
                    "rowCount": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of data rows to generate.",
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Optional random seed for reproducible output.",
                    },
                },
            },
        ),
        Tool(
            name="save_workbook",
            description=(
                "Write a base64-encoded .xlsx workbook to a file on disk. "
                "Returns the absolute path of the saved file."
            ),
            inputSchema={
                "type": "object",
                "required": ["workbookBase64", "destination"],
                "properties": {
                    "workbookBase64": {
                        "type": "string",
                        "description": "Base64-encoded workbook bytes (from generate_workbook or generate_sample_workbook).",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Absolute or relative path where the .xlsx file should be saved.",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[CallToolResult]:
    try:
        if name == "generate_workbook":
            xlsx = _run_java("generate", {
                "headers": arguments["headers"],
                "rows": arguments["rows"],
            })
            return [TextContent(type="text", text=json.dumps({
                "workbookBase64": base64.b64encode(xlsx).decode(),
                "sizeBytes": len(xlsx),
            }))]

        elif name == "generate_sample_workbook":
            payload: dict[str, Any] = {
                "columns": arguments["columns"],
                "rowCount": arguments["rowCount"],
            }
            if "seed" in arguments:
                payload["seed"] = arguments["seed"]
            xlsx = _run_java("generateSample", payload)
            return [TextContent(type="text", text=json.dumps({
                "workbookBase64": base64.b64encode(xlsx).decode(),
                "sizeBytes": len(xlsx),
            }))]

        elif name == "save_workbook":
            raw = base64.b64decode(arguments["workbookBase64"])
            dest = Path(arguments["destination"]).expanduser().resolve()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            return [TextContent(type="text", text=json.dumps({
                "savedTo": str(dest),
                "sizeBytes": len(raw),
            }))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
