package br.com.planilhapdf;

import java.awt.*;
import java.awt.datatransfer.DataFlavor;
import java.io.*;
import java.nio.file.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.List;
import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.filechooser.FileNameExtensionFilter;
import javax.swing.table.DefaultTableModel;

public final class Main {
    static final Color NAVY = new Color(19, 43, 68), BLUE = new Color(33, 99, 165), PALE = new Color(241, 245, 249);
    static final Color GRAY = new Color(91, 110, 127);
    private final JFrame frame = new JFrame("PlanilhaPDF Portátil · Alunos por Situação");
    private final JLabel status = new JLabel("Pronto para importar. Os dados permanecem neste computador.");
    private final JLabel info = new JLabel("Nenhuma planilha importada");
    private final JLabel sourceInfo = new JLabel("Importe um arquivo para conferir os registros.");
    private final JLabel destination = new JLabel();
    private final JTable preview = new JTable();
    private final JProgressBar progress = new JProgressBar();
    private final JButton importButton = new JButton("Importar e gerar PDF");
    private final JButton generateButton = new JButton("Gerar novamente");
    private final JButton openButton = new JButton("Abrir último PDF");
    private final JButton folderButton = new JButton("Escolher pasta...");
    private final JTextField title = new JTextField("RELATÓRIO DE ALUNOS POR SITUAÇÃO");
    private final JComboBox<String> model = new JComboBox<>(new String[]{"Completo · todas as colunas", "Conferência · modelo do PDF"});
    private final JComboBox<String> paper = new JComboBox<>(new String[]{"Automático · melhor ajuste", "A4 horizontal", "A3 horizontal"});
    private final JSpinner font = new JSpinner(new SpinnerNumberModel(8.5, 7.0, 12.0, .5));
    private final JCheckBox alphabetical = new JCheckBox("Ordenar pelo nome do aluno", true);
    private final JCheckBox observation = new JCheckBox("Adicionar coluna de observação", false);
    private final JCheckBox openAutomatically = new JCheckBox("Abrir o PDF ao concluir", true);
    private final JPanel columnsPanel = new JPanel(new GridLayout(0, 1, 3, 3));
    private final List<JCheckBox> columns = new ArrayList<>();
    private TableData table;
    private Path outputFolder = appDirectory().resolve("Relatorios");
    private Path lastPdf;
    private boolean busy;

    public static Path appDirectory() {
        try {
            Path location = Path.of(Main.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            return Files.isDirectory(location) ? location : location.getParent();
        } catch (Exception ex) { return Path.of("").toAbsolutePath(); }
    }
    public static void main(String[] args) {
        if (args.length > 0 && args[0].equals("--gerar")) {
            try {
                if (args.length < 2) throw new IOException("Uso: --gerar arquivo [--saida arquivo.pdf] [--modelo completo|conferencia] [--papel AUTO|A4|A3]");
                Path input = Path.of(args[1]), out = null;
                String template = "completo", page = "AUTO";
                for (int i = 2; i < args.length; i += 2) {
                    if (i + 1 == args.length) throw new IOException("Falta o valor da opção " + args[i]);
                    switch (args[i]) {
                        case "--saida" -> out = Path.of(args[i + 1]);
                        case "--modelo" -> template = args[i + 1];
                        case "--papel" -> page = args[i + 1].toUpperCase(Locale.ROOT);
                        default -> throw new IOException("Opção desconhecida: " + args[i]);
                    }
                }
                if (!Set.of("AUTO", "A4", "A3").contains(page)) throw new IOException("Papel inválido. Use AUTO, A4 ou A3.");
                if (!Set.of("completo", "conferencia").contains(template)) throw new IOException("Modelo inválido.");
                TableData data = SpreadsheetReader.read(input);
                boolean conference = template.equals("conferencia");
                var options = new ReportOptions("RELATÓRIO DE ALUNOS POR SITUAÇÃO", page, true, conference, 8.5f,
                    conference ? ReportOptions.conference(data) : ReportOptions.complete(data));
                if (out == null) out = uniqueOutput(appDirectory().resolve("Relatorios"), input);
                var result = PdfReport.generate(data, options, out);
                System.out.println("PDF gerado: " + result.file());
                System.out.printf("Registros: %d | Colunas importadas: %d | Páginas: %d | Papel: %s%n", result.records(), result.importedColumns(), result.pages(), result.paper());
            } catch (Exception ex) {
                System.err.println("Não foi possível gerar o PDF: " + ex.getMessage());
                System.exit(1);
            }
            return;
        }
        SwingUtilities.invokeLater(() -> {
            try {
                UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
                UIManager.put("FileChooser.openButtonText", "Importar");
                UIManager.put("FileChooser.cancelButtonText", "Cancelar");
                Main app = new Main();
                app.openAutomatically.setSelected(!Arrays.asList(args).contains("--nao-abrir-pdf"));
                app.show();
                if (args.length >= 2 && args[0].equals("--abrir")) app.importFile(Path.of(args[1]));
                else if (args.length > 0 && !args[0].startsWith("--")) app.importFile(Path.of(args[0]));
            } catch (Exception ex) { JOptionPane.showMessageDialog(null, ex.getMessage(), "Erro ao iniciar", JOptionPane.ERROR_MESSAGE); }
        });
    }
    public void show() {
        frame.setDefaultCloseOperation(WindowConstants.DO_NOTHING_ON_CLOSE);
        frame.addWindowListener(new java.awt.event.WindowAdapter() {
            @Override public void windowClosing(java.awt.event.WindowEvent event) {
                if (busy) { JOptionPane.showMessageDialog(frame, "Aguarde a geração terminar antes de fechar ou retirar o pendrive."); return; }
                frame.dispose();
            }
        });
        JPanel root = new JPanel(new BorderLayout(0, 12)); root.setBackground(PALE); root.setBorder(new EmptyBorder(0, 0, 10, 0));
        JPanel header = new JPanel(new BorderLayout()); header.setBackground(NAVY); header.setBorder(new EmptyBorder(18, 24, 18, 24));
        JLabel name = new JLabel("PlanilhaPDF"); name.setFont(new Font("Dialog", Font.BOLD, 25)); name.setForeground(Color.WHITE);
        JLabel subtitle = new JLabel("PORTÁTIL  |  Importar, conferir e gerar"); subtitle.setForeground(new Color(188, 213, 236));
        header.add(name, BorderLayout.WEST); header.add(subtitle, BorderLayout.EAST); root.add(header, BorderLayout.NORTH);

        JPanel left = new JPanel(); left.setLayout(new BoxLayout(left, BoxLayout.Y_AXIS)); left.setBackground(Color.WHITE); left.setBorder(new EmptyBorder(18, 18, 18, 18));
        left.add(label("1. IMPORTAR", true)); left.add(Box.createVerticalStrut(9));
        importButton.setBackground(BLUE); importButton.setForeground(Color.WHITE); importButton.setOpaque(true); importButton.setFont(new Font("Dialog", Font.BOLD, 14));
        stretch(importButton); left.add(importButton); left.add(Box.createVerticalStrut(9));
        left.add(label("CSV, Excel XLSX ou XLS", false)); left.add(Box.createVerticalStrut(16));
        JTextArea drop = new JTextArea("Arraste sua planilha para cá.\nAo importar, o PDF será gerado\nautomaticamente.");
        drop.setEditable(false); drop.setLineWrap(true); drop.setWrapStyleWord(true); drop.setFont(new Font("Dialog", Font.PLAIN, 12));
        drop.setBackground(new Color(233, 242, 250)); drop.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(new Color(197, 216, 234)), new EmptyBorder(14, 12, 14, 12)));
        drop.setMaximumSize(new Dimension(Integer.MAX_VALUE, 90)); drop.setAlignmentX(Component.LEFT_ALIGNMENT); left.add(drop);
        TransferHandler files = new TransferHandler() {
            @Override public boolean canImport(TransferSupport support) { return !busy && support.isDataFlavorSupported(DataFlavor.javaFileListFlavor); }
            @Override public boolean importData(TransferSupport support) {
                if (!canImport(support)) return false;
                try {
                    List<?> items = (List<?>)support.getTransferable().getTransferData(DataFlavor.javaFileListFlavor);
                    if (items.size() != 1) { message("Importe uma planilha de cada vez."); return false; }
                    importFile(((File)items.getFirst()).toPath()); return true;
                } catch (Exception ex) { message("Não foi possível receber o arquivo arrastado."); return false; }
            }
        };
        drop.setTransferHandler(files); frame.setTransferHandler(files);
        left.add(Box.createVerticalStrut(20)); left.add(label("2. AJUSTAR O RELATÓRIO", true)); left.add(Box.createVerticalStrut(10));
        addField(left, "Título", title); addField(left, "Modelo", model); addField(left, "Papel", paper); addField(left, "Fonte (pontos)", font);
        for (JCheckBox check : List.of(alphabetical, observation, openAutomatically)) { check.setBackground(Color.WHITE); check.setAlignmentX(Component.LEFT_ALIGNMENT); left.add(check); }
        left.add(Box.createVerticalStrut(12)); left.add(label("Colunas incluídas no PDF", true)); columnsPanel.setBackground(Color.WHITE); columnsPanel.setAlignmentX(Component.LEFT_ALIGNMENT);
        columnsPanel.add(label("Disponíveis após importar.", false)); left.add(columnsPanel);
        left.add(Box.createVerticalStrut(18)); left.add(label("3. SALVAR NO PENDRIVE", true)); left.add(Box.createVerticalStrut(8));
        destination.setForeground(GRAY); destination.setToolTipText(outputFolder.toString()); destination.setText("Pasta: Relatorios, junto do programa"); destination.setAlignmentX(Component.LEFT_ALIGNMENT); left.add(destination);
        stretch(folderButton); left.add(Box.createVerticalStrut(7)); left.add(folderButton);
        for (JButton button : List.of(generateButton, openButton)) { stretch(button); left.add(Box.createVerticalStrut(8)); left.add(button); button.setEnabled(false); }
        JScrollPane optionsScroll = new JScrollPane(left); optionsScroll.setBorder(null); optionsScroll.setPreferredSize(new Dimension(335, 500)); optionsScroll.getVerticalScrollBar().setUnitIncrement(18);

        JPanel right = new JPanel(new BorderLayout(0, 12)); right.setBackground(Color.WHITE); right.setBorder(new EmptyBorder(18, 18, 18, 18));
        JPanel summary = new JPanel(new GridLayout(0, 1, 0, 6)); summary.setOpaque(false);
        info.setFont(new Font("Dialog", Font.BOLD, 18)); sourceInfo.setForeground(GRAY); summary.add(info); summary.add(sourceInfo);
        JLabel hint = new JLabel("A prévia permite conferir os dados. O PDF repete cabeçalhos e ajusta as quebras de linha."); hint.setForeground(GRAY); hint.setFont(new Font("Dialog", Font.PLAIN, 11)); summary.add(hint); right.add(summary, BorderLayout.NORTH);
        preview.setAutoResizeMode(JTable.AUTO_RESIZE_OFF); preview.setRowHeight(27); preview.setFont(new Font("Dialog", Font.PLAIN, 12));
        preview.getTableHeader().setFont(new Font("Dialog", Font.BOLD, 12)); preview.setGridColor(new Color(220, 228, 236));
        preview.setFillsViewportHeight(true); preview.setSelectionBackground(new Color(212, 231, 249));
        JScrollPane tableScroll = new JScrollPane(preview); tableScroll.setTransferHandler(files); right.add(tableScroll, BorderLayout.CENTER);
        JLabel privacy = new JLabel("Processamento local · CPF/NIS mantidos como texto · Não modifica a planilha original"); privacy.setForeground(GRAY); privacy.setFont(new Font("Dialog", Font.PLAIN, 11)); right.add(privacy, BorderLayout.SOUTH);
        JSplitPane split = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, optionsScroll, right); split.setDividerLocation(335); split.setBorder(new EmptyBorder(0, 14, 0, 14)); split.setResizeWeight(0);
        root.add(split, BorderLayout.CENTER);
        JPanel footer = new JPanel(new BorderLayout(12, 0)); footer.setBackground(PALE); footer.setBorder(new EmptyBorder(2, 20, 0, 20));
        status.setForeground(NAVY); progress.setPreferredSize(new Dimension(140, 17)); progress.setVisible(false); footer.add(status, BorderLayout.CENTER); footer.add(progress, BorderLayout.EAST); root.add(footer, BorderLayout.SOUTH);
        frame.setContentPane(root); frame.setMinimumSize(new Dimension(950, 650));
        Dimension screen = Toolkit.getDefaultToolkit().getScreenSize(); frame.setSize(Math.min(1280, screen.width - 40), Math.min(850, screen.height - 75)); frame.setLocationRelativeTo(null);
        importButton.addActionListener(e -> chooseInput()); generateButton.addActionListener(e -> generate()); openButton.addActionListener(e -> open(lastPdf));
        folderButton.addActionListener(e -> chooseFolder()); model.addActionListener(e -> applyTemplate());
        frame.setVisible(true);
    }
    private static JLabel label(String text, boolean bold) {
        JLabel label = new JLabel(text); label.setFont(new Font("Dialog", bold ? Font.BOLD : Font.PLAIN, bold ? 12 : 11)); label.setForeground(bold ? NAVY : GRAY); label.setAlignmentX(Component.LEFT_ALIGNMENT); return label;
    }
    private static void stretch(JComponent c) { c.setMaximumSize(new Dimension(Integer.MAX_VALUE, 36)); c.setAlignmentX(Component.LEFT_ALIGNMENT); }
    private static void addField(JPanel panel, String text, JComponent component) {
        panel.add(label(text, false)); panel.add(Box.createVerticalStrut(4)); stretch(component); panel.add(component); panel.add(Box.createVerticalStrut(10));
    }
    private void chooseInput() {
        JFileChooser chooser = new JFileChooser(); chooser.setDialogTitle("Importar planilha e gerar PDF");
        chooser.setFileFilter(new FileNameExtensionFilter("Planilhas CSV e Excel", "csv", "tsv", "xlsx", "xls", "txt"));
        if (chooser.showOpenDialog(frame) == JFileChooser.APPROVE_OPTION) importFile(chooser.getSelectedFile().toPath());
    }
    void importFile(Path file) {
        if (busy) return;
        setBusy(true, "Lendo a planilha...");
        new SwingWorker<TableData, Void>() {
            @Override protected TableData doInBackground() throws Exception { return SpreadsheetReader.read(file); }
            @Override protected void done() {
                try {
                    table = get();
                    info.setText(table.rows().size() + " registros  ·  " + table.headers().size() + " colunas");
                    sourceInfo.setText(file.getFileName() + "  |  " + table.encoding()); sourceInfo.setToolTipText(file.toAbsolutePath().toString());
                    DefaultTableModel dataModel = new DefaultTableModel(table.headers().toArray(), 0) {
                        @Override public boolean isCellEditable(int row, int col) { return false; }
                        @Override public Class<?> getColumnClass(int col) { return String.class; }
                    };
                    for (List<String> row : table.rows()) dataModel.addRow(row.toArray());
                    preview.setModel(dataModel);
                    for (int i = 0; i < table.headers().size(); i++) {
                        String k = TableData.key(table.headers().get(i));
                        preview.getColumnModel().getColumn(i).setPreferredWidth(k.contains("nome") || k.contains("acompanhamento") || k.contains("situacao") ? 235 : k.equals("uf") ? 50 : 150);
                    }
                    columns.clear(); columnsPanel.removeAll();
                    for (String name : table.headers()) { JCheckBox box = new JCheckBox(name, true); box.setBackground(Color.WHITE); columns.add(box); columnsPanel.add(box); }
                    applyTemplate(); columnsPanel.revalidate(); columnsPanel.repaint();
                    setBusy(false, "Planilha importada. Preparando PDF...");
                    generate();
                } catch (Exception ex) { setBusy(false, "Importação não concluída."); message(rootMessage(ex)); }
            }
        }.execute();
    }
    private void applyTemplate() {
        if (table == null) return;
        List<Integer> selected = model.getSelectedIndex() == 1 ? ReportOptions.conference(table) : ReportOptions.complete(table);
        for (int i = 0; i < columns.size(); i++) columns.get(i).setSelected(selected.contains(i));
        observation.setSelected(model.getSelectedIndex() == 1);
    }
    private void generate() {
        if (table == null || busy) return;
        List<Integer> selected = new ArrayList<>();
        for (int i = 0; i < columns.size(); i++) if (columns.get(i).isSelected()) selected.add(i);
        if (selected.isEmpty()) { message("Marque pelo menos uma coluna."); return; }
        if (title.getText().isBlank() || title.getText().length() > 180) { message("Informe um título de até 180 caracteres."); return; }
        String page = switch (paper.getSelectedIndex()) { case 1 -> "A4"; case 2 -> "A3"; default -> "AUTO"; };
        int obsColumn = table.column("Observação", "Observacoes");
        boolean addObs = observation.isSelected() && !selected.contains(obsColumn);
        ReportOptions opts = new ReportOptions(title.getText().strip(), page, alphabetical.isSelected(), addObs,
            ((Number)font.getValue()).floatValue(), selected);
        TableData snapshot = table;
        boolean open = openAutomatically.isSelected();
        Path out = uniqueOutput(outputFolder, snapshot.source());
        setBusy(true, "Gerando PDF com todas as linhas e colunas selecionadas...");
        new SwingWorker<PdfReport.Result, Void>() {
            @Override protected PdfReport.Result doInBackground() throws Exception { return PdfReport.generate(snapshot, opts, out); }
            @Override protected void done() {
                try {
                    var result = get(); lastPdf = result.file();
                    setBusy(false, "PDF concluído · " + result.records() + " registros · " + result.pages() + " páginas · " + result.paper());
                    if (open) open(lastPdf);
                } catch (Exception ex) { setBusy(false, "PDF não gerado. Confira a mensagem."); message(rootMessage(ex) + "\n\nSe a pasta estiver sem permissão de escrita, escolha outra pasta de destino."); }
            }
        }.execute();
    }
    static Path uniqueOutput(Path folder, Path input) {
        String stem = input.getFileName().toString().replaceFirst("\\.[^.]+$", "").replaceAll("[<>:\"/\\\\|?*]", "_");
        String stamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss_SSS"));
        Path result = folder.resolve(stem + "_" + stamp + ".pdf");
        int i = 2;
        while (Files.exists(result)) result = folder.resolve(stem + "_" + stamp + "_" + i++ + ".pdf");
        return result;
    }
    private void chooseFolder() {
        JFileChooser chooser = new JFileChooser(outputFolder.toFile()); chooser.setDialogTitle("Pasta para os PDFs"); chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);
        if (chooser.showOpenDialog(frame) == JFileChooser.APPROVE_OPTION) { outputFolder = chooser.getSelectedFile().toPath(); destination.setText("Pasta: " + outputFolder.getFileName()); destination.setToolTipText(outputFolder.toAbsolutePath().toString()); }
    }
    private void open(Path file) {
        if (file == null) return;
        try { if (!Desktop.isDesktopSupported()) throw new IOException(); Desktop.getDesktop().open(file.toFile()); }
        catch (Exception ex) { message("O PDF foi salvo, mas não há leitor disponível para abrir automaticamente.\n\n" + file); }
    }
    private void setBusy(boolean value, String text) {
        busy = value; status.setText(text); progress.setVisible(value); progress.setIndeterminate(value);
        importButton.setEnabled(!value); folderButton.setEnabled(!value); generateButton.setEnabled(!value && table != null); openButton.setEnabled(!value && lastPdf != null);
        model.setEnabled(!value); paper.setEnabled(!value); font.setEnabled(!value); title.setEnabled(!value);
        alphabetical.setEnabled(!value); observation.setEnabled(!value); openAutomatically.setEnabled(!value);
        for (JCheckBox col : columns) col.setEnabled(!value);
    }
    private void message(String text) { JOptionPane.showMessageDialog(frame, text, "PlanilhaPDF", JOptionPane.INFORMATION_MESSAGE); }
    private static String rootMessage(Throwable ex) {
        while (ex instanceof java.util.concurrent.ExecutionException && ex.getCause() != null) ex = ex.getCause();
        return ex.getMessage() == null ? "Não foi possível concluir a operação." : ex.getMessage();
    }
}
