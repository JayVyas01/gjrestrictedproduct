import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The demo CSV files (backend/demo/csv_export.py), read on the host: docker-compose.demo.yml
// bind-mounts ./demo-data (at the repository root) into the backend, which rewrites the files
// after every change. They hold the demo passwords: the test harness reads them, the app never.
const DEMO_DATA = fileURLToPath(new URL("../../demo-data/", import.meta.url));

export type CsvFile = "parties.csv" | "officials.csv" | "transactions.csv";
export type CsvRow = Record<string, string>;

/** RFC 4180 fields: commas and line breaks inside double quotes, "" for a quote. */
function parse(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[index + 1] === "\n") index += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

/** Every row of a demo CSV file, keyed by the header row's column names. */
export function readCsv(file: CsvFile): CsvRow[] {
  const [header, ...rows] = parse(readFileSync(DEMO_DATA + file, "utf8"));
  if (!header) throw new Error(`e2e: demo-data/${file} is empty`);
  return rows.map((cells) => Object.fromEntries(header.map((name, i) => [name, cells[i] ?? ""])));
}

/** The one row whose `column` is `value`, or undefined (the file may not have caught up yet). */
export function csvRow(file: CsvFile, column: string, value: string): CsvRow | undefined {
  return readCsv(file).find((row) => row[column] === value);
}
