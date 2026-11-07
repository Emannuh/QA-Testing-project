package com.example.workbooktools;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * Thin CLI shim used by the MCP server (mcp-server/server.py).
 *
 * Usage:
 *   java -cp workbook-tools.jar com.example.workbooktools.McpHelper <operation> <json>
 *
 * Operations:
 *   generate        { "headers": [...], "rows": [[...], ...] }
 *   generateSample  { "columns": [...], "rowCount": N, "seed": L? }
 *
 * Output: raw .xlsx bytes written to stdout.
 * Errors: JSON {"error": "..."} written to stderr, exit code 1.
 */
public class McpHelper {

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("{\"error\": \"Usage: McpHelper <operation> <json>\"}");
            System.exit(1);
        }

        String operation = args[0];
        String json = args[1];

        ObjectMapper mapper = new ObjectMapper();
        JsonNode root = mapper.readTree(json);
        WorkbookGenerator generator = new WorkbookGenerator();

        byte[] result;

        switch (operation) {
            case "generate" -> {
                List<String> headers = toStringList(root.get("headers"));
                List<List<String>> rows = new ArrayList<>();
                for (JsonNode rowNode : root.get("rows")) {
                    rows.add(toStringList(rowNode));
                }
                result = generator.generate(headers, rows);
            }
            case "generateSample" -> {
                List<ColumnSpec> columns = parseColumns(root.get("columns"));
                int rowCount = root.get("rowCount").asInt();
                if (root.has("seed")) {
                    result = generator.generateSample(columns, rowCount, root.get("seed").asLong());
                } else {
                    result = generator.generateSample(columns, rowCount);
                }
            }
            default -> {
                System.err.println("{\"error\": \"Unknown operation: " + operation + "\"}");
                System.exit(1);
                return;
            }
        }

        System.out.write(result);
        System.out.flush();
    }

    private static List<String> toStringList(JsonNode node) {
        List<String> list = new ArrayList<>();
        for (JsonNode item : node) {
            list.add(item.asText());
        }
        return list;
    }

    private static List<ColumnSpec> parseColumns(JsonNode columnsNode) {
        List<ColumnSpec> specs = new ArrayList<>();
        for (JsonNode col : columnsNode) {
            String type = col.get("type").asText();
            String header = col.get("header").asText();

            ColumnSpec spec = switch (type) {
                case "text" -> {
                    if (col.has("words")) {
                        yield ColumnSpec.text(header, toStringList(col.get("words")));
                    } else {
                        yield ColumnSpec.text(header);
                    }
                }
                case "integer" -> ColumnSpec.integer(header,
                        col.get("min").asLong(), col.get("max").asLong());
                case "decimal" -> ColumnSpec.decimal(header,
                        col.get("min").asDouble(), col.get("max").asDouble());
                case "date" -> ColumnSpec.date(header,
                        LocalDate.parse(col.get("min").asText()),
                        LocalDate.parse(col.get("max").asText()));
                case "choice" -> ColumnSpec.choice(header, toStringList(col.get("options")));
                default -> throw new IllegalArgumentException("Unknown column type: " + type);
            };

            if (col.has("blankProbability")) {
                spec = spec.withBlankProbability(col.get("blankProbability").asDouble());
            }

            specs.add(spec);
        }
        return specs;
    }
}
