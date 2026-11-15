"""Montagem visual de blocos com encaixes estruturados por arrastar e soltar."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tema import FONTE_UI, FONTE_CODIGO

from blocos import CONTAINERS, TIPOS


def forma(canvas, tipo, x, y, largura, altura, cor, borda='#cbd5e1', espessura=1, tags=()):
    opcoes = dict(fill=cor, outline=borda, width=espessura, tags=tags)
    direita, baixo = x + largura, y + altura
    if tipo == 'oval':
        return canvas.create_oval(x, y, direita, baixo, **opcoes)
    if tipo == 'losango':
        return canvas.create_polygon(x + largura / 2, y, direita, y + altura / 2,
                                     x + largura / 2, baixo, x, y + altura / 2, **opcoes)
    if tipo == 'paralelogramo':
        return canvas.create_polygon(x + 18, y, direita, y, direita - 18, baixo, x, baixo, **opcoes)
    if tipo == 'hexagono':
        return canvas.create_polygon(x + 16, y, direita - 16, y, direita, y + altura / 2,
                                     direita - 16, baixo, x + 16, baixo, x, y + altura / 2, **opcoes)
    if tipo == 'nota':
        return canvas.create_polygon(x, y, direita - 12, y, direita, y + 12, direita, baixo, x, baixo, **opcoes)
    objeto = canvas.create_rectangle(x, y, direita, baixo, **opcoes)
    if tipo == 'funcao':
        canvas.create_line(x + 9, y, x + 9, baixo, fill=borda, tags=tags)
        canvas.create_line(direita - 9, y, direita - 9, baixo, fill=borda, tags=tags)
    return objeto


def resumo(bloco):
    c = bloco.campos
    if bloco.tipo == 'variavel':
        return f'{c["nome"]} = {c["valor"]}'
    if bloco.tipo == 'entrada':
        return f'Ler {c["nome"]} · {c["tipo"]}'
    if bloco.tipo == 'saida':
        return c['expressao']
    if bloco.tipo in {'condicao', 'enquanto'}:
        return c['condicao']
    if bloco.tipo == 'repetir':
        return f'{c["variavel"]}: {c["inicio"]} até antes de {c["fim"]}'
    if bloco.tipo == 'funcao':
        return f'{c["nome"]}({c["parametros"]})'
    if bloco.tipo == 'retorno':
        return 'retorne ' + c['expressao']
    if bloco.tipo == 'chamada':
        return c['expressao']
    if bloco.tipo == 'importar':
        return c['modulo'] + (' como ' + c['apelido'] if c['apelido'] else '')
    if bloco.tipo == 'comentario':
        return c['texto']
    return 'Sai da repetição atual'


class Diagrama(ttk.Frame):
    def __init__(self, parent, obter_projeto, selecionar, soltar, remover):
        super().__init__(parent)
        self.obter_projeto = obter_projeto
        self.ao_selecionar = selecionar
        self.ao_soltar = soltar
        self.ao_remover = remover
        self.selecionado = None
        self.slots = []
        self.caixas = {}
        self.drag = None
        self.ghost = None
        self.alvo = None
        self.canvas = tk.Canvas(self, bg='#f8fafc', highlightthickness=0)
        vertical = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        horizontal = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        vertical.pack(side='right', fill='y')
        horizontal.pack(side='bottom', fill='x')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.bind('<Configure>', lambda _: self.redesenhar())
        self.canvas.bind('<ButtonPress-1>', self.pressionar)
        self.canvas.bind('<B1-Motion>', self.arrastar)
        self.canvas.bind('<ButtonRelease-1>', self.soltar)
        self.canvas.bind('<Delete>', lambda _: self.ao_remover())
        self.canvas.bind('<MouseWheel>', self.roda)
        self.canvas.bind('<Button-4>', lambda _: self.canvas.yview_scroll(-3, 'units'))
        self.canvas.bind('<Button-5>', lambda _: self.canvas.yview_scroll(3, 'units'))

    def roda(self, evento):
        self.canvas.yview_scroll(-1 if evento.delta > 0 else 1, 'units')

    def selecionar(self, identidade, revelar=False):
        self.selecionado = identidade
        self.redesenhar()
        if revelar and identidade in self.caixas:
            _, y, _, altura = self.caixas[identidade]
            total = float(self.canvas.cget('scrollregion').split()[3])
            if total:
                self.canvas.yview_moveto(max(0, (y - 60) / total))

    def redesenhar(self):
        c = self.canvas
        c.delete('all')
        self.slots = []
        self.caixas = {}
        largura = max(480, c.winfo_width())
        for x in range(18, largura, 24):
            for y in range(18, min(c.winfo_height(), 1000), 24):
                c.create_oval(x, y, x + 1, y + 1, fill='#dfe5ee', outline='')
        forma(c, 'oval', 74, 25, 170, 42, '#dcfce7', '#86efac')
        c.create_text(159, 46, text='INÍCIO', fill='#166534', font=(FONTE_UI, 10, 'bold'))
        c.create_text(275, 45, text='Clique para editar · arraste para organizar', anchor='w', fill='#94a3b8', font=(FONTE_UI, 9))

        def slot(y, nivel, pai, lado, indice):
            x = 48 + nivel * 30
            fim = x + 320
            ident = f'slot{len(self.slots)}'
            c.create_line(x + 12, y, fim, y, fill='#dbe3ef', dash=(3, 4), tags=(ident, 'slot'))
            c.create_oval(x, y - 8, x + 16, y + 8, fill='white', outline='#cbd5e1', tags=(ident, 'slot'))
            c.create_text(x + 8, y, text='+', fill='#94a3b8', font=(FONTE_UI, 10), tags=(ident, 'slot'))
            self.slots.append({'x': x, 'y': y, 'pai': pai, 'lado': lado, 'indice': indice, 'tag': ident})

        def ramo(blocos, nivel, pai=None, lado='filhos', y=92):
            slot(y, nivel, pai, lado, 0)
            y += 20
            if not blocos:
                c.create_text(80 + nivel * 30, y + 4, anchor='w', text='Solte um bloco na linha com +', fill='#94a3b8', font=(FONTE_UI, 9))
                return y + 26
            for indice, bloco in enumerate(blocos):
                x = 48 + nivel * 30
                w, h = 320, 72
                if bloco.tipo in {'condicao', 'enquanto'}:
                    h = 92
                _, desenho, cor, _ = TIPOS[bloco.tipo]
                selecionado = bloco.id == self.selecionado
                tags = ('bloco', 'b:' + bloco.id)
                forma(c, desenho, x + 3, y + 4, w, h, '#e2e8f0', '#e2e8f0', tags=tags)
                forma(c, desenho, x, y, w, h, cor, '#7c3aed' if selecionado else '#b9c7d8', 2 if selecionado else 1, tags)
                meio = x + w / 2
                max_chars = 35 if desenho == 'losango' else 42
                texto = resumo(bloco).replace('\n', ' ')
                if len(texto) > max_chars:
                    texto = texto[:max_chars - 1] + '…'
                c.create_text(meio, y + h / 2 - 10, text=TIPOS[bloco.tipo][0].upper(), fill='#64748b', font=(FONTE_UI, 8, 'bold'), tags=tags)
                c.create_text(meio, y + h / 2 + 10, text=texto, fill='#172033', font=(FONTE_UI, 10, 'bold'), tags=tags)
                self.caixas[bloco.id] = (x, y, w, h)
                c.create_line(x + 20, y + h + 4, x + 20, y + h + 17, fill='#a7b5c8', arrow='last')
                y += h + 26
                if bloco.tipo in CONTAINERS:
                    inicio = y
                    titulo = 'SE VERDADEIRO' if bloco.tipo == 'condicao' else ('CORPO DA FUNÇÃO' if bloco.tipo == 'funcao' else 'A CADA REPETIÇÃO')
                    c.create_text(x + 30, y + 2, text=titulo, anchor='w', fill='#7c3aed', font=(FONTE_UI, 8, 'bold'))
                    y = ramo(bloco.filhos, nivel + 1, bloco.id, 'filhos', y + 23)
                    if bloco.tipo == 'condicao':
                        c.create_text(x + 30, y + 2, text='SENÃO', anchor='w', fill='#b45309', font=(FONTE_UI, 8, 'bold'))
                        y = ramo(bloco.senao, nivel + 1, bloco.id, 'senao', y + 23)
                    c.create_line(x + 12, inicio, x + 12, y - 8, x + 25, y - 8, fill='#c4b5fd', width=2)
                    y += 9
                slot(y, nivel, pai, lado, indice + 1)
                y += 21
            return y

        fim = ramo(self.obter_projeto().blocos, 0)
        forma(c, 'oval', 74, fim + 8, 170, 42, '#f1f5f9', '#cbd5e1')
        c.create_text(159, fim + 29, text='FIM', fill='#64748b', font=(FONTE_UI, 10, 'bold'))
        max_x = max([480, *(x + w + 60 for x, _, w, _ in self.caixas.values())])
        c.configure(scrollregion=(0, 0, max(largura, max_x), fim + 85))

    def bloco_em(self, x, y):
        objetos = self.canvas.find_overlapping(x, y, x, y)
        for objeto in reversed(objetos):
            for tag in self.canvas.gettags(objeto):
                if tag.startswith('b:'):
                    return tag[2:]
        return None

    def pressionar(self, evento):
        self.canvas.focus_set()
        identidade = self.bloco_em(self.canvas.canvasx(evento.x), self.canvas.canvasy(evento.y))
        if identidade:
            if self.ao_selecionar(identidade) is False:
                return
            self.drag = {'id': identidade, 'inicio': (evento.x_root, evento.y_root), 'ativo': False}

    def comecar_paleta(self, tipo, evento):
        self.drag = {'tipo': tipo, 'inicio': (evento.x_root, evento.y_root), 'ativo': False}

    def arrastar(self, evento):
        if not self.drag:
            return
        inicio = self.drag['inicio']
        if not self.drag['ativo'] and abs(evento.x_root - inicio[0]) + abs(evento.y_root - inicio[1]) < 7:
            return
        self.drag['ativo'] = True
        if not self.ghost:
            self.ghost = tk.Toplevel(self)
            self.ghost.overrideredirect(True)
            self.ghost.attributes('-topmost', True)
            tipo = self.drag.get('tipo')
            if not tipo:
                tipo = self.obter_projeto().buscar(self.drag['id']).tipo
            tk.Label(self.ghost, text='  ＋ ' + TIPOS[tipo][0] + '  ', bg='#7c3aed', fg='white', font=(FONTE_UI, 10, 'bold'), padx=10, pady=9).pack()
        self.ghost.geometry(f'+{evento.x_root + 14}+{evento.y_root + 14}')
        self.destacar_alvo(evento.x_root, evento.y_root)

    def destacar_alvo(self, raiz_x, raiz_y):
        self.canvas.delete('alvo')
        self.alvo = None
        x = raiz_x - self.canvas.winfo_rootx()
        y = raiz_y - self.canvas.winfo_rooty()
        if not (0 <= x < self.canvas.winfo_width() and 0 <= y < self.canvas.winfo_height()):
            return
        if y < 32:
            self.canvas.yview_scroll(-2, 'units')
        elif y > self.canvas.winfo_height() - 32:
            self.canvas.yview_scroll(2, 'units')
        cx, cy = self.canvas.canvasx(x), self.canvas.canvasy(y)
        if not self.slots:
            return
        # A distância horizontal diferencia o encaixe interno do encaixe externo.
        alvo = min(self.slots, key=lambda s: abs(s['y'] - cy) + abs((s['x'] + 70) - cx) * .18)
        if abs(alvo['y'] - cy) <= 65:
            self.alvo = alvo
            self.canvas.create_line(alvo['x'], alvo['y'], alvo['x'] + 320, alvo['y'], fill='#7c3aed', width=4, tags='alvo')
            self.canvas.create_text(alvo['x'] + 325, alvo['y'], text='ENCAIXAR', anchor='w', fill='#7c3aed', font=(FONTE_UI, 8, 'bold'), tags='alvo')

    def soltar(self, evento):
        if not self.drag:
            return
        drag = self.drag
        if drag['ativo']:
            self.destacar_alvo(evento.x_root, evento.y_root)
            if self.alvo:
                self.ao_soltar(drag, dict(self.alvo))
        elif 'tipo' in drag:
            self.ao_soltar(drag, None)
        self.cancelar_arrasto()

    def cancelar_arrasto(self):
        if self.ghost:
            self.ghost.destroy()
            self.ghost = None
        self.drag = None
        self.alvo = None
        self.canvas.delete('alvo')
