package br.com.planilhapdf;

import java.io.*;
import java.nio.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import org.apache.commons.csv.*;
import org.apache.poi.ss.usermodel.*;

public final class SpreadsheetReader {
    private SpreadsheetReader() {}
    public static TableData read(Path file) throws IOException {
        if (!Files.isRegularFile(file)) throw new IOException("Selecione um arquivo existente.");
        if (Files.size(file) > 80_000_000) throw new IOException("O limite de importação é 80 MB por arquivo.");
        String name = file.getFileName().toString().toLowerCase(Locale.ROOT);
        if (name.endsWith(".xlsx") || name.endsWith(".xls")) return excel(file);
        if (name.endsWith(".csv") || name.endsWith(".tsv") || name.endsWith(".txt")) return csv(file);
        throw new IOException("Formato não aceito. Use CSV, TSV, XLSX ou XLS.");
    }
    private static TableData csv(Path file) throws IOException {
        byte[] bytes = Files.readAllBytes(file);
        String text, encoding;
        if (bytes.length >= 2 && bytes[0] == (byte)0xff && bytes[1] == (byte)0xfe) {
            text = new String(bytes, 2, bytes.length - 2, StandardCharsets.UTF_16LE); encoding = "UTF-16LE";
        } else if (bytes.length >= 2 && bytes[0] == (byte)0xfe && bytes[1] == (byte)0xff) {
            text = new String(bytes, 2, bytes.length - 2, StandardCharsets.UTF_16BE); encoding = "UTF-16BE";
        } else {
            try {
                text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
                encoding = "UTF-8";
            } catch (CharacterCodingException ex) {
                text = new String(bytes, Charset.forName("windows-1252")); encoding = "Windows-1252";
            }
        }
        if (text.startsWith("\uFEFF")) text = text.substring(1);
        List<List<String>> best = null;
        long bestScore = Long.MIN_VALUE;
        IOException failure = null;
        for (char delimiter : new char[] {';', ',', '\t'}) {
            try (CSVParser parser = CSVFormat.DEFAULT.builder().setDelimiter(delimiter)
                    .setIgnoreEmptyLines(false).get().parse(new StringReader(text))) {
                List<List<String>> records = new ArrayList<>();
                for (CSVRecord r : parser) {
                    List<String> row = new ArrayList<>();
                    r.forEach(row::add); records.add(row);
                    if (records.size() > 100_000) throw new IOException("O limite é 100 mil linhas por arquivo.");
                }
                Map<Integer, Integer> lengths = new HashMap<>();
                for (List<String> r : records) if (!empty(r)) lengths.merge(r.size(), 1, Integer::sum);
                long score = lengths.entrySet().stream().filter(e -> e.getKey() > 1)
                    .mapToLong(e -> (long)e.getValue() * e.getKey()).max().orElse(0);
                if (score > bestScore) { bestScore = score; best = records; }
            } catch (UncheckedIOException ex) { failure = ex.getCause(); }
              catch (IOException ex) { failure = ex; }
        }
        if (best == null) throw new IOException("Não foi possível interpretar o CSV. Confira as aspas e o separador.", failure);
        return normalize(file, best, encoding);
    }
    private static TableData excel(Path file) throws IOException {
        try (InputStream input = Files.newInputStream(file); Workbook workbook = WorkbookFactory.create(input)) {
            DataFormatter formatter = new DataFormatter(Locale.forLanguageTag("pt-BR"));
            formatter.setUseCachedValuesForFormulaCells(true);
            Sheet selected = null;
            for (Sheet sheet : workbook) {
                if (sheet.getPhysicalNumberOfRows() > 0 && !workbook.isSheetHidden(workbook.getSheetIndex(sheet))) {
                    selected = sheet; break;
                }
            }
            if (selected == null) throw new IOException("A planilha não contém uma aba visível com dados.");
            if (selected.getLastRowNum() > 100_000) throw new IOException("O limite é 100 mil linhas por arquivo.");
            List<List<String>> records = new ArrayList<>();
            for (Row row : selected) {
                List<String> values = new ArrayList<>();
                int last = Math.max(0, row.getLastCellNum());
                if (last > 200) throw new IOException("A planilha excede o limite de 200 colunas.");
                for (int col = 0; col < last; col++) {
                    Cell cell = row.getCell(col, Row.MissingCellPolicy.RETURN_BLANK_AS_NULL);
                    String value = cell == null ? "" : formatter.formatCellValue(cell);
                    if (cell != null && cell.getCellType() == CellType.NUMERIC && DateUtil.isCellDateFormatted(cell)) {
                        var dt = cell.getLocalDateTimeCellValue();
                        value = dt.format(DateTimeFormatter.ofPattern(dt.toLocalTime().equals(java.time.LocalTime.MIDNIGHT)
                            ? "dd/MM/uuuu" : "dd/MM/uuuu HH:mm:ss"));
                    }
                    values.add(value);
                }
                records.add(values);
            }
            return normalize(file, records, "Excel · " + selected.getSheetName());
        } catch (org.apache.poi.EncryptedDocumentException ex) {
            throw new IOException("A planilha está protegida por senha. Exporte uma cópia CSV ou sem senha.", ex);
        } catch (RuntimeException ex) {
            throw new IOException("Não foi possível abrir o Excel. Confira se o arquivo está íntegro.", ex);
        }
    }
    private static boolean empty(List<String> row) { return row.stream().allMatch(String::isBlank); }
    static TableData normalize(Path file, List<List<String>> records, String encoding) throws IOException {
        int header = -1;
        for (int i = 0; i < Math.min(100, records.size()); i++) {
            List<String> row = records.get(i);
            if (row.stream().anyMatch(s -> TableData.key(s).equals("nomedoaluno"))) { header = i; break; }
        }
        if (header < 0) {
            for (int i = 0; i < records.size(); i++) {
                long nonempty = records.get(i).stream().filter(s -> !s.isBlank()).count();
                if (nonempty >= 2) { header = i; break; }
            }
        }
        if (header < 0) throw new IOException("Não foi encontrado um cabeçalho com pelo menos duas colunas.");
        List<String> headers = new ArrayList<>(records.get(header));
        while (headers.size() > 1 && headers.getLast().isBlank()) headers.removeLast();
        if (headers.size() > 40) throw new IOException("O relatório admite até 40 colunas. Selecione uma tabela menor.");
        Set<String> known = new HashSet<>();
        for (int i = 0; i < headers.size(); i++) {
            String name = headers.get(i).strip();
            if (name.isEmpty()) name = "Coluna " + (i + 1);
            if (!known.add(TableData.key(name))) throw new IOException("Há títulos de coluna repetidos: " + name);
            headers.set(i, name);
        }
        List<String> metadata = new ArrayList<>();
        for (int i = 0; i < header; i++) for (String value : records.get(i))
            if (!value.isBlank() && !metadata.contains(value.strip())) metadata.add(value.strip());
        List<List<String>> rows = new ArrayList<>();
        for (int i = header + 1; i < records.size(); i++) {
            List<String> original = records.get(i);
            if (empty(original)) continue;
            if (original.size() > headers.size() && original.subList(headers.size(), original.size()).stream().anyMatch(s -> !s.isBlank()))
                throw new IOException("A linha " + (i + 1) + " tem dados além das colunas do cabeçalho. Nenhum PDF foi gerado.");
            List<String> row = new ArrayList<>();
            for (int j = 0; j < headers.size(); j++) row.add(j < original.size() ? original.get(j) : "");
            rows.add(row);
        }
        if (rows.isEmpty()) throw new IOException("Não há registros abaixo do cabeçalho.");
        return new TableData(file, headers, rows, metadata, encoding);
    }
}
