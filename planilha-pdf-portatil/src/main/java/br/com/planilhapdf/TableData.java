package br.com.planilhapdf;

import java.nio.file.Path;
import java.text.Normalizer;
import java.util.*;

public record TableData(Path source, List<String> headers, List<List<String>> rows,
                        List<String> metadata, String encoding) {
    public TableData {
        headers = List.copyOf(headers);
        rows = rows.stream().map(List::copyOf).toList();
        metadata = List.copyOf(metadata);
    }
    public static String key(String value) {
        return Normalizer.normalize(value, Normalizer.Form.NFD).replaceAll("\\p{M}", "")
            .toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }
    public int column(String... names) {
        for (String name : names) for (int i = 0; i < headers.size(); i++)
            if (key(headers.get(i)).equals(key(name))) return i;
        return -1;
    }
}
