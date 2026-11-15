"""Lume IDE: editor e programação visual em português. Python 3.12+."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tema import FONTE_UI, FONTE_CODIGO

from blocos import Bloco, CONTAINERS, ErroDeBloco, Projeto, TIPOS, exemplo, percorrer
from diagrama import Diagrama, forma
from editor import Editor
from executor import traduzir

PASTA = Path(__file__).resolve().parent
CONFIG = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.config'))) / 'LumeIDE' / 'preferencias.json'


class LumeIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Lume IDE · Programe em português')
        self.geometry(f'{min(1380, self.winfo_screenwidth() - 50)}x{min(900, self.winfo_screenheight() - 100)}')
        self.minsize(1000, 640)
        self.configure(bg='#f1f5f9')
        self.projeto = exemplo()
        self.caminho = None
        self.sujo = False
        self.manual = False
        self.selecionado = None
        self.campos = {}
        self.historico = [self.projeto.dados()]
        self.posicao_historico = 0
        self.eventos = queue.Queue(maxsize=50000)
        self.processo = None
        self.pasta_execucao = None
        self.interrompido = False
        self.inicio_execucao = 0
        self._fechando = False
        self.nativo = ''
        try:
            preferencias = json.loads(CONFIG.read_text(encoding='utf-8'))
            if isinstance(preferencias, dict) and isinstance(preferencias.get('interpretador'), str):
                self.nativo = preferencias['interpretador']
        except (OSError, ValueError):
            pass
        self.status = tk.StringVar(value='Arraste um bloco da biblioteca para uma linha com +.')
        self.modo = tk.StringVar(value='Código gerado pelos blocos')
        self.exec_status = tk.StringVar(value='Pronto para executar')
        self.entrada = tk.StringVar()
        self.estilo()
        self.montar()
        self.editor.definir(self.projeto.gerar())
        self.mostrar_propriedades()
        self.protocol('WM_DELETE_WINDOW', self.fechar)
        self.bind('<Control-s>', lambda _: self.salvar())
        self.bind('<Control-o>', lambda _: self.abrir())
        self.bind('<Control-n>', lambda _: self.novo())
        self.bind('<Control-Shift-S>', lambda _: self.exportar())
        self.bind('<F5>', lambda _: self.executar())
        self.bind('<Shift-F5>', lambda _: self.parar())
        self.bind('<Control-d>', self.atalho_duplicar)
        self.bind('<Control-z>', self.atalho_desfazer)
        self.bind('<Control-y>', self.atalho_refazer)
        self.bind('<Escape>', lambda _: self.diagrama.cancelar_arrasto())
        self.after(60, self.processar_eventos)

    def estilo(self):
        estilo = ttk.Style(self)
        estilo.theme_use('clam')
        estilo.configure('.', font=(FONTE_UI, 10), background='#f1f5f9', foreground='#172033')
        estilo.configure('TFrame', background='#f1f5f9')
        estilo.configure('Painel.TFrame', background='white')
        estilo.configure('TLabel', background='#f1f5f9')
        estilo.configure('Painel.TLabel', background='white')
        estilo.configure('TButton', padding=(10, 7), background='white', borderwidth=1, bordercolor='#dbe3ef')
        estilo.map('TButton', background=[('active', '#ede9fe')])
        estilo.configure('Primario.TButton', background='#7c3aed', foreground='white', bordercolor='#7c3aed', padding=(16, 8))
        estilo.map('Primario.TButton', background=[('active', '#6d28d9'), ('disabled', '#c4b5fd')])
        estilo.configure('TNotebook', background='#f1f5f9', borderwidth=0)
        estilo.configure('TNotebook.Tab', padding=(19, 10), background='#e2e8f0')
        estilo.map('TNotebook.Tab', background=[('selected', 'white')], foreground=[('selected', '#7c3aed')])
        estilo.configure('TEntry', padding=6)
        estilo.configure('TCombobox', padding=5)

    def montar(self):
        menu = tk.Menu(self)
        arquivo = tk.Menu(menu, tearoff=False)
        for texto, comando in [('Novo projeto   Ctrl+N', self.novo), ('Abrir…   Ctrl+O', self.abrir),
                                ('Salvar projeto…   Ctrl+S', self.salvar), ('Exportar código .ptpy…', self.exportar)]:
            arquivo.add_command(label=texto, command=comando)
        arquivo.add_separator()
        arquivo.add_command(label='Sair', command=self.fechar)
        menu.add_cascade(label='Arquivo', menu=arquivo)
        editar = tk.Menu(menu, tearoff=False)
        editar.add_command(label='Desfazer nos blocos', command=self.desfazer)
        editar.add_command(label='Refazer nos blocos', command=self.refazer)
        editar.add_command(label='Duplicar bloco   Ctrl+D', command=self.duplicar)
        editar.add_command(label='Excluir bloco', command=self.excluir)
        menu.add_cascade(label='Editar', menu=editar)
        exemplos = tk.Menu(menu, tearoff=False)
        for titulo, nome in [('Soma e condição', 'soma'), ('Par ou ímpar com entrada', 'paridade'), ('Repetição de 1 a 5', 'repeticao'), ('Criar e chamar uma função', 'funcao')]:
            exemplos.add_command(label=titulo, command=lambda n=nome: self.carregar_exemplo(n))
        menu.add_cascade(label='Exemplos', menu=exemplos)
        menu.add_command(label='Interpretador', command=self.preferencias)
        menu.add_command(label='Ajuda', command=self.ajuda)
        self.configure(menu=menu)

        cabecalho = tk.Frame(self, bg='#172033', padx=22, pady=15)
        cabecalho.pack(fill='x')
        tk.Label(cabecalho, text='lume', bg='#172033', fg='white', font=(FONTE_UI, 23, 'bold')).pack(side='left')
        tk.Label(cabecalho, text='IDE EM PORTUGUÊS', bg='#172033', fg='#a5b4fc', font=(FONTE_UI, 9, 'bold')).pack(side='left', padx=20)
        tk.Label(cabecalho, text='Imagine. Encaixe. Execute.', bg='#172033', fg='#cbd5e1', font=(FONTE_UI, 11)).pack(side='right')
        barra = ttk.Frame(self, padding=(15, 10))
        barra.pack(fill='x')
        ttk.Button(barra, text='Novo', command=self.novo).pack(side='left', padx=(0, 5))
        ttk.Button(barra, text='Abrir', command=self.abrir).pack(side='left', padx=5)
        ttk.Button(barra, text='Salvar projeto', command=self.salvar).pack(side='left', padx=5)
        ttk.Button(barra, text='Exportar .ptpy', command=self.exportar).pack(side='left', padx=5)
        ttk.Button(barra, text='Verificar', command=self.verificar).pack(side='left', padx=5)
        self.botao_rodar = ttk.Button(barra, text='Executar · F5', style='Primario.TButton', command=self.executar)
        self.botao_rodar.pack(side='right', padx=(7, 0))
        self.botao_parar = ttk.Button(barra, text='Parar', command=self.parar, state='disabled')
        self.botao_parar.pack(side='right')

        ttk.Label(self, textvariable=self.status, padding=(18, 8), foreground='#64748b', font=(FONTE_UI, 9), anchor='w').pack(side='bottom', fill='x')
        principal = ttk.Panedwindow(self, orient='vertical')
        self.divisor = principal
        principal.pack(fill='both', expand=True, padx=14)
        corpo = ttk.Frame(principal)
        principal.add(corpo, weight=5)
        self.montar_paleta(corpo)
        painel_propriedades = ttk.Frame(corpo, style='Painel.TFrame', width=280)
        painel_propriedades.pack(side='right', fill='y', padx=(10, 0))
        painel_propriedades.pack_propagate(False)
        self.rolagem_propriedades = tk.Canvas(painel_propriedades, bg='white', highlightthickness=0)
        barra_propriedades = ttk.Scrollbar(painel_propriedades, command=self.rolagem_propriedades.yview)
        barra_propriedades.pack(side='right', fill='y')
        self.rolagem_propriedades.pack(fill='both', expand=True)
        self.rolagem_propriedades.configure(yscrollcommand=barra_propriedades.set)
        self.inspector = ttk.Frame(self.rolagem_propriedades, style='Painel.TFrame', padding=16)
        janela_propriedades = self.rolagem_propriedades.create_window(0, 0, window=self.inspector, anchor='nw')
        self.inspector.bind('<Configure>', lambda _: self.rolagem_propriedades.configure(scrollregion=self.rolagem_propriedades.bbox('all')))
        self.rolagem_propriedades.bind('<Configure>', lambda e: self.rolagem_propriedades.itemconfigure(janela_propriedades, width=e.width))
        centro = ttk.Frame(corpo)
        centro.pack(side='left', fill='both', expand=True, padx=(10, 0))
        self.abas = ttk.Notebook(centro)
        self.abas.pack(fill='both', expand=True)
        visual = ttk.Frame(self.abas)
        self.diagrama = Diagrama(visual, lambda: self.projeto, self.selecionar_bloco, self.soltar_bloco, self.excluir)
        self.diagrama.pack(fill='both', expand=True)
        self.abas.add(visual, text='Montagem visual')
        codigo = ttk.Frame(self.abas)
        ferramentas = ttk.Frame(codigo, padding=(10, 8))
        ferramentas.pack(fill='x')
        ttk.Label(ferramentas, textvariable=self.modo, foreground='#64748b').pack(side='left')
        ttk.Button(ferramentas, text='Gerar código dos blocos', command=self.gerar_codigo).pack(side='right')
        self.editor = Editor(codigo, self.codigo_editado)
        self.editor.pack(fill='both', expand=True)
        rodape_editor = ttk.Frame(codigo, padding=8)
        rodape_editor.pack(fill='x')
        ttk.Label(rodape_editor, text='Dicas ao digitar · Ctrl+Espaço para sugerir · Tab/Enter para inserir · Ctrl+F para buscar', foreground='#64748b', font=(FONTE_UI, 9)).pack(anchor='w')
        self.abas.add(codigo, text='Editor de código')
        self.abas.bind('<<NotebookTabChanged>>', self.trocar_aba)

        terminal = ttk.Frame(principal)
        principal.add(terminal, weight=1)
        topo_console = ttk.Frame(terminal, padding=(6, 7))
        topo_console.pack(fill='x')
        ttk.Label(topo_console, text='CONSOLE', font=(FONTE_UI, 9, 'bold')).pack(side='left')
        ttk.Label(topo_console, textvariable=self.exec_status, foreground='#64748b', font=(FONTE_UI, 9)).pack(side='left', padx=20)
        ttk.Button(topo_console, text='Limpar', command=self.limpar_console).pack(side='right')
        caixa = ttk.Frame(terminal)
        caixa.pack(fill='both', expand=True)
        self.console = tk.Text(caixa, bg='#172033', fg='#dbeafe', font=(FONTE_CODIGO, 11),
                               height=6, padx=12, pady=10, wrap='word', borderwidth=0, state='disabled')
        sc = ttk.Scrollbar(caixa, command=self.console.yview)
        sc.pack(side='right', fill='y')
        self.console.configure(yscrollcommand=sc.set)
        self.console.pack(fill='both', expand=True)
        self.console.tag_configure('aviso', foreground='#c4b5fd')
        self.console.tag_configure('entrada', foreground='#5eead4')
        self.console.tag_configure('erro', foreground='#fca5a5')
        entrada = ttk.Frame(terminal, padding=(0, 7))
        entrada.pack(fill='x')
        ttk.Label(entrada, text='Entrada do programa:').pack(side='left', padx=(0, 8))
        self.campo_entrada = ttk.Entry(entrada, textvariable=self.entrada, state='disabled')
        self.campo_entrada.pack(side='left', fill='x', expand=True)
        self.campo_entrada.bind('<Return>', lambda _: self.enviar_entrada())
        self.botao_enviar = ttk.Button(entrada, text='Enviar', command=self.enviar_entrada, state='disabled')
        self.botao_enviar.pack(side='right', padx=(8, 0))
        principal.bind('<Map>', lambda _: self.after_idle(lambda: principal.sashpos(0, max(240, principal.winfo_height() - 230))), add='+')
        self.escrever_console('Pronto. Monte um programa ou abra um exemplo e pressione F5.\n', 'aviso')

    def montar_paleta(self, parent):
        painel = tk.Frame(parent, bg='white', width=220)
        painel.pack(side='left', fill='y')
        painel.pack_propagate(False)
        tk.Label(painel, text='BIBLIOTECA DE BLOCOS', bg='white', fg='#64748b', font=(FONTE_UI, 9, 'bold')).pack(anchor='w', padx=14, pady=(16, 5))
        tk.Label(painel, text='Arraste para um encaixe +\nou clique para adicionar.', bg='white', fg='#94a3b8', justify='left', font=(FONTE_UI, 9)).pack(anchor='w', padx=14, pady=(0, 10))
        canvas = tk.Canvas(painel, bg='white', highlightthickness=0)
        scroll = ttk.Scrollbar(painel, command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        lista = tk.Frame(canvas, bg='white')
        janela = canvas.create_window(0, 0, anchor='nw', window=lista)
        lista.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(janela, width=e.width))
        for tipo, (titulo, desenho, cor, _) in TIPOS.items():
            row = tk.Frame(lista, bg='white', padx=10, pady=7, cursor='hand2')
            row.pack(fill='x')
            icone = tk.Canvas(row, width=42, height=31, bg='white', highlightthickness=0)
            icone.pack(side='left')
            forma(icone, desenho, 1, 3, 38, 24, cor, '#b9c7d8')
            label = tk.Label(row, text=titulo, bg='white', fg='#334155', font=(FONTE_UI, 10), wraplength=130, justify='left')
            label.pack(side='left', padx=9)
            for widget in (row, icone, label):
                widget.bind('<ButtonPress-1>', lambda e, t=tipo: self.iniciar_arrasto_paleta(t, e))
                widget.bind('<B1-Motion>', lambda e: self.diagrama.arrastar(e))
                widget.bind('<ButtonRelease-1>', lambda e: self.diagrama.soltar(e))
                widget.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
                widget.bind('<Button-4>', lambda e: canvas.yview_scroll(-2, 'units'))
                widget.bind('<Button-5>', lambda e: canvas.yview_scroll(2, 'units'))

    def iniciar_arrasto_paleta(self, tipo, evento):
        self.abas.select(0)
        self.diagrama.comecar_paleta(tipo, evento)

    def visual_ativo(self):
        return self.abas.index(self.abas.select()) == 0

    def marcar_sujo(self):
        self.sujo = True
        self.atualizar_titulo()

    def atualizar_titulo(self):
        nome = self.caminho.name if self.caminho else 'Sem título'
        self.title(f'{"● " if self.sujo else ""}{nome} — Lume IDE')

    def codigo_editado(self):
        self.manual = True
        self.modo.set('Edição manual · os blocos são preservados separadamente')
        self.marcar_sujo()

    def alteracao_visual(self):
        dados = self.projeto.dados()
        if dados != self.historico[self.posicao_historico]:
            self.historico = self.historico[:self.posicao_historico + 1] + [dados]
            self.historico = self.historico[-100:]
            self.posicao_historico = len(self.historico) - 1
        self.marcar_sujo()
        self.diagrama.selecionar(self.selecionado)
        if not self.manual:
            try:
                self.editor.definir(self.projeto.gerar())
                self.modo.set('Código gerado pelos blocos')
            except ErroDeBloco as erro:
                self.status.set(str(erro))
                self.editor.definir('# Complete os blocos para gerar o programa.\n# ' + str(erro) + '\n')
                self.modo.set('Blocos incompletos · veja a mensagem no editor')
        else:
            self.status.set('Blocos alterados. A edição manual foi mantida; use Gerar código dos blocos para substituí-la.')

    def selecionar_bloco(self, identidade):
        if not self.aplicar_campos():
            return False
        self.selecionado = identidade
        self.diagrama.selecionar(identidade)
        self.mostrar_propriedades()
        return True

    def mostrar_propriedades(self):
        for widget in self.inspector.winfo_children():
            widget.destroy()
        self.campos = {}
        self.rolagem_propriedades.yview_moveto(0)
        ttk.Label(self.inspector, text='PROPRIEDADES', style='Painel.TLabel', font=(FONTE_UI, 9, 'bold'), foreground='#64748b').pack(anchor='w')
        bloco = self.projeto.buscar(self.selecionado)
        if not bloco:
            ttk.Label(self.inspector, text='Cada forma tem\numa função.', style='Painel.TLabel', font=(FONTE_UI, 19, 'bold')).pack(anchor='w', pady=(25, 13))
            ttk.Label(self.inspector, text='Selecione um bloco para editar seus valores.\n\nOs encaixes + definem a ordem das instruções.\n\nDentro de um losango, escolha o caminho "Se verdadeiro" ou "Senão".', style='Painel.TLabel', wraplength=220, justify='left', foreground='#64748b').pack(anchor='w')
            ttk.Button(self.inspector, text='Abrir exemplo: par ou ímpar', command=lambda: self.carregar_exemplo('paridade')).pack(anchor='w', pady=25)
            self.ativar_rolagem_propriedades()
            return
        titulo, _, _, campos = TIPOS[bloco.tipo]
        ttk.Label(self.inspector, text=titulo, style='Painel.TLabel', font=(FONTE_UI, 16, 'bold'), wraplength=220).pack(anchor='w', pady=(16, 8))
        for chave, rotulo, _ in campos:
            ttk.Label(self.inspector, text=rotulo, style='Painel.TLabel', wraplength=220).pack(anchor='w', pady=(12, 5))
            variavel = tk.StringVar(value=bloco.campos[chave])
            self.campos[chave] = variavel
            if chave == 'tipo' and bloco.tipo == 'entrada':
                widget = ttk.Combobox(self.inspector, textvariable=variavel, values=('inteiro', 'real', 'texto'), state='readonly')
            else:
                widget = ttk.Entry(self.inspector, textvariable=variavel, font=(FONTE_CODIGO, 10))
            widget.pack(fill='x')
            widget.bind('<Return>', lambda _: self.aplicar_campos())
        if campos:
            ttk.Button(self.inspector, text='Aplicar alterações', style='Primario.TButton', command=self.aplicar_campos).pack(fill='x', pady=(18, 10))
        dica = 'Expressões aceitam contas e comparações. Para texto literal, use aspas: "Olá".'
        if bloco.tipo == 'repetir':
            dica = 'O limite final não é incluído. Para mostrar 1 até 5, comece em 1 e pare antes de 6.'
        elif bloco.tipo == 'entrada':
            dica = 'Durante a execução, responda no campo Entrada do programa, abaixo do console.'
        elif bloco.tipo == 'funcao':
            dica = 'Encaixe instruções no corpo da função. Use Executar expressão para chamá-la depois.'
        ttk.Label(self.inspector, text=dica, style='Painel.TLabel', foreground='#64748b', wraplength=220, justify='left', font=(FONTE_UI, 9)).pack(anchor='w', pady=10)
        ttk.Separator(self.inspector).pack(fill='x', pady=12)
        ttk.Button(self.inspector, text='Duplicar bloco', command=self.duplicar).pack(fill='x', pady=4)
        ttk.Button(self.inspector, text='Excluir bloco e conteúdo', command=self.excluir).pack(fill='x', pady=4)
        ttk.Button(self.inspector, text='Desfazer alteração', command=self.desfazer).pack(fill='x', pady=4)
        self.ativar_rolagem_propriedades()

    def ativar_rolagem_propriedades(self):
        def rolar(evento):
            self.rolagem_propriedades.yview_scroll(-1 if evento.delta > 0 else 1, 'units')
            return 'break'
        for widget in (self.inspector, *self.inspector.winfo_children()):
            widget.bind('<MouseWheel>', rolar)
            widget.bind('<Button-4>', lambda _: self.rolagem_propriedades.yview_scroll(-2, 'units'))
            widget.bind('<Button-5>', lambda _: self.rolagem_propriedades.yview_scroll(2, 'units'))

    def aplicar_campos(self):
        bloco = self.projeto.buscar(self.selecionado)
        if not bloco or not self.campos:
            return True
        valores = {chave: var.get() for chave, var in self.campos.items()}
        if valores == bloco.campos:
            return True
        bloco.campos = valores
        self.alteracao_visual()
        self.status.set('Propriedades aplicadas. Use Verificar para conferir a estrutura do programa.')
        return True

    def soltar_bloco(self, drag, alvo):
        self.aplicar_campos()
        if alvo is None:
            # Um clique adiciona ao final; arrastar dá controle sobre o encaixe.
            alvo = {'pai': None, 'lado': 'filhos', 'indice': len(self.projeto.blocos)}
        try:
            if 'tipo' in drag:
                bloco = Bloco.novo(drag['tipo'])
                self.projeto.inserir(bloco, alvo['pai'], alvo['lado'], alvo['indice'])
                self.selecionado = bloco.id
            else:
                self.projeto.mover(drag['id'], alvo['pai'], alvo['lado'], alvo['indice'])
                self.selecionado = drag['id']
            self.alteracao_visual()
            self.mostrar_propriedades()
            self.status.set('Bloco encaixado. Edite as propriedades à direita e pressione Aplicar.')
        except ErroDeBloco as erro:
            self.status.set(str(erro))
            self.bell()

    def excluir(self):
        if not self.selecionado:
            return
        self.projeto.excluir(self.selecionado)
        self.selecionado = None
        self.alteracao_visual()
        self.mostrar_propriedades()

    def duplicar(self):
        if not self.selecionado:
            return
        self.aplicar_campos()
        try:
            self.selecionado = self.projeto.duplicar(self.selecionado).id
            self.alteracao_visual()
            self.mostrar_propriedades()
        except ErroDeBloco as erro:
            self.status.set(str(erro))

    def atalho_duplicar(self, _=None):
        if self.visual_ativo() and self.focus_get() is self.diagrama.canvas:
            self.duplicar()
            return 'break'

    def desfazer(self):
        if self.posicao_historico <= 0:
            return
        self.posicao_historico -= 1
        self.restaurar_historico()

    def refazer(self):
        if self.posicao_historico + 1 >= len(self.historico):
            return
        self.posicao_historico += 1
        self.restaurar_historico()

    def restaurar_historico(self):
        self.projeto = Projeto.de_dados(self.historico[self.posicao_historico])
        self.selecionado = None
        self.diagrama.selecionar(None)
        self.mostrar_propriedades()
        if not self.manual:
            try:
                self.editor.definir(self.projeto.gerar())
            except ErroDeBloco as erro:
                self.editor.definir('# Complete os blocos para gerar o programa.\n# ' + str(erro) + '\n')
                self.modo.set('Blocos incompletos · veja a mensagem no editor')
        self.marcar_sujo()

    def atalho_desfazer(self, _=None):
        if self.visual_ativo() and self.focus_get() is self.diagrama.canvas:
            self.desfazer()
            return 'break'

    def atalho_refazer(self, _=None):
        if self.visual_ativo() and self.focus_get() is self.diagrama.canvas:
            self.refazer()
            return 'break'

    def trocar_aba(self, _=None):
        if not hasattr(self, 'editor'):
            return
        self.aplicar_campos()
        if not self.visual_ativo():
            self.editor.texto.focus_set()
        self.status.set('Monte o programa arrastando os blocos.' if self.visual_ativo() else 'Digite um comando em português para receber sugestões.')

    def gerar_codigo(self):
        self.aplicar_campos()
        if self.manual and not messagebox.askyesno('Substituir edição manual?', 'Gerar novamente substituirá o texto editado pelo código dos blocos. Deseja continuar?', parent=self):
            return
        try:
            codigo = self.projeto.gerar()
        except ErroDeBloco as erro:
            self.mostrar_erro_bloco(erro)
            return
        self.editor.definir(codigo)
        self.manual = False
        self.modo.set('Código gerado pelos blocos')
        self.marcar_sujo()
        self.abas.select(1)

    def obter_codigo(self):
        self.aplicar_campos()
        return self.projeto.gerar() if self.visual_ativo() else self.editor.obter()

    def mostrar_erro_bloco(self, erro):
        self.status.set(str(erro))
        if erro.bloco_id:
            self.selecionado = erro.bloco_id
            self.diagrama.selecionar(erro.bloco_id, revelar=True)
            self.mostrar_propriedades()
        self.escrever_console(str(erro) + '\n', 'erro')

    def verificar(self):
        try:
            codigo = self.obter_codigo()
            compile(traduzir(codigo), 'programa.ptpy', 'exec')
        except ErroDeBloco as erro:
            self.mostrar_erro_bloco(erro)
        except (SyntaxError, ValueError) as erro:
            mensagem = f'Erro de sintaxe na linha {getattr(erro, "lineno", None) or "?"}: {getattr(erro, "msg", str(erro))}'
            self.status.set(mensagem)
            self.escrever_console(mensagem + '\n', 'erro')
        else:
            self.status.set('Sintaxe válida. A execução ainda pode encontrar erros de valores ou nomes.')
            self.escrever_console('Verificação: sintaxe válida.\n', 'aviso')

    def pode_descartar(self):
        self.aplicar_campos()
        if not self.sujo:
            return True
        resposta = messagebox.askyesnocancel('Salvar projeto?', 'Há alterações não salvas. Deseja salvar o projeto antes de continuar?', parent=self)
        if resposta is None:
            return False
        return self.salvar() if resposta else True

    def carregar_projeto(self, projeto, codigo=None, manual=False, caminho=None):
        self.projeto = projeto
        self.caminho = caminho
        self.manual = manual
        self.selecionado = None
        self.historico = [projeto.dados()]
        self.posicao_historico = 0
        self.editor.definir(codigo if codigo is not None else projeto.gerar())
        self.modo.set('Edição manual · os blocos são preservados separadamente' if manual else 'Código gerado pelos blocos')
        self.diagrama.selecionar(None)
        self.diagrama.canvas.yview_moveto(0)
        self.mostrar_propriedades()
        self.sujo = False
        self.atualizar_titulo()

    def novo(self):
        if self.pode_descartar():
            self.carregar_projeto(Projeto())
            self.abas.select(0)

    def carregar_exemplo(self, nome):
        if self.pode_descartar():
            self.carregar_projeto(exemplo(nome))
            self.abas.select(0)

    def abrir(self):
        if not self.pode_descartar():
            return
        path = filedialog.askopenfilename(parent=self, filetypes=[('Projetos e programas', '*.json *.ptpy *.py'), ('Todos os arquivos', '*')])
        if not path:
            return
        caminho = Path(path)
        try:
            if caminho.stat().st_size > 5_000_000:
                raise ValueError('Este arquivo excede o limite de 5 MB do editor.')
            texto = caminho.read_text(encoding='utf-8-sig')
            if caminho.suffix == '.json':
                dado = json.loads(texto)
                if not isinstance(dado, dict) or dado.get('formato') != 'lume-ide' or dado.get('versao') != 1:
                    raise ValueError('Formato de projeto não reconhecido.')
                projeto = Projeto.de_dados(dado.get('blocos'))
                codigo = dado.get('codigo')
                if not isinstance(codigo, str) or not isinstance(dado.get('edicao_manual'), bool):
                    raise ValueError('O projeto não contém código e modo de edição válidos.')
                self.carregar_projeto(projeto, codigo, dado['edicao_manual'], caminho)
                self.abas.select(1 if self.manual else 0)
            else:
                self.carregar_projeto(Projeto(), texto, True)
                self.abas.select(1)
                self.status.set('Código aberto. Não há conversão automática de texto para blocos; salve um projeto para preservar sua edição.')
        except (OSError, ValueError, TypeError, RecursionError) as erro:
            messagebox.showerror('Não foi possível abrir', str(erro), parent=self)

    def salvar(self):
        self.aplicar_campos()
        path = str(self.caminho) if self.caminho else filedialog.asksaveasfilename(parent=self, title='Salvar projeto completo', defaultextension='.lume.json', filetypes=[('Projeto Lume', '*.lume.json')])
        if not path:
            return False
        dado = {'formato': 'lume-ide', 'versao': 1, 'blocos': self.projeto.dados(),
                'codigo': self.editor.obter(), 'edicao_manual': self.manual}
        try:
            caminho = Path(path)
            temporario = caminho.with_name(caminho.name + '.tmp')
            temporario.write_text(json.dumps(dado, ensure_ascii=False, indent=2), encoding='utf-8')
            temporario.replace(caminho)
        except OSError as erro:
            messagebox.showerror('Erro ao salvar', str(erro), parent=self)
            return False
        self.caminho = caminho
        self.sujo = False
        self.atualizar_titulo()
        self.status.set('Projeto salvo com blocos e código: ' + caminho.name)
        return True

    def exportar(self):
        try:
            codigo = self.obter_codigo()
        except ErroDeBloco as erro:
            self.mostrar_erro_bloco(erro)
            return
        path = filedialog.asksaveasfilename(parent=self, title='Exportar programa', defaultextension='.ptpy', filetypes=[('Programa em português', '*.ptpy')])
        if path:
            try:
                Path(path).write_text(codigo, encoding='utf-8')
                self.status.set('Código exportado. Para preservar os blocos também, use Salvar projeto.')
            except OSError as erro:
                messagebox.showerror('Erro ao exportar', str(erro), parent=self)

    def preferencias(self):
        janela = tk.Toplevel(self)
        janela.title('Interpretador do programa')
        janela.geometry('570x270')
        janela.transient(self)
        frame = ttk.Frame(janela, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Como executar seus programas', font=(FONTE_UI, 15, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Sem caminho configurado, a IDE executa em modo compatível com o Python instalado. Se você compilou o interpretador português, selecione o executável dele.', wraplength=520, justify='left').pack(anchor='w', pady=12)
        valor = tk.StringVar(value=self.nativo)
        ttk.Entry(frame, textvariable=valor).pack(fill='x')
        def localizar():
            path = filedialog.askopenfilename(parent=janela, title='Selecionar interpretador Python em português')
            if path:
                valor.set(path)
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=12)
        ttk.Button(row, text='Localizar executável', command=localizar).pack(side='left')
        ttk.Button(row, text='Usar execução integrada', command=lambda: valor.set('')).pack(side='left', padx=8)
        def aplicar():
            caminho = valor.get().strip()
            if caminho and not Path(caminho).is_file():
                messagebox.showerror('Interpretador', 'Selecione um arquivo executável existente.', parent=janela)
                return
            try:
                CONFIG.parent.mkdir(parents=True, exist_ok=True)
                CONFIG.write_text(json.dumps({'interpretador': caminho}), encoding='utf-8')
            except OSError as erro:
                messagebox.showerror('Preferências', str(erro), parent=janela)
                return
            self.nativo = caminho
            janela.destroy()
            self.status.set('Interpretador atualizado.')
        ttk.Button(frame, text='Salvar preferência', style='Primario.TButton', command=aplicar).pack(anchor='e')

    def executar(self):
        if self.processo:
            self.status.set('Há um programa em execução. Use Parar antes de iniciar outro.')
            return
        try:
            codigo = self.obter_codigo()
            compile(traduzir(codigo), 'programa.ptpy', 'exec')
        except ErroDeBloco as erro:
            self.mostrar_erro_bloco(erro)
            return
        except (SyntaxError, ValueError) as erro:
            self.escrever_console(f'Erro de sintaxe: {erro}\n', 'erro')
            return
        self.pasta_execucao = tempfile.TemporaryDirectory(prefix='lume_')
        arquivo = Path(self.pasta_execucao.name) / 'programa.ptpy'
        arquivo.write_text(codigo, encoding='utf-8')
        comando = [self.nativo, '-u', '-X', 'utf8', str(PASTA / 'executor.py'), '--nativo', str(arquivo)] if self.nativo else [sys.executable, '-u', '-X', 'utf8', str(PASTA / 'executor.py'), str(arquivo)]
        ambiente = dict(os.environ)
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        pasta = self.caminho.parent if self.caminho else PASTA
        ambiente['PYTHONPATH'] = str(pasta) + os.pathsep + str(PASTA) + os.pathsep + ambiente.get('PYTHONPATH', '')
        try:
            self.processo = subprocess.Popen(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                              stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                              bufsize=0, cwd=pasta, env=ambiente,
                                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError as erro:
            self.pasta_execucao.cleanup()
            self.pasta_execucao = None
            self.escrever_console(f'Não foi possível iniciar o interpretador: {erro}\n', 'erro')
            return
        processo = self.processo
        self.interrompido = False
        self.inicio_execucao = time.monotonic()
        self.botao_rodar.configure(state='disabled')
        self.botao_parar.configure(state='normal')
        self.campo_entrada.configure(state='normal')
        self.botao_enviar.configure(state='normal')
        self.exec_status.set('Em execução · responda no campo de entrada quando solicitado')
        self.escrever_console('\nExecutando programa...\n', 'aviso')
        def ler():
            try:
                while True:
                    caractere = processo.stdout.read(1)
                    if not caractere:
                        break
                    self.eventos.put(('saida', caractere))
            finally:
                codigo_saida = processo.wait()
                processo.stdout.close()
                if processo.stdin:
                    processo.stdin.close()
                self.eventos.put(('fim', codigo_saida))
        threading.Thread(target=ler, daemon=True).start()

    def enviar_entrada(self):
        if not self.processo or self.processo.poll() is not None:
            return
        texto = self.entrada.get()
        try:
            self.processo.stdin.write(texto + '\n')
            self.processo.stdin.flush()
        except (OSError, ValueError):
            self.status.set('O programa já encerrou a entrada de dados.')
            return
        self.escrever_console(texto + '\n', 'entrada')
        self.entrada.set('')

    def parar(self):
        if self.processo and self.processo.poll() is None:
            self.interrompido = True
            processo = self.processo
            processo.terminate()
            def forcar():
                if processo.poll() is None:
                    processo.kill()
            self.after(1200, forcar)

    def processar_eventos(self):
        texto = []
        fim = None
        for _ in range(12000):
            try:
                tipo, dado = self.eventos.get_nowait()
            except queue.Empty:
                break
            if tipo == 'saida':
                texto.append(dado)
            else:
                fim = dado
        if texto:
            self.escrever_console(''.join(texto))
        if fim is not None:
            duracao = time.monotonic() - self.inicio_execucao
            mensagem = 'Interrompido pelo usuário' if self.interrompido else ('Concluído' if fim == 0 else f'Encerrado com erro · código {fim}')
            self.exec_status.set(f'{mensagem} · {duracao:.2f} s')
            self.escrever_console(f'\n{mensagem}.\n', 'aviso' if fim == 0 or self.interrompido else 'erro')
            self.processo = None
            if self.pasta_execucao:
                self.pasta_execucao.cleanup()
                self.pasta_execucao = None
            self.botao_rodar.configure(state='normal')
            self.botao_parar.configure(state='disabled')
            self.campo_entrada.configure(state='disabled')
            self.botao_enviar.configure(state='disabled')
            self.entrada.set('')
        if not self._fechando:
            self.after(60, self.processar_eventos)

    def escrever_console(self, texto, tag=None):
        self.console.configure(state='normal')
        self.console.insert('end', texto, tag or ())
        # Mantém a interface utilizável mesmo em programas que imprimem muito.
        if int(self.console.index('end-1c').split('.')[0]) > 2500:
            self.console.delete('1.0', '500.0')
        caracteres = self.console.count('1.0', 'end-1c', 'chars')
        if caracteres and caracteres[0] > 300000:
            self.console.delete('1.0', '1.0+100000c')
        self.console.see('end')
        self.console.configure(state='disabled')

    def limpar_console(self):
        self.console.configure(state='normal')
        self.console.delete('1.0', 'end')
        self.console.configure(state='disabled')

    def ajuda(self):
        messagebox.showinfo('Como usar a Lume IDE',
            '1. Arraste uma forma da biblioteca para uma linha com +.\n'
            '2. Clique no bloco, preencha as propriedades e aplique.\n'
            '3. Encaixe instruções dentro de condições, funções e repetições.\n'
            '4. Abra Editor de código para ver o programa gerado.\n'
            '5. Pressione F5. Responda pelo campo abaixo do console.\n\n'
            'Ao digitar código, use Ctrl+Espaço para sugestões e Tab/Enter para aceitar.\n\n'
            'Salvar projeto preserva blocos e texto. Exportar .ptpy salva apenas o código.\n'
            'Não há conversão automática de código editado para blocos.', parent=self)

    def fechar(self):
        if not self.pode_descartar():
            return
        if self.processo and self.processo.poll() is None:
            if not messagebox.askyesno('Programa em execução', 'Encerrar o programa e fechar a IDE?', parent=self):
                return
            self.processo.kill()
            self.processo.wait(timeout=5)
        self._fechando = True
        self.editor.fechar_popup()
        self.diagrama.cancelar_arrasto()
        if self.pasta_execucao:
            self.pasta_execucao.cleanup()
        self.destroy()


def main():
    if sys.version_info < (3, 12):
        print('A Lume IDE requer Python 3.12 ou superior.')
        raise SystemExit(1)
    try:
        app = LumeIDE()
    except tk.TclError as erro:
        print('Não foi possível abrir a interface gráfica:', erro)
        raise SystemExit(1)
    app.mainloop()


if __name__ == '__main__':
    main()
