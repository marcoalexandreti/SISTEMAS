package br.com.planilhapdf;

import java.awt.Color;
import java.io.*;
import java.nio.file.*;
import java.text.Collator;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.List;
import org.apache.pdfbox.pdmodel.*;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.*;

public final class PdfReport {
    private static final Color NAVY = new Color(25, 64, 101), GRID = new Color(193, 205, 216);
    private static final Color INK = new Color(32, 45, 59), LIGHT = new Color(241, 246, 250);
    private static final float MARGIN = 28, PAD = 5;
    public record Result(Path file, int pages, int records, int importedColumns, String paper) {}
    private final PDDocument document = new PDDocument();
    private PDFont normal, bold;
    private PDPageContentStream stream;
    private float width, height, y, headerHeight, fontSize, lineHeight;
    private float[] widths;
    private List<String> labels;
    private List<List<String>> headerLines;
    private TableData table;
    private ReportOptions options;
    private String paperName;

    public static Result generate(TableData table, ReportOptions options, Path target) throws IOException {
        return new PdfReport().create(table, options, target);
    }
    private Result create(TableData data, ReportOptions settings, Path target) throws IOException {
        this.table = data; this.options = settings;
        if (options.title().isBlank() || options.title().length() > 180) throw new IOException("Informe um título de até 180 caracteres.");
        if (options.columns().isEmpty()) throw new IOException("Selecione pelo menos uma coluna.");
        if (options.columns().size() > 18) throw new IOException("Para preservar a leitura, selecione até 18 colunas por relatório.");
        for (int col : options.columns()) if (col < 0 || col >= table.headers().size()) throw new IOException("Coluna inválida.");
        fontSize = options.fontSize();
        if (fontSize < 7 || fontSize > 12) throw new IOException("Use tamanho de fonte entre 7 e 12 pontos.");
        lineHeight = fontSize * 1.35f;
        boolean a3 = options.paper().equals("A3") || (options.paper().equals("AUTO") && options.columns().size() >= 10);
        PDRectangle base = a3 ? PDRectangle.A3 : PDRectangle.A4;
        width = base.getHeight(); height = base.getWidth();
        paperName = a3 ? "A3 horizontal" : "A4 horizontal";
        Path absolute = target.toAbsolutePath();
        Files.createDirectories(absolute.getParent());
        Path temp = Files.createTempFile(absolute.getParent(), ".planilha-pdf-", ".tmp");
        boolean success = false;
        try (document) {
            try (InputStream a = resource("/fonts/DejaVuSans.ttf"); InputStream b = resource("/fonts/DejaVuSans-Bold.ttf")) {
                normal = PDType0Font.load(document, a, true);
                bold = PDType0Font.load(document, b, true);
            }
            document.getDocumentInformation().setTitle(options.title());
            document.getDocumentInformation().setCreator("PlanilhaPDF Portátil 1.0");
            labels = new ArrayList<>(); labels.add("Nº");
            for (int index : options.columns()) labels.add(table.headers().get(index));
            if (options.observation()) labels.add("Observação");
            widths = calculateWidths(labels, width - MARGIN * 2);
            headerLines = new ArrayList<>();
            int maxHeaderLines = 1;
            for (int i = 0; i < labels.size(); i++) {
                List<String> wrapped = wrap(labels.get(i), bold, fontSize, widths[i] - PAD * 2);
                headerLines.add(wrapped); maxHeaderLines = Math.max(maxHeaderLines, wrapped.size());
            }
            headerHeight = maxHeaderLines * lineHeight + PAD * 2;
            List<List<String>> rows = new ArrayList<>(table.rows());
            int student = table.column("Nome do Aluno");
            if (options.alphabetical() && student >= 0) {
                Collator collator = Collator.getInstance(Locale.forLanguageTag("pt-BR"));
                rows.sort((a, b) -> collator.compare(a.get(student), b.get(student)));
            }
            newPage();
            for (int index = 0; index < rows.size(); index++) {
                List<String> values = new ArrayList<>(); values.add(String.valueOf(index + 1));
                for (int col : options.columns()) values.add(rows.get(index).get(col));
                if (options.observation()) {
                    int original = table.column("Observação", "Observacoes");
                    values.add(original >= 0 ? rows.get(index).get(original) : "");
                }
                List<List<String>> cells = new ArrayList<>();
                int lines = 1;
                for (int c = 0; c < values.size(); c++) {
                    List<String> wrapped = wrap(values.get(c), normal, fontSize, widths[c] - PAD * 2);
                    cells.add(wrapped); lines = Math.max(lines, wrapped.size());
                }
                drawRow(cells, lines, index);
            }
            stream.close(); stream = null;
            int pages = document.getNumberOfPages();
            for (int i = 0; i < pages; i++) {
                try (PDPageContentStream footer = new PDPageContentStream(document, document.getPage(i), PDPageContentStream.AppendMode.APPEND, true, true)) {
                    text(footer, normal, 7.5f, INK, MARGIN, 17,
                        "PlanilhaPDF · " + table.rows().size() + " registros · " + paperName);
                    String number = "Página " + (i + 1) + " de " + pages;
                    text(footer, normal, 7.5f, INK, width - MARGIN - measure(number, normal, 7.5f), 17, number);
                }
            }
            document.save(temp.toFile());
            try { Files.move(temp, absolute, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); }
            catch (AtomicMoveNotSupportedException ex) { Files.move(temp, absolute, StandardCopyOption.REPLACE_EXISTING); }
            success = true;
            return new Result(absolute, pages, rows.size(), options.columns().size(), paperName);
        } catch (IllegalArgumentException ex) {
            throw new IOException("Há um caractere ou configuração não suportado pelo PDF. Confira os dados; nenhum conteúdo foi truncado.", ex);
        } finally {
            if (stream != null) stream.close();
            if (!success) Files.deleteIfExists(temp);
        }
    }
    private static InputStream resource(String path) throws IOException {
        InputStream stream = PdfReport.class.getResourceAsStream(path);
        if (stream == null) throw new IOException("Recurso do programa ausente: " + path);
        return stream;
    }
    private static float weight(String header) {
        String key = TableData.key(header);
        if (key.equals("no") || key.equals("n")) return 3;
        if (key.equals("uf")) return 3.5f;
        if (key.contains("nome") || key.contains("observa")) return 22;
        if (key.contains("acompanhamento")) return 18;
        if (key.contains("municipio") || key.contains("situacao")) return 17;
        if (key.contains("periodo")) return 12;
        if (key.contains("nascimento")) return 10;
        if (key.contains("nis") || key.equals("cpf")) return 10.5f;
        return 13;
    }
    private float[] calculateWidths(List<String> headers, float available) throws IOException {
        float[] result = new float[headers.size()];
        float sum = 0;
        for (String s : headers) sum += weight(s);
        for (int i = 0; i < result.length; i++) result[i] = available * weight(headers.get(i)) / sum;
        for (int i = 0; i < result.length; i++) {
            String k = TableData.key(headers.get(i));
            if (k.contains("nis") || k.equals("cpf")) result[i] = Math.max(result[i], measure("00000000000", normal, fontSize) + PAD * 2);
            if (k.equals("uf")) result[i] = Math.max(result[i], 25);
            if (i == 0) result[i] = Math.max(result[i], 26);
            if (k.contains("nascimento")) result[i] = Math.max(result[i], measure("00/00/0000", normal, fontSize) + PAD * 2);
        }
        float excess = 0;
        for (float n : result) excess += n;
        excess -= available;
        if (excess > 0) {
            float shrinkable = 0;
            for (int i = 0; i < result.length; i++) if (weight(headers.get(i)) >= 12) shrinkable += Math.max(0, result[i] - 40);
            if (shrinkable < excess) throw new IOException("As colunas não cabem com esta fonte. Escolha A3, diminua a fonte ou selecione menos colunas.");
            for (int i = 0; i < result.length; i++) if (weight(headers.get(i)) >= 12)
                result[i] -= excess * Math.max(0, result[i] - 40) / shrinkable;
        }
        return result;
    }
    private void newPage() throws IOException {
        if (stream != null) stream.close();
        PDPage page = new PDPage(new PDRectangle(width, height)); document.addPage(page);
        stream = new PDPageContentStream(document, page);
        y = height - MARGIN;
        List<String> title = wrap(options.title(), bold, 15, width - MARGIN * 2);
        for (String line : title) { text(stream, bold, 15, NAVY, MARGIN, y - 14, line); y -= 20; }
        String summary = table.rows().size() + " registros  |  " + options.columns().size() + " colunas da planilha  |  " + paperName;
        text(stream, normal, 8, INK, MARGIN, y - 11, summary); y -= 18;
        String source = "Arquivo: " + table.source().getFileName() + "  |  Gerado em " + LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd/MM/uuuu HH:mm"));
        for (String line : wrap(source, normal, 7.5f, width - MARGIN * 2)) {
            text(stream, normal, 7.5f, INK, MARGIN, y - 9, line); y -= 12;
        }
        y -= 8;
        drawCells(headerLines, 0, headerLines.stream().mapToInt(List::size).max().orElse(1), headerHeight, true, -1);
        if (y < 35 + lineHeight + PAD * 2) throw new IOException("O cabeçalho ficou grande demais. Use títulos de coluna menores ou papel A3.");
    }
    private void drawRow(List<List<String>> cells, int lines, int row) throws IOException {
        float fullHeight = lines * lineHeight + PAD * 2;
        float pageBody = height - MARGIN - 120 - headerHeight - 35;
        if (y - fullHeight < 35 && fullHeight <= pageBody) newPage();
        int offset = 0;
        while (offset < lines) {
            int capacity = (int)Math.floor((y - 35 - PAD * 2) / lineHeight);
            if (capacity < 1) { newPage(); continue; }
            int count = Math.min(lines - offset, capacity);
            drawCells(cells, offset, count, count * lineHeight + PAD * 2, false, row);
            offset += count;
            if (offset < lines) newPage();
        }
    }
    private void drawCells(List<List<String>> cells, int offset, int count, float rowHeight, boolean header, int row) throws IOException {
        float x = MARGIN;
        for (int c = 0; c < cells.size(); c++) {
            stream.setNonStrokingColor(header ? NAVY : (row % 2 == 0 ? Color.WHITE : LIGHT));
            stream.addRect(x, y - rowHeight, widths[c], rowHeight); stream.fill();
            stream.setStrokingColor(GRID); stream.setLineWidth(.35f);
            stream.addRect(x, y - rowHeight, widths[c], rowHeight); stream.stroke();
            List<String> lines = cells.get(c);
            for (int line = offset; line < Math.min(lines.size(), offset + count); line++) {
                String value = lines.get(line);
                boolean center = header || c == 0 || TableData.key(labels.get(c)).matches("uf|cpf|nis.*|datadenascimento");
                float tx = center ? x + (widths[c] - measure(value, header ? bold : normal, fontSize)) / 2 : x + PAD;
                text(stream, header ? bold : normal, fontSize, header ? Color.WHITE : INK,
                    tx, y - PAD - fontSize - (line - offset) * lineHeight, value);
            }
            x += widths[c];
        }
        y -= rowHeight;
    }
    static List<String> wrap(String input, PDFont font, float size, float maxWidth) throws IOException {
        List<String> lines = new ArrayList<>();
        String text = input.replace('\t', ' ').replace('\u0000', ' ');
        for (String paragraph : text.split("\\R", -1)) {
            if (paragraph.isBlank()) { lines.add(""); continue; }
            String current = "";
            for (String word : paragraph.strip().split("\\s+")) {
                if (!current.isEmpty() && measure(current + " " + word, font, size) <= maxWidth) { current += " " + word; continue; }
                if (!current.isEmpty()) { lines.add(current); current = ""; }
                for (int start = 0; start < word.length();) {
                    int end = start;
                    while (end < word.length()) {
                        int next = end + Character.charCount(word.codePointAt(end));
                        if (measure(word.substring(start, next), font, size) > maxWidth) break;
                        end = next;
                    }
                    if (end == start) throw new IOException("Uma coluna está estreita demais. Use A3 ou uma fonte menor.");
                    String part = word.substring(start, end);
                    if (end < word.length()) lines.add(part); else current = part;
                    start = end;
                }
            }
            if (!current.isEmpty()) lines.add(current);
        }
        return lines.isEmpty() ? List.of("") : lines;
    }
    private static float measure(String text, PDFont font, float size) throws IOException { return font.getStringWidth(text) * size / 1000; }
    private static void text(PDPageContentStream s, PDFont font, float size, Color color, float x, float y, String text) throws IOException {
        if (text.isEmpty()) return;
        s.beginText(); s.setFont(font, size); s.setNonStrokingColor(color); s.newLineAtOffset(x, y); s.showText(text); s.endText();
    }
}
