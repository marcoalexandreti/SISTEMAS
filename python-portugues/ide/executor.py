"""Executor separado da interface: Python em português em modo compatível."""
from __future__ import annotations

import builtins
import io
import linecache
from pathlib import Path
import sys
import tokenize
import traceback

from vocabulario import EXCECOES, FUNCOES, PALAVRAS


def traduzir(codigo: str) -> str:
    """Traduz tokens de nomes; não substitui palavras em strings ou comentários."""
    tokens = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(codigo).readline):
            valor = PALAVRAS.get(token.string, token.string) if token.type == tokenize.NAME else token.string
            tokens.append((token.type, valor))
    except IndentationError:
        raise
    except tokenize.TokenError as erro:
        # A compilação valida indentação e sintaxe; tokens incompletos precisam
        # de um diagnóstico explícito, em vez de executar um programa parcial.
        mensagem, posicao = erro.args
        raise SyntaxError(mensagem, ('<programa>', posicao[0], posicao[1] + 1, '')) from erro
    return tokenize.untokenize(tokens)


def ambiente() -> dict:
    nomes = dict(vars(builtins))
    for portugues, original in {**FUNCOES, **EXCECOES}.items():
        nomes[portugues] = getattr(builtins, original)
    nomes['abra'] = builtins.open
    return nomes


def executar(arquivo: Path, nativo=False) -> int:
    codigo = arquivo.read_text(encoding='utf-8-sig')
    linecache.cache[str(arquivo)] = (len(codigo), None, codigo.splitlines(True), str(arquivo))
    try:
        traduzido = codigo if nativo else traduzir(codigo)
        compilado = compile(traduzido, str(arquivo), 'exec')
        contexto = {'__name__': '__main__', '__file__': str(arquivo), '__builtins__': ambiente()}
        sys.path.insert(0, str(arquivo.parent))
        exec(compilado, contexto)
        return 0
    except SystemExit as erro:
        if erro.code is None:
            return 0
        if isinstance(erro.code, int):
            return erro.code
        print(erro.code, file=sys.stderr)
        return 1
    except SyntaxError as erro:
        linha = erro.lineno or 1
        print(f'Erro de sintaxe na linha {linha}: {erro.msg}', file=sys.stderr)
        linhas = codigo.splitlines()
        if 0 < linha <= len(linhas):
            print(f'    {linhas[linha - 1]}', file=sys.stderr)
        return 1
    except Exception as erro:
        pilha = traceback.extract_tb(erro.__traceback__)
        ocorrencias = [item for item in pilha if item.filename == str(arquivo)]
        local = f' na linha {ocorrencias[-1].lineno}' if ocorrencias else ''
        print(f'Erro de execução{local}: {type(erro).__name__}: {erro}', file=sys.stderr)
        for item in ocorrencias:
            print(f'    Linha {item.lineno}: {item.line or ""}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    argumentos = sys.argv[1:]
    nativo = bool(argumentos and argumentos[0] == '--nativo')
    if nativo:
        argumentos.pop(0)
    if len(argumentos) != 1:
        print('Uso: python executor.py [--nativo] programa.ptpy', file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(executar(Path(argumentos[0]).resolve(), nativo=nativo))
