"""Zero Oil - Barco Catador de Lixo, em Pygame puro.

Releitura da fase especial do Sonic 3 & Knuckles: um barco limpando um rio
poluido. O chao de agua tem perspectiva (estilo "Mode 7"): as ondas sao
poligonos projetados direto na tela, e as manchas, as setas do guia e o chao
da estacao sao imagens deitadas nele, esticadas em faixas. O resto vem da pasta
assets/: o barco e um sprite pre-renderizado e as boias, o marcador da
estacao... sao imagens em pe (tudo gerado por gerar_assets.py).

Corrida infinita: limpe um rio atras do outro; cada rio e um pouco mais
dificil (mais oleo, cones, jatos e velocidade). A corrida acaba quando os
barcos acabam. Bata o seu recorde!

Regras:
  Oleo      recolha as manchas; a cacamba leva 16, depois leve ate a estacao
  Estacao   passe pela vaga tracejada para descarregar (o guia mostra o caminho)
  Peixe     cada mancha recolhida solta um peixe: nao passe por cima!
  Cone      nao bata (aparecem a partir do rio 2)
  Jato      lanca o barco num pulo longo
  Barcos    3 no inicio; +1 a cada 3 rios limpos (maximo 5)
  Pontos    manchas seguidas fazem combo; cacamba cheia vale x2; rio rapido da bonus

Menu: setas para cima/baixo + Enter (ou o mouse).

Controles:
  Setas esquerda/direita  virar (no centro da proxima casa)
  Qualquer tecla          comecar a andar
  Espaco                  pular (de novo no ar: salto duplo; no console TTEA o
                          jogador tambem pula de verdade: veja Game.feet_jump)
  R                       recomecar a corrida na hora
  Esc                     pausar (no menu principal: sair)

No console TTEA (chao interativo) o barco e controlado pelos pes: veja
console_ttea.py. Para instalar no console: python instalar_ttea.py <pasta do TTEA>.
"""
import bisect
import io
import json
import math
import os
import random
import re
import sys
import time
import warnings
from collections import deque

import pygame

import console_ttea
import painel_ajustes

try:  # contas das ondas em lote (a tela larga do console tem muitos pontos); sem ele, em Python
    import numpy as np
except ImportError:
    np = None

W, H = 640, 480
WINDOW_FILL = 0.9  # janela maior que esta fracao do monitor nao cabe (barras de titulo e de tarefas): maximiza
RESOLUTION_HEIGHTS = (720, 900, 1080, 1440, 2160)  # alturas das janelas da tela OPÇÕES
DEFAULT_RESOLUTION = "1191 x 670"  # janela da primeira vez (sem config.json com outra escolha)
FPS = 60
N = 32  # tamanho do tabuleiro (as bordas se conectam)

EMPTY, OIL, BUOY, SPOUT, DOCK, FISH, STATION = range(7)

# --- camera e chao ------------------------------------------------------------
R = 9.0          # altura do chao no espaco 3D
CAM_H = 5.0      # altura da camera acima do jogador
CAM_B = 2.2      # distancia da camera atras do jogador
PITCH = 0.86     # inclinacao da camera para baixo (rad)
FOCAL = 520.0
Y0 = 150         # linha da tela onde fica o eixo optico
RNG = 13         # casas desenhadas em cada direcao
LIM = 13.5       # distancia maxima desenhada
GROUND_PPC = 112 # pixels por casa das imagens deitadas no chao (manchas, setas, estacao)
WATER_PERIOD = 4 # o desenho das ondas se repete a cada 4 casas
WATER_STEP = WATER_PERIOD / 32  # casas entre os pontos das ondas
STRIP = 2        # altura (px) de cada faixa do chao na tela
GROUND_WHOLE = 1.5  # imagens do chao ate este tamanho (casas) sao esticadas inteiras
WATER_COLORS = {  # (fundo, ondas); o jogo mistura as duas conforme a poluicao
    "clean": ((74, 178, 228), (124, 205, 240)),
    "dirty": ((84, 96, 58), (108, 122, 78)),
}
WATER_FOAM_DIRTY = (205, 212, 175)  # o branco da espuma na agua poluida
WATER_TINT_STEPS = 24  # tons entre a agua limpa e a poluida (jato d'agua)

CAM = (0.0, R + CAM_H, -CAM_B)
CP, SP = math.cos(PITCH), math.sin(PITCH)
PLAYER_DEPTH = CAM_H * SP + CAM_B * CP  # profundidade do jogador vista pela camera
CELL_PX = FOCAL / PLAYER_DEPTH  # tamanho (px) de uma casa no barco: o desenho do barco foi feito para ele
CAM_ZOOM = 1.0  # camera mais perto (> 1: casas e barco maiores) ou mais longe (< 1); muda com set_screen_size
BASE_W, BASE_H = W, H  # tamanho para o qual os menus foram desenhados (a tela do console e maior)


def set_screen_size(width, height, boat_y=None, view=None, bottom_angle=math.radians(88)):
    """Tela maior (console TTEA: na proporcao da tela calibrada, com espaco
    embaixo para as marcacoes do chao); o rio continua ate embaixo.

    Sem view, a camera e a lente continuam as de sempre e, com boat_y, so o
    centro da imagem desce junto com o barco (ele fica na linha boat_y, na mesma
    posicao em relacao ao centro).

    Com view = (angulo do barco, inclinacao), em graus a partir da horizontal, a
    camera fica mais de cima: o barco e visto daquele angulo e a camera inclina
    tanto (menos que o angulo do barco: ele fica um pouco abaixo do centro). A
    lente, a altura e a distancia saem das contas para o barco ficar na linha
    boat_y, a ultima linha olhar para o chao a bottom_angle da horizontal e uma
    casa ter, no barco, CELL_PX * CAM_ZOOM na tela (o desenho do barco foi
    feito para CELL_PX e e ampliado junto). Pode ser chamada de novo com o jogo
    rodando (painel de ajustes): depois, Game.setup_view."""
    global W, H, Y0, FOCAL, PITCH, CAM_H, CAM_B, CAM, CP, SP, PLAYER_DEPTH, RNG, LIM
    W, H = width, height
    if view is not None:
        px_per_cell = CELL_PX * CAM_ZOOM
        elev, pitch = (math.radians(a) for a in view)
        below = math.tan(elev - pitch)  # o barco abaixo do centro da imagem (tangente)
        FOCAL = (H - boat_y) / (math.tan(bottom_angle - pitch) - below)
        Y0 = boat_y - FOCAL * below
        PITCH = pitch
        CP, SP = math.cos(PITCH), math.sin(PITCH)
        CAM_H = FOCAL / px_per_cell / (SP + CP / math.tan(elev))
        CAM_B = CAM_H / math.tan(elev)
        CAM = (0.0, R + CAM_H, -CAM_B)
        PLAYER_DEPTH = CAM_H * SP + CAM_B * CP
    elif boat_y is not None:
        Y0 += boat_y - project(surface_point(0, 0))[1]
    if PITCH + math.atan((H - Y0) / FOCAL) >= math.radians(89.5):  # a ultima linha olharia atras da camera
        raise ValueError("tela alta demais para a camera: %dx%d com o barco na linha %s" % (W, H, boat_y))
    # desenha os objetos ate os cantos de cima da tela mais larga (o laco do
    # desenho limita a uma volta do rio, que tem as bordas conectadas)
    far = floor_f(0)
    LIM = max(LIM, math.hypot(far, floor_half(far)) + 0.5)
    RNG = max(RNG, math.ceil(LIM))

# direcoes no sentido horario: norte, leste, sul, oeste (curvas de 90 graus).
# Para curvas de 45 graus use: [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
ND = len(DIRS)
TURN_ANGLE = math.tau / ND

SPEED_START = 4.0
SPEED_MAX = 9.0
# perfil PES (console TTEA): o que muda do padrao acima. Com os pes o jogador
# reage mais devagar; o painel de ajustes (Ctrl+D) parte destes valores
FEET_DEFAULTS = {"SPEED_START": 2.0, "SPEED_MAX": 5.0}
SPEED_GAIN = 1 / 18  # casas/s ganhas por segundo de jogo
SPEED_RIVER = 0.35   # casas/s a mais na largada a cada rio (a maxima sobe 0.25 / 0.35 disso)
SPEED_RIVER_CAP = (3.0, 2.0)  # o que os rios somam, no maximo, a largada e a maxima
TURN_TIME = 0.24     # segundos que o barco leva para virar
TURN_SLOW = 0.55     # fracao da velocidade no centro da curva (freia antes, acelera depois)
TURN_BRAKE = 0.5     # casas antes do centro em que o barco comeca a frear para virar
TURN_RECOVER = 0.35  # segundos para voltar a velocidade toda depois de virar
MENU_X = 430            # meio do bloco do menu (titulo e botoes), a direita do barco
MENU_BUTTON = (230, 63)       # botoes dos menus: largura e distancia entre os centros
FEET_MENU_BUTTON = (290, 82)  # com os pes (console TTEA): maiores e mais afastados, sem um encostar no outro
MENU_BOAT_ANGLE = 0     # direcao do barco do menu (graus a partir de "para cima", sentido horario)
MENU_BUTTON_FONT = ("Rubik-Bold.ttf", 19, 21)  # fonte dos botoes (normal, selecionado); outra: ("Creepster-Regular.ttf", 26, 28)
MENU_WATER_SPEED = 70   # velocidade da agua rolando no menu (px/s)
CAM_FOLLOW = 12.0   # quao rapido a camera alcanca o barco nas curvas (maior = mais colada)
ITEM_R = 0.4
POPUP_LIFT = 0.15     # altura do marcador de reciclagem acima da agua (casas), no meio da vaga
DOCK_CLEAR = 2        # casas livres em volta da estacao (mais 3 na frente da vaga)
HUD_Y = 36            # linha do alto da tela (meio): coracoes, "RIO x" e pontos / recorde
LIVES_START = 3       # barcos no inicio da corrida
BELT_TIME = 0.45      # segundos que o oleo recolhido leva para descer a esteira ate a cacamba
MAP_CELL = 6         # minimapa: pixels por casa no desenho (reduzido para 3 na tela)
MAP_RADIUS = 44      # raio do circulo do minimapa na tela
MAP_ALPHA_CONSOLE = 130  # no console o minimapa fica no meio do alto: semitransparente (0 a 255)
FISH_SCALE = 0.62     # tamanho do peixe em relacao a casa (1 = a casa toda)
LIGHT_BLINK = 0.8     # a luz em cima do barco pisca a cada 0.8 s (acesa na primeira metade)
LIVES_MAX = 5
CAPACITY = 16       # itens que cabem na cacamba

# --- geometria ----------------------------------------------------------------
def surface_point(l, f, lift=0.0):
    """Ponto 3D no chao plano para um deslocamento lateral l e frontal f (em casas)."""
    return l, R + lift, f


def project(p):
    """Projecao perspectiva: devolve (x_tela, y_tela, profundidade, visivel)."""
    x, y, z = p[0] - CAM[0], p[1] - CAM[1], p[2] - CAM[2]
    cz = -y * SP + z * CP
    if cz < 0.05:
        return None
    cy = y * CP + z * SP
    k = FOCAL / cz
    return W / 2 + x * k, Y0 - cy * k, cz, True


# --- geracao de fases ---------------------------------------------------------
def river_params(river):
    """Dificuldade de cada rio da corrida (rio 1 = aprender)."""
    k = max(0, river - 2)
    return {
        "blocks": min(9, river + 1),                               # blocos de oleo: 2, 3, 4...
        "jet": 0.0 if river < 3  # chance de um bloco virar jato (sem jatos nos rios 1 e 2)
        else min(0.3, 0.12 + 0.03 * k),
        "cross": 0.0 if river < 2 else min(0.65, 0.25 + 0.07 * k),  # cone nos cruzamentos
        "lane": 0.0 if river < 2 else min(0.4, 0.12 + 0.05 * k),    # cone nos corredores
    }


def generate_level(river, seed=0):
    """Rio no estilo do Blue Sphere: blocos 4x4 de oleo numa grade, separados
    por corredores vazios de 4 casas. A largada e a estacao ficam em cruzamentos
    de corredores, com uma area livre em volta da estacao. A cada rio entram mais
    blocos, mais cones (so nos corredores) e jatos. O seed muda a cada corrida."""
    rnd = random.Random(seed * 1000 + river)
    prm = river_params(river)
    g = [[EMPTY] * N for _ in range(N)]
    C = N // 2
    BLOCK, PERIOD = 4, 8
    origin = (C + 2) % PERIOD  # blocos comecam 2 casas depois da largada: ela fica no corredor

    # um unico ponto de descarga, num cruzamento de corredores vizinho da largada
    a, b = rnd.choice([(0, -PERIOD), (PERIOD, 0), (0, PERIOD), (-PERIOD, 0)])
    sa, sb = (a > 0) - (a < 0), (b > 0) - (b < 0)  # direcao da largada para a estacao
    pa, pb = -sb, sa                                 # direcao lateral
    for w in (-1, 0, 1):  # 3 casas de largura
        for k in (-2, -1, 0):  # vaga: 3 casas de profundidade (quadrada)
            g[(C + b + sb * k + pb * w) % N][(C + a + sa * k + pa * w) % N] = DOCK
        for k in (1, 2):   # estacao: 2 casas logo atras da vaga (a plataforma desenhada ocupa 1,5)
            g[(C + b + sb * k + pb * w) % N][(C + a + sa * k + pa * w) % N] = STATION
    # area livre em volta da estacao (2 casas) e na frente da vaga (mais 3): nenhum
    # bloco encosta nela, para o barco nao bater em nada quando a estacao o empurra
    zone = {((C + a + sa * k + pa * w) % N, (C + b + sb * k + pb * w) % N)
            for w in range(-1 - DOCK_CLEAR, 2 + DOCK_CLEAR)
            for k in range(-2 - DOCK_CLEAR - 3, 3 + DOCK_CLEAR)}

    def block_cells(bx, by):
        return {((bx + i) % N, (by + j) % N) for i in range(BLOCK) for j in range(BLOCK)}

    def dist(blk):  # distancia do centro do bloco ate a largada
        dx = (blk[0] + 1.5 - C + N / 2) % N - N / 2
        dy = (blk[1] + 1.5 - C + N / 2) % N - N / 2
        return math.hypot(dx, dy)

    blocks = [(bx % N, by % N) for by in range(origin, N + origin, PERIOD) for bx in range(origin, N + origin, PERIOD)]
    free = sorted((blk for blk in blocks if not block_cells(*blk) & zone), key=dist)
    pool = free[:prm["blocks"] + (0 if river == 1 else 3)]  # perto da largada: viagens rapidas
    chosen = sorted(rnd.sample(pool, min(len(pool), prm["blocks"])), key=dist)

    # blocos sempre cheios de oleo (dentro deles o desafio sao os peixes);
    # de vez em quando um bloco vira um jato d'agua. "o" = mancha, "j" = jato
    full = ["oooo", "oooo", "oooo", "oooo"]
    jet = ["....", ".j..", "....", "...."]
    for i, (bx, by) in enumerate(chosen):
        art = full
        if i > 0 and rnd.random() < prm["jet"]:  # o bloco mais perto e sempre de oleo
            art = jet
        for j2, row in enumerate(art):
            for i2, ch in enumerate(row):
                if ch != ".":
                    g[(by + j2) % N][(bx + i2) % N] = {"o": OIL, "b": BUOY, "j": SPOUT}[ch]

    # cones so nos corredores e cruzamentos (no maximo um por trecho: sempre sobra
    # passagem), longe da largada e da estacao
    def clear_around(x, y, r):
        for ey in range(-r, r + 1):
            for ex in range(-r, r + 1):
                if g[(y + ey) % N][(x + ex) % N] in (DOCK, STATION):
                    return False
        return (x, y) not in zone and g[y][x] == EMPTY and \
            max(abs((x - C + N // 2) % N - N // 2), abs((y - C + N // 2) % N - N // 2)) > 3

    lanes = [origin + BLOCK + k * PERIOD for k in range(N // PERIOD)]  # inicio de cada corredor
    starts = [origin + k * PERIOD for k in range(N // PERIOD)]       # inicio de cada bloco
    for y0 in lanes:
        for x0 in lanes:  # cruzamentos: um cone no miolo
            x, y = (x0 + rnd.randint(1, 2)) % N, (y0 + rnd.randint(1, 2)) % N
            if rnd.random() < prm["cross"] and clear_around(x, y, DOCK_CLEAR + 1):
                g[y][x] = BUOY
        for b0 in starts:  # trechos de corredor entre dois blocos
            for x, y in (((b0 + rnd.randint(0, 3)) % N, (y0 + rnd.randint(0, 3)) % N),
                         ((y0 + rnd.randint(0, 3)) % N, (b0 + rnd.randint(0, 3)) % N)):
                if rnd.random() < prm["lane"] and clear_around(x, y, DOCK_CLEAR + 1):
                    g[y][x] = BUOY
    return g


RECORD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recorde.json")


def load_record():
    try:
        with open(RECORD_FILE, encoding="utf-8") as fp:
            rec = json.load(fp)
        return {"pontos": int(rec.get("pontos", 0)), "rio": int(rec.get("rio", 0))}
    except (OSError, ValueError):
        return {"pontos": 0, "rio": 0}


def save_record(points, river):
    try:
        with open(RECORD_FILE, "w", encoding="utf-8") as fp:
            json.dump({"pontos": points, "rio": river}, fp)
    except OSError:
        pass


# --- imagens -------------------------------------------------------------------
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


# --- sons ----------------------------------------------------------------------
# efeitos em assets/sons/<nome>.ogg ou .wav (creditos e licencas no assets/README.md)
SOUND_VOLUME = {"oleo": 0.5, "menu_mover": 0.5, "jato": 0.7}
MUSIC_VOLUME = 0.22
sounds = {}
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
volume = {"musica": 1.0, "efeitos": 1.0}  # niveis da tela OPÇÕES (0 a 1), por cima dos volumes acima
# janela da tela OPÇÕES fora do TTEA: resolucao "L x A" e tela cheia
config = {"resolucao": DEFAULT_RESOLUTION, "tela_cheia": False}


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fp:
            cfg = json.load(fp)
        for key in volume:
            volume[key] = min(1.0, max(0.0, float(cfg.get(key, volume[key]))))
        if isinstance(cfg.get("resolucao"), str):
            config["resolucao"] = cfg["resolucao"]
        config["tela_cheia"] = bool(cfg.get("tela_cheia", False))
        if config["resolucao"] == "TELA CHEIA":  # versao em que a tela cheia era uma das resolucoes
            config["resolucao"], config["tela_cheia"] = None, True
    except (OSError, ValueError, AttributeError):
        pass


def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as fp:
            json.dump({**volume, **config}, fp)
    except OSError:
        pass


def init_sounds():
    """Liga o audio e carrega os efeitos. Sem placa de som (ou sem os arquivos)
    o jogo segue mudo, sem erro."""
    try:
        pygame.mixer.init()
        pygame.mixer.set_num_channels(16)
    except pygame.error:
        return
    folder = os.path.join(ASSETS_DIR, "sons")
    for file in os.listdir(folder) if os.path.isdir(folder) else []:
        name, ext = os.path.splitext(file)
        if ext in (".ogg", ".wav") and name != "musica":
            try:
                sounds[name] = pygame.mixer.Sound(os.path.join(folder, file))
                sounds[name].set_volume(SOUND_VOLUME.get(name, 0.8))
            except pygame.error:
                pass
    try:
        pygame.mixer.music.load(os.path.join(folder, "musica.ogg"))
        pygame.mixer.music.set_volume(MUSIC_VOLUME * volume["musica"])
        pygame.mixer.music.play(-1)  # musica de fundo em loop, no menu e no jogo
    except pygame.error:
        pass


def play(name):
    if name in sounds:
        channel = sounds[name].play()
        if channel:
            channel.set_volume(volume["efeitos"])


def music_volume(k):
    """Abaixa a musica (k < 1) na pausa e no fim de jogo; 1 volta ao normal."""
    if pygame.mixer.get_init():
        pygame.mixer.music.set_volume(MUSIC_VOLUME * k * volume["musica"])


def load_svg(src, size):
    """SVG (caminho ou arquivo aberto) rasterizado ja no tamanho pedido, sem
    distorcer (como o load_sized_svg do pygame-ce). O pygame comum (o do console
    TTEA) nao tem essa funcao e o SDL_image dele ignora o viewBox: entao a raiz
    ganha o tamanho pedido e o desenho vai dentro de um grupo ja escalado."""
    if hasattr(pygame.image, "load_sized_svg"):
        return pygame.image.load_sized_svg(src, size)
    if hasattr(src, "read"):
        text = src.read()
    else:
        with open(src, "rb") as fp:
            text = fp.read()
    text = text.decode("utf-8") if isinstance(text, bytes) else text
    root = re.search(r"<svg\b[^>]*>", text)
    box = re.search(r'viewBox="([^"]*)"', root.group(0))
    if box:
        x0, y0, w, h = (float(v) for v in box.group(1).replace(",", " ").split())
    else:
        x0 = y0 = 0.0
        w, h = (float(re.search(r'\s%s="([\d.]+)' % k, root.group(0)).group(1)) for k in ("width", "height"))
    sw, sh = size
    k = min(sw / w, sh / h)  # cabe inteiro no tamanho pedido, centralizado
    move = ((sw - w * k) / 2 - x0 * k, (sh - h * k) / 2 - y0 * k)
    tag = re.sub(r'\s(width|height|viewBox)="[^"]*"', "", root.group(0))
    tag = tag.replace("<svg", '<svg width="%d" height="%d" viewBox="0 0 %d %d"' % (sw, sh, sw, sh), 1)
    group = '<g transform="translate(%.4f %.4f) scale(%.6f)">' % (move[0], move[1], k)
    end = text.rindex("</svg>")
    text = text[:root.start()] + tag + group + text[root.end():end] + "</g>" + text[end:]
    return pygame.image.load(io.BytesIO(text.encode("utf-8")), "imagem.svg")


def load_image(name, size=None):
    path = os.path.join(ASSETS_DIR, name)
    if name.endswith(".svg"):  # vetor: rasterizado ja no tamanho pedido (nitido)
        return (load_svg(path, size) if size else pygame.image.load(path)).convert_alpha()
    img = pygame.image.load(path).convert_alpha()
    if size and img.get_size() != size:
        img = pygame.transform.smoothscale(img, size)
    return img


def water_tinted(name, size, steps=WATER_TINT_STEPS):
    """Um SVG desenhado nas cores da agua limpa, em steps + 1 tons que vao da agua
    limpa (0) ate a poluida (steps): cada cor vira o tom da agua poluida com a
    mesma claridade (do fundo da agua ate a espuma). O contorno escuro nao muda."""
    with open(os.path.join(ASSETS_DIR, name), "rb") as fp:
        text = fp.read().decode("utf-8")
    base0, base1 = WATER_COLORS["clean"][0], WATER_COLORS["dirty"][0]
    lum0 = sum(base0) / 3

    def tinted(hexcolor, k):
        rgb = [int(hexcolor[i:i + 2], 16) for i in (1, 3, 5)]
        t = min(1.0, max(0.0, (sum(rgb) / 3 - lum0) / (255 - lum0)))  # claridade acima do fundo
        dirty = [b + (f - b) * t for b, f in zip(base1, WATER_FOAM_DIRTY)]
        return "#%02x%02x%02x" % tuple(round(c + (d - c) * k) for c, d in zip(rgb, dirty))

    out = []
    for i in range(steps + 1):
        k = i / steps
        svg = re.sub(r"#[0-9a-fA-F]{6}", lambda m: m.group(0) if m.group(0).lower() == "#20242b"
                     else tinted(m.group(0), k), text)
        out.append(load_svg(io.BytesIO(svg.encode("utf-8")), size).convert_alpha())
    return out


def load_group(json_name):
    """Quadros de um grupo (barco ou estacao) + o .json com o ponto de apoio."""
    with open(os.path.join(ASSETS_DIR, json_name), encoding="utf-8") as fp:
        meta = json.load(fp)
    return [load_image(n) for n in meta["arquivos"]], meta


def floor_f(sy):
    """Distancia a frente do jogador (em casas) do ponto do chao na linha sy."""
    t = (Y0 - sy) / FOCAL
    z = CAM_H * (CP + t * SP) / (SP - t * CP)
    return z - CAM_B


def floor_half(f):
    """Meia largura (em casas) do chao que aparece na tela a f casas a frente."""
    return (W / 2) * (CAM_H * SP + (f + CAM_B) * CP) / FOCAL


def floor_y(f):
    """Linha da tela do ponto do chao f casas a frente do jogador."""
    z = f + CAM_B
    return Y0 - (z * SP - CAM_H * CP) * FOCAL / (CAM_H * SP + z * CP)


def build_strips():
    """Para cada faixa horizontal da tela: (y, altura, f longe, f perto, meia
    largura), com as distancias em casas a partir do jogador. E constante: a
    camera e fixa. Tambem devolve ate onde (em casas) o chao aparece."""
    strips, reach = [], 0.0
    for y in range(0, H, STRIP):
        h = min(STRIP, H - y)
        f_top, f_bot = floor_f(y), floor_f(y + h)
        half = floor_half(floor_f(y + h / 2))
        strips.append((y, h, f_top, f_bot, half))
        reach = max(reach, math.hypot(half, f_top), math.hypot(half, f_bot))
    return strips, reach


def water_bands():
    """Ondas da agua vista de cima: faixas claras que atravessam o desenho (de
    WATER_PERIOD casas, repetido nas duas direcoes). Para cada uma, a borda de
    cima e a grossura (em casas) a cada WATER_STEP casas, numa volta do desenho."""
    rnd = random.Random(5)
    n = round(WATER_PERIOD / WATER_STEP)
    bands = []
    for i in range(4):
        y0 = (i + rnd.uniform(0.2, 0.8)) * WATER_PERIOD / 4
        f1, f2 = rnd.choice((1, 2)), rnd.choice((2, 3))
        p1, p2, p3 = rnd.uniform(0, math.tau), rnd.uniform(0, math.tau), rnd.uniform(0, math.tau)
        edge = []
        for j in range(n):  # ondas com numero inteiro de voltas: emendam sem costura
            t = math.tau * j / n
            top = y0 + 10 / 56 * math.sin(f1 * t + p1)
            thick = (2 + 6 * (0.5 + 0.5 * math.sin(f2 * t + p2)) + 9 * max(0.0, math.sin(t + p3)) ** 2) / 56
            edge.append((top, thick))
        bands.append(edge)
    return bands


def slab_span(poly, v0, v1):
    """Trecho em u (min, max) do poligono convexo 'poly' [(u, v)...] entre as
    linhas v0 e v1, ou None se ele nao passa por ali."""
    us = [u for u, v in poly if v0 <= v <= v1]
    for (ua, va), (ub, vb) in zip(poly, poly[1:] + poly[:1]):
        for c in (v0, v1):
            if (va - c) * (vb - c) < 0:
                us.append(ua + (ub - ua) * (c - va) / (vb - va))
    return (min(us), max(us)) if us else None


def clip_near(poly, f_min):
    """Corta o poligono [(l, f)...] do chao onde f < f_min (atras da tela)."""
    out = []
    prev = poly[-1]
    for cur in poly:
        if (cur[1] >= f_min) != (prev[1] >= f_min):
            t = (f_min - prev[1]) / (cur[1] - prev[1])
            out.append((prev[0] + (cur[0] - prev[0]) * t, f_min))
        if cur[1] >= f_min:
            out.append(cur)
        prev = cur
    return out


# --- jogo ---------------------------------------------------------------------
class Game:
    def __init__(self, screen, demo=False, jump=True):
        self.screen = screen
        self.demo = demo  # fundo do menu: camera girando devagar, sem placar
        self.jump = jump  # Espaco pula (tambem no console TTEA, junto do pulo com o corpo)
        self.paused = False  # o menu de pausa esta por cima (esconde o aviso do centro)
        self.show_hud = True  # False: desenha so o rio (a tela OPCOES poe o titulo no lugar do placar)
        # textos do jogo: mesma fonte e contorno do marcador de reciclagem (estilo cartoon)
        rubik = os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf")
        self.font = pygame.font.Font(rubik, 34)
        self.small = pygame.font.Font(rubik, 20)
        self.tiny = pygame.font.Font(rubik, 15)  # aviso de apertar uma tecla nos rios seguintes
        self.big = pygame.font.Font(rubik, 56)
        self.text_cache = {}
        import gerar_assets  # cria a arte padrao que ainda nao existir em assets/
        if gerar_assets.missing():
            gerar_assets.generate(log=lambda msg: None)
        self.sprites = {
            BUOY: [load_image("base/boia.svg", (96, 96))],  # boia de sinalizacao
            SPOUT: water_tinted("base/jato.svg", (96, 144)),  # um tom por nivel de poluicao
            FISH: [load_image("base/peixe.svg", (96, 96)), load_image("base/peixe_nadando.svg", (96, 72))],
        }
        self.img = {"sombra": load_image("sombra.png")}
        # marcador da estacao: bolha verde com o simbolo de reciclagem e o contador "0/x"
        self.img["popup_contador"] = load_image("base/popup_contador.svg", (240, 120))
        # anel de onda em volta do que boia: um tom por nivel de poluicao (da cor da agua)
        self.ripples = water_tinted("base/onda.svg", (128, 128))
        self.img["coracao"] = load_image("base/coracao.svg", (28, 26))  # vidas no placar
        self.img["coracao_grande"] = load_image("base/coracao.svg", (40, 37))  # "+1" no fim do rio
        # minimapa: moldura redonda e a setinha do barco no meio
        self.img["minimapa"] = load_image("base/minimapa.svg", (108, 108))
        self.img["minimapa_barco"] = load_image("base/minimapa_barco.svg", (16, 16))
        self.popup_font = pygame.font.Font(os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf"), 44)
        self.popup_cache = {}
        self.slicks = [load_image("mancha_%d.png" % i) for i in range(1, 5)]
        self.boat_frames, self.boat_meta = load_group("barco.json")  # parado, ar, andando...
        # contorno do barco na tela em relacao ao ponto onde ele encosta na agua (sem a espuma)
        ax, ay = self.boat_meta["apoio"]
        # camadas por cima do barco (se a arte tiver): oleo na cacamba, luz acesa e a gota da esteira
        meta = self.boat_meta
        self.boat_bucket = [load_image(n) for n in meta.get("cacamba", [])]
        self.boat_light = load_image(meta["luz"]) if "luz" in meta else None
        self.boat_drop = load_image(meta["gota"]) if "gota" in meta and "esteira" in meta else None
        # rastros atras do barco andando, ja curvados (linha = curva, coluna = quadro)
        self.boat_trail = []
        if "rastro" in meta:
            sheet = load_image(meta["rastro"]["arquivo"])
            rows, cols = len(meta["rastro"]["curvas"]), len(self.boat_frames) - 2
            tw, th = sheet.get_width() // cols, sheet.get_height() // rows
            self.boat_trail = [[sheet.subsurface((c * tw, r * th, tw, th)) for c in range(cols)] for r in range(rows)]
        # imagens deitadas no chao, vistas de cima, com GROUND_PPC px por casa
        ppc = GROUND_PPC
        self.slicks_ground = [pygame.transform.smoothscale(m, (ppc, ppc)) for m in self.slicks]
        arrow = load_image("base/seta_guia.svg", (int(ppc * 0.6),) * 2)
        self.arrows_ground = {d: pygame.transform.rotate(arrow, -90 * i) for i, d in enumerate(DIRS)}
        # chao da estacao (3 x 4,5 casas), desenhado com a estacao "para cima"
        self.img["estacao_chao"] = load_image("base/estacao_chao.svg", (3 * ppc, 9 * ppc // 2))
        self.ground_turns = {}  # imagens do chao ja giradas para a camera parada
        self.ground_turning = (None, {})  # e para o angulo do quadro atual, durante o giro
        self.water_bands = water_bands()
        if np is not None:  # as mesmas ondas em arrays: (borda de cima, grossura) de cada uma
            self.wave_arrays = [(np.array([v for v, _ in e]), np.array([t for _, t in e])) for e in self.water_bands]
        self.cache = {}      # sprites pequenos redimensionados
        self.big_cache = {}  # quadros grandes (barco no ar, estacao) redimensionados
        self.setup_view()
        self.minimap = pygame.Surface((N * MAP_CELL, N * MAP_CELL))  # desenhado grande e reduzido
        # mascara redonda do minimapa (desenhada 4x maior e reduzida: borda lisa)
        r = MAP_RADIUS
        mask = pygame.Surface((8 * r, 8 * r), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (4 * r, 4 * r), 4 * r)
        self.map_mask = pygame.transform.smoothscale(mask, (2 * r, 2 * r))
        self.fonts = {}
        self.run_log = None  # chamado com (jogo, motivo) quando uma corrida acaba (console TTEA)
        self.feet_mode = False   # console TTEA: os avisos falam dos pes, nao das teclas
        self.keys_off = False    # painel de ajustes aberto: as setas seguradas nao viram o barco
        self.reset_run()
        if demo:  # fundo do menu: um rio mais cheio
            self.river = 5
            self.reset_level()

    def setup_view(self):
        """O que sai da camera: faixas da tela, o trecho do chao que aparece (com
        folga, em (lado, frente)) e onde o barco encosta na agua. De novo a cada
        set_screen_size (barco em outra linha, zoom)."""
        self.strips, self.reach = build_strips()
        self.strip_keys = [-f_top for _, _, f_top, _, _ in self.strips]  # crescente, para o bisect
        self.f_far, self.f_near = floor_f(0) + 0.3, floor_f(H) - 0.5
        hf, hn = floor_half(self.f_far) + 0.3, floor_half(self.f_near) + 0.3
        self.view_box = [(-hn, self.f_near), (hn, self.f_near), (hf, self.f_far), (-hf, self.f_far)]
        self.ground = project(surface_point(0, 0))  # onde o barco encosta na agua
        # contorno do barco na tela em relacao a esse ponto (sem a espuma), no zoom da camera
        ax, ay = self.boat_meta["apoio"]
        hull = self.boat_frames[0].get_bounding_rect().move(-round(ax), -round(ay))
        self.boat_hull = pygame.Rect(round(hull.x * CAM_ZOOM), round(hull.y * CAM_ZOOM),
                                     round(hull.w * CAM_ZOOM), round(hull.h * CAM_ZOOM))
        self.ground_turns.clear()
        self.big_cache.clear()

    # ---- estado ----
    def reset_run(self):
        """Nova corrida: rio 1, 3 barcos, 0 pontos e rios novos (seed novo)."""
        if hasattr(self, "score"):
            self.end_run("recomecou")
        self.run_start = time.time()
        self.run_saved = False
        self.crashes = self.turns = self.jumps = 0  # para o registro da corrida
        self.river = 1
        self.lives = LIVES_START
        self.score = 0
        self.delivered = 0  # total de oleo entregue na estacao
        self.seed = random.randrange(10 ** 9)
        self.best = load_record()
        self.new_record = False
        self.popups = []  # textos "+10" que sobem na tela
        self.reset_level()

    def next_river(self):
        self.river += 1
        self.reset_level()

    def reset_level(self):
        self.grid = generate_level(self.river, self.seed)
        self.litter_left = self.litter_total = sum(row.count(OIL) for row in self.grid)
        self.popup_cache = {}
        self.popup_alpha = 255.0  # o marcador some quando encosta no barco
        self.load = 0
        self.belt = []  # idade (s) de cada oleo recolhido que ainda desce a esteira
        # dock_pos = casa do meio da vaga encostada na estacao; dock_side = lado da estacao
        self.dock_pos, self.dock_side = None, (0, -1)
        for y in range(N):
            for x in range(N):
                if self.grid[y][x] != DOCK:
                    continue
                near = [self.grid[(y + dy) % N][(x + dx) % N] for dx, dy in DIRS]
                if near.count(DOCK) == 3 and STATION in near:
                    self.dock_pos, self.dock_side = (x, y), DIRS[near.index(STATION)]
        # chao da estacao girado para o lado em que ela fica (a imagem e feita com ela "para cima")
        turns = DIRS.index(self.dock_side) if self.dock_side in DIRS else 0
        self.station_floor = pygame.transform.rotate(self.img["estacao_chao"], -90 * turns)
        self.ground_turns.clear()
        self.guide = []          # casas do caminho ate a descarga
        self.guide_turn = None   # -1 esquerda, 0 em frente, 1 direita (na proxima casa)
        self.px = self.py = float(N // 2)
        self.dir = 0
        self.view = 0.0      # angulo da camera
        self.heading = 0.0   # angulo do barco (a camera vai atras dele)
        self.turn_from = self.turn_to = 0.0
        self.turn_t = -1.0
        self.since_turn = 10.0  # tempo desde a ultima curva (para acelerar de novo)
        self.moving = False
        self.start_timer = 1.6
        self.queued = 0
        self.air = False
        self.air_dist = 0.0
        self.jump_len = 0.0
        self.jump_h = 0.0
        self.jump_from = 0.0     # altura em que o pulo comecou (o salto duplo comeca no ar)
        self.double_used = False  # o salto duplo ja foi usado neste pulo
        self.play_time = 0.0
        self.river_time = 0.0  # tempo andando neste rio (para o bonus de rapidez)
        self.combo = 0
        self.anim = 0.0
        self.state = "play"
        self.state_timer = 0.0
        self.clear_bonus = 0
        self.extra_life = False
        self.message = ""  # o numero do rio ja aparece no topo da tela
        self.fail_msg = ""
        self.msg_timer = 0.0
        self.waiting = True  # rio novo: o barco so sai quando apertar uma tecla

    @property
    def speed(self):
        """Comeca mais rapido e chega mais longe a cada rio; acelera com o tempo."""
        rivers = self.river - 1
        start = SPEED_START + min(SPEED_RIVER_CAP[0], SPEED_RIVER * rivers)
        top = SPEED_MAX + min(SPEED_RIVER_CAP[1], SPEED_RIVER * 0.25 / 0.35 * rivers)
        return min(top, start + self.play_time * SPEED_GAIN)

    # ---- pontos, barcos e fim da corrida ----
    def add_points(self, pts, label=None, color=(255, 235, 120)):
        self.score += pts
        if label:
            self.popups.append([label, 0.0, color])

    def end_run(self, reason):
        """Avisa o fim da corrida (uma vez so); corrida sem nenhum movimento nao conta."""
        if self.run_log and not self.run_saved and not self.demo and (self.score or self.crashes or self.moving):
            self.run_log(self, reason)
        self.run_saved = True

    def crash(self, msg):
        self.lives -= 1
        self.crashes += 1
        self.combo = 0
        self.fail_msg = msg
        if self.lives > 0:
            self.state, self.state_timer = "fail", 1.6
            return
        self.state = "gameover"
        self.best = load_record()
        if self.score > self.best["pontos"]:
            self.new_record = True
            save_record(self.score, self.river)
        play("recorde" if self.new_record else "fim")
        self.end_run("acabaram os barcos")

    def river_clear(self):
        quick = max(0, int(60 + 15 * self.river - self.river_time))  # segundos abaixo do tempo-alvo
        self.clear_bonus = 100 * self.river + quick * 5
        self.score += self.clear_bonus
        self.extra_life = self.river % 3 == 0 and self.lives < LIVES_MAX
        if self.extra_life:
            self.lives += 1
            play("vida")
        play("rio_limpo")
        self.state, self.state_timer = "clear", 2.8

    def height(self):
        if not self.air:
            return 0.0
        t = min(1.0, self.air_dist / self.jump_len)
        return self.jump_from * (1 - t) + math.sin(math.pi * t) * self.jump_h

    def rem_to_center(self):
        dx, dy = DIRS[self.dir]
        t = self.px * dx if dx else self.py * dy  # progresso em casas (vale para diagonais)
        frac = t - math.floor(t)
        return 1.0 - frac if frac > 1e-9 else 1.0

    def at_center(self):
        return abs(self.px - round(self.px)) < 1e-9 and abs(self.py - round(self.py)) < 1e-9

    def start_turn(self, delta):
        self.turns += 1
        self.dir = (self.dir + delta) % ND
        self.turn_from = self.heading
        self.turn_to = self.heading + delta * TURN_ANGLE
        self.turn_t = 0.0

    def start_jump(self, length, height):
        """Pulo de 'length' casas (termina no centro de uma casa). No ar, e o
        salto duplo: um novo arco a partir da altura em que o barco esta."""
        from_h = self.height()
        if not self.air:
            self.double_used = False
        self.air = True
        self.air_dist = 0.0
        self.jump_len = length
        self.jump_h = height
        self.jump_from = from_h

    # ---- regras ----
    def flash(self, msg, t=1.6):
        self.message = msg
        self.msg_timer = t

    @property
    def need_unload(self):
        return self.load >= CAPACITY or (self.litter_left <= 0 and self.load > 0)

    def respawn(self):
        """Depois de bater: continua no mesmo rio (o que foi limpo continua
        limpo e a carga e mantida), recomecando parado na largada. Se ela
        estiver ocupada, vai para a casa vazia mais proxima (nunca na estacao)."""
        start = (N // 2, N // 2)
        spot, seen, queue = None, {start}, deque([start])
        while queue:
            cx, cy = queue.popleft()
            if self.grid[cy][cx] == EMPTY:
                spot = (cx, cy)
                break
            for dx, dy in DIRS:
                nxt = ((cx + dx) % N, (cy + dy) % N)
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        self.px, self.py = float(spot[0]), float(spot[1])
        x, y = int(self.px), int(self.py)
        blocked = (BUOY, SPOUT, FISH)  # a estacao nao bloqueia: o barco passa por ela

        def free_run(d):  # quantas casas livres em linha reta nessa direcao
            k = 0
            while k < 8 and self.grid[(y + DIRS[d][1] * (k + 1)) % N][(x + DIRS[d][0] * (k + 1)) % N] not in blocked:
                k += 1
            return k

        best = max(range(ND), key=lambda d: (free_run(d), d == self.dir))
        delta = (best - self.dir + ND // 2) % ND - ND // 2  # menor giro ate a nova direcao
        self.dir = best
        self.heading += delta * TURN_ANGLE
        self.view = self.heading
        self.turn_t = -1.0
        self.since_turn = 10.0  # tempo desde a ultima curva (para acelerar de novo)
        self.moving = False
        self.start_timer = 1.6
        self.queued = 0
        self.air = False
        self.play_time = 0.0
        self.state = "play"
        self.flash("%d BARCO%s" % (self.lives, "S" if self.lives > 1 else ""), 1.2)
        self.update_guide()

    def update_guide(self):
        """Caminho mais curto ate uma descarga, respeitando como o barco anda:
        sem dar re e so virando nos centros das casas; desvia de boias, pneus
        e jatos. Comeca na proxima casa (a decisao desta casa ja foi tomada)."""
        self.guide, self.guide_turn = [], None
        if self.state != "play" or not self.need_unload:
            return
        x, y = round(self.px) % N, round(self.py) % N
        mi = self.dir
        sx, sy = (x + DIRS[mi][0]) % N, (y + DIRS[mi][1]) % N
        blocked = (BUOY, SPOUT, FISH)  # a estacao nao bloqueia: o barco passa por ela
        if self.grid[sy][sx] in blocked:
            return
        start = (sx, sy, mi)
        prev = {start: None}
        queue = deque([start])
        goal = None
        while queue:
            cur = queue.popleft()
            cx, cy, d = cur
            if self.grid[cy][cx] == DOCK:
                goal = cur
                break
            for nd in (d, (d + 1) % ND, (d - 1) % ND):
                nxt = ((cx + DIRS[nd][0]) % N, (cy + DIRS[nd][1]) % N, nd)
                if nxt not in prev and self.grid[nxt[1]][nxt[0]] not in blocked:
                    prev[nxt] = cur
                    queue.append(nxt)
        if goal is None:
            return
        path = []
        while goal:
            path.append(goal)
            goal = prev[goal]
        path.reverse()
        self.guide = [(x, y)] + [(cx, cy) for cx, cy, _ in path]
        if len(path) > 1:
            nd = path[1][2]
            self.guide_turn = 0 if nd == mi else 1 if nd == (mi + 1) % ND else -1
        else:
            self.guide_turn = 0

    def unloaded(self):
        """Oleo do rio que ja foi descarregado na estacao."""
        return self.litter_total - max(0, self.litter_left) - self.load

    def pollution(self):
        return max(0, self.litter_left) / max(1, self.litter_total)

    def on_center(self):
        self.arrive()
        self.update_guide()

    def collect(self, x, y):
        """Recolhe a mancha da casa (x, y), se houver e a cacamba tiver lugar."""
        if self.grid[y][x] != OIL or self.load >= CAPACITY:  # cheia: passa por cima sem recolher
            return False
        self.grid[y][x] = FISH  # o peixe que estava preso no oleo fica livre
        self.litter_left -= 1
        self.load += 1
        self.belt.append(0.0)  # desce a esteira ate a cacamba
        play("oleo")
        self.combo += 1  # manchas seguidas, sem pular nenhuma casa
        pts = 10 * min(self.combo, 5)
        self.add_points(pts, "+%d" % pts)
        return True

    def arrive(self):
        x, y = int(self.px), int(self.py)
        cell = self.grid[y][x]
        if self.air:
            if self.air_dist < self.jump_len - 1e-6:
                return
            self.air = False
        if not self.collect(x, y):
            self.combo = 0
        if cell == DOCK:
            if self.load:
                full = self.load >= CAPACITY
                pts = self.load * 5 * (2 if full else 1)
                self.delivered += self.load
                self.load = 0
                self.belt = []
                self.add_points(pts, "+%d  CHEIA x2!" % pts if full else "+%d" % pts, (150, 255, 170))
                if self.litter_left <= 0:
                    self.river_clear()
                    return
                play("descarga")
        elif cell == BUOY:
            play("batida")
            self.crash("BATEU NO CONE!")
            return
        elif cell == FISH:
            play("batida")
            self.crash("VOCÊ MATOU UM PEIXE!")
            return
        elif cell == SPOUT:
            play("jato")
            self.start_jump(6.0, 3.5)
        if not self.air:
            turn = self.queued or self.held_turn()
            if turn:
                self.queued = 0
                self.start_turn(turn)

    def advance(self, dist):
        while dist > 1e-9 and self.turn_t < 0 and self.state == "play":
            dx, dy = DIRS[self.dir]
            length = math.hypot(dx, dy)  # na diagonal cada casa fica a raiz de 2
            rem = self.rem_to_center()
            step = min(dist / length, rem)
            self.px += dx * step
            self.py += dy * step
            dist -= step * length
            if self.air:
                self.air_dist += step
            if step >= rem - 1e-9:
                self.px = float(round(self.px) % N)
                self.py = float(round(self.py) % N)
                self.on_center()

    # ---- loop ----
    def handle_event(self, ev):
        if ev.type != pygame.KEYDOWN:
            return
        enter = ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
        if ev.key == pygame.K_r or (self.state == "gameover" and enter):
            self.reset_run()  # mais uma vez!
            return
        if self.state == "fail" and enter:
            self.respawn()
            return
        if self.state == "clear" and enter:
            self.next_river()
            return
        if self.state != "play":
            return
        if self.waiting:  # a tecla so libera o barco (nao vira nem pula)
            self.waiting = False
            self.moving = True
            return
        if not self.moving:  # a primeira tecla so tira o barco do lugar (nao vira nem pula)
            self.moving = True
            return
        if ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.queued = -1 if ev.key == pygame.K_LEFT else 1
        elif ev.key == pygame.K_SPACE and self.jump and (not self.air or not self.double_used):
            if self.air:  # salto duplo: so um por pulo
                self.double_used = True
            play("salto_duplo" if self.air else "pulo")
            self.jumps += 1
            self.moving = True
            rem = self.rem_to_center()
            self.start_jump(rem + (1.0 if rem > 0.5 else 2.0), 1.4)

    def feet_jump(self):
        """Pulo do jogador no console TTEA. Em mar aberto e o pulo do teclado;
        num bloco, o barco passa por cima dos peixes (e cones) e cai no
        primeiro oleo a frente ou, sem oleo, do outro lado do bloco."""
        if self.state != "play" or self.waiting or self.air:
            return
        dx, dy = DIRS[self.dir]
        rem = self.rem_to_center()
        cx, cy = round(self.px + dx * rem), round(self.py + dy * rem)  # proxima casa em que o barco centra

        def cell(k):
            return self.grid[(cy + dy * k) % N][(cx + dx * k) % N]

        self.collect(cx % N, cy % N)  # a mancha em que o barco ja encostou conta (ele sai do chao antes do centro dela)
        k = 1 if rem > 0.5 else 2  # o pulo do teclado
        if cell(k) != EMPTY:
            while k < N and cell(k) in (FISH, BUOY):
                k += 1
        play("pulo")
        self.jumps += 1
        self.moving = True
        self.start_jump(rem + k, max(1.4, min(3.5, 0.45 * (rem + k))))  # mais longe, mais alto

    def update(self, dt):
        self.anim += dt
        self.belt = [age + dt for age in self.belt if age + dt < BELT_TIME]
        if self.demo:
            self.heading = self.view = self.view + dt * 0.12
            return
        if self.msg_timer > 0:
            self.msg_timer -= dt
        for pop in self.popups:
            pop[1] += dt
        self.popups = [pop for pop in self.popups if pop[1] < 1.1]
        if self.state in ("fail", "clear"):  # segue sozinho depois de um instante
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.respawn() if self.state == "fail" else self.next_river()
            return
        if self.state != "play" or self.waiting:
            return
        self.follow_camera(dt)
        if self.turn_t >= 0:
            self.turn_t += dt / TURN_TIME
            if self.turn_t >= 1:
                self.heading = self.turn_to
                self.turn_t = -1.0
                self.since_turn = 0.0
                self.update_guide()
            else:
                s = self.turn_t
                ease = s * s * s * (s * (6 * s - 15) + 10)  # comeca e termina devagar
                self.heading = self.turn_from + (self.turn_to - self.turn_from) * ease
            return
        self.since_turn += dt
        if not self.moving:
            if self.queued and self.at_center():
                self.start_turn(self.queued)
                self.queued = 0
                return
            self.start_timer -= dt
            if self.start_timer > 0:
                return
            self.moving = True
        self.play_time += dt
        self.river_time += dt
        self.advance(self.speed * self.turn_pace() * dt)

    def follow_camera(self, dt):
        """A camera vai atras do barco com um pouco de atraso: nas curvas o
        barco vira primeiro e a camera gira em seguida, sem tranco."""
        diff = self.heading - self.view
        if abs(diff) < 0.002:
            self.view = self.heading
        else:
            self.view += diff * (1 - math.exp(-CAM_FOLLOW * dt))

    def turn_pace(self):
        """Fracao da velocidade perto das curvas: com uma curva pedida o barco
        freia chegando no centro da casa, e depois de virar acelera de novo."""
        def smooth(t):
            t = max(0.0, min(1.0, t))
            return t * t * (3 - 2 * t)
        after = smooth(self.since_turn / TURN_RECOVER)
        before = 1.0
        if not self.air and (self.queued or self.held_turn()) and TURN_BRAKE > 0:
            before = smooth(self.rem_to_center() / TURN_BRAKE)
        return TURN_SLOW + (1 - TURN_SLOW) * min(after, before)

    def held_turn(self):
        """Seta segurada: -1 esquerda, 1 direita, 0 nenhuma (ou as duas). Com o
        painel de ajustes aberto as setas sao dele."""
        if self.keys_off:
            return 0
        keys = pygame.key.get_pressed()
        return keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]

    # ---- desenho ----
    def item_sprite(self, kind, variant, w, h=None):
        return self.scaled((kind, variant), self.sprites[kind][variant], w, h or w)

    def scaled(self, key, img, w, h, big=False):
        """Imagem redimensionada, guardada para os proximos quadros."""
        cache = self.big_cache if big else self.cache
        key = key + (w, h)
        out = cache.get(key)
        if out is None:
            if len(cache) > (40 if big else 1500):  # limita a memoria usada
                cache.clear()
            out = pygame.transform.smoothscale(img, (max(1, w), max(1, h)))
            cache[key] = out
        return out

    def flat_size(self, l, f, width, depth):
        """Tamanho na tela de algo deitado na agua (width x depth casas) em (l, f):
        devolve centro e tamanho, ja com o achatamento da perspectiva."""
        q1 = project(surface_point(l, f + depth / 2))
        q2 = project(surface_point(l, f - depth / 2))
        p = project(surface_point(l, f))
        if not (p and q1 and q2):
            return None
        # tamanhos arredondados de 4 em 4 px: o mesmo tamanho serve para varios quadros (cache)
        w = max(4, round(width * FOCAL / p[2] / 4) * 4)
        h = max(4, round(abs(q2[1] - q1[1]) / 4) * 4)
        if p[2] < 1.0 or w > W or h > H:  # colado na camera (ou atras dela): nao desenha
            return None
        return p[0], (q1[1] + q2[1]) / 2, w, h

    def draw(self):
        self.draw_water()

        fx, fy = math.sin(self.view), -math.cos(self.view)
        rx, ry = math.cos(self.view), math.sin(self.view)
        ipx, ipy = round(self.px), round(self.py)
        # o rio da a volta: cada casa uma vez so, mesmo com a tela larga (no maximo
        # uma volta, centrada no barco: de -N/2 a N/2 - 1 casas)
        n = min(2 * RNG + 1, N)
        lo = n // 2
        lim2 = LIM * LIM


        # objetos + jogador + estacao, do mais distante para o mais proximo
        objs = []
        for tj in range(n):
            cy = ipy - lo + tj
            grow = self.grid[cy % N]
            for ti in range(n):
                cx = ipx - lo + ti
                cell = grow[cx % N]
                if cell in (EMPTY, OIL, DOCK, STATION):  # a estacao e desenhada a parte
                    continue
                dx, dy = cx - self.px, cy - self.py
                f = dx * fx + dy * fy
                l = dx * rx + dy * ry
                if f * f + l * l > lim2:
                    continue
                p = project(surface_point(l, f))
                if p is None:
                    continue
                size = 2 * ITEM_R * FOCAL / p[2]
                # fora da tela (ex.: atras da camera) nao desenha: alem de inutil,
                # o sprite ficaria gigantesco e estouraria a memoria
                if not (-size < p[0] < W + size and -size * 6 < p[1] < H + size):
                    continue
                objs.append((p[2], cell, p[0], p[1], size, cx % N, cy % N))
        objs.append((PLAYER_DEPTH - 0.2, "player", 0, 0, 0, 0, 0))
        objs.extend(self.station_parts(fx, fy, rx, ry))
        objs.sort(key=lambda o: -o[0])

        for depth, kind, x, y, size, cx, cy in objs:
            if kind == "player":
                if not self.demo:  # no fundo do menu aparece so o rio
                    self.draw_boat()
            elif kind == "fn":
                x()
            else:
                self.draw_item(kind, x, y, size, cx, cy)

        if not self.demo and self.show_hud:
            self.draw_hud()

    def station_parts(self, fx, fy, rx, ry):
        """Estacao: so o chao (pintado na agua) e, flutuando em cima do lugar
        dela, o marcador de reciclagem com quanto oleo do rio ja foi entregue."""
        if self.dock_pos is None:
            return []
        side = self.dock_side
        gx = self.dock_pos[0] - side[0]  # meio da vaga (3 casas: dock_pos e as 2 de tras)
        gy = self.dock_pos[1] - side[1]
        ox = (gx - self.px + N / 2) % N - N / 2
        oy = (gy - self.py + N / 2) % N - N / 2
        l, f = ox * rx + oy * ry, ox * fx + oy * fy
        if l * l + f * f > (LIM + 2) ** 2:  # longe demais: nao desenha
            return []
        p = project(surface_point(l, f, POPUP_LIFT))
        if p is None:
            return []

        def popup():  # centrado no meio da vaga, subindo e descendo devagar
            size = max(10, min(32, int(0.5 * FOCAL / p[2])))
            pw = int(size * 3.6)
            bob = math.sin(self.anim * 2.5) * size * 0.25
            text = "%d/%d" % (self.unloaded(), self.litter_total)
            pin = self.scaled(("popup", text), self.popup_image(text), pw, pw // 2)
            rect = pin.get_rect(center=(p[0], p[1] + bob))
            boat = self.boat_hull.move(round(self.ground[0]), round(self.ground[1]))
            touching = not self.demo and rect.colliderect(boat)  # encostou no barco: some (devagar)
            self.popup_alpha += ((0 if touching else 255) - self.popup_alpha) * 0.25
            if self.popup_alpha < 5:
                return
            pin.set_alpha(round(self.popup_alpha))
            self.screen.blit(pin, rect)
        return [(0.0, "fn", popup, 0, 0, 0, 0)]  # profundidade 0: desenhado por ultimo, acima do barco

    def popup_image(self, text):
        """Marcador da estacao com o contador escrito em branco (com contorno)
        no espaco a direita do simbolo."""
        img = self.popup_cache.get(text)
        if img is None:
            img = self.img["popup_contador"].copy()
            font = self.popup_font
            txt = font.render(text, True, (255, 255, 255))
            ink = font.render(text, True, (32, 36, 43))
            k = min(1.0, 128 / txt.get_width())  # numeros grandes: diminui para caber
            if k < 1:
                size = (round(txt.get_width() * k), round(txt.get_height() * k))
                txt, ink = pygame.transform.smoothscale(txt, size), pygame.transform.smoothscale(ink, size)
            rect = txt.get_rect(center=(157, 49))  # x 120 a 300 do svg (320 x 160), na metade de cima
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2)):
                img.blit(ink, rect.move(dx, dy))
            img.blit(txt, rect)
            self.popup_cache[text] = img
        return img

    def draw_item(self, kind, x, y, size, cx, cy):
        scr = self.screen
        s = max(4, int(size))
        seed = cx * 7 + cy * 13
        t = self.anim
        tone = round(self.pollution() * WATER_TINT_STEPS)  # jato e ondas: da cor da agua
        ripple = self.ripples[tone]
        if kind == SPOUT:
            h = int(s * 1.5 * (1.0 + 0.12 * math.sin(t * 9 + seed)))
            scr.blit(self.item_sprite(SPOUT, tone, s, h), (x - s / 2, y - h + s * 0.12))
            return
        if kind == FISH:
            # nada debaixo d'agua (barbatana de fora) e de vez em quando pula
            s = max(4, int(s * FISH_SCALE))
            cyc = (t * 0.4 + (seed % 17) / 17) % 1.0
            d = 1 if (seed // 3) % 2 else -1
            if cyc < 0.3:
                u = cyc / 0.3
                hx = x + d * (u - 0.5) * s * 0.9
                hy = y - s * 0.1 - math.sin(math.pi * u) * s * 0.9
                img = self.item_sprite(FISH, 0, s)
                if d < 0:
                    img = pygame.transform.flip(img, True, False)
                img = pygame.transform.rotate(img, 50 * (1 - 2 * u) * d)
                for ex, near in ((x - d * s * 0.45, u < 0.35), (x + d * s * 0.45, u > 0.65)):
                    if near:
                        rw, rh = int(s * 0.6), int(s * 0.16)
                        scr.blit(self.scaled(("onda", tone), ripple, rw, rh), (ex - rw / 2, y - rh / 2))
                scr.blit(img, img.get_rect(center=(hx, hy)))
            else:
                sx = x + math.sin(t * 2 + seed) * s * 0.15
                rw, rh = int(s * 0.45), int(s * 0.12)
                scr.blit(self.scaled(("onda", tone), ripple, rw, rh), (sx - rw / 2, y - rh / 2))
                w, h = s, int(s * 0.75)
                img = self.item_sprite(FISH, 1, w, h)
                if math.cos(t * 2 + seed) < 0:
                    img = pygame.transform.flip(img, True, False)
                scr.blit(img, (sx - w / 2, y - h * 2 / 3))
            return
        variant = seed % len(self.sprites[kind])
        img = self.item_sprite(kind, variant, s)
        bob = math.sin(t * 2 + seed) * s * 0.04
        sink = int(s * 0.18)  # a parte de baixo fica "dentro" da agua
        rw, rh = int(s * 0.95), int(s * 0.28)
        scr.blit(self.scaled(("onda", tone), ripple, rw, rh), (x - rw / 2, y - rh / 2 + bob))
        scr.blit(img, (x - s / 2, y - s + sink + bob), area=pygame.Rect(0, 0, s, s - sink))

    def ground_turned(self, img, deg, still):
        """Imagem do chao girada junto com a camera. Com a camera parada fica
        guardada; girando, so vale para o quadro atual (as manchas repetem a imagem)."""
        if not still and self.ground_turning[0] != deg:
            self.ground_turning = (deg, {})
        cache = self.ground_turns if still else self.ground_turning[1]
        key = (img, deg)
        if key in cache:
            return cache[key]
        if deg % 90 == 0:
            out = pygame.transform.rotate(img, deg) if deg % 360 else img
        else:
            out = pygame.transform.rotozoom(img, deg, 1)  # suave nos angulos quebrados
        cache[key] = out
        return out

    def ground_image(self, img, dx, dy, view, alpha=None):
        """Desenha uma imagem deitada no chao (vista de cima, GROUND_PPC px por
        casa) com o centro a (dx, dy) casas do jogador: ela gira com a camera e
        ganha a perspectiva do chao. As pequenas (setas, manchas) sao esticadas
        inteiras de uma vez (borda lisa, sem degraus ao andar); as grandes
        (chao da estacao), faixa por faixa, onde a perspectiva pesa mais."""
        deg, ca, sa, still = view
        l, f = dx * ca + dy * sa, dx * sa - dy * ca
        rad = math.hypot(*img.get_size()) / 2 / GROUND_PPC  # cabe neste raio em qualquer giro
        if f - rad > self.f_far or f + rad < self.f_near or abs(l) - rad > floor_half(f + rad):
            return  # fora da tela: nem gira
        rimg = self.ground_turned(img, deg, still)
        iw, ih = rimg.get_size()
        rw, rh = iw / GROUND_PPC, ih / GROUND_PPC
        far, near = f + rh / 2, f - rh / 2  # bordas de cima e de baixo da imagem
        if near > self.f_far or far < self.f_near or abs(l) - rw / 2 > floor_half(far):
            return
        scr = self.screen
        if max(rw, rh) <= GROUND_WHOLE:  # pequena: a perspectiva quase nao muda dentro dela
            y0, y1 = floor_y(far), floor_y(near)
            k = W / (2 * floor_half(f))  # px da tela por casa no meio da imagem
            dw, dh = round(rw * k), round(y1 - y0)
            if dw < 1 or dh < 1:
                return
            piece = pygame.transform.smoothscale(rimg, (dw, dh))
            if alpha is not None:
                piece.set_alpha(alpha)
            scr.blit(piece, (round(W / 2 + l * k - dw / 2), round(y0)))
            return
        i0 = max(0, bisect.bisect_left(self.strip_keys, -far) - 1)
        i1 = bisect.bisect_left(self.strip_keys, -near)
        for y, h, f_top, f_bot, half in self.strips[i0:i1]:
            r0 = max(0, int((far - f_top) * GROUND_PPC))  # linhas da imagem nesta faixa
            r1 = min(ih, max(r0 + 1, math.ceil((far - f_bot) * GROUND_PPC)))
            if r0 >= r1:
                continue
            if r1 - r0 < 2 <= ih:  # o smoothscale do pygame comum le fora de uma fonte de 1 linha (e trava)
                r0, r1 = (r0, r1 + 1) if r1 < ih else (r0 - 1, r1)
            k = W / (2 * half)  # px da tela por casa nesta faixa
            x0, dw = W / 2 + (l - rw / 2) * k, round(rw * k)
            if dw < 1 or x0 > W or x0 + dw < 0:
                continue
            piece = pygame.transform.smoothscale(rimg.subsurface((0, r0, iw, r1 - r0)), (dw, h))
            if alpha is not None:
                piece.set_alpha(alpha)
            scr.blit(piece, (round(x0), y))

    def paint_ground(self, view):
        """Imagens deitadas na agua: as manchas, o chao da estacao e as setas do guia."""
        def at(gx, gy):  # casa do mapa -> distancia ate o jogador (com o mapa dando a volta)
            return (gx - self.px + N / 2) % N - N / 2, (gy - self.py + N / 2) % N - N / 2

        r = int(self.reach) + 1
        n = min(2 * r + 1, N)  # o rio da a volta: cada casa uma vez so (at() acha a mais perto)
        ipx, ipy = round(self.px), round(self.py)
        slicks = self.slicks_ground
        for cy in range(ipy - r, ipy - r + n):
            row = self.grid[cy % N]
            for cx in range(ipx - r, ipx - r + n):
                if row[cx % N] == OIL:
                    v = ((cx % N) * 7 + (cy % N) * 13) % len(slicks)
                    self.ground_image(slicks[v], *at(cx, cy), view)
        if self.dock_pos:
            # chao: 3 casas de vaga + 1,5 de plataforma -> o meio fica 0,25 casa para longe da estacao
            sx, sy = self.dock_side
            self.ground_image(self.station_floor, *at(self.dock_pos[0] - sx * 0.25, self.dock_pos[1] - sy * 0.25), view)
        path = self.guide
        for i in range(min(len(path) - 1, 18)):
            (ax, ay), (bx, by) = path[i], path[i + 1]
            d = ((bx - ax + N // 2) % N - N // 2, (by - ay + N // 2) % N - N // 2)
            img = self.arrows_ground.get(d)
            if img is None:
                continue
            alpha = int(150 + 105 * (0.5 + 0.5 * math.sin(self.anim * 6 - i * 0.6)))
            self.ground_image(img, *at(ax + d[0] * 0.5, ay + d[1] * 0.5), view, alpha)

    def draw_waves(self, ca, sa, color):
        """Faixas claras das ondas, desenhadas como poligonos ja em perspectiva.
        So entra o pedaco de cada faixa que cai no trecho do chao visivel."""
        drift = self.anim * 0.15  # correnteza lenta
        ou, ov = self.px + drift, self.py + drift * 0.6  # onde o jogador esta no desenho das ondas
        box = [(ou + l * ca + f * sa, ov + l * sa - f * ca) for l, f in self.view_box]
        vmin, vmax = min(v for _, v in box), max(v for _, v in box)
        n = len(self.water_bands[0])
        p, step = WATER_PERIOD, WATER_STEP
        f_min, scr = self.f_near, self.screen
        for rep in range(math.floor(vmin / p) - 1, math.floor(vmax / p) + 1):
            base = rep * p
            for b, edge in enumerate(self.water_bands):
                y0 = base + edge[0][0]
                span = slab_span(box, y0 - 0.3, y0 + 0.6)  # a onda sobe e desce ~0,2 casa
                if span is None:
                    continue
                j0, j1 = math.floor(span[0] / step), math.ceil(span[1] / step)
                if np is not None:
                    pts = self.wave_points(b, j0, j1, base, ou, ov, ca, sa, f_min)
                    if pts:
                        pygame.draw.polygon(scr, color, pts)
                        pygame.draw.aalines(scr, color, True, pts)  # borda lisa
                    continue
                top, bottom = [], []
                for j in range(j0, j1 + 1):
                    v, thick = edge[j % n]
                    du, dv = j * step - ou, base + v - ov
                    top.append((du * ca + dv * sa, du * sa - dv * ca))
                    dv += thick
                    bottom.append((du * ca + dv * sa, du * sa - dv * ca))
                poly = clip_near(top + bottom[::-1], f_min)
                if len(poly) < 3:
                    continue
                pts = []
                for l, f in poly:  # chao -> tela (mesma camera do project)
                    z = f + CAM_B
                    k = FOCAL / (CAM_H * SP + z * CP)
                    pts.append((W / 2 + l * k, Y0 - (z * SP - CAM_H * CP) * k))
                pygame.draw.polygon(scr, color, pts)
                pygame.draw.aalines(scr, color, True, pts)  # borda lisa

    def wave_points(self, b, j0, j1, base, ou, ov, ca, sa, f_min):
        """O mesmo poligono da onda b que draw_waves monta em Python, com as
        contas em lote (numpy): borda de cima, borda de baixo (de volta), o corte
        perto da camera e a projecao na tela. Devolve os pontos ou None."""
        n = len(self.water_bands[b])
        tops, thicks = self.wave_arrays[b]
        js = np.arange(j0, j1 + 1)
        du = js * WATER_STEP - ou
        dv = base + tops[js % n] - ov
        dv2 = dv + thicks[js % n]
        ls = np.concatenate((du * ca + dv * sa, (du * ca + dv2 * sa)[::-1]))
        fs = np.concatenate((du * sa - dv * ca, (du * sa - dv2 * ca)[::-1]))
        if fs.min() < f_min:  # passa da borda de baixo da tela: corta (poucas ondas por quadro)
            poly = clip_near(list(zip(ls.tolist(), fs.tolist())), f_min)
            if len(poly) < 3:
                return None
            ls, fs = np.array(poly).T
        z = fs + CAM_B
        k = FOCAL / (CAM_H * SP + z * CP)
        return np.column_stack((W / 2 + ls * k, Y0 - (z * SP - CAM_H * CP) * k)).tolist()

    def draw_water(self):
        """Chao estilo "Mode 7" desenhado direto na tela: fundo liso, ondas em
        perspectiva e as imagens deitadas na agua, tudo girando com a camera."""
        a = self.view
        still = self.view == self.heading and self.turn_t < 0 and not self.demo
        if still:  # camera parada: angulo exato
            a = round(a / TURN_ANGLE) * TURN_ANGLE
        ca, sa = math.cos(a), math.sin(a)
        k = self.pollution()
        (base0, wave0), (base1, wave1) = WATER_COLORS["clean"], WATER_COLORS["dirty"]

        def mix(c0, c1):
            return tuple(round(x + (y - x) * k) for x, y in zip(c0, c1))

        self.screen.fill(mix(base0, base1))
        self.draw_waves(ca, sa, mix(wave0, wave1))
        self.paint_ground((round(math.degrees(a), 2), ca, sa, still))

    def boat_layers(self, frame):
        """Quadro do barco com o que muda no jogo: o oleo na cacamba (enche
        com a carga), o oleo recolhido descendo a esteira e a luz piscando."""
        if not (self.boat_bucket or self.boat_light or self.boat_drop):
            return frame
        img = frame.copy()
        landed = max(0, self.load - len(self.belt))  # o que ainda desce a esteira nao chegou
        if landed and self.boat_bucket:
            n = len(self.boat_bucket)
            img.blit(self.boat_bucket[min(n, math.ceil(landed / CAPACITY * n)) - 1], (0, 0))
        if self.boat_drop:
            (x0, y0), (x1, y1) = self.boat_meta["esteira"]
            dw, dh = self.boat_drop.get_size()
            for age in self.belt:
                t = age / BELT_TIME
                img.blit(self.boat_drop, (round(x0 + (x1 - x0) * t - dw / 2), round(y0 + (y1 - y0) * t - dh / 2)))
        if self.boat_light and self.anim % LIGHT_BLINK < LIGHT_BLINK / 2:
            img.blit(self.boat_light, (0, 0))
        return img

    def draw_boat(self):
        """Barco: escolhe na folha o quadro do angulo (barco x camera) e do estado
        (parado, andando com espuma animada, no ar)."""
        scr = self.screen
        frames = self.boat_frames  # parado, ar, andando 1..n
        moving = self.moving and self.state == "play"  # nas curvas tambem: o rastro nao some
        if self.air:
            row = 1
        elif moving:
            row = 2 + int(self.anim * self.speed * 1.5) % (len(frames) - 2)
        else:
            row = 0
        frame = self.boat_layers(frames[row])
        ax, ay = self.boat_meta["apoio"]
        tilt = math.degrees(self.heading - self.view)  # nas curvas o barco vira antes da camera
        if row >= 2 and self.boat_trail:
            # rastro por baixo do barco: perto da popa segue o barco e, mais longe,
            # curva de volta para o caminho de antes (para onde a camera ainda olha)
            bends = self.boat_meta["rastro"]["curvas"]
            i = min(range(len(bends)), key=lambda j: abs(bends[j] - tilt))
            pad = self.boat_meta["rastro"]["margem"]
            img = self.boat_trail[i][row - 2].copy()
            img.blit(frame, (pad, 0))
            frame, ax = img, ax + pad
        if abs(tilt) > 0.3:
            # gira em volta do apoio: o ponto que encosta na agua fica no mesmo lugar
            pivot = pygame.Vector2(ax, ay)
            off = pivot - pygame.Vector2(frame.get_rect().center)
            frame = pygame.transform.rotozoom(frame, -tilt, 1.0)  # rotozoom: borda suave
            ax, ay = pygame.Vector2(frame.get_rect().center) + off.rotate(tilt)
        gx, gy = self.ground[0], self.ground[1]
        if self.air:
            fs = self.flat_size(0, 0, 0.9, 1.4)
            if fs:
                x, y, w, h = fs
                scr.blit(self.scaled(("sombra",), self.img["sombra"], w, h), (x - w / 2, y - h / 2))
            q = project(surface_point(0, 0, self.height()))
            k = PLAYER_DEPTH / q[2] * CAM_ZOOM  # mais perto da camera = maior (tamanho exato: sem tremer)
            w, h = round(frame.get_width() * k), round(frame.get_height() * k)
            img = pygame.transform.smoothscale(frame, (w, h))  # muda a cada quadro (luz, cacamba)
            scr.blit(img, (round(q[0] - ax * w / frame.get_width()), round(q[1] - ay * h / frame.get_height())))
        else:
            if CAM_ZOOM != 1:  # camera mais perto ou mais longe: o barco acompanha as casas
                w, h = round(frame.get_width() * CAM_ZOOM), round(frame.get_height() * CAM_ZOOM)
                frame, ax, ay = pygame.transform.smoothscale(frame, (w, h)), ax * CAM_ZOOM, ay * CAM_ZOOM
            bob = math.sin(self.anim * 3.1) * 2.5 * CAM_ZOOM
            scr.blit(frame, (gx - ax, gy - ay + bob))

    def text_image(self, msg, font, color=(255, 255, 255)):
        """Texto com o contorno escuro do estilo cartoon (o mesmo do marcador de
        reciclagem): a letra colorida por cima da mesma letra em #20242b, deslocada
        em 8 direcoes. Guardado pronto, porque quase sempre se repete."""
        key = (msg, font, color)
        img = self.text_cache.get(key)
        if img is None:
            if len(self.text_cache) > 256:  # pontos mudam sem parar: nao deixa crescer
                self.text_cache.clear()
            txt = font.render(msg, True, color)
            ink = font.render(msg, True, (32, 36, 43))
            r = max(2, font.get_height() // 16)  # contorno proporcional ao tamanho da letra
            img = pygame.Surface((txt.get_width() + 2 * r, txt.get_height() + 2 * r), pygame.SRCALPHA)
            for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r), (-r + 1, -r + 1), (r - 1, -r + 1),
                           (-r + 1, r - 1), (r - 1, r - 1)):
                img.blit(ink, (r + dx, r + dy))
            img.blit(txt, (r, r))
            self.text_cache[key] = img
        return img

    def text(self, msg, font, pos, color=(255, 255, 255), anchor="center"):
        """Escreve com o contorno cartoon; anchor = ponto do texto que fica em pos
        (center, midright...)."""
        img = self.text_image(msg, font, color)
        self.screen.blit(img, img.get_rect(**{anchor: pos}))

    def draw_hud(self):
        scr = self.screen
        if self.state == "gameover":
            self.draw_gameover()
            return
        icon = self.img["coracao"]
        step = icon.get_width() + 6
        best = max(self.best["pontos"], self.score)
        score = self.text_image(f"{self.score}", self.small, (255, 230, 120))
        rest = self.text_image(f"/  {best}", self.small, (220, 235, 245))
        if self.feet_mode:
            # console: o minimapa no alto, no meio, com as vidas a esquerda dele e os
            # pontos a direita, juntos perto do meio (a tela larga deixa os cantos
            # longe do jogador); sem o numero do rio
            gap = self.img["minimapa"].get_width() // 2 + 26
            x0 = W // 2 - gap - (step * self.lives - 6)
            for i in range(self.lives):
                scr.blit(icon, (x0 + i * step, HUD_Y - icon.get_height() // 2))
            scr.blit(score, score.get_rect(midleft=(W // 2 + gap, HUD_Y)))
            scr.blit(rest, rest.get_rect(midleft=(W // 2 + gap + score.get_width() + 4, HUD_Y)))
        else:
            for i in range(self.lives):  # coracoes = vidas restantes (no alto, a esquerda)
                scr.blit(icon, (46 + i * step, HUD_Y - icon.get_height() // 2))
            # pontos / recorde numa linha so, alinhada a direita (espelha os coracoes)
            rect = rest.get_rect(midright=(W - 40, HUD_Y))
            scr.blit(rest, rect)
            scr.blit(score, score.get_rect(midright=(rect.left - 4, rect.centery)))
            self.text(f"RIO {self.river}", self.small, (W // 2, HUD_Y))
        if self.state != "gameover":
            self.draw_minimap()
        if self.state == "play" and self.combo >= 2:
            self.text("COMBO x%d" % min(self.combo, 5), self.small, (W // 2, 140 if self.feet_mode else 116),
                      (255, 200, 80))
        for label, age, color in self.popups:  # "+10" subindo acima do barco
            img = self.text_image(label, self.small, color).copy()  # copia: o alpha nao vai para o cache
            img.set_alpha(int(255 * min(1.0, 2.2 - 2 * age)))
            scr.blit(img, img.get_rect(center=(self.ground[0], self.ground[1] - 140 - age * 45)))

        if self.state == "clear":
            lines = [(("RIO %d LIMPO!" % self.river, self.popup_font, (190, 255, 160)),
                      ("+%d" % self.clear_bonus, self.popup_font, (255, 230, 120)))]
            if self.extra_life:
                lines.append(("+1", self.font, (255, 255, 255), "coracao_grande"))
            self.draw_banner(lines, 2.8)
        elif self.state == "fail":
            left = "último barco!" if self.lives == 1 else "restam %d barcos" % self.lives
            self.draw_banner([(self.fail_msg, self.popup_font, (255, 140, 130)),
                              (left, self.small, (255, 255, 255))], 1.6)
        elif self.waiting and not self.paused:
            if self.feet_mode:
                # no meio entre o minimapa e a proa do barco
                self.text("FIQUE PARADO NAS PEGADAS PARA COMEÇAR", self.tiny, (W // 2, (140 + round(self.ground[1]) - 82) // 2))
            else:
                self.text("APERTE QUALQUER TECLA PARA INICIAR", self.tiny, (W // 2, 170))
        elif self.msg_timer > 0:
            self.text(self.message, self.font, (W // 2, 170))

    def draw_banner(self, lines, length):
        """Aviso do fim de rio / batida (sem caixa). Entra crescendo de leve e
        some no fim (length = duracao do estado)."""
        card = self.relief_text(lines)
        age = length - self.state_timer
        img = card
        if age < 0.25:  # entra crescendo e passa um pouquinho do tamanho (sem exagero)
            s = age / 0.25
            scale = 0.8 + 0.2 * (1 + 2.2 * (s - 1) ** 3 + 1.2 * (s - 1) ** 2)
            img = pygame.transform.smoothscale(card, (round(card.get_width() * scale),
                                                      round(card.get_height() * scale)))
        if self.state_timer < 0.3:  # some no fim
            img = img.copy()
            img.set_alpha(int(255 * max(0.0, self.state_timer) / 0.3))
        y = 215 if self.feet_mode else 125  # no console, abaixo do minimapa
        self.screen.blit(img, img.get_rect(center=(W // 2, y)))

    def relief_text(self, lines):
        """Linhas de texto empilhadas e centradas, com o contorno cartoon e um
        relevo escuro embaixo. Cada linha e um pedaco (msg, fonte, cor[, icone])
        ou uma tupla de pedacos lado a lado (alinhados pela base das letras); o icone (nome
        em self.img) vai logo antes do texto. Guardado pronto."""
        key = ("banner",) + tuple(lines)
        card = self.text_cache.get(key)
        if card is None:
            imgs = []
            for line in lines:
                specs = line if isinstance(line[0], tuple) else (line,)
                parts = [self.relief_part(*part) for part in specs]
                if len(parts) == 1:
                    imgs.append(parts[0])
                    continue
                # topo de cada pedaco ate a base das letras (o contorno soma r em volta)
                tops = [max(2, f.get_height() // 16) + f.get_ascent() for _, f, *_ in specs]
                base = max(tops)
                space = 14
                w = sum(img.get_width() for img, _ in parts) + space * (len(parts) - 1)
                h = max(base - t + img.get_height() for t, (img, _) in zip(tops, parts))
                row, under = pygame.Surface((w, h), pygame.SRCALPHA), pygame.Surface((w, h), pygame.SRCALPHA)
                x = 0
                for t, (img, relief) in zip(tops, parts):
                    row.blit(img, (x, base - t))
                    under.blit(relief, (x, base - t))
                    x += img.get_width() + space
                imgs.append((row, under))
            gap, depth = 0, 4
            w = max(img.get_width() for img, _ in imgs)
            h = sum(img.get_height() for img, _ in imgs) + gap * (len(imgs) - 1) + depth
            card = pygame.Surface((w, h), pygame.SRCALPHA)
            y = 0
            for img, relief in imgs:
                for d in range(depth, 0, -1):  # relevo descendo, como nos adesivos do menu
                    card.blit(relief, relief.get_rect(midtop=(w // 2, y + d)))
                card.blit(img, img.get_rect(midtop=(w // 2, y)))
                y += img.get_height() + gap
            self.text_cache[key] = card
        return card

    def relief_part(self, msg, font, color, *icon):
        """Um pedaco de relief_text: o texto e a mesma forma em escuro (o relevo)."""
        img, relief = self.text_image(msg, font, color), self.text_image(msg, font, (32, 36, 43))
        if icon:  # icone + texto lado a lado (o icone ja tem o proprio contorno)
            pic = self.img[icon[0]]
            w = img.get_width() + 4 + pic.get_width()
            h = max(img.get_height(), pic.get_height())
            both, under = pygame.Surface((w, h), pygame.SRCALPHA), pygame.Surface((w, h), pygame.SRCALPHA)
            both.blit(pic, pic.get_rect(midleft=(0, h // 2)))
            both.blit(img, img.get_rect(midright=(w, h // 2)))
            under.blit(relief, relief.get_rect(midright=(w, h // 2)))
            img, relief = both, under
        return img, relief

    # cores do minimapa (estilo cartoon: cada coisa e uma bolinha com contorno escuro)
    MAP_COLORS = {OIL: (12, 12, 16), FISH: (255, 140, 30), BUOY: (235, 55, 55),
                  SPOUT: (225, 248, 255), DOCK: (255, 215, 60)}
    MAP_LINE = (32, 36, 43)  # #20242b, o contorno do barco

    def draw_minimap(self):
        """Mapa do rio inteiro no canto, redondo e no estilo cartoon: centrado no
        barco (o rio da a volta nas bordas) e girado junto com a camera (para
        cima = para frente)."""
        m, cs = self.minimap, MAP_CELL
        m.fill((70, 165, 210) if self.pollution() < 0.5 else (105, 125, 80))
        x0, y0 = round(self.px) - N // 2, round(self.py) - N // 2
        cells = []
        for y in range(N):
            row = self.grid[(y0 + y) % N]
            for x in range(N):
                c = row[(x0 + x) % N]
                if c and c != STATION:  # a estacao fica de fora: o ponto e so o quadrado da vaga
                    cells.append((x * cs + cs / 2, y * cs + cs / 2, c))
        # duas passadas: primeiro todos os contornos, depois os recheios. Assim as
        # casas vizinhas (blocos de oleo, a vaga) viram uma forma so com um contorno
        for line in (True, False):
            for cx, cy, c in cells:
                grow = 2 if line else 0
                color = self.MAP_LINE if line else self.MAP_COLORS[c]
                if c == DOCK:  # a vaga: quadradinhos que se emendam num quadrado so
                    side = cs + 2 * grow
                    pygame.draw.rect(m, color, (cx - side / 2, cy - side / 2, side, side))
                else:
                    r = (cs * 0.75 if c == OIL else cs * 0.45) + grow
                    pygame.draw.circle(m, color, (cx, cy), r)
        if self.need_unload:  # caminho do guia ate a estacao: pontinhos claros
            for gx, gy in self.guide[1:]:
                pos = (((gx - x0) % N) * cs + cs / 2, ((gy - y0) % N) * cs + cs / 2)
                pygame.draw.circle(m, (255, 245, 170), pos, cs * 0.25)
        # gira suave e reduz para 3 px por casa, depois recorta o circulo do meio
        rot = pygame.transform.rotozoom(m, math.degrees(self.view), 3 / cs)
        r = MAP_RADIUS
        disc = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        disc.blit(rot, (r - rot.get_width() / 2, r - rot.get_height() / 2))
        disc.blit(self.map_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        frame = self.img["minimapa"]
        if self.feet_mode:  # console: no alto, no meio (no chao, o canto de baixo fica fora da vista)
            x, y = (W - frame.get_width()) // 2, 10
        else:
            x, y = W - frame.get_width() - 10, H - frame.get_height() - 10
        arrow = self.img["minimapa_barco"]
        if self.feet_mode:  # console: semitransparente, para ver o que vem pela frente atras dele
            card = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
            mid = (frame.get_width() // 2, frame.get_height() // 2)
            card.blit(disc, disc.get_rect(center=mid))
            card.blit(frame, (0, 0))
            card.blit(arrow, arrow.get_rect(center=mid))
            card.set_alpha(MAP_ALPHA_CONSOLE)
            self.screen.blit(card, (x, y))
            return
        center = (x + frame.get_width() // 2, y + frame.get_height() // 2)
        self.screen.blit(disc, disc.get_rect(center=center))
        self.screen.blit(frame, (x, y))
        self.screen.blit(arrow, arrow.get_rect(center=center))

    def draw_gameover(self):
        """Fim de jogo: o jogo escurecido, os pontos e o recorde (os botoes
        embaixo sao desenhados pelo App)."""
        scr = self.screen
        shade_ = pygame.Surface((W, H), pygame.SRCALPHA)
        shade_.fill((0, 15, 30, 160))
        scr.blit(shade_, (0, 0))
        lines = [("SEU BARCO AFUNDOU", self.font, (255, 255, 255))]
        if self.new_record:
            lines += [(str(self.score), self.big, (255, 230, 120)),
                      ("NOVO RECORDE!", self.font, (190, 255, 160))]
        else:  # "pontos / recorde", como no placar do alto da tela
            lines.append(((str(self.score), self.big, (255, 230, 120)),
                          ("/ %d" % self.best["pontos"], self.font, (220, 235, 245))))
        img = self.relief_text(lines)
        scr.blit(img, img.get_rect(midbottom=(W // 2, H // 2 + 10)))


# --- menu ---------------------------------------------------------------------
# controles: ([teclas desenhadas], o que faz, nome curto); "left"/"right"/"up"/"down" viram
# setas, "space" a barra de espaco, e o resto e o texto escrito na tecla. A tela OPCOES
# usa o texto completo; a faixa do comeco da corrida, o nome curto
CONTROLS = [
    (["left", "right"], "virar o barco", "VIRAR"),
    (["space"], "pular (2x: salto duplo)", "PULAR"),
    (["R"], "recomeçar", "RECOMEÇAR"),
    (["ESC"], "pausar", "PAUSAR"),
]


# creditos: (titulo da secao, [linhas]) — rolam na coluna da direita do menu
CREDITS_TEAM = "CREATIUS GAMES"
CREDITS = [
    ("DESENVOLVIMENTO", ["Felipe Neves"]),
    ("ARTE E INTERFACE", ["Marília Almeida"]),
    ("GAME DESIGN", ["Felipe Neves"]),
    ("MÚSICA", ["\"Flowerbed Fields\"", "Zane Little Music (CC0)"]),
    ("EFEITOS SONOROS", ["Kenney - kenney.nl (CC0)", "rubberduck - OpenGameArt (CC0)",
                         "Breviceps - Freesound (CC0)", "Universfield - Pixabay (Pixabay License)"]),
    ("ENGINE", ["Pygame"]),
]
CREDITS_SPEED = 30     # velocidade da rolagem dos creditos (px/s)
CREDITS_VIEW = (24, 382)  # faixa da tela (topo, base) onde os creditos rolam
# tela de agradecimento (ao SAIR): (foto em assets, nome, funcao)
THANKS = [("agradecimento_felipe.png", "Felipe Neves", "DESENVOLVEDOR E GAME DESIGNER"),
          ("agradecimento_marilia.png", "Marília Almeida", "GAME ART")]
THANKS_TIME = 15.0     # duracao da tela de agradecimento (s); depois o jogo fecha
THANKS_PHOTO_R = 72    # raio das fotos redondas (px)
FEET_KEYS = {"left": pygame.K_LEFT, "right": pygame.K_RIGHT}  # marcacoes do chao -> teclas do jogo


class App:
    """Telas do jogo: menu principal, opções, créditos, partida, pausa e fim de jogo."""

    MAIN = ["JOGAR", "OPÇÕES", "CRÉDITOS", "SAIR"]
    PAUSE = ["CONTINUAR", "OPÇÕES", "MENU PRINCIPAL"]
    SOUND = [("MÚSICA", "musica"), ("EFEITOS", "efeitos")]  # barras da tela OPÇÕES (+ VOLTAR)
    CHOICES = ("controle", "resolucao", "tela_cheia")  # linhas da tela OPÇÕES trocadas com as setas
    GAMEOVER = ["JOGAR DE NOVO", "MENU PRINCIPAL"]

    def __init__(self, screen, console=None):
        self.screen = screen
        self.console = console  # console TTEA (controle pelos pes), ou None so no teclado
        self.feet = console is not None  # no TTEA: pes (padrao) ou so teclado (tela OPÇÕES)
        self.dwell = 0.0         # tempo parado em cima do botao dwell_on (pes no console)
        self.dwell_on = None
        self.dwell_armed = True  # depois de escolher, os pes tem que sair dos botoes
        self.game = None
        self.mode = "menu"  # menu, credits, sound, game, pause, gameover, thanks
        self.sel = 0
        self.buttons = []
        # menu principal: agua rolando, barco andando na diagonal, titulo e botoes a direita
        self.menu_boat = [load_image("menu_barco_%d.png" % (i + 1)) for i in range(4)]
        self.menu_img = {"titulo": load_image("menu_titulo.png")}
        self.menu_water = load_image("agua_limpa.png")
        name, size, size_sel = MENU_BUTTON_FONT
        font = os.path.join(ASSETS_DIR, "fonts", name)
        self.menu_font = pygame.font.Font(font, size)
        self.menu_font_sel = pygame.font.Font(font, size_sel)
        self.record_font = pygame.font.Font(os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf"), 17)  # mais limpa
        self.credit_head_font = pygame.font.Font(os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf"), 13)
        # nome da equipe nos creditos: mesma fonte do titulo ZERO OIL
        self.credit_team_font = pygame.font.Font(os.path.join(ASSETS_DIR, "fonts", "Creepster-Regular.ttf"), 30)
        self.menu_t = 0.0
        self.sticker_cache = {}
        self.credits_img = self.credits_fade = None  # montados no primeiro desenho
        self.credits_scroll = 0.0
        self.thanks_cards = None  # agradecimento: montado no primeiro desenho
        self.thanks_t = 0.0
        self.thanks_scale = 1.0   # tamanho do agradecimento (o video em 1920 x 1080 usa mais)
        self.sound_from = "menu"  # tela que abriu a de OPÇÕES (volta para ela): menu ou pause
        self.window_choice = dict(config)  # resolucao e tela cheia na tela OPÇÕES, antes do Enter
        # menus desenhados para BASE_W x BASE_H: na tela maior do console, vao para o meio
        self.dx, self.dy = (W - BASE_W) // 2, (H - BASE_H) // 2
        self.dragging = None      # barra de volume sendo arrastada com o mouse
        # Ctrl+D: painel para mudar velocidade, curvas, marcacoes... com o jogo rodando
        saved = console.data_file("ajustes.json") if console else os.path.join(console_ttea.GAME_DIR, "ajustes.json")
        self.panel = painel_ajustes.Panel(self, sys.modules[__name__], console_ttea, saved)

    def options(self):
        return {"menu": self.MAIN, "gameover": self.GAMEOVER}.get(self.mode, self.PAUSE)

    def choose(self, option):
        play("menu_ok")
        if option == "JOGAR":
            self.game = Game(self.screen)
            if self.console:
                self.game.run_log = self.console.save_run
            self.game.feet_mode = self.feet
            self.mode = "game"
        elif option == "OPÇÕES":
            self.sound_from, self.mode, self.sel = self.mode, "sound", 0
            self.window_choice = {"resolucao": current_resolution(), "tela_cheia": config["tela_cheia"]}
        elif option == "CRÉDITOS":
            self.mode = "credits"
            self.credits_scroll = 0.0
        elif option == "SAIR":  # antes de fechar, o agradecimento
            self.mode, self.thanks_t, self.buttons = "thanks", 0.0, []
        elif option == "CONTINUAR":
            self.mode = "game"
        elif option == "JOGAR DE NOVO":
            self.game.reset_run()
            self.mode = "game"
        elif option == "MENU PRINCIPAL":
            self.game.end_run("menu")
            self.mode, self.sel = "menu", 0

    def quit(self):
        if self.game:
            self.game.end_run("saiu")
        if self.console:
            self.console.close()
        pygame.quit()
        sys.exit()

    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            self.quit()
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_d and ev.mod & pygame.KMOD_CTRL:
            self.panel.toggle()
            return
        if self.panel.open and self.panel.handle_event(ev):  # aberto, o teclado e dele
            return
        if self.console and ev.type == pygame.KEYDOWN and ev.key == pygame.K_F2:
            self.console.toggle_preview()  # janela da camera (profissional)
            return
        if self.mode == "game":
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if self.game.state == "gameover":
                    self.mode, self.sel = "menu", 0
                else:
                    self.mode, self.sel = "pause", 0
            else:
                self.game.handle_event(ev)
            return
        if self.mode == "credits":  # setas e roda do mouse rolam; o resto volta
            if ev.type == pygame.MOUSEWHEEL:
                self.credits_scroll -= ev.y * 40
            elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                self.credits_scroll += 40 if ev.key in (pygame.K_DOWN, pygame.K_s) else -40
            elif ev.type == pygame.KEYDOWN or (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
                self.mode = "menu"
                play("menu_ok")
            return
        if self.mode == "sound":
            self.handle_sound_event(ev)
            return
        if self.mode == "thanks":  # qualquer tecla ou clique fecha antes do fim
            if self.thanks_t > 0.5 and (ev.type == pygame.KEYDOWN or
                                        (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1)):
                self.quit()
            return
        opts = self.options()
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % len(opts)
                play("menu_mover")
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % len(opts)
                play("menu_mover")
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.choose(opts[self.sel])
            elif ev.key == pygame.K_ESCAPE:
                self.choose({"menu": "SAIR", "pause": "CONTINUAR"}.get(self.mode, "MENU PRINCIPAL"))
        elif ev.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.buttons):
                if rect.collidepoint(ev.pos) and i != self.sel:
                    self.sel = i
                    play("menu_mover")
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, rect in enumerate(self.buttons):
                if rect.collidepoint(ev.pos):
                    self.choose(opts[i])

    def sound_rows(self):
        """Linhas da tela OPÇÕES: as barras, as escolhas (o controle no TTEA; a
        resolucao e a tela cheia numa janela comum, tambem na simulacao dos pes)
        e o VOLTAR."""
        choices = (["controle"] if self.console else []) + (["resolucao", "tela_cheia"] if window else [])
        return [key for _, key in self.SOUND] + choices + ["voltar"]

    def choice_text(self, row):
        """(titulo, texto do botao) de uma linha de escolha da tela OPÇÕES. Escolha
        ainda nao aplicada: o titulo avisa do Enter."""
        if row == "controle":  # pes no console ou so o teclado
            return "CONTROLE", "CONSOLE TTEA" if self.feet else "TECLADO"
        if row == "resolucao":  # da janela, ou do monitor em tela cheia
            head, label = "RESOLUÇÃO", self.window_choice["resolucao"]
        else:
            head, label = "TELA CHEIA", "LIGADA" if self.window_choice["tela_cheia"] else "DESLIGADA"
        applied = {"resolucao": current_resolution(), "tela_cheia": config["tela_cheia"]}
        if self.window_choice[row] != applied[row]:
            head += " · ENTER APLICA"
        return head, label

    def change_choice(self, row, step):
        """Troca a escolha da linha row: step 1 para a seguinte, -1 para a anterior.
        O controle vale na hora; a resolucao e a tela cheia, so com o Enter."""
        if row == "controle":
            self.toggle_feet()
            return
        choice = self.window_choice
        if row == "resolucao":
            options = resolutions()
            index = options.index(choice["resolucao"]) if choice["resolucao"] in options else 0
            choice["resolucao"] = options[(index + step) % len(options)]
        else:
            choice["tela_cheia"] = not choice["tela_cheia"]
        play("menu_mover")

    def apply_window_choice(self):
        """Enter na resolucao ou na tela cheia: a janela (ou o monitor, em tela
        cheia) muda para o escolhido."""
        config.update(self.window_choice)
        apply_window()
        save_config()
        play("menu_ok")

    def handle_sound_event(self, ev):
        """Tela OPÇÕES: setas para cima/baixo escolhem a barra (ou a escolha, o
        VOLTAR), para os lados mudam 10% (ou trocam a escolha; a resolucao e a
        tela cheia so valem com o Enter); com o mouse, clicar ou arrastar na
        barra, e o clique numa escolha troca e aplica."""
        rows = self.sound_rows()
        if ev.type == pygame.KEYDOWN:
            row = rows[self.sel]
            if ev.key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + (1 if ev.key in (pygame.K_DOWN, pygame.K_s) else -1)) % len(rows)
                play("menu_mover")
            elif ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d) and row in volume:
                step = 0.1 if ev.key in (pygame.K_RIGHT, pygame.K_d) else -0.1
                self.set_volume(row, volume[row] + step)
            elif row in self.CHOICES and ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                self.change_choice(row, 1 if ev.key in (pygame.K_RIGHT, pygame.K_d) else -1)
            elif row == "controle" and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.toggle_feet()
            elif row in self.CHOICES and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.apply_window_choice()
            elif ev.key == pygame.K_ESCAPE or (ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
                                               and row == "voltar"):
                self.close_sound()
        elif ev.type == pygame.MOUSEMOTION:
            if self.dragging is not None:
                self.volume_from_mouse(self.dragging, ev.pos[0])
                return
            for i, rect in enumerate(self.buttons):
                if rect.inflate(0, 30).collidepoint(ev.pos) and i != self.sel:
                    self.sel = i
                    play("menu_mover")
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, rect in enumerate(self.buttons):
                if not rect.inflate(0, 30).collidepoint(ev.pos):
                    continue
                if rows[i] == "voltar":
                    self.close_sound()
                elif rows[i] in self.CHOICES:
                    self.sel = i
                    self.change_choice(rows[i], 1)
                    if rows[i] != "controle":
                        self.apply_window_choice()
                else:
                    self.sel = self.dragging = i
                    self.volume_from_mouse(i, ev.pos[0])
                break
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.dragging is not None:
            if self.SOUND[self.dragging][1] == "efeitos":
                play("menu_mover")  # amostra do volume novo
            self.dragging = None
            save_config()

    def set_volume(self, key, value):
        volume[key] = round(min(1.0, max(0.0, value)), 2)
        save_config()
        if key == "efeitos":
            play("menu_mover")  # amostra do volume novo

    def volume_from_mouse(self, row, x):
        bar = self.buttons[row]
        volume[self.SOUND[row][1]] = round(min(1.0, max(0.0, (x - bar.left) / bar.w)), 2)

    def toggle_feet(self):
        """Console TTEA: troca entre jogar com os pes e so no teclado."""
        self.feet = not self.feet
        self.console.present_t = 0.0
        self.dwell, self.dwell_on, self.dwell_armed = 0.0, None, True
        if self.game:
            self.game.feet_mode = self.feet
        self.panel.apply()  # cada controle tem o seu perfil de ajustes
        play("menu_ok")

    def relayout(self):
        """Barco em outra linha da tela ou camera mais perto/longe (painel de
        ajustes): a camera e o chao da partida sao montados de novo."""
        set_screen_size(W, H, console_ttea.BOAT_Y, console_ttea.CAMERA_VIEW)
        if self.game:
            self.game.setup_view()

    def close_sound(self):
        save_config()
        self.dragging = None
        self.mode = self.sound_from
        self.sel = self.options().index("OPÇÕES")
        play("menu_ok")

    def update_feet(self, dt):
        """Console TTEA: na partida os pes viram teclas (passo para o lado vira,
        parado sai andando, pulo pula); nos menus, parar em cima de um botao
        por DWELL_TIME escolhe."""
        con = self.console
        commands = con.update(dt)
        if self.mode != "game":
            self.dwell_update(con.pointer, dt)
            return
        game = self.game
        self.dwell, self.dwell_on, self.dwell_armed = 0.0, None, True  # na partida os pes nao estao em botao
        for command in commands:
            if command == "jump":
                game.feet_jump()
            else:
                game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=FEET_KEYS[command], mod=0))
        if game.state == "play" and game.waiting:
            if con.present(dt):  # parado em cima do barco: sai andando
                game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP, mod=0))
        else:
            con.present_t = 0.0

    def dwell_update(self, pos, dt):
        """Escolha pelos pes: o botao embaixo deles fica selecionado e, parado
        ali por DWELL_TIME, e escolhido. Nos creditos e nas barras de volume
        nao (sao para o profissional, no teclado ou no mouse)."""
        hit = None
        if pos is not None and self.mode != "credits":
            for i, rect in enumerate(self.buttons):
                if rect.inflate(16, 24).collidepoint(pos):
                    hit = i
            if self.mode == "sound" and hit is not None and self.sound_rows()[hit] != "voltar":
                hit = None
        if hit is None:
            self.dwell, self.dwell_on, self.dwell_armed = 0.0, None, True
            return
        if not self.dwell_armed:
            return
        if hit != self.dwell_on:
            self.dwell_on, self.dwell = hit, 0.0
            if hit != self.sel:
                self.sel = hit
                play("menu_mover")
        self.dwell += dt
        if self.dwell >= console_ttea.DWELL_TIME:
            self.dwell, self.dwell_on, self.dwell_armed = 0.0, None, False
            if self.mode == "sound":
                self.close_sound()
            else:
                self.choose(self.options()[hit])

    def draw_feet(self):
        """Marcador dos pes do jogador (console TTEA). Na partida uma bolinha
        por pe (as marcacoes respondem a cada pe); nos menus um marcador so, com
        o anel que enche enquanto ele fica parado em cima de um botao."""
        pos = self.console.pointer if self.feet else None
        if pos is None:
            return
        scr = self.screen
        if self.mode == "game":
            dot = self.smooth_dot(10, 7)
            for fx, fy in self.console.feet:
                scr.blit(dot, dot.get_rect(center=(round(fx), round(fy))))
            return
        x, y = round(pos[0]), round(pos[1])
        if self.dwell_on is not None:
            k = min(1.0, self.dwell / console_ttea.DWELL_TIME)
            ring = self.smooth_ring(52, 52, k, 8)  # o furo (raio 18) encosta no marcador
            scr.blit(ring, ring.get_rect(center=(x, y)))
        marker = self.smooth_dot(18, 15, 5)
        scr.blit(marker, marker.get_rect(center=(x, y)))

    def smooth_dot(self, r_ink, r_face, r_mid=0):
        """Bolinha clara com contorno escuro (e um ponto escuro no meio), desenhada
        4x maior e reduzida: a borda fica lisa mesmo com a tela ampliada no
        projetor. Guardada pronta."""
        key = ("dot", r_ink, r_face, r_mid)
        if key not in self.sticker_cache:
            k, size = 4, 2 * r_ink + 2
            big = pygame.Surface((size * k, size * k), pygame.SRCALPHA)
            c = (size * k // 2, size * k // 2)
            pygame.draw.circle(big, (32, 36, 43), c, r_ink * k)
            pygame.draw.circle(big, (232, 242, 250), c, r_face * k)
            if r_mid:
                pygame.draw.circle(big, (32, 36, 43), c, r_mid * k)
            self.sticker_cache[key] = pygame.transform.smoothscale(big, (size, size))
        return self.sticker_cache[key]

    def smooth_ring(self, w, h, progress, line=8):
        """Anel (elipse w x h) que enche no sentido horario a partir do alto:
        trilho escuro e a parte cheia em amarelo (como o botao selecionado).
        Desenhado 4x maior e reduzido, para a borda ficar lisa; guardado em 48
        passos de enchimento."""
        steps = 48
        n = round(min(1.0, max(0.0, progress)) * steps)
        key = ("ring", w, h, n, line)
        if key not in self.sticker_cache:
            k = 4
            big = pygame.Surface((w * k, h * k), pygame.SRCALPHA)
            outer = big.get_rect()
            pygame.draw.ellipse(big, (32, 36, 43), outer)
            pygame.draw.ellipse(big, (0, 0, 0, 0), outer.inflate(-2 * line * k, -2 * line * k))  # fura o meio
            if n:
                cx, cy = w * k / 2, h * k / 2
                pad = 2 * k  # a parte cheia fica dentro do trilho, com contorno dos dois lados
                ax, ay = w * k / 2 - pad, h * k / 2 - pad
                bx, by = ax - (line * k - 2 * pad), ay - (line * k - 2 * pad)
                end = n / steps * math.tau
                arc = [-math.pi / 2 + end * i / 96 for i in range(97)]
                pts = [(cx + ax * math.cos(a), cy + ay * math.sin(a)) for a in arc]
                pts += [(cx + bx * math.cos(a), cy + by * math.sin(a)) for a in reversed(arc)]
                pygame.draw.polygon(big, (242, 214, 130), pts)
            self.sticker_cache[key] = pygame.transform.smoothscale(big, (w, h))
        return self.sticker_cache[key]

    def draw_panel(self):
        """Marcacoes do console TTEA por cima do rio, na parte de baixo da tela
        (o rio continua por baixo delas): as pegadas no meio e uma seta de virar
        de cada lado. Uma seta com um pe em cima afunda e fica amarela (como o
        botao selecionado); fora da corrida elas ficam apagadas. Nos menus, um
        aviso de como escolher."""
        scr, con = self.screen, self.console
        if self.mode != "game":  # menus, pausa e fim: escolhe parando em cima de um botao
            hint = self.sticker("PARE EM CIMA DE UM BOTÃO PARA ESCOLHER", self.record_font)
            scr.blit(hint, hint.get_rect(center=(W // 2, H - 40)))
            return
        game = self.game
        playing = game.state == "play"
        (sx, sy), (stand_w, stand_h) = con.stand_spot
        img = self.floor_pad("stand", False, True)
        scr.blit(img, img.get_rect(center=(sx, sy)))
        for name, ((x, y), _) in con.pads.items():
            img = self.floor_pad(name, con.pressed[name] and playing, playing)
            scr.blit(img, img.get_rect(center=(x, y)))
        if playing and game.waiting and con.present_t > 0:  # parado nas pegadas: o anel enche e o barco sai
            ring = self.smooth_ring(stand_w - 8, stand_h + 12, con.present_t / console_ttea.START_HOLD)
            scr.blit(ring, ring.get_rect(center=(sx, sy)))

    def floor_pad(self, name, pressed, enabled):
        """Desenho de uma marcacao da faixa no estilo das teclas (keycap): face
        clara, contorno escuro e relevo embaixo. Apertada, afunda (relevo menor)
        e fica amarela; apagada, fica acinzentada. Guardado pronto."""
        key = ("pad", name, pressed, enabled)
        if key in self.sticker_cache:
            return self.sticker_cache[key]
        ink = (20, 19, 24)
        if name == "stand":  # as pegadas acompanham a area delas (desenhadas para 132 x 84)
            _, (w, h) = self.console.stand_spot
            img = pygame.transform.smoothscale(self.footprints(ink), (round(w * 96 / 132), round(h * 72 / 84)))
        else:
            w, h = self.console.pads[name][1]
            depth, line = 8, 3
            sink = 5 if pressed else 0  # apertada: a face desce e o relevo diminui
            face = (242, 214, 130) if pressed else (245, 250, 252) if enabled else (190, 202, 212)
            side = (176, 146, 72) if pressed else (160, 178, 190)
            img = pygame.Surface((w, h + depth), pygame.SRCALPHA)
            pygame.draw.rect(img, ink, (0, sink, w, h + depth - sink), border_radius=14)  # contorno
            pygame.draw.rect(img, side, (line, sink + line, w - 2 * line, h + depth - sink - 2 * line), border_radius=11)
            top = pygame.Rect(line, sink + line, w - 2 * line, h - 2 * line)
            pygame.draw.rect(img, face, top, border_radius=11)
            cx, cy = top.center
            glyph = ink if enabled else (110, 122, 134)
            s = -1 if name == "left" else 1  # seta grossa apontando para o lado
            k = min(w / 124, h / 88)  # a seta acompanha o tamanho da marcacao (desenhada para 124 x 88)
            pts = [(32, 0), (4, -26), (4, -12), (-28, -12), (-28, 12), (4, 12), (4, 26)]
            pygame.draw.polygon(img, glyph, [(cx + s * x * k, cy + y * k) for x, y in pts])
            if not enabled:
                img.set_alpha(150)
        self.sticker_cache[key] = img
        return img

    def footprints(self, ink):
        """Duas pegadas (onde o jogador fica parado), desenhadas 4x maiores e
        reduzidas para a borda ficar lisa."""
        k = 4
        w, h = 96, 72
        big = pygame.Surface((w * k, h * k), pygame.SRCALPHA)
        for sx in (-1, 1):
            cx = w // 2 + sx * 17
            sole = pygame.Rect(0, 0, 26, 34)
            sole.center = (cx + sx * 2, 26)
            heel = pygame.Rect(0, 0, 20, 20)
            heel.center = (cx, 54)
            for grow, color in ((3, ink), (0, (245, 250, 252))):
                for r in (sole, heel):
                    big_r = pygame.Rect(r.x * k, r.y * k, r.w * k, r.h * k).inflate(2 * grow * k, 2 * grow * k)
                    pygame.draw.ellipse(big, color, big_r)
        return pygame.transform.smoothscale(big, (w, h))

    def update(self, dt):
        if self.game:
            self.game.keys_off = self.panel.open
        if self.panel.frozen:  # pausado pelo painel: so as marcacoes acendem com os pes
            if self.feet:
                self.console.update(dt)
            return
        if self.feet:
            self.update_feet(dt)
        music_volume(0.4 if self.mode in ("pause", "gameover") else 1.0)  # mais baixa com o jogo parado
        if self.mode == "game":
            self.game.update(dt)
            if self.game.state == "gameover":  # acabaram os barcos: botoes de jogar de novo / menu
                self.mode, self.sel = "gameover", 0
                self.dwell_armed = False  # os pes tem que sair do lugar antes de escolher
        elif self.mode in ("menu", "credits", "thanks") or (self.mode == "sound" and self.sound_from == "menu"):
            self.menu_t += dt
            if self.mode == "credits":
                self.credits_scroll += CREDITS_SPEED * dt
            elif self.mode == "thanks":
                self.thanks_t += dt
                if self.thanks_t >= THANKS_TIME:
                    self.quit()

    def draw_menu_bg(self, title=True, boat=True):
        """Fundo do menu: a agua rola para tras do barco (que anda na direcao
        MENU_BOAT_ANGLE), o barco balanca com a espuma animada, e o titulo
        (se pedido) fica a direita."""
        scr, t = self.screen, self.menu_t
        tile = self.menu_water
        tw, th = tile.get_size()
        a, d = math.radians(MENU_BOAT_ANGLE), MENU_WATER_SPEED * t
        ox = int(-d * math.sin(a)) % tw  # a agua anda no sentido contrario ao do barco
        oy = int(d * math.cos(a)) % th
        for y in range(oy - th, H, th):
            for x in range(ox - tw, W, tw):
                scr.blit(tile, (x, y))
        if boat:
            frame = self.menu_boat[int(t * 8) % len(self.menu_boat)]
            scr.blit(frame, (self.dx, self.dy + round(math.sin(t * 2.2) * 3)))  # balanco na agua
        if title:  # com os pes os botoes sao maiores: o titulo sobe para nao encostar neles
            y = 50 if self.feet else 74
            scr.blit(self.menu_img["titulo"], self.menu_img["titulo"].get_rect(center=(MENU_X + self.dx, y + self.dy)))

    def button_layout(self):
        """(largura, distancia entre os centros) dos botoes dos menus."""
        return FEET_MENU_BUTTON if self.feet else MENU_BUTTON

    def draw_menu_button(self, label, center, sel, width=None):
        """Botao cartoon: contorno escuro e relevo embaixo; o selecionado num
        amarelo suave, os outros quase brancos. Devolve o retangulo (para o mouse)."""
        scr, ink = self.screen, (32, 36, 43)
        rect = pygame.Rect(0, 0, width or self.button_layout()[0], 44)
        rect.center = center
        pygame.draw.rect(scr, ink, rect.move(0, 4), border_radius=12)  # relevo embaixo
        pygame.draw.rect(scr, (242, 214, 130) if sel else (232, 242, 250), rect, border_radius=12)
        pygame.draw.rect(scr, ink, rect, 3, border_radius=12)
        txt = self.menu_font.render(label, True, ink)
        if txt.get_width() > rect.w - 30:  # texto comprido: encolhe para caber
            k = (rect.w - 30) / txt.get_width()
            txt = pygame.transform.smoothscale(txt, (int(txt.get_width() * k), int(txt.get_height() * k)))
        scr.blit(txt, txt.get_rect(center=(rect.centerx, rect.centery + 1)))
        return rect

    def draw_menu(self):
        """Menu principal: fundo animado, botoes e recorde na coluna da direita."""
        scr = self.screen
        self.draw_menu_bg()
        self.buttons = []
        step = self.button_layout()[1]
        top, record_y = (145, 448) if self.feet else (157, 418)  # botoes mais afastados: o recorde desce
        for i, label in enumerate(self.MAIN):
            self.buttons.append(self.draw_menu_button(label, (MENU_X + self.dx, top + i * step + self.dy), i == self.sel))
        rec = load_record()
        if rec["pontos"]:
            msg = "RECORDE  %d  ·  RIO %d" % (rec["pontos"], rec["rio"])
        else:  # no console o aviso de baixo ja diz como escolher
            msg = "SEM RECORDE" if self.feet else "SETAS E ENTER, OU O MOUSE"
        img = self.sticker(msg, self.record_font)
        scr.blit(img, img.get_rect(center=(MENU_X + self.dx, record_y + self.dy)))

    def draw_start_help(self):
        """Comeco da corrida: um painel escuro de cantos arredondados no alto com
        os controles em colunas (tecla em cima, nome embaixo) e, separado por
        uma linha fina, o aviso para apertar uma tecla (pulsando de leve). O
        barco fica livre no meio."""
        scr, game = self.screen, self.game
        controls = self.controls()
        col_w, scale = 100, 0.65  # largura de cada coluna; teclas menores
        panel = pygame.Rect(0, 0, col_w * len(controls) + 24, 112)
        panel.midtop = (W // 2, 70)
        box = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(box, (0, 15, 30, 165), box.get_rect(), border_radius=14)
        pygame.draw.line(box, (255, 255, 255, 50), (22, 80), (panel.w - 22, 80), 2)  # separa o aviso
        scr.blit(box, panel)
        for i, (keys, _, short) in enumerate(controls):
            cx = panel.left + 12 + col_w * i + col_w // 2
            caps = [self.keycap(k) for k in keys]
            caps = [pygame.transform.smoothscale(c, (round(c.get_width() * scale), round(c.get_height() * scale)))
                    for c in caps]
            w = sum(c.get_width() for c in caps) + 4 * (len(caps) - 1)
            x = cx - w // 2
            for cap in caps:
                scr.blit(cap, cap.get_rect(midleft=(x, panel.top + 28)))
                x += cap.get_width() + 4
            img = self.credit_head_font.render(short, True, (255, 255, 255))
            scr.blit(img, img.get_rect(center=(cx, panel.top + 60)))
        img = self.credit_head_font.render("APERTE QUALQUER TECLA PARA INICIAR", True, (220, 235, 245))
        img.set_alpha(round(175 + 80 * math.sin(game.anim * 3.5)))  # pulsa devagar
        scr.blit(img, img.get_rect(center=(panel.centerx, panel.top + 97)))

    def draw_feet_help(self):
        """Comeco da corrida no console TTEA: o mesmo painel do teclado, com o
        que o corpo faz (pegadas, setas e pulo) e, embaixo da linha, os avisos
        de tirar o pe da seta para virar de novo e de ficar parado para comecar."""
        scr, game = self.screen, self.game
        steps = pygame.transform.smoothscale(self.footprints((20, 19, 24)), (40, 30))
        arrows = [pygame.transform.smoothscale(c, (round(c.get_width() * 0.65), round(c.get_height() * 0.65)))
                  for c in (self.keycap("left"), self.keycap("right"))]
        columns = [([steps], "FIQUE PARADO"), (arrows, "PISE NA SETA: VIRA"), ([self.jump_icon(steps)], "PULE: O BARCO PULA")]
        col_w = 180
        panel = pygame.Rect(0, 0, col_w * len(columns) + 24, 112)
        panel.midtop = (W // 2, 118)  # abaixo do minimapa (no console ele fica no meio do alto)
        box = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(box, (0, 15, 30, 165), box.get_rect(), border_radius=14)
        pygame.draw.line(box, (255, 255, 255, 50), (22, 68), (panel.w - 22, 68), 2)  # separa os avisos
        scr.blit(box, panel)
        for i, (icons, name) in enumerate(columns):
            cx = panel.left + 12 + col_w * i + col_w // 2
            w = sum(c.get_width() for c in icons) + 4 * (len(icons) - 1)
            x = cx - w // 2
            for icon in icons:
                scr.blit(icon, icon.get_rect(midleft=(x, panel.top + 28)))
                x += icon.get_width() + 4
            img = self.credit_head_font.render(name, True, (255, 255, 255))
            scr.blit(img, img.get_rect(center=(cx, panel.top + 56)))
        img = self.credit_head_font.render("PARA VIRAR DE NOVO, TIRE O PÉ DA SETA E PISE OUTRA VEZ", True, (220, 235, 245))
        scr.blit(img, img.get_rect(center=(panel.centerx, panel.top + 83)))
        img = self.credit_head_font.render("FIQUE PARADO NAS PEGADAS PARA COMEÇAR", True, (242, 214, 130))
        img.set_alpha(round(175 + 80 * math.sin(game.anim * 3.5)))  # pulsa devagar
        scr.blit(img, img.get_rect(center=(panel.centerx, panel.top + 100)))

    def jump_icon(self, steps):
        """Pegadas com uma seta para cima: o jogador pula. Guardado pronto."""
        key = ("jump_icon",)
        if key not in self.sticker_cache:
            w, h = steps.get_width(), steps.get_height() + 15
            img = pygame.Surface((w, h), pygame.SRCALPHA)
            img.blit(steps, (0, 15))
            cx = w // 2
            pts = [(cx, 1), (cx + 10, 10), (cx + 4, 10), (cx + 4, 14), (cx - 4, 14), (cx - 4, 10), (cx - 10, 10)]
            pygame.draw.polygon(img, (245, 250, 252), pts)
            pygame.draw.polygon(img, (20, 19, 24), pts, 2)
            self.sticker_cache[key] = img
        return self.sticker_cache[key]

    def draw_pause(self):
        """Pausa no visual do jogo: o jogo escurecido atras, o titulo com o
        contorno do placar e os botoes cartoon."""
        scr, game = self.screen, self.game
        shade_ = pygame.Surface((W, H), pygame.SRCALPHA)
        shade_.fill((0, 15, 30, 160))
        scr.blit(shade_, (0, 0))
        title = game.text_image("PAUSADO", game.font)
        scr.blit(title, title.get_rect(center=(W // 2, H // 2 - 90)))
        self.buttons = []
        for i, label in enumerate(self.PAUSE):
            step = 58 if not self.feet else self.button_layout()[1]
            self.buttons.append(self.draw_menu_button(label, (W // 2, H // 2 - 24 + i * step), i == self.sel))

    def draw_sound(self):
        """Tela OPÇÕES: no visual do menu (aberta pelo menu, sem o barco) ou por
        cima do jogo escurecido, sem o placar (aberta pela pausa). Duas colunas:
        os volumes a esquerda e os controles a direita; o VOLTAR embaixo."""
        scr = self.screen
        if self.sound_from == "menu":
            self.draw_menu_bg(title=False, boat=False)
            img = self.sticker("OPÇÕES", self.menu_font_sel, depth=3)
        else:
            self.game.paused = True
            self.game.show_hud = False  # o titulo fica onde estaria o placar
            self.game.draw()
            self.game.show_hud = True
            shade_ = pygame.Surface((W, H), pygame.SRCALPHA)
            shade_.fill((0, 15, 30, 160))
            scr.blit(shade_, (0, 0))
            img = self.game.text_image("OPÇÕES", self.game.font)
        dy = self.dy
        scr.blit(img, img.get_rect(center=(W // 2, 48 + dy)))
        left, right = 155 + self.dx, 452 + self.dx  # meio de cada coluna
        rows = self.sound_rows()
        choices = [row for row in rows if row in self.CHOICES]
        # 3 linhas na coluna da esquerda no TTEA; fora dele 4, e o VOLTAR desce (a tela
        # tem CANVAS_H de altura, mais que BASE_H: cabe); na simulacao dos pes 5, mais juntas
        top, step = (172, 80) if len(choices) < 3 else (172, 66)
        back_y, line_h = {1: (418, 260), 2: (494, 340)}.get(len(choices), (496, 346))
        line = pygame.Rect(0, 0, 8, line_h)  # divisoria entre as colunas: traco claro com contorno escuro
        line.midtop = (296 + self.dx, 102 + dy)
        pygame.draw.rect(scr, (32, 36, 43), line, border_radius=4)
        pygame.draw.rect(scr, (245, 250, 252), line.inflate(-4, -4), border_radius=2)
        for cx, head in ((left, "VOLUME"), (right, "CONTROLES")):
            img = self.sticker(head, self.credit_head_font, ink=(245, 250, 252), line=(20, 19, 24), depth=1)
            scr.blit(img, img.get_rect(center=(cx, 112 + dy)))
        self.buttons = []
        for i, (label, key) in enumerate(self.SOUND):
            self.buttons.append(self.draw_slider(label, volume[key], (left, top + i * step + dy), i == self.sel))
        for i, row in enumerate(choices, len(self.SOUND)):  # escolhas: titulo em cima, botao embaixo
            cy = top + i * step + dy
            head, label = self.choice_text(row)
            img = self.sticker(head, self.record_font)
            scr.blit(img, img.get_rect(center=(left, cy - 30)))
            rect = self.draw_menu_button(label, (left, cy + 4), i == self.sel, width=210)
            if i == self.sel:  # setinhas: as setas do teclado trocam a escolha
                self.draw_side_arrows(rect)
            self.buttons.append(rect)
        self.draw_controls(right, 165 + dy, 56)
        self.buttons.append(self.draw_menu_button("VOLTAR", (W // 2, back_y + dy), rows[self.sel] == "voltar"))

    def draw_slider(self, label, value, center, sel):
        """Barra de volume no estilo dos botoes: nome em adesivo em cima, barra
        com contorno escuro e relevo, a parte cheia em amarelo (selecionada) ou
        cinza-azulado, a porcentagem no meio e setinhas dos lados quando
        selecionada. Devolve o retangulo da barra (para o mouse)."""
        scr, ink = self.screen, (32, 36, 43)
        cx, cy = center
        img = self.sticker(label, self.record_font)
        scr.blit(img, img.get_rect(center=(cx, cy - 30)))
        bar = pygame.Rect(0, 0, 210, 30)
        bar.center = (cx, cy + 4)
        pygame.draw.rect(scr, ink, bar.move(0, 4), border_radius=10)  # relevo embaixo
        pygame.draw.rect(scr, (232, 242, 250), bar, border_radius=10)
        if value > 0:
            full = pygame.Rect(bar.x, bar.y, max(20, round(bar.w * value)), bar.h)
            pygame.draw.rect(scr, (242, 214, 130) if sel else (164, 184, 198), full, border_radius=10)
        pygame.draw.rect(scr, ink, bar, 3, border_radius=10)
        txt = self.menu_font.render("%d%%" % round(value * 100), True, ink)
        scr.blit(txt, txt.get_rect(center=(bar.centerx, bar.centery + 1)))
        if sel:  # setinhas: as setas do teclado mudam o volume
            self.draw_side_arrows(bar)
        return bar

    def draw_side_arrows(self, rect):
        """Setinhas brancas com contorno escuro dos dois lados de rect."""
        for side in (-1, 1):
            x = rect.centerx + side * (rect.w // 2 + 18)
            pts = [(x + side * 8, rect.centery), (x - side * 6, rect.centery - 9), (x - side * 6, rect.centery + 9)]
            pygame.draw.polygon(self.screen, (245, 250, 252), pts)
            pygame.draw.polygon(self.screen, (32, 36, 43), pts, 2)

    def draw_credits(self):
        """Creditos no mesmo visual do menu: mesmo fundo, textos em adesivo
        subindo em loop na coluna da direita (sumindo nas bordas) e um botao
        VOLTAR no lugar do recorde."""
        scr = self.screen
        self.draw_menu_bg(title=False)
        if self.credits_img is None:
            self.credits_img, self.credits_fade = self.build_credits()
        img = self.credits_img
        top, bottom = (y + self.dy for y in CREDITS_VIEW)
        view_h = bottom - top
        # o texto entra por baixo, sai por cima e recomeca
        y = view_h - self.credits_scroll % (img.get_height() + view_h)
        view = pygame.Surface((img.get_width(), view_h), pygame.SRCALPHA)
        view.blit(img, (0, round(y)))
        view.blit(self.credits_fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        scr.blit(view, view.get_rect(midtop=(MENU_X + self.dx, top)))
        self.buttons = []  # qualquer tecla ou clique volta (ver handle_event)
        self.draw_menu_button("VOLTAR", (MENU_X + self.dx, 418 + self.dy), True)

    def draw_thanks(self):
        """Agradecimento ao SAIR: a agua do menu rolando, OBRIGADO! saltando no
        alto e os cartoes com as fotos subindo um depois do outro, balancando
        na agua. Comeca e termina num fade do preto. Desenhado para 640 x 480
        vezes thanks_scale, no meio da tela (o video usa a escala maior)."""
        scr, t, u = self.screen, self.thanks_t, self.thanks_scale
        self.draw_menu_bg(title=False, boat=False)
        if self.thanks_cards is None:
            self.thanks_cards = self.build_thanks()
        title, sub, team, cards = self.thanks_cards
        cx = W // 2

        def at(y):  # altura no desenho de 640 x 480 -> tela
            return round(H / 2 + (y - 240) * u)

        def grow(start, length):  # 0 -> 1 com um pequeno passo alem do fim (ease out back)
            x = min(1.0, max(0.0, (t - start) / length)) - 1
            return 1 + 2.70158 * x ** 3 + 1.70158 * x ** 2

        k = grow(0.2, 0.7)
        if k > 0:
            img = pygame.transform.smoothscale(title, (max(1, round(title.get_width() * k)), max(1, round(title.get_height() * k))))
            scr.blit(img, img.get_rect(center=(cx, at(66 + math.sin(t * 2.0) * 3))))
        for img, y, start in ((sub, 122, 0.8), (team, 436, 2.6)):
            img.set_alpha(round(255 * min(1.0, max(0.0, (t - start) / 0.6))))
            scr.blit(img, img.get_rect(center=(cx, at(y))))
        for i, card in enumerate(cards):
            start = 1.2 + 0.5 * i
            if t <= start:
                continue
            bob = math.sin(t * 1.8 + i * 1.3) * 4  # balanco na agua
            card.set_alpha(round(255 * min(1.0, (t - start) / 0.4)))
            scr.blit(card, card.get_rect(center=(round(cx + (2 * i - 1) * 155 * u), at(272 + (1 - grow(start, 0.8)) * 60 + bob))))
        fade = max(0.0, 1 - t / 0.5, t - (THANKS_TIME - 1))  # entra e sai pelo preto
        if fade > 0:
            veil = pygame.Surface((W, H))
            veil.set_alpha(round(255 * min(1.0, fade)))
            scr.blit(veil, (0, 0))

    def build_thanks(self):
        """Textos e cartoes do agradecimento, na escala thanks_scale: cada
        cartao tem a foto redonda com borda de adesivo (contorno escuro, aro
        claro e relevo embaixo), nome e funcao. Os circulos sao desenhados em
        2x e reduzidos, para a borda ficar lisa."""
        ink, light = (20, 19, 24), (245, 250, 252)
        u, s = self.thanks_scale, 2

        def font(name, size):
            return pygame.font.Font(os.path.join(ASSETS_DIR, "fonts", name), round(size * u))

        def sticker(msg, f, depth, **colors):
            return self.sticker(msg, f, depth=round(depth * u), r=max(2, round(2 * u)), **colors)

        title = sticker("OBRIGADO!", font("Creepster-Regular.ttf", 64), 4)
        sub = sticker("POR JOGAR ZERO OIL", font("Rubik-Bold.ttf", 17), 2)
        team = sticker(CREDITS_TEAM, font("Creepster-Regular.ttf", 30), 3)
        name_font, role_font = font("Rubik-Bold.ttf", 22), font("Rubik-Bold.ttf", 13)
        r = round(THANKS_PHOTO_R * u)

        def px(v):  # medida do desenho de 640 x 480 -> px na escala, ja em 2x
            return round(v * u * s)

        cards = []
        for file, name, role in THANKS:
            fw, fh = 2 * r * s + px(22), 2 * r * s + px(28)
            frame = pygame.Surface((fw, fh), pygame.SRCALPHA)
            c = (fw // 2, r * s + px(11))
            pygame.draw.circle(frame, ink, (c[0], c[1] + px(5)), r * s + px(11))  # relevo
            pygame.draw.circle(frame, ink, c, r * s + px(11))
            pygame.draw.circle(frame, light, c, r * s + px(8))
            pygame.draw.circle(frame, ink, c, r * s + px(3))
            photo = pygame.transform.smoothscale(load_image(file), (2 * r * s, 2 * r * s)).convert_alpha()
            mask = pygame.Surface(photo.get_size(), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255), (r * s, r * s), r * s)
            photo.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)  # so o circulo
            frame.blit(photo, (c[0] - r * s, c[1] - r * s))
            frame = pygame.transform.smoothscale(frame, (fw // s, fh // s))
            name_img = sticker(name, name_font, 3)
            role_img = sticker(role, role_font, 1, ink=light, line=ink)
            rows = ((frame, 0), (name_img, round(6 * u)), (role_img, round(4 * u)))
            card = pygame.Surface((max(img.get_width() for img, _ in rows),
                                   sum(img.get_height() + gap for img, gap in rows)), pygame.SRCALPHA)
            y = 0
            for img, gap in rows:
                y += gap
                card.blit(img, img.get_rect(midtop=(card.get_width() // 2, y)))
                y += img.get_height()
            cards.append(card)
        return title, sub, team, cards

    def controls(self):
        """Controles mostrados (os mesmos no console TTEA: o Espaco tambem pula)."""
        return CONTROLS

    def draw_controls(self, cx, y, step):
        """Lista de controles centrada em cx a partir de y: em cada linha as
        teclas desenhadas e, ao lado, o que elas fazem."""
        scr = self.screen
        keys_x, text_x = cx - 85, cx - 15  # meio das teclas, comeco do texto
        for keys, action, _ in self.controls():
            caps = [self.keycap(k) for k in keys]
            w = sum(c.get_width() for c in caps) + 6 * (len(caps) - 1)
            x = keys_x - w // 2
            for cap in caps:
                scr.blit(cap, cap.get_rect(midleft=(x, y)))
                x += cap.get_width() + 6
            img = self.sticker(action, self.record_font)
            scr.blit(img, img.get_rect(midleft=(text_x, y)))
            y += step

    def keycap(self, key):
        """Desenho de uma tecla no estilo dos botoes do menu: face clara, contorno
        escuro e relevo embaixo, com uma seta ou o texto da tecla. Guardado pronto."""
        cache_key = ("keycap", key)
        if cache_key not in self.sticker_cache:
            ink, face, side = (20, 19, 24), (245, 250, 252), (160, 178, 190)
            h, depth, line = 36, 5, 2
            label = None
            if key == "space":
                w = 120
            elif key in ("left", "right", "up", "down"):
                w = h
            else:
                label = self.record_font.render(key, True, ink)
                w = max(h, label.get_width() + 22)
            img = pygame.Surface((w, h + depth), pygame.SRCALPHA)
            pygame.draw.rect(img, ink, (0, 0, w, h + depth), border_radius=8)  # contorno
            pygame.draw.rect(img, side, (line, line, w - 2 * line, h + depth - 2 * line), border_radius=6)
            top = pygame.Rect(line, line, w - 2 * line, h - 2 * line)
            pygame.draw.rect(img, face, top, border_radius=6)
            cx, cy = top.center
            if label is not None:
                img.blit(label, label.get_rect(center=(cx, cy + 1)))
            elif key != "space":
                a = {"up": 0, "right": 90, "down": 180, "left": 270}[key]
                pts = [(0, -8), (8, 5), (-8, 5)]  # triangulo apontando para cima
                c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
                pygame.draw.polygon(img, ink, [(cx + px * c - py * s_, cy + px * s_ + py * c) for px, py in pts])
            self.sticker_cache[cache_key] = img
        return self.sticker_cache[cache_key]

    def build_credits(self):
        """Monta os creditos numa imagem alta (para rolar) e a mascara que
        apaga o texto suavemente no topo e na base da faixa."""
        max_w = 2 * (BASE_W - MENU_X) - 24  # largura da coluna, sem encostar na borda
        rows = [(self.sticker(CREDITS_TEAM, self.credit_team_font, depth=3), 0)]
        for head, lines in CREDITS:
            # titulo da secao com as cores invertidas, para separar dos nomes
            rows.append((self.sticker(head, self.credit_head_font, ink=(245, 250, 252), line=(20, 19, 24), depth=1), 30))
            for line in lines:
                rows.append((self.sticker(line, self.record_font), 2))
        fitted = []
        for img, gap in rows:
            if img.get_width() > max_w:  # linha comprida: encolhe para caber
                k = max_w / img.get_width()
                img = pygame.transform.smoothscale(img, (int(img.get_width() * k), int(img.get_height() * k)))
            fitted.append((img, gap))
        out = pygame.Surface((max_w, sum(i.get_height() + g for i, g in fitted)), pygame.SRCALPHA)
        y = 0
        for img, gap in fitted:
            y += gap
            out.blit(img, img.get_rect(midtop=(max_w // 2, y)))
            y += img.get_height()
        view_h = CREDITS_VIEW[1] - CREDITS_VIEW[0]
        fade = pygame.Surface((max_w, view_h), pygame.SRCALPHA)
        edge = 28
        for row in range(view_h):
            a = min(255, 255 * min(row, view_h - 1 - row) // edge)
            fade.fill((255, 255, 255, a), (0, row, max_w, 1))
        return out, fade

    def sticker(self, msg, font, ink=(20, 19, 24), line=(245, 250, 252), depth=2, r=2):
        """Texto no estilo do titulo: letra de uma cor com contorno (r px, com
        relevo descendo) de outra. Guardado pronto, porque quase nunca muda."""
        key = (msg, font, ink, line, depth, r)
        if key not in self.sticker_cache:
            front = font.render(msg, True, ink)
            back = font.render(msg, True, line)
            img = pygame.Surface((front.get_width() + 2 * r, front.get_height() + 2 * r + depth), pygame.SRCALPHA)
            for d in range(depth, -1, -1):  # contorno (com relevo descendo)
                for i in range(16):
                    a = i * math.tau / 16
                    img.blit(back, (r + round(math.cos(a) * r), r + round(math.sin(a) * r) + d))
            img.blit(front, (r, r))
            self.sticker_cache[key] = img
        return self.sticker_cache[key]

    def draw(self):
        self.draw_screen()
        if self.feet:
            self.draw_panel()
            self.draw_feet()
        self.panel.draw(self.screen)

    def draw_screen(self):
        scr = self.screen
        if self.mode == "menu":
            self.draw_menu()
            return
        if self.mode == "credits":
            self.draw_credits()
            return
        if self.mode == "thanks":
            self.draw_thanks()
            return
        if self.mode == "sound":
            self.draw_sound()
            return
        if self.mode in ("game", "pause", "gameover"):
            # comeco da corrida (rio 1 esperando a primeira tecla): mostra os controles
            # (no console as marcacoes do chao ja mostram os controles)
            help_ = self.mode == "game" and self.game.waiting and self.game.river == 1
            self.game.paused = self.mode == "pause" or help_  # o aviso do centro sai (vai embaixo dos controles)
            self.game.draw()
            if self.mode == "pause":
                self.draw_pause()
            elif help_:
                self.draw_feet_help() if self.feet else self.draw_start_help()
            elif self.mode == "gameover":
                self.buttons = []
                for i, label in enumerate(self.GAMEOVER):
                    step = 58 if not self.feet else self.button_layout()[1]
                    self.buttons.append(self.draw_menu_button(label, (W // 2, H // 2 + 50 + i * step), i == self.sel))

window = None  # janela comum (fora do TTEA), para a tela OPÇÕES mudar o tamanho


def resolutions():
    """Resolucoes da tela OPÇÕES: a do desenho (W x H, sem ampliar) e as maiores
    na mesma proporcao, ate a do monitor."""
    dw, dh = pygame.display.get_desktop_sizes()[0]
    sizes = [(W, H)] + [(round(h * W / H), h) for h in RESOLUTION_HEIGHTS
                        if h > H and round(h * W / H) <= dw and h <= dh]
    return ["%d x %d" % size for size in sizes]


def current_resolution():
    return config["resolucao"] or resolutions()[0]


def apply_window():
    """Janela como na tela OPÇÕES: do tamanho da resolucao, no meio da tela
    (maximizada, se nao couber), ou em tela cheia com o monitor nessa
    resolucao (o SDL usa o modo de video mais proximo do tamanho da janela).
    O pygame amplia o desenho."""
    window.set_windowed()
    window.restore()  # sai do maximizado
    size = tuple(int(v) for v in current_resolution().split(" x "))
    window.size = size
    free_scaling()
    dw, dh = pygame.display.get_desktop_sizes()[0]
    if config["tela_cheia"]:
        window.set_fullscreen(desktop=False)
    elif size[0] > dw * WINDOW_FILL or size[1] > dh * WINDOW_FILL:
        window.maximize()
    else:
        window.position = pygame.WINDOWPOS_CENTERED


def free_scaling():
    """O pygame (SCALED) so amplia a janela em multiplos inteiros do desenho: num
    tamanho no meio (1600 x 900 para 1191 x 670) ele fica em 1x, com borda
    preta. Liga a ampliacao livre direto no SDL do pygame; sem achar o SDL,
    fica a borda."""
    try:
        import ctypes
        import glob
        base = os.path.dirname(pygame.__file__)
        lib = (glob.glob(os.path.join(base, "SDL2.dll")) + glob.glob(os.path.join(base, ".dylibs", "libSDL2-*"))
               + glob.glob(os.path.join(os.path.dirname(base), "pygame_ce.libs", "libSDL2-*")))[0]
        sdl = ctypes.CDLL(lib)
        sdl.SDL_GetWindowFromID.restype = ctypes.c_void_p
        sdl.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
        sdl.SDL_GetRenderer.restype = ctypes.c_void_p
        sdl.SDL_GetRenderer.argtypes = [ctypes.c_void_p]
        sdl.SDL_RenderSetIntegerScale.argtypes = [ctypes.c_void_p, ctypes.c_int]
        renderer = sdl.SDL_GetRenderer(sdl.SDL_GetWindowFromID(window.id))
        if renderer:
            sdl.SDL_RenderSetIntegerScale(renderer, 0)
    except (OSError, IndexError, AttributeError):
        pass


def open_window():
    """Janela comum (fora do TTEA): o jogo e desenhado em W x H e a janela abre
    na resolucao e na tela cheia escolhidas na tela OPÇÕES (de inicio 1191 x 670,
    em janela); pode redimensionar e maximizar, e o pygame amplia o desenho. O
    mouse e convertido sozinho."""
    global window
    screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
    window_cls = getattr(pygame, "Window", None)  # pygame-ce; no pygame comum fica no _sdl2
    if window_cls is None:
        from pygame._sdl2.video import Window as window_cls
    with warnings.catch_warnings():  # from_display_module avisa que esta obsoleto, mas funciona
        warnings.simplefilter("ignore", DeprecationWarning)
        window = window_cls.from_display_module()
    if config["resolucao"] not in resolutions() + [DEFAULT_RESOLUTION]:
        config["resolucao"] = None  # monitor menor que o da ultima vez: a menor
    apply_window()
    return screen


def main():
    global RECORD_FILE, CONFIG_FILE
    args = console_ttea.parse_args()
    os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")  # ampliacao suave, sem serrilhado
    pygame.init()
    console = None
    if args.player_id is not None:  # aberto pelo console TTEA (veja console_ttea.py)
        console = console_ttea.Console(args)
        RECORD_FILE, CONFIG_FILE = console.record_file(), console.config_file()  # por jogador
        # o rio vai ate embaixo, por baixo das marcacoes; o barco desce junto com a tela
        set_screen_size(*console.canvas_size, console_ttea.BOAT_Y, console_ttea.CAMERA_VIEW)
        load_config()
        # simulacao: janela comum, com resolucao e tela cheia na tela OPÇÕES (o console usa a calibracao)
        screen = open_window() if args.simulate else console.open_display(pygame)
    else:  # mesma tela e camera do console, na proporcao do monitor (sem as marcacoes)
        canvas = console_ttea.canvas_for(pygame.display.get_desktop_sizes()[0])
        set_screen_size(*canvas, console_ttea.BOAT_Y, console_ttea.CAMERA_VIEW)
        load_config()  # antes da janela: ela abre na resolucao escolhida
        screen = open_window()
    pygame.display.set_caption("Zero Oil")
    init_sounds()
    clock = pygame.time.Clock()
    app = App(screen, console)
    while True:
        dt = min(clock.tick(FPS) / 1000.0, 1 / 20)
        for ev in pygame.event.get():
            app.handle_event(ev)
        app.update(dt)
        app.draw()
        pygame.display.flip()
        if console:
            console.show_preview()


if __name__ == "__main__":
    main()
