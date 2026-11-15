"""Testes de integração: executar com o interpretador CPython modificado."""
import ast
import pathlib
import subprocess
import sys
import tempfile
import unittest

class PortuguesNativo(unittest.TestCase):
    def executar(self, source, esperado, entrada=None, sufixo='.ptpy'):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = pathlib.Path(pasta) / ('programa' + sufixo)
            arquivo.write_text(source, encoding='utf-8')
            r = subprocess.run([sys.executable, '-X', 'utf8', str(arquivo)], input=entrada,
                               capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, esperado)

    def test_funcao_condicao(self):
        self.executar('função somar(a, b):\n    retorne a+b\nx=somar(2,3)\nse x >= 20:\n    escreva("grande")\nsenão:\n    escreva(x)\n', '5\n')

    def test_ascii_e_lacos(self):
        self.executar('funcao dobro(n):\n    retorne n*2\npara n em intervalo(4):\n    se n == 0:\n        continue\n    senaose n == 3:\n        interrompa\n    senao:\n        escreva(dobro(n))\n', '2\n4\n')

    def test_booleanos(self):
        self.executar('se Verdadeiro e não Falso ou Falso:\n    escreva(Nenhum é Nenhum)\n', 'True\n')

    def test_tipos_e_colecoes(self):
        self.executar('valores = [n*n para n em intervalo(4) se n > 0]\nescreva(valores, tamanho(valores), inteiro("12"), real("2.5"))\n', '[1, 4, 9] 3 12 2.5\n')

    def test_excecoes(self):
        self.executar('tente:\n    inteiro("texto")\nexceto ErroDeValor como erro:\n    escreva("capturado")\nfinalmente:\n    escreva("fim")\n', 'capturado\nfim\n')

    def test_strings_comentarios_e_fstrings(self):
        self.executar('# se para não devem alterar este comentário\nn=3\nescreva("se senão função e não", f"n={n+2}", f"{1 se n>0 senão 2}")\n', 'se senão função e não n=5 1\n')

    def test_stdlib_preservada(self):
        self.executar('importe json\nde math importe sqrt como raiz\nescreva(json.loads("[1,2]"), raiz(25))\n', '[1, 2] 5.0\n')

    def test_classe(self):
        self.executar('classe Contador:\n    função __init__(self, valor):\n        self.valor=valor\n    função obter(self):\n        retorne self.valor\nescreva(Contador(7).obter())\n', '7\n')

    def test_enquanto(self):
        self.executar('n=0\nenquanto n<3:\n    n+=1\nescreva(n)\n', '3\n')

    def test_entrada(self):
        self.executar('idade=inteiro(leia())\nescreva(idade+1)\n', '36\n', entrada='35\n')

    def test_contexto_arquivo(self):
        self.executar('de io importe StringIO\ncom StringIO("abc") como arquivo:\n    escreva(arquivo.read())\n', 'abc\n')

    def test_gerador(self):
        self.executar('função numeros():\n    produza 1\n    produza 2\nescreva(lista(numeros()))\n', '[1, 2]\n')

    def test_async(self):
        self.executar('importe asyncio\nassíncrono função valor():\n    retorne 8\nassíncrono função principal():\n    escreva(aguarde valor())\nasyncio.run(principal())\n', '8\n')

    def test_arquivo_ingles(self):
        self.executar('e=2\nse=3\npara=4\nprint(e+se+para)\n', '9\n', sufixo='.py')

    def test_ast_e_posicoes(self):
        tree = ast.parse('se Verdadeiro:\n    escreva("ação")\n', filename='posicoes.ptpy')
        self.assertIsInstance(tree.body[0], ast.If)
        self.assertEqual(tree.body[0].body[0].lineno, 2)
        self.assertEqual(tree.body[0].body[0].col_offset, 4)

    def test_erro_indica_linha_original(self):
        with self.assertRaises(SyntaxError) as erro:
            compile('x=1\nse Verdadeiro\n    passe\n', 'erro.ptpy', 'exec')
        self.assertEqual(erro.exception.lineno, 2)
        self.assertIn('se Verdadeiro', erro.exception.text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
