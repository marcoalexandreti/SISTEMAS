"""Verificações de comportamento do gerador e do executor."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blocos import Bloco, ErroDeBloco, Projeto, exemplo, percorrer
from editor import sugestoes
from executor import executar, traduzir


class Programas(unittest.TestCase):
    def rodar(self, codigo, entradas=()):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'programa.ptpy'
            arquivo.write_text(codigo, encoding='utf-8')
            saida, erros = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erros), patch('builtins.input', side_effect=list(entradas)):
                retorno = executar(arquivo)
            return retorno, saida.getvalue(), erros.getvalue()

    def test_soma_e_decisao(self):
        self.assertEqual(self.rodar(exemplo().gerar()), (0, 'Resultado: 5\n', ''))

    def test_paridade_recebe_inteiros(self):
        for entrada, esperado in [('0', 'Número par'), ('41', 'Número ímpar'), ('-3', 'Número ímpar')]:
            with self.subTest(entrada=entrada):
                self.assertEqual(self.rodar(exemplo('paridade').gerar(), [entrada]), (0, esperado + '\n', ''))

    def test_funcao_retornando_valor(self):
        self.assertEqual(self.rodar(exemplo('funcao').gerar()), (0, 'Resultado: 5\n', ''))

    def test_repeticao_limite_exclusivo(self):
        retorno, texto, erro = self.rodar(exemplo('repeticao').gerar())
        self.assertEqual(retorno, 0, erro)
        self.assertIn('1 ao quadrado = 1', texto)
        self.assertIn('5 ao quadrado = 25', texto)
        self.assertNotIn('6 ao quadrado', texto)

    def test_aninhamento_condicao_em_repeticao(self):
        laco = Bloco.novo('repetir')
        laco.campos.update(inicio='1', fim='4')
        condicao = Bloco.novo('condicao')
        condicao.campos['condicao'] = 'numero % 2 == 0'
        saida = Bloco.novo('saida')
        saida.campos['expressao'] = 'numero'
        condicao.filhos = [saida]
        laco.filhos = [condicao]
        self.assertEqual(self.rodar(Projeto([laco]).gerar()), (0, '2\n', ''))

    def test_corpo_com_apenas_comentario(self):
        condicao = Bloco.novo('condicao')
        condicao.campos['condicao'] = 'Verdadeiro'
        condicao.filhos = [Bloco.novo('comentario')]
        self.assertEqual(self.rodar(Projeto([condicao]).gerar()), (0, '', ''))

    def test_passos_zero_sao_rejeitados(self):
        bloco = Bloco.novo('repetir')
        bloco.campos['passo'] = '0'
        with self.assertRaisesRegex(ErroDeBloco, 'zero'):
            Projeto([bloco]).gerar()

    def test_retorno_fora_de_funcao(self):
        with self.assertRaisesRegex(ErroDeBloco, 'dentro de uma função'):
            Projeto([Bloco.novo('retorno')]).gerar()

    def test_interromper_fora_de_laco(self):
        with self.assertRaisesRegex(ErroDeBloco, 'dentro de uma repetição'):
            Projeto([Bloco.novo('parar')]).gerar()

    def test_nomes_invalidos_e_palavras_reservadas(self):
        for nome in ['2valor', 'se', 'a b', 'if']:
            with self.subTest(nome=nome):
                bloco = Bloco.novo('variavel')
                bloco.campos['nome'] = nome
                with self.assertRaises(ErroDeBloco):
                    Projeto([bloco]).gerar()

    def test_textos_nao_sao_traduzidos(self):
        codigo = '# se e para\nescreva("se e para função", "não")\n'
        self.assertEqual(self.rodar(codigo), (0, 'se e para função não\n', ''))

    def test_expressoes_em_fstrings(self):
        self.assertEqual(self.rodar('escreva(f"{1 se Verdadeiro senão 2}")\n'), (0, '1\n', ''))

    def test_biblioteca_matematica_em_portugues(self):
        self.assertEqual(self.rodar('importe matematica como m\nescreva(m.raiz_quadrada(25), m.fatorial(5))\n'), (0, '5.0 120\n', ''))

    def test_erro_de_execucao_informa_linha(self):
        retorno, _, erro = self.rodar('x = 1\nescreva(x / 0)\n')
        self.assertEqual(retorno, 1)
        self.assertIn('linha 2', erro)

    def test_erro_de_sintaxe_informa_linha(self):
        retorno, _, erro = self.rodar('x = 1\nse Verdadeiro\n    passe\n')
        self.assertEqual(retorno, 1)
        self.assertIn('linha 2', erro)

    def test_movimento_entre_ramos_preserva_conteudo(self):
        projeto = exemplo('paridade')
        condicao = projeto.blocos[1]
        mover = condicao.filhos[0]
        projeto.mover(mover.id, condicao.id, 'senao', 1)
        self.assertFalse(condicao.filhos)
        self.assertEqual(condicao.senao[-1].id, mover.id)
        restaurado = Projeto.de_dados(json.loads(json.dumps(projeto.dados())))
        self.assertEqual(restaurado.gerar(), projeto.gerar())

    def test_movimento_na_mesma_lista(self):
        projeto = exemplo()
        primeiro = projeto.blocos[0]
        projeto.mover(primeiro.id, indice=3)
        self.assertEqual(projeto.blocos[2].id, primeiro.id)

    def test_impede_ciclo_sem_perder_blocos(self):
        projeto = exemplo('paridade')
        condicao = projeto.blocos[1]
        antes = projeto.dados()
        with self.assertRaises(ErroDeBloco):
            projeto.mover(condicao.id, condicao.id)
        self.assertEqual(projeto.dados(), antes)

    def test_duplicacao_identidades_independentes(self):
        projeto = exemplo('paridade')
        original = projeto.blocos[1]
        copia = projeto.duplicar(original.id)
        ids = [b.id for b in percorrer(projeto.blocos)]
        self.assertEqual(len(ids), len(set(ids)))
        copia.filhos[0].campos['expressao'] = '"alterado"'
        self.assertNotEqual(copia.filhos[0].campos, original.filhos[0].campos)

    def test_projeto_corrompido_nao_e_aceito(self):
        dados = exemplo().dados()
        dados[1]['id'] = dados[0]['id']
        with self.assertRaises(ErroDeBloco):
            Projeto.de_dados(dados)

    def test_sugestao_ignora_acentos(self):
        self.assertIn('função', [opcao[0] for opcao in sugestoes('func')])
        self.assertIn('senão', [opcao[0] for opcao in sugestoes('sena')])
        self.assertIn('escreva', [opcao[0] for opcao in sugestoes('escr')])

    def test_mesmo_programa_no_interpretador_nativo(self):
        caminho = os.environ.get('LUME_PYTHON_NATIVO')
        if not caminho:
            self.skipTest('Defina LUME_PYTHON_NATIVO para verificar o interpretador compilado.')
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'programa.ptpy'
            arquivo.write_text(exemplo('funcao').gerar(), encoding='utf-8')
            r = subprocess.run([caminho, '-X', 'utf8', str(Path(__file__).resolve().parents[1] / 'executor.py'), '--nativo', str(arquivo)],
                               capture_output=True, text=True, encoding='utf-8', timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, 'Resultado: 5\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
