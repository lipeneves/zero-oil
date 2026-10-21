# Zero Oil

Barco catador de lixo para o console T-TEA (chão interativo), em Pygame. Releitura
da fase especial do Sonic 3 & Knuckles: recolha o óleo do rio, leve a caçamba até
a estação e desvie dos peixes e dos cones.

O jogo roda dentro do [T-TEA](https://github.com/larvattea/ttea), que projeta a
tela no chão e acompanha os pés do jogador com uma webcam.

## Rodar no console (passo a passo)

### 1. Preparar o computador

Só na primeira vez em um computador novo. Precisa de internet.

```powershell
winget install --id=astral-sh.uv -e
git clone https://github.com/larvattea/ttea C:\Projects\ttea
```

Feche e abra o PowerShell depois de instalar o `uv`.

### 2. Instalar o jogo no T-TEA

Da pasta deste repositório:

```powershell
python instalar_ttea.py C:\Projects\ttea
```

O jogo é copiado para `C:\Projects\ttea\src\ttea\games\zerooil`. Rode de novo
sempre que alterar o jogo. Os recordes, as opções e as corridas salvas lá não
são apagados.

### 3. Abrir o T-TEA

Da pasta do T-TEA:

```powershell
cd C:\Projects\ttea
uv run dev
```

Na primeira vez ele baixa o Python e as dependências (MediaPipe, OpenCV, Pygame,
PySide6), o que leva alguns minutos e precisa de internet. Se o Windows
perguntar, libere o acesso à câmera.

### 4. Montar o hardware

- Ligue o **projetor** como segunda tela (Windows + P → Estender), apontado
  para o chão.
- Posicione a **webcam** vendo toda a área projetada.
- Ligue os dois **antes** de abrir o T-TEA.

### 5. Calibrar no T-TEA

Sem a calibração o T-TEA não deixa iniciar o jogo.

1. Na configuração de calibração, escolha a **câmera** e a **tela do projetor**
   e salve.
2. Faça a calibração (automática ou manual, marcando os 4 cantos da projeção).

### 6. Jogar

1. Cadastre um **profissional** e um **jogador** (ou escolha os já cadastrados).
2. Escolha o **Zero Oil** e clique em jogar.

O jogo abre em tela cheia no projetor, com o controle pelos pés.

## Como se joga no console

Na parte de baixo da tela ficam as marcações:

| Marcação | O que faz |
| --- | --- |
| Pegadas (no meio) | ficar parado nelas faz o barco começar a andar |
| Setas (dos lados) | vira o barco para esse lado |
| Botões dos menus | parado em cima, o anel enche e escolhe |

Basta um pé na marcação. Cada pisada vale uma vez: para repetir, tire o pé e
pise de novo.

Teclado e mouse continuam funcionando para o profissional. Em
**OPÇÕES → CONTROLE** dá para trocar entre CONSOLE TTEA e TECLADO.

## Painel de ajustes (Ctrl+D)

Durante o jogo (ou nos menus), **Ctrl+D** abre um painel para mudar parâmetros
na hora, sem mexer no código:

- **JOGO:** velocidade inicial e máxima, aceleração, quanto cada rio acelera,
  tempo da curva, quanto o barco freia e demora para retomar, câmera seguindo,
  zoom da câmera (mais perto ou mais longe), linha do barco na tela (mais
  para cima, longe das setas) e barcos no início. Tem **um perfil para cada
  controle** (TECLADO e PÉS), porque com os pés o jogador reage mais devagar.
  Vale o perfil do controle em uso.
- **CONSOLE** (só no console ou com `--simular-pes`): tamanho e altura das
  setas, distância delas até o meio, tamanho das pegadas, folga da detecção e os
  tempos (parado para sair, parado para escolher, pés somem sem ver).

| Tecla | O que faz |
| --- | --- |
| Setas cima/baixo | escolher o parâmetro |
| Setas lados | mudar (com Shift: 5 passos) |
| Del / Backspace | voltar ao padrão (com Shift: a seção inteira) |
| P | pausar / continuar o jogo |
| Tab | trocar entre pés e teclado (e o perfil), só no console |
| Ctrl+D | fechar |

Com o painel aberto, o teclado controla o painel; os pés (ou o mouse da
simulação) continuam jogando. Os valores fora do padrão ficam em amarelo e são
gravados em `ajustes.json`, com o nome da constante do código, e voltam na
próxima vez. No T-TEA ele fica em
`C:\Projects\ttea\src\ttea\games\zerooil\ajustes.json`, junto do `zerooil.log`
(reinstalar o jogo não apaga). Quando achar bons valores, passe-os para as
constantes em `zero_oil.py` / `console_ttea.py`.

## Problemas comuns

| Problema | O que fazer |
| --- | --- |
| "O arquivo de calibração não foi encontrado" | faça o passo 5 |
| Avisa que a câmera ou a tela mudou | as portas mudaram: salve a configuração de hardware de novo |
| Os pés não aparecem / o jogo só responde ao teclado | veja o `zerooil.log` (abaixo); confira se a câmera vê a área toda e se há luz suficiente |
| O jogo abre no monitor errado | confira a tela escolhida na calibração |
| O T-TEA não abre | rode `uv run dev` de novo dentro de `C:\Projects\ttea` e leia o erro |

O log do jogo fica em `C:\Projects\ttea\src\ttea\games\zerooil\zerooil.log`.
Ele diz se a câmera ligou, se encontrou a calibração e por que caiu para o
teclado.

## Testar sem o console

Sem câmera nem projetor, da pasta deste repositório (precisa do `pygame`:
`pip install pygame`):

```powershell
python zero_oil.py                 # só teclado
python zero_oil.py --simular-pes   # o mouse faz o papel dos pés, com as marcações
```

Para testar com o mesmo Python (e as mesmas versões) do T-TEA:

```powershell
C:\Projects\ttea\.venv\Scripts\python C:\Projects\ttea\src\ttea\games\zerooil\zero_oil.py --simular-pes
```

Também dá para ligar a simulação com a variável de ambiente
`ZEROOIL_SIMULAR_PES=1`. Ela vale inclusive quando o jogo é aberto pelo T-TEA.

Controles do teclado: setas esquerda/direita viram, Espaço pula, R recomeça a
corrida e Esc pausa.

## Checklist antes de sair

- [ ] `python instalar_ttea.py C:\Projects\ttea` com a versão final do jogo
- [ ] `uv run dev` abriu pelo menos uma vez (dependências já baixadas)
- [ ] `python zero_oil.py --simular-pes` funcionando, com o painel (Ctrl+D) abrindo
- [ ] Notebook com carregador, cabo HDMI para o projetor e webcam USB
