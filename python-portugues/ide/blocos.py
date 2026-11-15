"""Modelo de blocos estruturados e geração de código, independente de Tk."""
from __future__ import annotations

import ast
import copy
from dataclasses import asdict, dataclass, field
import keyword
import uuid

from executor import traduzir
from vocabulario import PALAVRAS


TIPOS = {
    'variavel': ('Variável', 'retangulo', '#dbeafe', [('nome', 'Nome', 'valor'), ('valor', 'Valor ou expressão', '0')]),
    'entrada': ('Ler informação', 'paralelogramo', '#ccfbf1', [('nome', 'Guardar em', 'numero'), ('mensagem', 'Pergunta', 'Digite um número: '), ('tipo', 'Tipo de dado', 'inteiro')]),
    'saida': ('Mostrar resultado', 'paralelogramo', '#ccfbf1', [('expressao', 'O que mostrar (expressão)', '"Olá, mundo!"')]),
    'condicao': ('Se / senão', 'losango', '#fef3c7', [('condicao', 'Condição', 'valor > 0')]),
    'repetir': ('Repetir com contador', 'hexagono', '#ede9fe', [('variavel', 'Contador', 'numero'), ('inicio', 'Começar em', '0'), ('fim', 'Parar antes de', '5'), ('passo', 'Passo', '1')]),
    'enquanto': ('Enquanto', 'losango', '#ede9fe', [('condicao', 'Continuar enquanto', 'valor < 10')]),
    'funcao': ('Criar função', 'funcao', '#fce7f3', [('nome', 'Nome da função', 'minha_funcao'), ('parametros', 'Parâmetros separados por vírgula', '')]),
    'retorno': ('Retornar valor', 'retangulo', '#fce7f3', [('expressao', 'Valor retornado', '0')]),
    'chamada': ('Executar expressão', 'funcao', '#dbeafe', [('expressao', 'Chamada ou operação', 'escreva("Olá!")')]),
    'importar': ('Importar biblioteca', 'retangulo', '#e0e7ff', [('modulo', 'Nome da biblioteca', 'matematica'), ('apelido', 'Apelido (opcional)', 'm')]),
    'parar': ('Interromper repetição', 'retangulo', '#fee2e2', []),
    'comentario': ('Anotação', 'nota', '#f1f5f9', [('texto', 'Comentário', 'Explique esta parte do programa')]),
}
CONTAINERS = {'condicao', 'enquanto', 'repetir', 'funcao'}


class ErroDeBloco(ValueError):
    def __init__(self, mensagem, bloco_id=None):
        super().__init__(mensagem)
        self.bloco_id = bloco_id


@dataclass
class Bloco:
    tipo: str
    campos: dict[str, str] = field(default_factory=dict)
    filhos: list['Bloco'] = field(default_factory=list)
    senao: list['Bloco'] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @classmethod
    def novo(cls, tipo):
        if tipo not in TIPOS:
            raise ErroDeBloco('Tipo de bloco desconhecido.')
        return cls(tipo, {nome: valor for nome, _, valor in TIPOS[tipo][3]})

    @classmethod
    def de_dict(cls, dado, vistos=None, profundidade=0):
        if vistos is None:
            vistos = set()
        if profundidade > 40 or len(vistos) >= 1500:
            raise ErroDeBloco('O projeto excede o limite de blocos ou de aninhamento.')
        if not isinstance(dado, dict) or dado.get('tipo') not in TIPOS:
            raise ErroDeBloco('O projeto contém um bloco inválido.')
        identidade = dado.get('id')
        if not isinstance(identidade, str) or not identidade or identidade in vistos:
            raise ErroDeBloco('O projeto contém identificadores ausentes ou repetidos.')
        vistos.add(identidade)
        campos = dado.get('campos')
        esperados = {nome for nome, _, _ in TIPOS[dado['tipo']][3]}
        if not isinstance(campos, dict) or set(campos) != esperados or not all(isinstance(v, str) for v in campos.values()):
            raise ErroDeBloco('Os campos de um bloco estão inválidos.')
        filhos, senao = dado.get('filhos', []), dado.get('senao', [])
        if not isinstance(filhos, list) or not isinstance(senao, list):
            raise ErroDeBloco('Estrutura de blocos inválida.')
        if filhos and dado['tipo'] not in CONTAINERS:
            raise ErroDeBloco('Este bloco não pode conter outros blocos.')
        if senao and dado['tipo'] != 'condicao':
            raise ErroDeBloco('Somente uma condição pode ter um ramo senão.')
        return cls(dado['tipo'], dict(campos),
                   [cls.de_dict(b, vistos, profundidade + 1) for b in filhos],
                   [cls.de_dict(b, vistos, profundidade + 1) for b in senao], identidade)


def percorrer(blocos):
    for bloco in blocos:
        yield bloco
        yield from percorrer(bloco.filhos)
        yield from percorrer(bloco.senao)


class Projeto:
    def __init__(self, blocos=None):
        self.blocos = list(blocos or [])
        self.linhas = {}

    def dados(self):
        return [asdict(bloco) for bloco in self.blocos]

    @classmethod
    def de_dados(cls, dados):
        if not isinstance(dados, list):
            raise ErroDeBloco('Lista de blocos inválida.')
        vistos = set()
        return cls([Bloco.de_dict(b, vistos) for b in dados])

    def buscar(self, identidade):
        return next((b for b in percorrer(self.blocos) if b.id == identidade), None)

    def ramo(self, pai=None, lado='filhos'):
        if pai is None:
            return self.blocos
        bloco = self.buscar(pai)
        if bloco is None or bloco.tipo not in CONTAINERS or lado not in {'filhos', 'senao'}:
            raise ErroDeBloco('Destino inválido para o bloco.')
        if lado == 'senao' and bloco.tipo != 'condicao':
            raise ErroDeBloco('Este bloco não possui ramo senão.')
        return getattr(bloco, lado)

    def localizar(self, identidade):
        def procurar(ramo):
            for indice, bloco in enumerate(ramo):
                if bloco.id == identidade:
                    return ramo, indice
                resultado = procurar(bloco.filhos) or procurar(bloco.senao)
                if resultado:
                    return resultado
            return None
        return procurar(self.blocos)

    def inserir(self, bloco, pai=None, lado='filhos', indice=None):
        destino = self.ramo(pai, lado)
        if len(list(percorrer(self.blocos))) >= 1500:
            raise ErroDeBloco('Limite de 1500 blocos atingido.')
        destino.insert(len(destino) if indice is None else indice, bloco)

    def mover(self, identidade, pai=None, lado='filhos', indice=0):
        origem = self.localizar(identidade)
        if origem is None:
            raise ErroDeBloco('Bloco não encontrado.')
        ramo, posicao = origem
        bloco = ramo[posicao]
        if pai in {b.id for b in percorrer([bloco])}:
            raise ErroDeBloco('Não é possível mover um bloco para dentro dele mesmo.')
        destino = self.ramo(pai, lado)
        if ramo is destino and posicao < indice:
            indice -= 1
        ramo.pop(posicao)
        destino.insert(max(0, min(indice, len(destino))), bloco)

    def excluir(self, identidade):
        local = self.localizar(identidade)
        if local:
            return local[0].pop(local[1])
        return None

    def duplicar(self, identidade):
        local = self.localizar(identidade)
        if not local:
            raise ErroDeBloco('Selecione um bloco para duplicar.')
        copia = copy.deepcopy(local[0][local[1]])
        for bloco in percorrer([copia]):
            bloco.id = uuid.uuid4().hex[:12]
        local[0].insert(local[1] + 1, copia)
        return copia

    def gerar(self):
        linhas = ['# Programa criado na Lume IDE', '']
        self.linhas = {}

        def erro(mensagem, bloco):
            raise ErroDeBloco(mensagem, bloco.id)

        def nome(valor, bloco):
            if not valor.isidentifier() or keyword.iskeyword(valor) or valor in PALAVRAS:
                erro(f'Nome inválido: {valor!r}. Use um identificador que não seja uma palavra reservada.', bloco)
            return valor

        def expressao(valor, bloco):
            if not valor.strip():
                erro('Preencha a expressão do bloco.', bloco)
            try:
                ast.parse(traduzir(valor), mode='eval')
            except (SyntaxError, ValueError):
                erro(f'Expressão inválida: {valor}', bloco)
            return valor.strip()

        def emitir(texto, nivel, bloco=None):
            linhas.append('    ' * nivel + texto)
            if bloco:
                self.linhas[len(linhas)] = bloco.id

        def ramo(blocos, nivel, em_funcao=False, em_laco=False):
            if not blocos:
                emitir('passe', nivel)
                return
            for b in blocos:
                c = b.campos
                if b.tipo == 'variavel':
                    emitir(f'{nome(c["nome"], b)} = {expressao(c["valor"], b)}', nivel, b)
                elif b.tipo == 'entrada':
                    if c['tipo'] not in {'inteiro', 'real', 'texto'}:
                        erro('Escolha inteiro, real ou texto para a entrada.', b)
                    leitura = f'leia({c["mensagem"]!r})'
                    if c['tipo'] != 'texto':
                        leitura = f'{c["tipo"]}({leitura})'
                    emitir(f'{nome(c["nome"], b)} = {leitura}', nivel, b)
                elif b.tipo == 'saida':
                    emitir(f'escreva({expressao(c["expressao"], b)})', nivel, b)
                elif b.tipo == 'condicao':
                    emitir(f'se {expressao(c["condicao"], b)}:', nivel, b)
                    ramo(b.filhos, nivel + 1, em_funcao, em_laco)
                    if b.senao:
                        emitir('senão:', nivel, b)
                        ramo(b.senao, nivel + 1, em_funcao, em_laco)
                elif b.tipo == 'repetir':
                    valores = [expressao(c[chave], b) for chave in ('inicio', 'fim', 'passo')]
                    try:
                        passo_literal = ast.literal_eval(traduzir(c['passo']))
                    except (ValueError, SyntaxError):
                        passo_literal = None
                    if passo_literal == 0:
                        erro('O passo de uma repetição não pode ser zero.', b)
                    emitir(f'para {nome(c["variavel"], b)} em intervalo({", ".join(valores)}):', nivel, b)
                    ramo(b.filhos, nivel + 1, em_funcao, True)
                elif b.tipo == 'enquanto':
                    emitir(f'enquanto {expressao(c["condicao"], b)}:', nivel, b)
                    ramo(b.filhos, nivel + 1, em_funcao, True)
                elif b.tipo == 'funcao':
                    parametros = [p.strip() for p in c['parametros'].split(',') if p.strip()]
                    for parametro in parametros:
                        nome(parametro, b)
                    if len(set(parametros)) != len(parametros):
                        erro('Há parâmetros repetidos na função.', b)
                    emitir(f'função {nome(c["nome"], b)}({", ".join(parametros)}):', nivel, b)
                    ramo(b.filhos, nivel + 1, True, False)
                elif b.tipo == 'retorno':
                    if not em_funcao:
                        erro('Coloque o bloco Retornar dentro de uma função.', b)
                    emitir(f'retorne {expressao(c["expressao"], b)}', nivel, b)
                elif b.tipo == 'chamada':
                    emitir(expressao(c['expressao'], b), nivel, b)
                elif b.tipo == 'importar':
                    for parte in c['modulo'].split('.'):
                        nome(parte, b)
                    apelido = ' como ' + nome(c['apelido'], b) if c['apelido'].strip() else ''
                    emitir('importe ' + c['modulo'] + apelido, nivel, b)
                elif b.tipo == 'parar':
                    if not em_laco:
                        erro('Coloque Interromper dentro de uma repetição.', b)
                    emitir('interrompa', nivel, b)
                elif b.tipo == 'comentario':
                    for linha in c['texto'].splitlines() or ['']:
                        emitir('# ' + linha, nivel, b)
            # Uma anotação não é uma instrução Python suficiente para um corpo.
            if all(b.tipo == 'comentario' for b in blocos):
                emitir('passe', nivel)

        if self.blocos:
            ramo(self.blocos, 0)
        else:
            linhas.append('# Arraste blocos para começar seu programa.')
        return '\n'.join(linhas) + '\n'


def exemplo(nome='soma'):
    def bloco(tipo, **campos):
        b = Bloco.novo(tipo)
        b.campos.update(campos)
        return b
    if nome == 'paridade':
        entrada = bloco('entrada', nome='numero', mensagem='Digite um número inteiro: ')
        condicao = bloco('condicao', condicao='numero % 2 == 0')
        condicao.filhos = [bloco('saida', expressao='"Número par"')]
        condicao.senao = [bloco('saida', expressao='"Número ímpar"')]
        return Projeto([entrada, condicao])
    if nome == 'repeticao':
        repetir = bloco('repetir', variavel='numero', inicio='1', fim='6')
        repetir.filhos = [bloco('saida', expressao='numero, "ao quadrado =", numero ** 2')]
        return Projeto([repetir])
    if nome == 'funcao':
        funcao = bloco('funcao', nome='somar', parametros='a, b')
        funcao.filhos = [bloco('retorno', expressao='a + b')]
        return Projeto([funcao, bloco('variavel', nome='resultado', valor='somar(2, 3)'), bloco('saida', expressao='"Resultado:", resultado')])
    condicao = bloco('condicao', condicao='soma >= 20')
    condicao.filhos = [bloco('saida', expressao='"Chegou a vinte"')]
    condicao.senao = [bloco('saida', expressao='"Resultado:", soma')]
    return Projeto([bloco('variavel', nome='a', valor='2'), bloco('variavel', nome='b', valor='3'), bloco('variavel', nome='soma', valor='a + b'), condicao])
