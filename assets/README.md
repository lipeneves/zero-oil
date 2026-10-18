# Assets

O jogo só desenha imagens desta pasta. Os únicos textos gerados por código são os números e as mensagens, que usam a fonte do sistema.

A arte padrão é criada pelo `gerar_assets.py`:

- **Sprites simples:** desenhados com o pygame.
- **Barco e estação:** renderizados a partir de modelos 3D feitos à mão (sprites pré-renderizados).

O jogo gera automaticamente qualquer arquivo que estiver faltando.

## Como substituir

1. Troque o PNG por outro **com o mesmo nome**.
2. Rode o jogo.

Para voltar ao desenho original, apague o arquivo. Ele é recriado na próxima vez.

Para recriar **tudo**, rode `python gerar_assets.py --todos`. Atenção: isso sobrescreve a sua arte.

Use PNG com fundo transparente. A textura de água do menu é a exceção.

**Água:** a água do jogo não é imagem: o fundo e as ondas são desenhados pelo código (cores em `WATER_COLORS` e formato das ondas em `water_bands`, no `blue_sphere.py`). Só o fundo do menu usa a textura `agua_limpa.png`, feita com as mesmas ondas; recrie com `python gerar_assets.py --agua`.

## Barco (sempre visto de costas)

| Arquivo | Quando aparece |
|---|---|
| `barco_parado.png` | Parado |
| `barco_ar.png` | No pulo, sem espuma (o jogo põe a `sombra.png` na água) |
| `barco_andando_1.png` … `_4.png` | Andando; animação da espuma e da esteira, em loop. |

- **Arte vetorizada:** os 6 quadros são gerados do `base/barco-cartoon.svg` com `python gerar_assets.py --barco-svg` (que também cria os `barco_*.svg` de cada quadro). O desenho é encaixado no quadro (`BOAT_SVG_FIT`); nos quadros andando o gerador desenha por baixo do barco uma esteira animada (V de ondas + espuma da hélice) em branco semitransparente, para a cor da água aparecer. O óleo enche o baú aberto de trás (camadas `cacamba_1..8.png`): no SVG, `id="cacamba"` é a boca do baú e `id="cacamba_parede"` a parede de dentro que aparece (a altura dela é o quanto o óleo sobe). A luz da cabine tem `id="luz"`.
- **Camadas do barco (geradas junto):** `cacamba_1.png` … `_8.png` são o óleo na caçamba verde, do vazio ao cheio (o jogo escolhe pela carga). `luz_acesa.png` é a luz da cabine acesa (o jogo faz piscar). `gota_oleo.png` é o óleo recolhido que desce a esteira coletora. No `barco.json`, `esteira` diz de onde até onde a gota desliza. A esteira coletora roda nos quadros `barco_andando_*`.
- **Mesmo tamanho:** os 6 quadros precisam ter o mesmo tamanho. O padrão é o que está em `barco.json`, em `tamanho`.
- **Ponto de apoio:** `apoio` no `barco.json` é o ponto, em pixels a partir do canto de cima à esquerda, onde o barco encosta na água. Se o desenho novo tiver outro tamanho ou posição, ajuste `tamanho` e `apoio`.

## Vidas

| Arquivo | O que é | Tamanho |
|---|---|---|
| `base/coracao.svg` | Coração vermelho do placar (um por vida), estilo cartoon: contorno escuro, sombra embaixo e brilho em cima; o jogo lê o SVG direto em 28×26 | 100×92 |

## Estação de reciclagem

| Arquivo | O que é | Tamanho |
|---|---|---|
| `base/estacao_chao.svg` | Chão da estação **visto de cima** (56 unidades = 1 casa; o jogo lê o SVG direto), estilo cartoon: em cima, a sombra da plataforma de petróleo e as ondinhas das 4 colunas (o tampo e as colunas são desenhados em 3D pelo jogo, ver `DECK_*` em `blue_sphere.py`); embaixo, a vaga de descarga (3×3 casas) | 168×252 |
| `estacao_torre.svg` | Torre de vidro redonda antiga (não usada: o tanque de vidro agora é quadrado e desenhado em 3D pelo jogo, ver `TANK_*` em `blue_sphere.py`) | 240×500 |

**`base/estacao_chao.svg`**
- **Como aparece:** fica deitado na água; o jogo gira junto com a câmera e estica em faixas com a perspectiva do chão.
- **Tamanho:** equivale a 3 casas de largura por 4,5 de profundidade, com 56 unidades por casa (168×252). A 1,5 casa de cima fica embaixo da plataforma e as 3 de baixo são a vaga (quadrada). Mantenha esse tamanho ao editar.
- **Orientação:** desenhe com a estação **para cima**. O jogo gira a imagem conforme a posição da estação no mapa.

**Plataforma e tanque de vidro:** são desenhados em 3D pelo jogo (função `oil_rig` em `blue_sphere.py`), com o óleo entregue subindo dentro do tanque. O feixe de luz e o marcador de reciclagem (`popup_reciclagem.svg`) saem da tampa do tanque.

**Arte vetorizada:** a torre (`estacao_torre.svg`), o chão (`base/estacao_chao.svg`) e o marcador (`popup_reciclagem.svg`) são SVGs no estilo cartoon do barco, carregados direto pelo jogo: é só editar e rodar.

## Objetos

| Arquivo | O que é | Tamanho | Observação |
|---|---|---|---|
| `base/boia.svg` | Boia de sinalização (obstáculo), estilo cartoon | 96×96 | A parte de baixo (~18%) fica "dentro" da água: o flutuador é cortado em y = 79 |
| `base/jato.svg` | Jato d'água (lança o barco num pulo), estilo cartoon | 96×144 | Desenhe nas cores da água limpa: o jogo tinge para a cor da água poluída conforme a poluição (o contorno `#20242b` não muda). Ele estica a altura para o jato pulsar; a base fica em y ≈ 128 |
| `base/peixe.svg` | Peixe pulando, estilo cartoon (contorno escuro, brilho e barriga clara); o jogo lê o SVG direto | 96×96 | Virado para a direita |
| `base/peixe_nadando.svg` | Peixe debaixo d'água | 96×72 | Silhueta escura com a barbatana laranja (cartoon) para fora |
| `feixe_luz.png` | Feixe de luz sobre a estação | 32×256 | Transparência em degradê |

## Coisas deitadas na água (vistas de cima)

| Arquivo | O que é | Observação |
|---|---|---|
| `mancha_1.png` … `mancha_4.png` | Manchas de óleo pretas com contorno escuro (geradas por `make_slick` no `gerar_assets.py`) | Pintadas na água; a imagem inteira equivale a 1 casa |
| `base/seta_guia.svg` | Seta do caminho até a descarga | Pintada na água; desenhe apontando para cima |
| `base/onda.svg` | Anel de onda em volta do que boia (boias e peixes) | O jogo achata conforme a perspectiva. Desenhe nas cores da água limpa: o jogo tinge para a cor da água poluída |
| `sombra.png` | Sombra do barco no pulo | O jogo achata conforme a perspectiva |
| `agua_limpa.png` | Água do fundo do menu | Precisa repetir sem emendas (224×224). A água do jogo é desenhada pelo código |

## Interface

| Arquivo | O que é |
|---|---|
| `placa_contador.png` | Plaquinha do óleo entregue (não usada no jogo por enquanto) |
| `base/minimapa.svg` | Moldura redonda do minimapa, estilo cartoon (108×108); o jogo desenha o mapa no círculo do meio (raio 44) |
| `base/minimapa_barco.svg` | Setinha amarela do barco no centro do minimapa (desenhada em 16×16) |

## Menu

| Arquivo | O que é | Tamanho |
|---|---|---|
| `logo.png` | Título do jogo na tela inicial | 460×150 |
| `menu_painel.png` | Painel atrás dos botões (menu e pausa) | 300×260 |
| `botao.png` | Botão normal; o texto é escrito pelo jogo | 240×46 |
| `botao_selecionado.png` | Botão selecionado (pelas setas ou com o mouse em cima) | 240×46 |
