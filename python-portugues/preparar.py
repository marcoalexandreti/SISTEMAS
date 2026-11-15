"""Aplica extensões de português ao código-fonte oficial do CPython."""
import hashlib
import json
from pathlib import Path
import tarfile

VERSAO = '3.14.10'
SHA256 = 'de414a57119abef52784d8993e341d53aed635fc2b05c2607d9f98a2c5b72032'
PALAVRAS = {
    'Falso': 'False', 'Nenhum': 'None', 'Verdadeiro': 'True',
    'e': 'and', 'como': 'as', 'afirme': 'assert',
    'assíncrono': 'async', 'assincrono': 'async', 'aguarde': 'await',
    'interrompa': 'break', 'classe': 'class', 'continue': 'continue',
    'função': 'def', 'funcao': 'def', 'defina': 'def', 'apague': 'del',
    'senãose': 'elif', 'senaose': 'elif', 'senão': 'else', 'senao': 'else',
    'exceto': 'except', 'finalmente': 'finally', 'para': 'for',
    'de': 'from', 'global': 'global', 'se': 'if', 'importe': 'import',
    'em': 'in', 'é': 'is', 'eh': 'is', 'lambda': 'lambda',
    'nãolocal': 'nonlocal', 'naolocal': 'nonlocal', 'não': 'not', 'nao': 'not',
    'ou': 'or', 'passe': 'pass', 'lance': 'raise', 'retorne': 'return',
    'tente': 'try', 'enquanto': 'while', 'com': 'with', 'produza': 'yield',
}
FUNCOES = {
    'escreva': 'print', 'leia': 'input', 'inteiro': 'int', 'real': 'float',
    'texto': 'str', 'booleano': 'bool', 'lista': 'list', 'tupla': 'tuple',
    'dicionário': 'dict', 'dicionario': 'dict', 'conjunto': 'set',
    'intervalo': 'range', 'tamanho': 'len', 'soma': 'sum',
    'mínimo': 'min', 'minimo': 'min', 'máximo': 'max', 'maximo': 'max',
    'absoluto': 'abs', 'arredonde': 'round',
    'enumere': 'enumerate', 'ordenado': 'sorted', 'tipo': 'type',
}

def cstr(value):
    # UTF-8 explícito em escapes octais: independente da página de código do MSVC.
    return '"' + ''.join(chr(b) if 32 <= b < 127 and chr(b) not in '\\"' else '\\%03o' % b
                         for b in value.encode('utf-8')) + '"'

def aplicar(raiz):
    arquivo = raiz / 'Parser/pegen.c'
    original = arquivo.read_text(encoding='utf-8')
    if 'PYTHON_PT_NATIVE_KEYWORDS' in original:
        print('Extensão em português já aplicada.'); return
    helper = '''/* PYTHON_PT_NATIVE_KEYWORDS: português apenas em arquivos .ptpy. */
static int
_python_pt_source(Parser *p)
{
    PyObject *filename = p->tok->filename;
    if (filename == NULL || !PyUnicode_Check(filename)) return 0;
    Py_ssize_t length = PyUnicode_GET_LENGTH(filename);
    const char *suffix = ".ptpy";
    if (length < 5) return 0;
    for (int i = 0; i < 5; i++) {
        if (PyUnicode_READ_CHAR(filename, length - 5 + i) != (unsigned char)suffix[i])
            return 0;
    }
    return 1;
}

static const char *
_python_pt_keyword(const char *text, Py_ssize_t length)
{
    static const struct { const char *pt; const char *en; } words[] = {
'''
    helper += ''.join('        {' + cstr(pt) + ', ' + cstr(en) + '},\n' for pt, en in PALAVRAS.items())
    helper += '''        {NULL, NULL}
    };
    for (int i = 0; words[i].pt != NULL; i++) {
        if ((Py_ssize_t)strlen(words[i].pt) == length &&
            memcmp(words[i].pt, text, (size_t)length) == 0)
            return words[i].en;
    }
    return NULL;
}

'''
    anchor = 'static int\ninitialize_token(Parser *p, Token *parser_token, struct token *new_token, int token_type) {'
    assert original.count(anchor) == 1
    original = original.replace(anchor, helper + anchor)
    before = '''    parser_token->type = (token_type == NAME) ? _get_keyword_or_name_type(p, new_token) : token_type;
    parser_token->bytes = PyBytes_FromStringAndSize(new_token->start, new_token->end - new_token->start);'''
    after = '''    const char *text = new_token->start;
    Py_ssize_t text_length = new_token->end - new_token->start;
    struct token translated = *new_token;
    if (token_type == NAME && _python_pt_source(p)) {
        const char *english = _python_pt_keyword(text, text_length);
        if (english != NULL) {
            text = english;
            text_length = (Py_ssize_t)strlen(english);
            translated.start = text;
            translated.end = text + text_length;
            translated.end_col_offset = translated.col_offset + (int)text_length;
        }
    }
    parser_token->type = (token_type == NAME) ? _get_keyword_or_name_type(p, &translated) : token_type;
    parser_token->bytes = PyBytes_FromStringAndSize(text, text_length);'''
    assert original.count(before) == 1
    original = original.replace(before, after)
    builtin = raiz / 'Python/bltinmodule.c'
    content = builtin.read_text(encoding='utf-8')
    additions = '\n    /* PYTHON_PT_NATIVE_BUILTINS: aliases, sem remover a API original. */\n'
    for pt, en in FUNCOES.items():
        additions += '    {\n        PyObject *alias = PyDict_GetItemString(dict, ' + cstr(en) + ');\n        if (alias == NULL) {\n            PyErr_SetString(PyExc_RuntimeError, \"Missing Portuguese builtin target\");\n            return NULL;\n        }\n        SETBUILTIN(' + cstr(pt) + ', alias);\n    }\n'
    for pt, obj in {'ErroDeValor': 'PyExc_ValueError', 'ErroDeTipo': 'PyExc_TypeError',
                    'ErroDeDivisaoPorZero': 'PyExc_ZeroDivisionError', 'Excecao': 'PyExc_Exception'}.items():
        additions += '    SETBUILTIN(' + cstr(pt) + ', ' + obj + ');\n'
    anchor2 = '    debug = PyBool_FromLong(config->optimization_level == 0);'
    assert content.count(anchor2) == 1
    content = content.replace(anchor2, additions + '\n' + anchor2)
    arquivo.write_text(original, encoding='utf-8')
    builtin.write_text(content, encoding='utf-8')
    print('Código-fonte adaptado:', raiz)

def main():
    pasta = Path(__file__).resolve().parent
    raiz = pasta / ('Python-' + VERSAO)
    if not raiz.exists():
        pacote = pasta / ('Python-' + VERSAO + '.tar.xz')
        if hashlib.sha256(pacote.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError('O arquivo-fonte não corresponde ao SHA-256 esperado.')
        with tarfile.open(pacote, 'r:xz') as arquivo:
            # O pacote é oficial e seu hash foi conferido; ainda validamos os caminhos.
            for membro in arquivo.getmembers():
                destino = (pasta / membro.name).resolve()
                if pasta != destino and pasta not in destino.parents:
                    raise RuntimeError('Caminho inválido no pacote.')
                if membro.issym() or membro.islnk():
                    raise RuntimeError('Link não permitido no pacote.')
            arquivo.extractall(pasta, filter='data')
    aplicar(raiz)
    mapa = {'palavras_chave': PALAVRAS, 'funcoes': FUNCOES}
    (pasta / 'vocabulario.json').write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
