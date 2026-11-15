# Python em português — protótipo nativo

Extensão experimental do CPython 3.14.10 com palavras-chave em português em arquivos `.ptpy`.

## IDE visual em português

A **Lume IDE** oferece sugestões ao digitar comandos e funções, montagem de programas com formas geométricas arrastáveis, editor com cores e console interativo.

- [Baixar a IDE](https://github.com/marcoalexandreti/SISTEMAS/raw/refs/heads/main/python-portugues/Lume_IDE_Portugues.zip)
- [Ver instruções e capturas de tela](ide/README.md)

Para abrir no Windows, extraia o ZIP e execute `iniciar_ide.bat` com Python 3.12+ instalado. Não é necessário compilar o CPython para usar a execução integrada.

## Baixar o interpretador nativo

[Baixar o pacote completo (ZIP, aproximadamente 24 MB)](https://github.com/marcoalexandreti/SISTEMAS/raw/refs/heads/main/python-portugues/Python_em_Portugues_Prototipo.zip)

O ZIP inclui o código-fonte oficial completo, as alterações, exemplos e instruções para compilar.

## Exemplo

```python
função somar(a, b):
    retorne a + b

resultado = somar(2, 3)
se resultado >= 20:
    escreva("Chegou a vinte")
senão:
    escreva("Resultado:", resultado)
```

## Windows

1. Baixe e extraia o ZIP.
2. Leia `LEIA-ME.md`.
3. Instale os requisitos de desenvolvimento descritos no guia: Python 3.12+ e ferramentas C++/SDK do Visual Studio 2022.
4. Execute `compilar_windows.bat`.

**O build e a execução foram validados em Linux. A compilação Windows ainda precisa ser validada.** Não há instalador Windows pronto neste pacote.

## Validação e limites

16 testes próprios passaram. As suítes oficiais selecionadas de gramática, funções embutidas, f-strings e imports tiveram resultado de sucesso (436 testes executados; 10 ignorados). A suíte completa não foi executada.

A localização é parcial: mensagens de erro, biblioteca padrão, ferramentas e vários nomes de APIs ainda estão em inglês. Não é um produto oficial da Python Software Foundation. As licenças e avisos do CPython estão preservados dentro do arquivo-fonte oficial incluído.

SHA-256 do ZIP:

```text
754f1fa4077a3d96dac555eded3d0d04b1b08a4414f4c3be9fe4f335217ba95b
```
