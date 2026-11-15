"""Editor Tk com cores, números de linha e sugestões contextuais."""
from __future__ import annotations

import io
import re
import tkinter as tk
from tkinter import ttk
from tema import FONTE_UI, FONTE_CODIGO
import tokenize
import unicodedata

from vocabulario import FUNCOES, PALAVRAS


SUGESTOES = [
    ('função', 'função nome(parametros):\n    passe', 'Cria uma função reutilizável.', 'nome'),
    ('se', 'se condição:\n    passe', 'Executa um bloco quando a condição é verdadeira.', 'condição'),
    ('senão', 'senão:\n    passe', 'Caminho alternativo de uma condição.', None),
    ('senãose', 'senãose condição:\n    passe', 'Testa outra condição depois de um se.', 'condição'),
    ('para', 'para item em intervalo(5):\n    escreva(item)', 'Percorre os valores de uma sequência.', 'item'),
    ('enquanto', 'enquanto condição:\n    passe', 'Repete enquanto a condição for verdadeira.', 'condição'),
    ('escreva', 'escreva()', 'Mostra valores no console. Ex.: escreva("Olá", nome).', None),
    ('leia', 'leia()', 'Lê um texto digitado no campo de entrada do console.', None),
    ('inteiro', 'inteiro()', 'Converte um valor em número inteiro. Ex.: inteiro(leia()).', None),
    ('real', 'real()', 'Converte um valor em número com parte decimal.', None),
    ('texto', 'texto()', 'Converte um valor em texto.', None),
    ('intervalo', 'intervalo()', 'Gera valores: intervalo(inicio, fim, passo). O fim não é incluído.', None),
    ('tamanho', 'tamanho()', 'Informa o número de elementos de um texto ou coleção.', None),
    ('retorne', 'retorne ', 'Devolve um valor de uma função.', None),
    ('importe', 'importe matematica como m', 'Importa uma biblioteca; como define um apelido.', None),
    ('tente', 'tente:\n    passe\nexceto Excecao como erro:\n    escreva(erro)', 'Trata falhas durante a execução.', None),
    ('classe', 'classe Nome:\n    passe', 'Define um novo tipo de objeto.', 'Nome'),
    ('com', 'com abra("arquivo.txt") como arquivo:\n    escreva(arquivo.read())', 'Usa um recurso e o encerra ao sair do bloco.', None),
]
_existentes = {item[0] for item in SUGESTOES}
for _nome in [*PALAVRAS, *FUNCOES, 'abra', 'ErroDeValor', 'Excecao']:
    if _nome not in _existentes:
        _funcao = _nome in FUNCOES or _nome == 'abra'
        SUGESTOES.append((_nome, _nome + ('()' if _funcao else ''),
                          ('Função ou tipo' if _funcao else 'Palavra da linguagem') + ' em português.', None))
        _existentes.add(_nome)


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.casefold()) if not unicodedata.combining(c))


def sugestoes(prefixo):
    busca = normalizar(prefixo)
    return [item for item in SUGESTOES if normalizar(item[0]).startswith(busca)]


class Editor(ttk.Frame):
    def __init__(self, parent, ao_editar):
        super().__init__(parent)
        self.ao_editar = ao_editar
        self.silencioso = False
        self.agendado = None
        self.popup = None
        self.opcoes = []
        self.gutter = tk.Canvas(self, width=52, bg='#f1f5f9', highlightthickness=0)
        self.gutter.pack(side='left', fill='y')
        self.texto = tk.Text(self, bg='#ffffff', fg='#172033', insertbackground='#7c3aed',
                             selectbackground='#ddd6fe', selectforeground='#172033',
                             font=(FONTE_CODIGO, 12), undo=True, wrap='none', borderwidth=0,
                             padx=14, pady=12, tabs=('4c',), spacing1=2, spacing3=2)
        vertical = ttk.Scrollbar(self, command=self.rolar)
        vertical.pack(side='right', fill='y')
        self.texto.pack(fill='both', expand=True)
        self.texto.configure(yscrollcommand=lambda a, b: (vertical.set(a, b), self.desenhar_linhas()))
        self.texto.tag_configure('reservada', foreground='#9333ea')
        self.texto.tag_configure('funcao', foreground='#0369a1')
        self.texto.tag_configure('texto', foreground='#15803d')
        self.texto.tag_configure('comentario', foreground='#7c899a')
        self.texto.tag_configure('numero', foreground='#c2410c')
        self.texto.tag_configure('busca', background='#fef08a')
        self.texto.bind('<<Modified>>', self.modificado)
        self.texto.bind('<KeyRelease>', self.tecla_liberada)
        self.texto.bind('<Configure>', lambda _: self.desenhar_linhas())
        self.texto.bind('<Control-space>', self.forcar_sugestoes)
        self.texto.bind('<Tab>', self.tab)
        self.texto.bind('<Return>', self.enter)
        self.texto.bind('<Escape>', lambda _: self.fechar_popup())
        self.texto.bind('<Down>', lambda e: self.navegar(1))
        self.texto.bind('<Up>', lambda e: self.navegar(-1))
        self.texto.bind('<Button-1>', lambda _: self.fechar_popup())
        self.texto.bind('<FocusOut>', lambda _: self.after(150, self.fechar_popup))
        self.texto.bind('<Control-f>', self.buscar)
        self.texto.bind('<Shift-Tab>', self.desindentar)
        self.texto.bind('<MouseWheel>', lambda _: self.after_idle(self.desenhar_linhas), add='+')
        self.texto.bind('<Button-4>', lambda _: self.after_idle(self.desenhar_linhas), add='+')
        self.texto.bind('<Button-5>', lambda _: self.after_idle(self.desenhar_linhas), add='+')

    def obter(self):
        return self.texto.get('1.0', 'end-1c')

    def definir(self, codigo):
        self.silencioso = True
        self.texto.delete('1.0', 'end')
        self.texto.insert('1.0', codigo)
        self.texto.edit_reset()
        self.texto.edit_modified(False)
        self.silencioso = False
        self.colorir()

    def modificado(self, _=None):
        if not self.texto.edit_modified():
            return
        self.texto.edit_modified(False)
        if self.agendado:
            self.after_cancel(self.agendado)
        self.agendado = self.after(180, self.colorir)
        if not self.silencioso:
            self.ao_editar()

    def colorir(self):
        self.agendado = None
        for tag in ('reservada', 'funcao', 'texto', 'comentario', 'numero'):
            self.texto.tag_remove(tag, '1.0', 'end')
        try:
            for token in tokenize.generate_tokens(io.StringIO(self.obter()).readline):
                tag = None
                if token.type == tokenize.NAME:
                    if token.string in PALAVRAS:
                        tag = 'reservada'
                    elif token.string in FUNCOES or token.string in {'abra', 'ErroDeValor', 'Excecao'}:
                        tag = 'funcao'
                elif token.type == tokenize.STRING:
                    tag = 'texto'
                elif token.type == tokenize.COMMENT:
                    tag = 'comentario'
                elif token.type == tokenize.NUMBER:
                    tag = 'numero'
                if tag:
                    self.texto.tag_add(tag, f'{token.start[0]}.{token.start[1]}', f'{token.end[0]}.{token.end[1]}')
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass
        self.desenhar_linhas()

    def desenhar_linhas(self):
        self.gutter.delete('all')
        indice = self.texto.index('@0,0')
        for _ in range(200):
            bbox = self.texto.dlineinfo(indice)
            if bbox is None:
                break
            self.gutter.create_text(40, bbox[1] + 1, anchor='ne', text=indice.split('.')[0], fill='#94a3b8', font=(FONTE_CODIGO, 11))
            indice = self.texto.index(indice + '+1line')

    def rolar(self, *args):
        self.texto.yview(*args)
        self.desenhar_linhas()
        self.fechar_popup()

    def prefixo(self):
        linha = self.texto.get('insert linestart', 'insert')
        encontrado = re.search(r'[^\W\d]\w*$', linha)
        if not encontrado:
            return ''
        # Não sugerir comandos enquanto alguém escreve uma propriedade.
        if encontrado.start() and linha[encontrado.start() - 1] == '.':
            return ''
        return encontrado.group()

    def dentro_de_texto(self):
        anterior = self.texto.index('insert-1c')
        tags = self.texto.tag_names(anterior)
        return 'texto' in tags or 'comentario' in tags

    def tecla_liberada(self, evento):
        if evento.keysym in {'Up', 'Down', 'Return', 'Tab', 'Escape', 'Left', 'Right'} or evento.state & 4:
            return
        prefixo = self.prefixo()
        if prefixo and not self.dentro_de_texto():
            self.mostrar_sugestoes(prefixo)
        else:
            self.fechar_popup()

    def forcar_sugestoes(self, _=None):
        self.mostrar_sugestoes(self.prefixo())
        return 'break'

    def mostrar_sugestoes(self, prefixo):
        opcoes = sugestoes(prefixo)[:12]
        if not opcoes:
            self.fechar_popup()
            return
        self.fechar_popup()
        self.opcoes = opcoes
        self.popup = tk.Toplevel(self)
        self.popup.overrideredirect(True)
        self.popup.configure(bg='#c4b5fd')
        interior = tk.Frame(self.popup, bg='white', padx=8, pady=6)
        interior.pack(fill='both', expand=True, padx=1, pady=1)
        tk.Label(interior, text='SUGESTÕES · Tab ou Enter para inserir', bg='white', fg='#7c3aed', font=(FONTE_UI, 9, 'bold')).pack(anchor='w', pady=(0, 5))
        self.lista = tk.Listbox(interior, height=min(7, len(opcoes)), width=38,
                                bg='white', fg='#172033', borderwidth=0, highlightthickness=0,
                                selectbackground='#ede9fe', selectforeground='#6d28d9',
                                font=(FONTE_CODIGO, 11), exportselection=False, activestyle='none')
        self.lista.pack(fill='x')
        for opcao in opcoes:
            self.lista.insert('end', opcao[0])
        self.lista.selection_set(0)
        self.dica = tk.Label(interior, text=opcoes[0][2], bg='white', fg='#64748b', wraplength=330, justify='left', font=(FONTE_UI, 9))
        self.dica.pack(anchor='w', pady=(6, 2))
        self.lista.bind('<<ListboxSelect>>', self.atualizar_dica)
        self.lista.bind('<Double-Button-1>', lambda _: self.aceitar())
        bbox = self.texto.bbox('insert') or (0, 0, 10, 20)
        x = min(self.texto.winfo_rootx() + bbox[0], max(0, self.winfo_screenwidth() - 365))
        y = self.texto.winfo_rooty() + bbox[1] + bbox[3] + 3
        self.popup.update_idletasks()
        if y + self.popup.winfo_reqheight() > self.winfo_screenheight():
            y = self.texto.winfo_rooty() + bbox[1] - self.popup.winfo_reqheight()
        self.popup.geometry(f'+{max(0,x)}+{max(0,y)}')

    def atualizar_dica(self, _=None):
        if self.popup and self.lista.curselection():
            self.dica.configure(text=self.opcoes[self.lista.curselection()[0]][2])

    def navegar(self, deslocamento):
        if not self.popup:
            return None
        atual = self.lista.curselection()
        indice = max(0, min(len(self.opcoes) - 1, (atual[0] if atual else 0) + deslocamento))
        self.lista.selection_clear(0, 'end')
        self.lista.selection_set(indice)
        self.lista.see(indice)
        self.atualizar_dica()
        return 'break'

    def aceitar(self):
        if not self.popup:
            return False
        selecao = self.lista.curselection()
        if not selecao:
            return False
        _, insercao, _, marcador = self.opcoes[selecao[0]]
        prefixo = self.prefixo()
        inicio = self.texto.index(f'insert-{len(prefixo)}c')
        linha = self.texto.get('insert linestart', inicio)
        indentacao = re.match(r'\s*', linha).group()
        insercao = insercao.replace('\n', '\n' + indentacao)
        self.texto.edit_separator()
        self.texto.delete(inicio, 'insert')
        self.texto.insert(inicio, insercao)
        self.texto.tag_remove('sel', '1.0', 'end')
        if marcador and marcador in insercao:
            posicao = insercao.index(marcador)
            comeco = self.texto.index(f'{inicio}+{posicao}c')
            self.texto.tag_add('sel', comeco, f'{comeco}+{len(marcador)}c')
            self.texto.mark_set('insert', comeco)
        elif insercao.endswith('()'):
            self.texto.mark_set('insert', f'{inicio}+{len(insercao)-1}c')
        else:
            self.texto.mark_set('insert', f'{inicio}+{len(insercao)}c')
        self.texto.edit_separator()
        self.fechar_popup()
        self.texto.focus_set()
        self.colorir()
        return True

    def tab(self, _=None):
        if not self.aceitar():
            self.texto.insert('insert', '    ')
        return 'break'

    def desindentar(self, _=None):
        inicio = self.texto.index('insert linestart')
        prefixo = self.texto.get(inicio, inicio + '+4c')
        remover = min(4, len(prefixo) - len(prefixo.lstrip(' ')))
        if remover:
            self.texto.delete(inicio, f'{inicio}+{remover}c')
        return 'break'

    def enter(self, _=None):
        if self.aceitar():
            return 'break'
        linha = self.texto.get('insert linestart', 'insert')
        espacos = re.match(r' *', linha).group()
        if linha.rstrip().endswith(':'):
            espacos += '    '
        self.texto.insert('insert', '\n' + espacos)
        return 'break'

    def fechar_popup(self):
        if self.popup:
            try:
                self.popup.destroy()
            except tk.TclError:
                pass
            self.popup = None

    def buscar(self, _=None):
        janela = tk.Toplevel(self)
        janela.title('Buscar no código')
        janela.transient(self.winfo_toplevel())
        janela.geometry('360x110')
        valor = tk.StringVar()
        entrada = ttk.Entry(janela, textvariable=valor)
        entrada.pack(fill='x', padx=14, pady=12)
        def aplicar(*_):
            self.texto.tag_remove('busca', '1.0', 'end')
            if not valor.get():
                return
            indice = '1.0'
            primeiro = None
            while True:
                indice = self.texto.search(valor.get(), indice, stopindex='end', nocase=True)
                if not indice:
                    break
                primeiro = primeiro or indice
                fim = self.texto.index(f'{indice}+{len(valor.get())}c')
                self.texto.tag_add('busca', indice, fim)
                indice = fim
            if primeiro:
                self.texto.see(primeiro)
        ttk.Button(janela, text='Destacar resultados', command=aplicar).pack()
        entrada.bind('<Return>', aplicar)
        entrada.focus_set()
        return 'break'
