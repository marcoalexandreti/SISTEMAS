# CPython com comandos em português — protótipo nativo

Esta entrega contém o código-fonte oficial completo do CPython 3.14.10, um script que aplica as alterações em C, exemplos, testes e instruções de compilação. Não é um produto oficial da Python Software Foundation.

## O que foi implementado

O parser do próprio CPython reconhece palavras-chave portuguesas quando o nome do arquivo termina em **`.ptpy`**. Não há substituição de texto nem um tradutor externo durante a execução. Strings, comentários e posições no arquivo original são preservados. Os comandos ingleses continuam disponíveis.

Foram adicionados aliases de funções e tipos ao módulo de funções embutidas, por exemplo `escreva`, `leia`, `inteiro`, `real`, `texto`, `intervalo` e `tamanho`. Eles apontam para as implementações originais. Não exigem imports ou `sitecustomize`.

A extensão `.ptpy` separa a sintaxe portuguesa da inglesa: uma biblioteca `.py` pode usar variáveis chamadas `e`, `se` ou `para` sem ser afetada pelo parser português. Em arquivos portugueses, esses nomes são palavras reservadas.

## Exemplo

Salve em UTF-8 como `exemplo.ptpy`:

```python
função somar(primeiro, segundo):
    retorne primeiro + segundo

resultado = somar(2, 3)
se resultado >= 20:
    escreva("Chegou a vinte")
senão:
    escreva("Resultado:", resultado)

para numero em intervalo(3):
    escreva(numero)
```

O arquivo `exemplos/inicio.ptpy` inclui outro exemplo pronto.

## Vocabulário principal

| Python | Português |
|---|---|
| def | função / funcao / defina |
| return | retorne |
| if | se |
| elif | senãose / senaose |
| else | senão / senao |
| for | para |
| in | em |
| while | enquanto |
| break | interrompa |
| continue | continue |
| and / or / not | e / ou / não (ou nao) |
| is | é / eh |
| True / False / None | Verdadeiro / Falso / Nenhum |
| import / from / as | importe / de / como |
| try / except / finally | tente / exceto / finalmente |
| raise / assert | lance / afirme |
| with | com |
| class | classe |
| pass / del | passe / apague |
| yield | produza |
| async / await | assíncrono (ou assincrono) / aguarde |
| nonlocal | nãolocal / naolocal |

`global`, `continue` e `lambda` mantêm as grafias originais. As funções adicionadas estão listadas em `vocabulario.json`.

## Compilar no Windows x64

Requisitos de desenvolvimento:

- Windows x64 compatível com CPython 3.14.
- Python 3.12 ou superior instalado com o launcher `py`, para executar `preparar.py`.
- Visual Studio 2022 com ferramentas de desenvolvimento C++ para desktop e Windows SDK, conforme o guia `PCbuild/readme.txt` do CPython.
- Internet para obter as dependências externas solicitadas pelo build oficial.
- Espaço em disco para extrair e compilar o projeto.

Execute `compilar_windows.bat`. Ele extrai o código-fonte, aplica as alterações e chama `PCbuild\build.bat -p x64`.

O executável esperado fica em:

```text
Python-3.14.10\PCbuild\amd64\python.exe
```

Execute um programa com:

```bat
Python-3.14.10\PCbuild\amd64\python.exe exemplos\inicio.ptpy
```

Ou use `executar_windows.bat caminho\programa.ptpy`. Sem argumento, ele executa o exemplo. O BAT não é um instalador nem gera uma distribuição independente: mantenha a árvore de desenvolvimento junto do interpretador.

Execute os testes com:

```bat
Python-3.14.10\PCbuild\amd64\python.exe testar.py
```

A compilação para Windows não foi executada neste ambiente Linux; os scripts seguem o processo do projeto, mas precisam ser validados no computador Windows.

## Compilar no Linux

```sh
python3 preparar.py
cd Python-3.14.10
./configure --without-ensurepip
make -j3
./python ../exemplos/inicio.ptpy
./python ../testar.py
```

São necessários compilador C, make e dependências de desenvolvimento adequadas ao CPython. O arquivo `PCbuild/readme.txt` trata do Windows e o README oficial do projeto aponta a documentação de build.

## Limites desta primeira versão

- **Ainda não é uma linguagem totalmente localizada.** Mensagens de erro, documentação interna, nomes de módulos, métodos, parâmetros nomeados e grande parte da biblioteca padrão continuam em inglês.
- A representação dos objetos não mudou: por exemplo, `escreva(Verdadeiro)` mostra `True`.
- Palavras-chave contextuais `match`, `case` e `type` mantêm a sintaxe inglesa.
- O console interativo, `-c` e arquivos `.py` mantêm as palavras-chave inglesas. `compile`/`ast.parse` reconhecem português se receberem um nome de arquivo terminado em `.ptpy`.
- Imports comuns ainda não procuram módulos `.ptpy`; o protótipo executa scripts `.ptpy` e importa bibliotecas Python normais.
- `keyword`, `tokenize`, editores, formatadores e analisadores externos não foram adaptados ao novo dialeto. Evite presumir compatibilidade dessas ferramentas.
- Palavras reservadas portuguesas também não podem ser usadas como atributos diretamente: por exemplo, para acessar `math.e`, use `getattr(math, "e")` ou uma variável com nome não reservado.
- A indentação, os dois-pontos e as demais regras estruturais continuam sendo os do Python.
- A alteração nativa foi testada em Linux, não em Windows.

## Origem e licença

Fonte oficial: https://www.python.org/ftp/python/3.14.10/Python-3.14.10.tar.xz

SHA-256 do arquivo baixado:

```text
de414a57119abef52784d8993e341d53aed635fc2b05c2607d9f98a2c5b72032
```

`preparar.py` verifica esse hash antes de extrair um novo diretório. O pacote oficial inclui a licença PSF e os avisos de terceiros em `LICENSE` e nos arquivos correspondentes. Preserve-os ao redistribuir. As mudanças desta entrega estão em `alteracoes.patch` e no script `preparar.py`.

## Validação desta entrega

- Compilação nativa do CPython modificado em Linux: concluída.
- Execução do exemplo `.ptpy`: concluída.
- 16 testes próprios de integração: passaram.
- Suítes oficiais `test_grammar`, `test_builtin`, `test_fstring` e `test_import`: resultado de sucesso, 436 testes executados e 10 ignorados pelo runner. Não foi executada a suíte completa do CPython.
- Extração limpa, aplicação do patch, reaplicação idempotente e comparação dos arquivos gerados: verificadas.
- O build Linux disponível não inclui módulos opcionais cujas dependências de desenvolvimento não estavam instaladas, entre eles `_tkinter`, `_ctypes`, `_bz2`, `_lzma`, `readline`, `_uuid`, módulos de curses e bancos DBM. Isso não impediu os testes acima e não estabelece quais módulos estarão disponíveis no build Windows.

Os resultados completos das verificações estão em `testes_portugues.log` e `testes_cpython.log`.
