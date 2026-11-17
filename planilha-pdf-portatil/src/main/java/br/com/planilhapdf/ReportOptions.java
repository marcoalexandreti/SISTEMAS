package br.com.planilhapdf;

import java.util.*;

public record ReportOptions(String title, String paper, boolean alphabetical, boolean observation,
                            float fontSize, List<Integer> columns) {
    public ReportOptions { columns = List.copyOf(columns); }
    public static List<Integer> complete(TableData table) {
        List<Integer> cols = new ArrayList<>();
        for (int i = 0; i < table.headers().size(); i++) cols.add(i);
        return cols;
    }
    public static List<Integer> conference(TableData table) {
        List<Integer> cols = new ArrayList<>();
        for (String name : List.of("Nome do Aluno", "NIS", "CPF", "Data de Nascimento", "Nome do Responsável", "NIS Responsável", "Tipo Acompanhamento")) {
            int index = table.column(name);
            if (index >= 0) cols.add(index);
        }
        return cols.isEmpty() ? complete(table) : cols;
    }
}
