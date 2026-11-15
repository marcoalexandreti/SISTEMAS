"""Fluxos reais em Tk. Execute com um display ou Xvfb disponível."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blocos import Bloco, Projeto, exemplo
from ide import LumeIDE


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'Interface requer uma tela disponível.')
class Interface(unittest.TestCase):
    def setUp(self):
        self.app = LumeIDE()
        self.app.nativo = ''
        self.erros = []
        self.app.report_callback_exception = lambda *e: self.erros.append(''.join(traceback.format_exception(*e)))
        self.app.update()

    def tearDown(self):
        app = self.app
        if app.processo:
            app.processo.kill()
            app.processo.wait(timeout=5)
        for ident in app.tk.call('after', 'info'):
            app.tk.call('after', 'cancel', ident)
        app.editor.fechar_popup()
        app.diagrama.cancelar_arrasto()
        if app.pasta_execucao:
            app.pasta_execucao.cleanup()
        app.destroy()
        self.assertEqual(self.erros, [])

    def aguardar(self, condicao, timeout=6):
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            self.app.update()
            if condicao():
                return
            time.sleep(.01)
        self.fail('O fluxo não terminou no tempo esperado.')

    def widgets(self, raiz):
        yield raiz
        for filho in raiz.winfo_children():
            yield from self.widgets(filho)

    def arrastar_da_paleta(self, titulo, alvo):
        app = self.app
        label = next(w for w in self.widgets(app) if isinstance(w, tk.Label) and w.cget('text') == titulo)
        app.update()
        x = app.diagrama.canvas.winfo_rootx() + alvo['x'] + 90
        y = app.diagrama.canvas.winfo_rooty() + alvo['y'] - app.diagrama.canvas.canvasy(0)
        label.event_generate('<ButtonPress-1>', x=3, y=3)
        label.event_generate('<B1-Motion>', x=int(x - label.winfo_rootx()), y=int(y - label.winfo_rooty()), rootx=int(x), rooty=int(y))
        app.update()
        label.event_generate('<ButtonRelease-1>', x=int(x - label.winfo_rootx()), y=int(y - label.winfo_rooty()), rootx=int(x), rooty=int(y))
        app.update()

    def test_arrastar_forma_cria_bloco(self):
        app = self.app
        app.carregar_projeto(Projeto())
        app.update()
        self.arrastar_da_paleta('Variável', app.diagrama.slots[0])
        self.assertEqual(len(app.projeto.blocos), 1)
        self.assertEqual(app.projeto.blocos[0].tipo, 'variavel')
        self.assertIn('valor = 0', app.editor.obter())

    def test_encaixar_dentro_da_condicao(self):
        app = self.app
        condicao = Bloco.novo('condicao')
        condicao.campos['condicao'] = 'Verdadeiro'
        app.carregar_projeto(Projeto([condicao]))
        app.update()
        alvo = next(s for s in app.diagrama.slots if s['pai'] == condicao.id and s['lado'] == 'filhos')
        self.arrastar_da_paleta('Mostrar resultado', alvo)
        self.assertEqual(condicao.filhos[0].tipo, 'saida')
        self.assertIn('    escreva(', app.projeto.gerar())

    def test_arrastar_bloco_existente_reordena(self):
        app = self.app
        ultimo = app.projeto.blocos[2]
        c = app.diagrama.canvas
        x, y, w, h = app.diagrama.caixas[ultimo.id]
        c.event_generate('<ButtonPress-1>', x=int(x+w/2), y=int(y+h/2))
        alvo = app.diagrama.slots[0]
        c.event_generate('<B1-Motion>', x=int(alvo['x']+80), y=int(alvo['y']))
        app.update()
        c.event_generate('<ButtonRelease-1>', x=int(alvo['x']+80), y=int(alvo['y']))
        app.update()
        self.assertEqual(app.projeto.blocos[0].id, ultimo.id)

    def test_autocompletar_com_tab(self):
        app = self.app
        app.abas.select(1)
        app.editor.definir('escr')
        app.editor.texto.mark_set('insert', 'end-1c')
        app.editor.texto.focus_force()
        app.update()
        app.editor.texto.event_generate('<Control-space>')
        app.update()
        self.assertIsNotNone(app.editor.popup)
        app.editor.texto.event_generate('<Tab>')
        app.update()
        self.assertEqual(app.editor.obter(), 'escreva()')
        self.assertEqual(app.editor.texto.index('insert'), '1.8')

    def test_sugestoes_aparecem_ao_digitar(self):
        app = self.app
        app.abas.select(1)
        app.editor.definir('')
        app.editor.texto.focus_force()
        app.update()
        app.editor.texto.insert('insert', 'escr')
        app.editor.texto.event_generate('<KeyRelease>', keysym='r')
        app.update()
        self.assertIsNotNone(app.editor.popup)
        self.assertEqual(app.editor.opcoes[0][0], 'escreva')

    def test_alterar_blocos_preserva_edicao_manual(self):
        app = self.app
        app.editor.definir('escreva("manual")\n')
        app.codigo_editado()
        app.projeto.blocos[0].campos['valor'] = '10'
        app.alteracao_visual()
        self.assertEqual(app.editor.obter(), 'escreva("manual")\n')

    def test_desfazer_e_refazer(self):
        app = self.app
        antes = app.projeto.dados()
        app.soltar_bloco({'tipo': 'saida'}, None)
        depois = app.projeto.dados()
        self.assertNotEqual(antes, depois)
        app.desfazer()
        self.assertEqual(app.projeto.dados(), antes)
        app.refazer()
        self.assertEqual(app.projeto.dados(), depois)

    def test_salvar_e_reabrir_preserva_blocos_e_texto(self):
        app = self.app
        app.editor.definir('escreva("edição manual")\n')
        app.codigo_editado()
        blocos = app.projeto.dados()
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = str(Path(pasta) / 'exemplo.lume.json')
            with patch('ide.filedialog.asksaveasfilename', return_value=arquivo):
                self.assertTrue(app.salvar())
            app.carregar_projeto(Projeto())
            with patch('ide.filedialog.askopenfilename', return_value=arquivo):
                app.abrir()
            self.assertEqual(app.projeto.dados(), blocos)
            self.assertEqual(app.editor.obter(), 'escreva("edição manual")\n')
            self.assertTrue(app.manual)

    def test_execucao_interativa_no_console(self):
        app = self.app
        app.carregar_projeto(exemplo('paridade'))
        app.executar()
        self.aguardar(lambda: 'Digite um número' in app.console.get('1.0', 'end'))
        app.entrada.set('41')
        app.enviar_entrada()
        self.aguardar(lambda: app.processo is None)
        self.assertIn('Número ímpar', app.console.get('1.0', 'end'))
        self.assertIn('Concluído', app.exec_status.get())
        self.assertEqual(str(app.campo_entrada.cget('state')), 'disabled')

    def test_parar_programa_com_repeticao_infinita(self):
        app = self.app
        app.abas.select(1)
        app.editor.definir('enquanto Verdadeiro:\n    passe\n')
        app.executar()
        self.assertIsNotNone(app.processo)
        app.parar()
        self.aguardar(lambda: app.processo is None)
        self.assertIn('Interrompido', app.exec_status.get())

    def test_console_e_entrada_visiveis_na_janela(self):
        app = self.app
        self.assertGreater(app.campo_entrada.winfo_height(), 20)
        self.assertLess(app.campo_entrada.winfo_rooty() + app.campo_entrada.winfo_height(), app.winfo_rooty() + app.winfo_height())

    def test_propriedades_tem_rolagem_em_janela_menor(self):
        app = self.app
        app.geometry('1080x700')
        app.carregar_projeto(exemplo('repeticao'))
        app.selecionar_bloco(app.projeto.blocos[0].id)
        app.update()
        canvas = app.rolagem_propriedades
        canvas.yview_moveto(1)
        app.update()
        self.assertGreater(canvas.yview()[0], 0)
        self.assertEqual(canvas.yview()[1], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
