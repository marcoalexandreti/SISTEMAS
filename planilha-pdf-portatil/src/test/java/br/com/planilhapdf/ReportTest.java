package br.com.planilhapdf;

import java.io.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.time.LocalDate;
import java.util.*;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.*;
import org.apache.pdfbox.text.*;
import org.apache.poi.hssf.usermodel.HSSFWorkbook;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

public class ReportTest {
    @TempDir Path folder;
    private Path write(String name, String text) throws IOException {
        Path path = folder.resolve(name); Files.writeString(path, text); return path;
    }
    private TableData example() {
        List<String> headers = List.of("Ano/Período", "UF", "Município", "NIS", "CPF", "Nome do Aluno", "Data de Nascimento", "Nome do Responsável", "NIS Responsável", "Situação", "Tipo Acompanhamento");
        List<List<String>> rows = List.of(
            List.of("2026(October/November)", "PA", "Município de exemplo", "00000000001", "00000000002", "ALUNO DE EXEMPLO A", "10/11/2017", "RESPONSÁVEL DE EXEMPLO", "00000000003", "NLOC - Aluno não localizado", "6 a 18 anos incompletos (75%)"),
            List.of("2026(October/November)", "PA", "Município de exemplo", "00000000004", "", "ALUNO DE EXEMPLO B", "11/03/2009", "OUTRO RESPONSÁVEL", "00000000005", "NLOC - Aluno não localizado", "6 a 18 anos incompletos (75%)")
        );
        return new TableData(folder.resolve("exemplo.csv"), headers, rows, List.of(), "UTF-8");
    }
    @Test void csvPreambleAndLeadingZeros() throws Exception {
        Path path = write("a.csv", ";;;Relatório emitido\n;;;\nNome do Aluno;NIS;CPF;Data de Nascimento\nEXEMPLO;00000000001;;10/11/2017\n");
        TableData t = SpreadsheetReader.read(path);
        assertEquals(1, t.rows().size()); assertEquals(4, t.headers().size());
        assertEquals("00000000001", t.rows().getFirst().get(1)); assertEquals("", t.rows().getFirst().get(2));
        assertEquals("10/11/2017", t.rows().getFirst().get(3));
    }
    @Test void quotedSeparatorsAndMultilineCells() throws Exception {
        TableData t = SpreadsheetReader.read(write("quoted.csv", "Nome do Aluno;Observação\n\"EXEMPLO; TESTE\";\"Linha 1\nLinha 2\"\n"));
        assertEquals(1, t.rows().size()); assertEquals("EXEMPLO; TESTE", t.rows().getFirst().getFirst());
        assertEquals("Linha 1\nLinha 2", t.rows().getFirst().get(1));
    }
    @Test void windows1252AndCommaDelimiter() throws Exception {
        Path path = folder.resolve("ansi.csv"); Files.write(path, "Nome do Aluno,CPF\nEXEMPLO JOÃO,00000000001\n".getBytes(Charset.forName("windows-1252")));
        TableData t = SpreadsheetReader.read(path);
        assertEquals("Windows-1252", t.encoding()); assertEquals("EXEMPLO JOÃO", t.rows().getFirst().getFirst());
    }
    @Test void utf16BomAndTabs() throws Exception {
        Path path = folder.resolve("utf16.tsv"); Files.write(path, "\uFEFFNome do Aluno\tCPF\nEXEMPLO\t00000000001\n".getBytes(StandardCharsets.UTF_16LE));
        TableData t = SpreadsheetReader.read(path); assertEquals(2, t.headers().size()); assertEquals("00000000001", t.rows().getFirst().get(1));
    }
    @Test void rejectsExtraDataInsteadOfDroppingIt() throws Exception {
        Path path = write("bad.csv", "Nome do Aluno;CPF\nEXEMPLO;00000000001;EXTRA\n");
        assertThrows(IOException.class, () -> SpreadsheetReader.read(path));
    }
    @Test void xlsxFormattedIdsAndFullDate() throws Exception {
        Path path = folder.resolve("exemplo.xlsx");
        try (Workbook w = new XSSFWorkbook()) {
            Sheet s = w.createSheet("Alunos"); Row h = s.createRow(0);
            for (int i = 0; i < 3; i++) h.createCell(i).setCellValue(List.of("Nome do Aluno", "CPF", "Data de Nascimento").get(i));
            Row r = s.createRow(1); r.createCell(0).setCellValue("EXEMPLO"); r.createCell(1).setCellValue(12345);
            CellStyle id = w.createCellStyle(); id.setDataFormat(w.createDataFormat().getFormat("00000000000")); r.getCell(1).setCellStyle(id);
            r.createCell(2).setCellValue(LocalDate.of(2017, 11, 10)); CellStyle date = w.createCellStyle(); date.setDataFormat(w.createDataFormat().getFormat("dd/mm/yy")); r.getCell(2).setCellStyle(date);
            try (OutputStream out = Files.newOutputStream(path)) { w.write(out); }
        }
        TableData t = SpreadsheetReader.read(path);
        assertEquals("00000012345", t.rows().getFirst().get(1)); assertEquals("10/11/2017", t.rows().getFirst().get(2));
    }
    @Test void legacyXls() throws Exception {
        Path path = folder.resolve("exemplo.xls");
        try (Workbook w = new HSSFWorkbook()) {
            Sheet s = w.createSheet(); s.createRow(0).createCell(0).setCellValue("Nome do Aluno"); s.getRow(0).createCell(1).setCellValue("CPF");
            s.createRow(1).createCell(0).setCellValue("EXEMPLO"); s.getRow(1).createCell(1).setCellValue("00000000001");
            try (OutputStream out = Files.newOutputStream(path)) { w.write(out); }
        }
        assertEquals("00000000001", SpreadsheetReader.read(path).rows().getFirst().get(1));
    }
    @Test void allColumnsAndIdentifiersInPdf() throws Exception {
        TableData t = example(); Path path = folder.resolve("completo.pdf");
        var result = PdfReport.generate(t, new ReportOptions("RELATÓRIO DE ALUNOS", "AUTO", true, false, 8.5f, ReportOptions.complete(t)), path);
        assertEquals(2, result.records()); assertEquals(11, result.importedColumns()); assertEquals("A3 horizontal", result.paper());
        try (PDDocument d = Loader.loadPDF(path.toFile())) {
            String text = new PDFTextStripper().getText(d); String flat = text.replaceAll("\\s+", "");
            for (List<String> row : t.rows()) for (String value : row) if (!value.isEmpty()) assertTrue(flat.contains(value.replaceAll("\\s+", "")), "Conteúdo ausente no PDF");
            assertTrue(text.contains("Página 1 de 1"));
            assertBounds(d);
        }
    }
    @Test void a4ConferenceModelWithObservation() throws Exception {
        TableData t = example(); Path path = folder.resolve("conferencia.pdf");
        var result = PdfReport.generate(t, new ReportOptions("RELATÓRIO DE ALUNOS", "A4", true, true, 8.5f, ReportOptions.conference(t)), path);
        assertEquals(7, result.importedColumns()); assertEquals("A4 horizontal", result.paper());
        try (PDDocument d = Loader.loadPDF(path.toFile())) {
            String text = new PDFTextStripper().getText(d); assertTrue(text.contains("Observação")); assertTrue(text.contains("10/11/2017")); assertBounds(d);
        }
    }
    @Test void allColumnsFitA4WithoutClipping() throws Exception {
        TableData t = example(); Path path = folder.resolve("completo-a4.pdf");
        var r = PdfReport.generate(t, new ReportOptions("RELATÓRIO DE ALUNOS", "A4", true, false, 8.5f, ReportOptions.complete(t)), path);
        assertEquals("A4 horizontal", r.paper());
        try (PDDocument d = Loader.loadPDF(path.toFile())) { assertBounds(d); }
    }
    @Test void multipageHeadersAndNoMissingRows() throws Exception {
        TableData base = example(); List<List<String>> rows = new ArrayList<>();
        for (int i = 0; i < 180; i++) { List<String> row = new ArrayList<>(base.rows().getFirst()); row.set(3, String.format("%011d", i + 1)); rows.add(row); }
        TableData t = new TableData(base.source(), base.headers(), rows, List.of(), "UTF-8"); Path path = folder.resolve("long.pdf");
        var result = PdfReport.generate(t, new ReportOptions("RELATÓRIO DE ALUNOS", "A4", true, true, 9, ReportOptions.conference(t)), path);
        assertTrue(result.pages() > 1);
        try (PDDocument d = Loader.loadPDF(path.toFile())) {
            String text = new PDFTextStripper().getText(d);
            for (int i = 1; i <= 180; i++) assertTrue(text.contains(String.format("%011d", i)));
            for (int i = 1; i <= result.pages(); i++) assertTrue(text.contains("Página " + i + " de " + result.pages()));
            assertBounds(d);
        }
    }
    @Test void oversizedRowContinuesWithoutTruncation() throws Exception {
        TableData t = new TableData(folder.resolve("long.csv"), List.of("Nome do Aluno", "Observação"),
            List.of(List.of("EXEMPLO", "conteudo ".repeat(3500) + "MARCADORFINAL")), List.of(), "UTF-8");
        Path path = folder.resolve("continuacao.pdf");
        var r = PdfReport.generate(t, new ReportOptions("TESTE", "A4", false, false, 10, ReportOptions.complete(t)), path);
        assertTrue(r.pages() > 1);
        try (PDDocument d = Loader.loadPDF(path.toFile())) { assertTrue(new PDFTextStripper().getText(d).contains("MARCADORFINAL")); assertBounds(d); }
    }
    @Test void invalidLayoutDoesNotOverwriteExistingFile() throws Exception {
        Path path = write("preservar.pdf", "arquivo anterior");
        assertThrows(IOException.class, () -> PdfReport.generate(example(), new ReportOptions("TESTE", "A4", true, false, 8.5f, List.of()), path));
        assertEquals("arquivo anterior", Files.readString(path));
    }
    private static void assertBounds(PDDocument document) throws IOException {
        new PDFTextStripper() {
            @Override protected void processTextPosition(TextPosition p) {
                assertTrue(p.getXDirAdj() >= 26, "Texto fora da margem esquerda");
                assertTrue(p.getXDirAdj() + p.getWidthDirAdj() <= p.getPageWidth() - 26, "Texto fora da margem direita");
                assertTrue(p.getYDirAdj() >= 10 && p.getYDirAdj() <= p.getPageHeight() - 10, "Texto fora da página");
                super.processTextPosition(p);
            }
        }.getText(document);
    }
}
