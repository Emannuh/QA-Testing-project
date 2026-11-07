# Software-QA — workbook-generator + MCP Server

A Java library that generates `.xlsx` workbooks, wrapped as an **MCP (Model Context Protocol) server** so any MCP-compatible AI agent (Kiro, Claude Desktop, etc.) can create Excel files on demand.

---

## Repository layout

```
Software-QA/
├── src/
│   ├── main/java/com/example/workbooktools/
│   │   ├── WorkbookGenerator.java   # Core library — generate & generateSample
│   │   ├── ColumnSpec.java          # Sealed interface for column types
│   │   └── McpHelper.java           # CLI shim called by the MCP server
│   └── test/java/com/example/workbooktools/
│       └── WorkbookGeneratorTest.java
├── mcp-server/
│   ├── server.py                    # Python MCP server (stdio transport)
│   └── requirements.txt
├── pom.xml                          # Maven build — produces a fat JAR
└── README.md
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Java JDK | 21+ | Compile & run the JAR |
| Maven | 3.9+ | Build the fat JAR |
| Python | 3.11+ | Run the MCP server |
| pip | any | Install Python deps |

---

## Quick start

### 1 — Build the JAR

```bash
cd Software-QA
mvn package -DskipTests
```

This produces `target/workbook-tools-0.0.1-SNAPSHOT.jar` — a fat JAR with all dependencies bundled.

### 2 — Install Python dependencies

```bash
pip install -r mcp-server/requirements.txt
```

### 3 — Run the MCP server

```bash
python mcp-server/server.py
```

The server communicates over **stdio** (standard MCP transport). Connect it from your MCP client config (see below).

---

## Running the tests

```bash
mvn test
```

The test suite covers:
- `generate` — headers and rows round-trip through Apache POI
- `generateSample` — column types, ranges, reproducible seeds
- `withBlankProbability` — nullable cell behaviour
- `choice` columns — only valid options produced
- `writeToFile` — bytes persisted correctly
- Validation — inverted ranges, empty word/option lists, out-of-range probabilities

---

## MCP tools exposed

### `generate_workbook`

Build a workbook from explicit data.

**Input**

```json
{
  "headers": ["Name", "Quantity", "Price"],
  "rows": [
    ["Widget", "5", "9.99"],
    ["Gadget", "3", "14.50"]
  ]
}
```

**Output**

```json
{
  "workbookBase64": "<base64 .xlsx bytes>",
  "sizeBytes": 4821
}
```

---

### `generate_sample_workbook`

Generate a workbook filled with randomised sample data.

**Column types**

| type | required fields | optional fields |
|------|----------------|-----------------|
| `text` | `header` | `words` (custom word list) |
| `integer` | `header`, `min`, `max` | |
| `decimal` | `header`, `min`, `max` | |
| `date` | `header`, `min` (ISO-8601), `max` (ISO-8601) | |
| `choice` | `header`, `options` | |

All column types accept `blankProbability` (0.0–1.0) to leave cells empty.

**Input example**

```json
{
  "columns": [
    { "type": "text",    "header": "Product" },
    { "type": "integer", "header": "Qty",      "min": 1,   "max": 100 },
    { "type": "decimal", "header": "Price",    "min": 1.0, "max": 99.99 },
    { "type": "date",    "header": "OrderDate","min": "2024-01-01", "max": "2024-12-31" },
    { "type": "choice",  "header": "Status",   "options": ["Pending","Shipped","Delivered"] }
  ],
  "rowCount": 50,
  "seed": 42
}
```

**Output**

```json
{
  "workbookBase64": "<base64 .xlsx bytes>",
  "sizeBytes": 7340
}
```

---

### `save_workbook`

Write a base64 workbook to disk.

**Input**

```json
{
  "workbookBase64": "<from generate_workbook or generate_sample_workbook>",
  "destination": "C:/Users/HomePC/Desktop/output.xlsx"
}
```

**Output**

```json
{
  "savedTo": "C:\\Users\\HomePC\\Desktop\\output.xlsx",
  "sizeBytes": 7340
}
```

---

## Connecting to Kiro / Claude Desktop

Add this block to your MCP config file (`.kiro/settings/mcp.json` for Kiro, or `claude_desktop_config.json` for Claude Desktop):

```json
{
  "mcpServers": {
    "workbook-generator": {
      "command": "python",
      "args": ["C:/Users/HomePC/Desktop/Software-QA/mcp-server/server.py"],
      "disabled": false
    }
  }
}
```

> **Tip:** Use `uvx` if you prefer an isolated environment:
> ```json
> {
>   "command": "uvx",
>   "args": ["--from", ".", "python", "mcp-server/server.py"]
> }
> ```

---

## Example agent workflow

```
User:  Generate a 100-row sample workbook with columns for product name,
       quantity (1–500), price ($0.50–$99.99), and order status.
       Save it to my Desktop as orders.xlsx.

Agent: [calls generate_sample_workbook with appropriate column specs]
       [calls save_workbook with destination = Desktop/orders.xlsx]
       Done — saved to C:\Users\HomePC\Desktop\orders.xlsx (12,340 bytes)
```

---

## Architecture

```
MCP Client (Kiro / Claude)
        │  stdio (JSON-RPC)
        ▼
  mcp-server/server.py   ← Python, handles MCP protocol
        │  subprocess
        ▼
  java -cp workbook-tools.jar McpHelper <op> <json>
        │
        ▼
  WorkbookGenerator.java  +  ColumnSpec.java
        │  Apache POI
        ▼
  .xlsx bytes → stdout → base64 → MCP response
```

---

## Tech stack

- **Java 21** — core library
- **Apache POI 5.3.0** — Excel file generation
- **Jackson 2.17.2** — JSON parsing in the CLI shim
- **JUnit Jupiter 5.11.3** — unit tests
- **Maven Shade Plugin** — fat JAR packaging
- **Python 3.11+** / **mcp 1.3.0** — MCP stdio server

---

## License

[MIT](LICENSE)
