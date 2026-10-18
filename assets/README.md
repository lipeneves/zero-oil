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

Use PNG com fundo transparente. As texturas de água são a exceção.

**Água:** recrie só `agua_limpa.png` e `agua_poluida.png` com `python gerar_assets.py --agua`.

## Barco (sempre visto de costas)

| Arquivo | Quando aparece |
|---|---|
| `barco_parado.png` | Parado |
| `barco_ar.png` | No pulo, sem espuma (o jogo põe a `sombra.png` na água) |
| `barco_andando_1.png` … `_4.png` | Andando; animação da espuma e da esteira, em loop. |

- **Arte vetorizada:** os 6 quadros são gerados do `boat2.svg` com `python gerar_assets.py --barco-svg` (que também cria os `boat2_*.svg` de cada quadro). O fundo azul e a esteira fixa do SVG são removidos; nos quadros andando o gerador desenha por baixo do barco uma esteira animada (V de ondas + espuma da hélice) em branco semitransparente, para a cor da água aparecer.
- **Camadas do barco (geradas junto):** `cacamba_1.png` … `_8.png` são o óleo na caçamba verde, do vazio ao cheio (o jogo escolhe pela carga). `luz_acesa.png` é a luz da cabine acesa (o jogo faz piscar). `gota_oleo.png` é o óleo recolhido que desce a esteira coletora. No `barco.json`, `esteira` diz de onde até onde a gota desliza. A esteira coletora roda nos quadros `barco_andando_*`.
- **Mesmo tamanho:** os 6 quadros precisam ter o mesmo tamanho. O padrão é o que está em `barco.json`, em `tamanho`.
- **Ponto de apoio:** `apoio` no `barco.json` é o ponto, em pixels a partir do canto de cima à esquerda, onde o barco encosta na água. Se o desenho novo tiver outro tamanho ou posição, ajuste `tamanho` e `apoio`.

## Estação de reciclagem

| Arquivo | O que é | Tamanho |
|---|---|---|
| `estacao_chao.png` | Chão da estação **visto de cima**: a plataforma em cima e a vaga de descarga embaixo | 168×224 |
| `estacao_torre.png` | Torre de reciclagem em pé. O feixe de luz e o contador saem do topo dela | 96×200 |
| `tanque.png` | Os dois tambores nos cantos de trás da plataforma | 32×80 |

**`estacao_chao.png`**
- **Como aparece:** é pintado na água, então ganha a perspectiva e o giro corretos de graça.
- **Tamanho:** equivale a 3 casas de largura por 4 de profundidade, com 56 px por casa. As 2 casas de cima são a plataforma e as 2 de baixo são a vaga.
- **Orientação:** desenhe com a estação **para cima**. O jogo gira a imagem conforme a posição da estação no mapa.

**Torre e tambores:** são desenhados em pé, sempre de frente para a câmera. Por isso devem ser redondos, como cilindros, para parecerem iguais de qualquer lado.

## Objetos

| Arquivo | O que é | Tamanho | Observação |
|---|---|---|---|
| `boia.png` | Boia (obstáculo) | 96×96 | A parte de baixo (~18%) fica "dentro" da água |
| `jato.png` | Jato d'água | 96×144 | — |
| `peixe.png` | Peixe pulando | 96×96 | Virado para a direita |
| `peixe_nadando.png` | Peixe debaixo d'água | 96×72 | Silhueta escura com a barbatana para fora |
| `feixe_luz.png` | Feixe de luz sobre a estação | 32×256 | Transparência em degradê |
| `garrafa.png`, `sacola.png`, `lata_vermelha.png`, `lata_prateada.png` | Lixo boiando | 96×96 | Só aparecem com `TRASH_SHARE` maior que 0 |

## Coisas deitadas na água (vistas de cima)

| Arquivo | O que é | Observação |
|---|---|---|
| `mancha_1.png` … `mancha_4.png` | Manchas de óleo | Pintadas na água; a imagem inteira equivale a 1 casa |
| `seta_guia.png` | Seta do caminho até a descarga | Pintada na água; desenhe apontando para cima |
| `onda.png` | Anel de onda em volta do que boia | O jogo achata conforme a perspectiva |
| `sombra.png` | Sombra do barco no pulo | O jogo achata conforme a perspectiva |
| `agua_limpa.png`, `agua_poluida.png` | Texturas da água | Precisam repetir sem emendas; o jogo ajusta para 224×224 |

## Interface

| Arquivo | O que é |
|---|---|
| `painel.png` | Caixas do placar (160×46) |
| `bussola.png`, `bussola_seta.png` | Fundo da bússola e a seta (desenhe a seta apontando para cima) |
| `placa_contador.png` | Plaquinha do óleo entregue; é esticada na largura do número |
| `minimapa.png` | Moldura do minimapa (108×108); o mapa aparece no quadrado de 96×96 do meio |

## Menu

| Arquivo | O que é | Tamanho |
|---|---|---|
| `logo.png` | Título do jogo na tela inicial | 460×150 |
| `menu_painel.png` | Painel atrás dos botões (menu e pausa) | 300×260 |
| `botao.png` | Botão normal; o texto é escrito pelo jogo | 240×46 |
| `botao_selecionado.png` | Botão selecionado (pelas setas ou com o mouse em cima) | 240×46 |
