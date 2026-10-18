"""Zero Oil - Barco Catador de Lixo, em Pygame puro.

Releitura da fase especial do Sonic 3 & Knuckles: um barco limpando um rio
poluido. O jogo so desenha imagens (pasta assets/): o chao de agua e esticado em
faixas com perspectiva (estilo "Mode 7"), com as manchas, as setas do guia
e o chao da estacao pintados nele; o barco e um sprite pre-renderizado e o
resto (boias, torre...) sao imagens em pe (tudo gerado por gerar_assets.py).

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
  Seta para cima          comecar a andar
  Espaco                  pular
  R                       recomecar a corrida na hora
  Esc                     pausar (no menu principal: sair)
"""
import json
import math
import os
import random
import sys
from collections import deque

import pygame

W, H = 640, 480
FPS = 60
N = 32  # tamanho do tabuleiro (as bordas se conectam)

EMPTY, OIL, BUOY, SPOUT, TRASH, DOCK, FISH, STATION = range(8)
LITTER = (OIL, TRASH)

# --- camera e chao ------------------------------------------------------------
R = 9.0          # altura do chao no espaco 3D
CAM_H = 5.0      # altura da camera acima do jogador
CAM_B = 2.2      # distancia da camera atras do jogador
PITCH = 0.86     # inclinacao da camera para baixo (rad)
FOCAL = 520.0
Y0 = 150         # linha da tela onde fica o eixo optico
RNG = 13         # casas desenhadas em cada direcao
LIM = 13.5       # distancia maxima desenhada
WATER_PPC = 56   # pixels por casa na textura da agua
WATER_PERIOD = 4 # a textura da agua se repete a cada 4 casas
STRIP = 2        # altura (px) de cada faixa do chao na tela

CAM = (0.0, R + CAM_H, -CAM_B)
CP, SP = math.cos(PITCH), math.sin(PITCH)
PLAYER_DEPTH = CAM_H * SP + CAM_B * CP  # profundidade do jogador vista pela camera

# direcoes no sentido horario: norte, leste, sul, oeste (curvas de 90 graus).
# Para curvas de 45 graus use: [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
ND = len(DIRS)
TURN_ANGLE = math.tau / ND

SPEED_START = 4.0
SPEED_MAX = 9.0
SPEED_GAIN = 1 / 18  # casas/s ganhas por segundo de jogo
TURN_TIME = 0.24     # segundos que o barco leva para virar
TURN_SLOW = 0.55     # fracao da velocidade no centro da curva (freia antes, acelera depois)
TURN_BRAKE = 0.5     # casas antes do centro em que o barco comeca a frear para virar
TURN_RECOVER = 0.35  # segundos para voltar a velocidade toda depois de virar
MENU_X = 430            # meio do bloco do menu (titulo e botoes), a direita do barco
MENU_BOAT_ANGLE = 0     # direcao do barco do menu (graus a partir de "para cima", sentido horario)
MENU_BUTTON_FONT = ("Rubik-Bold.ttf", 19, 21)  # fonte dos botoes (normal, selecionado); outra: ("Creepster-Regular.ttf", 26, 28)
MENU_WATER_SPEED = 70   # velocidade da agua rolando no menu (px/s)
CAM_FOLLOW = 12.0   # quao rapido a camera alcanca o barco nas curvas (maior = mais colada)
ITEM_R = 0.4
STATION_SCALE = 1.65  # tamanho do modelo da estacao
DOCK_CLEAR = 2        # casas livres em volta da estacao (mais 3 na frente da vaga)
LIVES_START = 3       # barcos no inicio da corrida
BELT_TIME = 0.45      # segundos que o oleo recolhido leva para descer a esteira ate a cacamba
FISH_SCALE = 0.5      # tamanho do peixe em relacao a casa (1 = a casa toda)
LIGHT_BLINK = 0.8     # a luz em cima do barco pisca a cada 0.8 s (acesa na primeira metade)
LIVES_MAX = 5
CAPACITY = 16       # itens que cabem na cacamba
TRASH_SHARE = 0.0   # parte do lixo que e lixo boiando (0 = so manchas de oleo)

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
        "jet": 0.0 if river < 3 else min(0.3, 0.12 + 0.03 * k),     # chance de um bloco virar jato
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
        for k in (-1, 0):  # vaga: 2 casas de profundidade
            g[(C + b + sb * k + pb * w) % N][(C + a + sa * k + pa * w) % N] = DOCK
        for k in (1, 2):   # estacao: 2 casas de profundidade, logo atras da vaga
            g[(C + b + sb * k + pb * w) % N][(C + a + sa * k + pa * w) % N] = STATION
    # area livre em volta da estacao (2 casas) e na frente da vaga (mais 3): nenhum
    # bloco encosta nela, para o barco nao bater em nada quando a estacao o empurra
    zone = {((C + a + sa * k + pa * w) % N, (C + b + sb * k + pb * w) % N)
            for w in range(-1 - DOCK_CLEAR, 2 + DOCK_CLEAR)
            for k in range(-1 - DOCK_CLEAR - 3, 3 + DOCK_CLEAR)}

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
        litter = TRASH if rnd.random() < TRASH_SHARE else OIL
        for j2, row in enumerate(art):
            for i2, ch in enumerate(row):
                if ch != ".":
                    g[(by + j2) % N][(bx + i2) % N] = {"o": litter, "b": BUOY, "j": SPOUT}[ch]

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


def load_image(name, size=None):
    img = pygame.image.load(os.path.join(ASSETS_DIR, name)).convert_alpha()
    if size and img.get_size() != size:
        img = pygame.transform.smoothscale(img, size)
    return img


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


def build_strips():
    """Para cada faixa horizontal da tela, o retangulo correspondente na
    textura vista de cima (relativo ao jogador). E constante: a camera e fixa."""
    strips, reach = [], 0.0
    for y in range(0, H, STRIP):
        h = min(STRIP, H - y)
        f_top, f_bot = floor_f(y), floor_f(y + h)
        cz = CAM_H * SP + (floor_f(y + h / 2) + CAM_B) * CP
        half = (W / 2) * cz / FOCAL
        rect = pygame.Rect(round(-half * WATER_PPC), round(-f_top * WATER_PPC),
                           max(1, round(2 * half * WATER_PPC)),
                           max(1, round((f_top - f_bot) * WATER_PPC)))
        strips.append((y, h, rect))
        reach = max(reach, math.hypot(half, f_top), math.hypot(half, f_bot))
    return strips, reach


# --- jogo ---------------------------------------------------------------------
class Game:
    def __init__(self, screen, demo=False):
        self.screen = screen
        self.demo = demo  # fundo do menu: camera girando devagar, sem placar
        self.font = pygame.font.SysFont("arialblack,arial", 34, bold=True)
        self.small = pygame.font.SysFont("arial", 20, bold=True)
        self.big = pygame.font.SysFont("arialblack,arial", 56, bold=True)
        import gerar_assets  # cria a arte padrao que ainda nao existir em assets/
        if gerar_assets.missing():
            gerar_assets.generate(log=lambda msg: None)
        self.sprites = {
            BUOY: [load_image("boia.png")],
            SPOUT: [load_image("jato.png")],
            TRASH: [load_image(n) for n in ("garrafa.png", "sacola.png", "lata_vermelha.png", "lata_prateada.png")],
            FISH: [load_image("peixe.png"), load_image("peixe_nadando.png")],
        }
        self.img = {n: load_image(n + ".png") for n in (
            "feixe_luz", "onda", "sombra", "seta_guia", "painel", "bussola", "bussola_seta", "placa_contador",
            "estacao_chao", "estacao_torre", "tanque", "minimapa", "menu_painel")}
        self.slicks = [load_image("mancha_%d.png" % i) for i in range(1, 5)]
        self.boat_frames, self.boat_meta = load_group("barco.json")  # parado, ar, andando...
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
        # versoes do tamanho de 1 casa na textura da agua (onde sao pintadas)
        self.slicks_ground = [pygame.transform.smoothscale(m, (WATER_PPC, WATER_PPC)) for m in self.slicks]
        arrow = pygame.transform.smoothscale(self.img["seta_guia"], (int(WATER_PPC * 0.6),) * 2)
        self.arrows_ground = {d: pygame.transform.rotate(arrow, -90 * i) for i, d in enumerate(DIRS)}
        tile = (WATER_PPC * WATER_PERIOD,) * 2
        self.water_clean = load_image("agua_limpa.png", tile)
        self.water_dirty = load_image("agua_poluida.png", tile)
        self.water_tiles = {}
        self.strips, reach = build_strips()
        size = 2 * int(reach * WATER_PPC) + 8
        self.water_buf = pygame.Surface((size, size))
        self.ground = project(surface_point(0, 0))           # onde o barco encosta na agua
        self.cache = {}      # sprites pequenos redimensionados
        self.big_cache = {}  # quadros grandes (barco no ar, estacao) redimensionados
        self.minimap = pygame.Surface((N, N))  # 1 pixel por casa (ampliado na tela)
        self.map_arrow = pygame.transform.smoothscale(self.img["bussola_seta"], (14, 14))
        self.fonts = {}
        self.reset_run()
        if demo:  # fundo do menu: um rio mais cheio
            self.river = 5
            self.reset_level()

    # ---- estado ----
    def reset_run(self):
        """Nova corrida: rio 1, 3 barcos, 0 pontos e rios novos (seed novo)."""
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
        self.litter_left = self.litter_total = sum(row.count(OIL) + row.count(TRASH) for row in self.grid)
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
        self.guide = []          # casas do caminho ate a descarga
        self.guide_turn = None   # -1 esquerda, 0 em frente, 1 direita (na proxima casa)
        self.guide_target = None
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
        self.play_time = 0.0
        self.river_time = 0.0  # tempo andando neste rio (para o bonus de rapidez)
        self.combo = 0
        self.anim = 0.0
        self.state = "play"
        self.state_timer = 0.0
        self.clear_bonus = 0
        self.extra_life = False
        self.message = "RIO %d" % self.river if self.river > 1 else "RIO 1  ·  LIMPE O ÓLEO!"
        self.fail_msg = ""
        self.msg_timer = 1.6

    @property
    def speed(self):
        """Comeca mais rapido e chega mais longe a cada rio; acelera com o tempo."""
        start = min(7.0, SPEED_START + 0.35 * (self.river - 1))
        top = min(11.0, SPEED_MAX + 0.25 * (self.river - 1))
        return min(top, start + self.play_time * SPEED_GAIN)

    # ---- pontos, barcos e fim da corrida ----
    def add_points(self, pts, label=None, color=(255, 235, 120)):
        self.score += pts
        if label:
            self.popups.append([label, 0.0, color])

    def crash(self, msg):
        self.lives -= 1
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

    def river_clear(self):
        quick = max(0, int(60 + 15 * self.river - self.river_time))  # segundos abaixo do tempo-alvo
        self.clear_bonus = 100 * self.river + quick * 5
        self.score += self.clear_bonus
        self.extra_life = self.river % 3 == 0 and self.lives < LIVES_MAX
        if self.extra_life:
            self.lives += 1
        self.state, self.state_timer = "clear", 2.8

    def height(self):
        if not self.air:
            return 0.0
        t = min(1.0, self.air_dist / self.jump_len)
        return math.sin(math.pi * t) * self.jump_h

    def rem_to_center(self):
        dx, dy = DIRS[self.dir]
        t = self.px * dx if dx else self.py * dy  # progresso em casas (vale para diagonais)
        frac = t - math.floor(t)
        return 1.0 - frac if frac > 1e-9 else 1.0

    def at_center(self):
        return abs(self.px - round(self.px)) < 1e-9 and abs(self.py - round(self.py)) < 1e-9

    def start_turn(self, delta):
        self.dir = (self.dir + delta) % ND
        self.turn_from = self.heading
        self.turn_to = self.heading + delta * TURN_ANGLE
        self.turn_t = 0.0

    def start_jump(self, length, height):
        self.air = True
        self.air_dist = 0.0
        self.jump_len = length
        self.jump_h = height

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
        blocked = (BUOY, SPOUT, FISH, STATION)

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

    def nearest_dock(self, x, y):
        best, best_d = None, 1e9
        for cy in range(N):
            for cx in range(N):
                if self.grid[cy][cx] == DOCK:
                    dx = (cx - x + N // 2) % N - N // 2
                    dy = (cy - y + N // 2) % N - N // 2
                    if abs(dx) + abs(dy) < best_d:
                        best, best_d = (cx, cy), abs(dx) + abs(dy)
        return best

    def update_guide(self):
        """Caminho mais curto ate uma descarga, respeitando como o barco anda:
        sem dar re e so virando nos centros das casas; desvia de boias, pneus
        e jatos. Comeca na proxima casa (a decisao desta casa ja foi tomada)."""
        self.guide, self.guide_turn, self.guide_target = [], None, None
        if self.state != "play" or not self.need_unload:
            return
        x, y = round(self.px) % N, round(self.py) % N
        self.guide_target = self.nearest_dock(x, y)
        mi = self.dir
        sx, sy = (x + DIRS[mi][0]) % N, (y + DIRS[mi][1]) % N
        blocked = (BUOY, SPOUT, FISH, STATION)
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
        self.guide_target = self.guide[-1]
        if len(path) > 1:
            nd = path[1][2]
            self.guide_turn = 0 if nd == mi else 1 if nd == (mi + 1) % ND else -1
        else:
            self.guide_turn = 0

    def pollution(self):
        return max(0, self.litter_left) / max(1, self.litter_total)

    def on_center(self):
        self.arrive()
        self.update_guide()

    def arrive(self):
        x, y = int(self.px), int(self.py)
        cell = self.grid[y][x]
        if self.air:
            if self.air_dist < self.jump_len - 1e-6:
                return
            self.air = False
        collected = False
        if cell in LITTER:
            if self.load < CAPACITY:  # cheia: passa por cima sem recolher
                self.grid[y][x] = FISH  # o peixe que estava preso no oleo fica livre
                self.litter_left -= 1
                self.load += 1
                self.belt.append(0.0)  # desce a esteira ate a cacamba
                collected = True
                self.combo += 1  # manchas seguidas, sem pular nenhuma casa
                pts = 10 * min(self.combo, 5)
                self.add_points(pts, "+%d" % pts)
        if not collected:
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
                self.flash("ÓLEO DESCARREGADO!", 1.0)
        elif cell == BUOY:
            self.crash("BATEU NO CONE!")
            return
        elif cell == FISH:
            self.crash("ATROPELOU UM PEIXE!")
            return
        elif cell == SPOUT:
            self.start_jump(6.0, 3.5)
        if not self.air:
            keys = pygame.key.get_pressed()
            turn = self.queued or (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT])
            if turn:
                self.queued = 0
                self.start_turn(turn)
                return
            self.check_station()

    def check_station(self):
        """A estacao nao machuca: se o barco vai entrar nela, ela empurra o
        barco de volta (meia-volta, igual ao antigo pneu)."""
        dx, dy = DIRS[self.dir]
        x, y = round(self.px) % N, round(self.py) % N
        if self.grid[(y + dy) % N][(x + dx) % N] == STATION:
            self.start_turn(ND // 2)
            return True
        return False

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
        if ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.queued = -1 if ev.key == pygame.K_LEFT else 1
        elif ev.key == pygame.K_UP:
            self.moving = True
        elif ev.key == pygame.K_SPACE and not self.air:
            self.moving = True
            rem = self.rem_to_center()
            self.start_jump(rem + (1.0 if rem > 0.5 else 2.0), 1.4)

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
        if self.state != "play":
            return
        self.follow_camera(dt)
        if self.turn_t >= 0:
            self.turn_t += dt / TURN_TIME
            if self.turn_t >= 1:
                self.heading = self.turn_to
                self.turn_t = -1.0
                self.since_turn = 0.0
                if not self.check_station():  # virou de frente para a estacao
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
        if not self.air:
            keys = pygame.key.get_pressed()
            if self.queued or keys[pygame.K_RIGHT] != keys[pygame.K_LEFT]:
                before = smooth(self.rem_to_center() / TURN_BRAKE)
        return TURN_SLOW + (1 - TURN_SLOW) * min(after, before)

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
        n = 2 * RNG + 1
        lim2 = LIM * LIM


        # objetos + jogador + estacao, do mais distante para o mais proximo
        objs = []
        for tj in range(n):
            cy = ipy - RNG + tj
            grow = self.grid[cy % N]
            for ti in range(n):
                cx = ipx - RNG + ti
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

        if not self.demo:
            self.draw_hud()

    def station_parts(self, fx, fy, rx, ry):
        """Pecas em pe da estacao: torre de reciclagem e dois tambores (todos
        cilindros, iguais de qualquer lado), o feixe de luz e o contador."""
        if self.dock_pos is None:
            return []
        scr = self.screen
        side = self.dock_side
        perp = (-side[1], side[0])
        parts = []

        def place(a, b):  # (a casas para o lado da estacao, b para o lado) -> camera
            gx = self.dock_pos[0] + side[0] * a + perp[0] * b
            gy = self.dock_pos[1] + side[1] * a + perp[1] * b
            ox = (gx - self.px + N / 2) % N - N / 2
            oy = (gy - self.py + N / 2) % N - N / 2
            l, f = ox * rx + oy * ry, ox * fx + oy * fy
            if l * l + f * f > (LIM + 2) ** 2:
                return None
            p = project(surface_point(l, f))
            # entre a camera e o barco (ex.: logo depois da estacao empurrar o barco),
            # as pecas em pe cobririam a tela: nao desenha
            return (l, f, p) if p and p[2] > PLAYER_DEPTH else None

        def standing(img, a, b, width):
            spot = place(a, b)
            if spot is None:
                return None
            l, f, p = spot
            w = max(2, round(width * FOCAL / p[2]))
            h = max(2, round(w * img.get_height() / img.get_width()))
            if w > W or h > 2 * H:
                return None

            def draw():
                scr.blit(self.scaled(("pe", id(img)), img, w, h), (round(p[0] - w / 2), round(p[1] - h * 0.97)))
            parts.append((p[2], draw))
            return l, f, p, h

        tower = standing(self.img["estacao_torre"], 1.5, 0.0, 1.0)
        standing(self.img["tanque"], 1.9, -1.0, 0.36)
        standing(self.img["tanque"], 1.9, 1.0, 0.36)
        if tower is None:
            return [(d, "fn", fn, 0, 0, 0, 0) for d, fn in parts]
        l, f, p, th = tower
        top_y = p[1] - th * 0.95

        def beam():
            sz = 2 * ITEM_R * FOCAL / p[2]
            bw, bh = int(sz * 1.1), int(sz * 7)
            scr.blit(self.scaled(("feixe",), self.img["feixe_luz"], bw, bh), (p[0] - bw / 2, top_y - bh))
        if self.need_unload:
            parts.append((p[2] + 0.01, beam))

        def counter():
            size = max(10, min(32, int(0.5 * FOCAL / p[2])))
            font = self.fonts.get(size)
            if font is None:
                font = self.fonts[size] = pygame.font.SysFont("arialblack,arial", size, bold=True)
            txt = font.render(str(self.delivered), True, (60, 40, 30))
            bw, bh = int(txt.get_width() + size * 1.9), int(size * 1.35)
            plate = self.scaled(("placa",), self.img["placa_contador"], bw, bh)
            rect = plate.get_rect(midbottom=(p[0], top_y - size * 0.4))
            scr.blit(plate, rect)
            scr.blit(txt, txt.get_rect(midright=(rect.right - size * 0.4, rect.centery)))
        parts.append((p[2] - 0.02, counter))
        return [(d, "fn", fn, 0, 0, 0, 0) for d, fn in parts]

    def draw_item(self, kind, x, y, size, cx, cy):
        scr = self.screen
        s = max(4, int(size))
        seed = cx * 7 + cy * 13
        t = self.anim
        ripple = self.img["onda"]
        if kind == SPOUT:
            h = int(s * 1.5 * (1.0 + 0.12 * math.sin(t * 9 + seed)))
            scr.blit(self.item_sprite(SPOUT, 0, s, h), (x - s / 2, y - h + s * 0.12))
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
                        scr.blit(self.scaled(("onda",), ripple, rw, rh), (ex - rw / 2, y - rh / 2))
                scr.blit(img, img.get_rect(center=(hx, hy)))
            else:
                sx = x + math.sin(t * 2 + seed) * s * 0.15
                rw, rh = int(s * 0.45), int(s * 0.12)
                scr.blit(self.scaled(("onda",), ripple, rw, rh), (sx - rw / 2, y - rh / 2))
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
        scr.blit(self.scaled(("onda",), ripple, rw, rh), (x - rw / 2, y - rh / 2 + bob))
        scr.blit(img, (x - s / 2, y - s + sink + bob), area=pygame.Rect(0, 0, s, s - sink))

    def paint_ground(self, buf):
        """Pinta na textura da agua (vista de cima, antes de girar e esticar):
        as manchas, o chao da estacao e as setas do guia. Assim eles ganham a
        perspectiva e o giro da agua de graca."""
        size = buf.get_width()
        half = size / 2

        def at(gx, gy):  # casa do mapa -> pixel na textura (com o mapa dando a volta)
            dx = (gx - self.px + N / 2) % N - N / 2
            dy = (gy - self.py + N / 2) % N - N / 2
            return half + dx * WATER_PPC, half + dy * WATER_PPC

        r = int(half / WATER_PPC) + 1
        ipx, ipy = round(self.px), round(self.py)
        c = WATER_PPC / 2
        for cy in range(ipy - r, ipy + r + 1):
            row = self.grid[cy % N]
            for cx in range(ipx - r, ipx + r + 1):
                if row[cx % N] == OIL:
                    x, y = at(cx, cy)
                    v = ((cx % N) * 7 + (cy % N) * 13) % len(self.slicks_ground)
                    buf.blit(self.slicks_ground[v], (x - c, y - c))
        if self.dock_pos:
            sx, sy = self.dock_side
            x, y = at(self.dock_pos[0] + sx * 0.5, self.dock_pos[1] + sy * 0.5)
            floor = self.station_floor
            buf.blit(floor, (x - floor.get_width() / 2, y - floor.get_height() / 2))
        path = self.guide
        for i in range(min(len(path) - 1, 18)):
            (ax, ay), (bx, by) = path[i], path[i + 1]
            d = ((bx - ax + N // 2) % N - N // 2, (by - ay + N // 2) % N - N // 2)
            img = self.arrows_ground.get(d)
            if img is None:
                continue
            x, y = at(ax + d[0] * 0.5, ay + d[1] * 0.5)
            img.set_alpha(int(150 + 105 * (0.5 + 0.5 * math.sin(self.anim * 6 - i * 0.6))))
            buf.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))

    def draw_water(self):
        """Chao estilo "Mode 7": monta a agua vista de cima ao redor do jogador,
        gira conforme a direcao e estica cada faixa horizontal na tela."""
        buf = self.water_buf
        size = buf.get_width()
        level = round(self.pollution() * 24)
        tile = self.water_tiles.get(level)
        if tile is None:
            tile = self.water_clean.copy()
            dirty = self.water_dirty.copy()
            dirty.set_alpha(int(255 * level / 24))
            tile.blit(dirty, (0, 0))
            self.water_tiles[level] = tile
        tw = tile.get_width()
        drift = self.anim * 0.15  # correnteza lenta
        ox = int((self.px + drift) * WATER_PPC - size / 2) % tw
        oy = int((self.py + drift * 0.6) * WATER_PPC - size / 2) % tw
        for y in range(-oy, size, tw):
            for x in range(-ox, size, tw):
                buf.blit(tile, (x, y))
        self.paint_ground(buf)
        ang = math.degrees(self.view)
        if self.view == self.heading and self.turn_t < 0 and not self.demo:  # camera parada: angulo exato
            step = math.degrees(TURN_ANGLE)
            ang = round(ang / step) * step
        rot = pygame.transform.rotate(buf, ang) if ang % 360 else buf
        cx, cy = rot.get_width() // 2, rot.get_height() // 2
        scr = self.screen
        for y, h, rect in self.strips:
            strip = rot.subsurface(rect.move(cx, cy))
            scr.blit(pygame.transform.scale(strip, (W, h)), (0, y))

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
            k = PLAYER_DEPTH / q[2]  # mais perto da camera = maior (tamanho exato: sem tremer)
            w, h = round(frame.get_width() * k), round(frame.get_height() * k)
            img = pygame.transform.smoothscale(frame, (w, h))  # muda a cada quadro (luz, cacamba)
            scr.blit(img, (round(q[0] - ax * w / frame.get_width()), round(q[1] - ay * h / frame.get_height())))
        else:
            bob = math.sin(self.anim * 3.1) * 2.5
            scr.blit(frame, (gx - ax, gy - ay + bob))

    def text(self, msg, font, center, color=(255, 255, 255)):
        img = font.render(msg, True, color)
        shadow = font.render(msg, True, (0, 0, 60))
        rect = img.get_rect(center=center)
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
            self.screen.blit(shadow, rect.move(ox, oy))
        self.screen.blit(img, rect)

    def draw_hud(self):
        scr = self.screen
        if self.state == "gameover":
            self.draw_gameover()
            return
        scr.blit(self.img["painel"], (40, 18))
        self.text(f"{max(0, self.litter_left):03d}", self.font, (100, 41))
        scr.blit(self.scaled(("mancha", 0), self.slicks[0], 38, 30), (157, 26))
        boat = self.boat_frames[0]
        boat = boat.subsurface(boat.get_bounding_rect())  # so o barco, sem a margem da espuma
        icon = self.scaled(("vida",), boat, round(26 * boat.get_width() / boat.get_height()), 26)
        for i in range(self.lives):  # barcos restantes
            scr.blit(icon, (46 + i * (icon.get_width() + 6), 68))
        # pontos e recorde
        scr.blit(self.img["painel"], (W - 200, 18))
        self.text(f"{self.score}", self.font, (W - 120, 41), (255, 230, 120))
        best = max(self.best["pontos"], self.score)
        self.text(f"RECORDE {best}", self.small, (W - 120, 78), (220, 235, 245))
        self.text(f"RIO {self.river}", self.small, (W // 2, 30))
        if self.state == "play" and self.need_unload:
            self.draw_compass()
        if self.state != "gameover":
            self.draw_minimap()
        if self.state == "play" and self.combo >= 2:
            self.text("COMBO x%d" % min(self.combo, 5), self.small, (W // 2, 116), (255, 200, 80))
        for label, age, color in self.popups:  # "+10" subindo acima do barco
            img = self.small.render(label, True, color)
            img.set_alpha(int(255 * min(1.0, 2.2 - 2 * age)))
            scr.blit(img, img.get_rect(center=(self.ground[0], self.ground[1] - 140 - age * 45)))

        if self.state == "clear":
            self.text("RIO %d LIMPO!" % self.river, self.font, (W // 2, 160), (190, 255, 160))
            self.text("bônus +%d" % self.clear_bonus, self.small, (W // 2, 200), (255, 230, 120))
            if self.extra_life:
                self.text("+1 BARCO!", self.small, (W // 2, 228), (150, 255, 170))
        elif self.state == "fail":
            self.text(self.fail_msg, self.font, (W // 2, 160), (255, 120, 120))
            left = "último barco!" if self.lives == 1 else "restam %d barcos" % self.lives
            self.text("-1 barco  ·  " + left, self.small, (W // 2, 200))
        elif self.msg_timer > 0:
            self.text(self.message, self.font, (W // 2, 170))

    MAP_COLORS = {OIL: (25, 25, 20), TRASH: (25, 25, 20), FISH: (255, 140, 30), BUOY: (235, 45, 45),
                  SPOUT: (215, 245, 255), DOCK: (255, 215, 60), STATION: (90, 205, 95)}

    def draw_minimap(self):
        """Mapa do rio inteiro no canto: centrado no barco (o rio da a volta nas
        bordas) e girado junto com a camera (para cima = para frente)."""
        m = self.minimap
        m.fill((25, 95, 135) if self.pollution() < 0.5 else (60, 80, 55))
        x0, y0 = round(self.px) - N // 2, round(self.py) - N // 2
        colors = self.MAP_COLORS
        for y in range(N):
            row = self.grid[(y0 + y) % N]
            for x in range(N):
                c = row[(x0 + x) % N]
                if c:
                    m.set_at((x, y), colors[c])
        if self.need_unload:  # caminho do guia ate a estacao
            for gx, gy in self.guide[1:]:
                m.set_at(((gx - x0) % N, (gy - y0) % N), (255, 245, 170))
        size = 96
        big = pygame.transform.scale(m, (size, size))
        rot = pygame.transform.rotate(big, math.degrees(self.view))
        area = pygame.Rect(0, 0, size, size)
        area.center = rot.get_rect().center
        frame = self.img["minimapa"]
        x, y = W - frame.get_width() - 10, H - frame.get_height() - 10
        self.screen.blit(frame, (x, y))
        self.screen.blit(rot, (x + 6, y + 6), area=area)
        center = (x + 6 + size // 2 + 1, y + 6 + size // 2 + 1)
        self.screen.blit(self.map_arrow, self.map_arrow.get_rect(center=center))

    def draw_gameover(self):
        """Fim da corrida: so o essencial, num painel central sobre o jogo escurecido."""
        scr = self.screen
        shade_ = pygame.Surface((W, H), pygame.SRCALPHA)
        shade_.fill((0, 15, 30, 205))
        scr.blit(shade_, (0, 0))
        panel = self.scaled(("painel_fim",), self.img["menu_painel"], 380, 300)
        rect = panel.get_rect(center=(W // 2, H // 2))
        scr.blit(panel, rect)
        cx, top = W // 2, rect.top
        self.text("FIM DA CORRIDA", self.font, (cx, top + 42))
        self.text(str(self.score), self.big, (cx, top + 112), (255, 230, 120))
        self.text("pontos  ·  rio %d" % self.river, self.small, (cx, top + 158), (220, 235, 245))
        if self.new_record:
            self.text("NOVO RECORDE!", self.small, (cx, top + 192), (150, 255, 170))
        else:
            self.text("recorde %d" % self.best["pontos"], self.small, (cx, top + 192), (160, 180, 195))
        self.text("ENTER  mais uma vez", self.small, (cx, top + 238), (255, 215, 80))
        self.text("Esc  menu", self.small, (cx, top + 266), (160, 180, 195))

    def draw_compass(self):
        """Bussola pequena apontando para a descarga."""
        scr = self.screen
        target = self.guide[min(2, len(self.guide) - 1)] if self.guide else self.guide_target
        if target is None:
            return
        dx = (target[0] - self.px + N / 2) % N - N / 2
        dy = (target[1] - self.py + N / 2) % N - N / 2
        fx, fy = math.sin(self.view), -math.cos(self.view)
        rx, ry = math.cos(self.view), math.sin(self.view)
        a = math.atan2(dx * rx + dy * ry, dx * fx + dy * fy)
        center = (W // 2, 74)
        bg = self.img["bussola"]
        scr.blit(bg, bg.get_rect(center=center))
        arrow = pygame.transform.rotate(self.img["bussola_seta"], -math.degrees(a))
        scr.blit(arrow, arrow.get_rect(center=center))


# --- menu ---------------------------------------------------------------------
HOWTO = [
    ("OBJETIVO", None),
    ("Limpe um rio atrás do outro: cada rio é mais difícil que o anterior.", "txt"),
    ("A caçamba leva 16 manchas. Cheia, siga as setas até a estação.", "txt"),
    ("Cada mancha recolhida solta um peixe: não passe por cima!", "txt"),
    ("Você tem 3 barcos e ganha +1 a cada 3 rios limpos.", "txt"),
    ("PONTOS", None),
    ("manchas seguidas = combo  ·  caçamba cheia = x2  ·  rio rápido = bônus", "txt"),
    ("CONTROLES", None),
    ("← → virar   ↑ começar   Espaço pular   R recomeçar   Esc pausar", "txt"),
]


# creditos: (texto, None) = titulo de secao; (texto, "txt") = linha comum
CREDITS = [
    ("DESENVOLVIMENTO", None),
    ("Seu nome aqui", "txt"),
    ("ARTE E GAME DESIGN", None),
    ("Seu nome aqui", "txt"),
    ("FERRAMENTAS", None),
    ("Python + pygame-ce  ·  código feito com ajuda do Claude Code", "txt"),
    ("INSPIRAÇÃO", None),
    ("Blue Sphere, de Sonic 3 & Knuckles (SEGA, 1994)", "txt"),
    ("Feito para a Game Jam", "txt"),
]


class App:
    """Telas do jogo: menu principal, como jogar, partida e pausa."""

    MAIN = ["JOGAR", "COMO JOGAR", "CRÉDITOS", "SAIR"]
    PAUSE = ["CONTINUAR", "MENU PRINCIPAL"]

    def __init__(self, screen):
        self.screen = screen
        self.demo = Game(screen, demo=True)  # o rio de fundo do menu
        self.demo.msg_timer = 0
        self.game = None
        self.mode = "menu"  # menu, howto, game, pause
        self.sel = 0
        self.img = {n: load_image(n + ".png") for n in ("logo", "menu_painel", "botao", "botao_selecionado")}
        self.font = pygame.font.SysFont("arialblack,arial", 22, bold=True)
        self.title = pygame.font.SysFont("arialblack,arial", 34, bold=True)
        self.small = pygame.font.SysFont("arial", 19, bold=True)
        self.buttons = []
        # menu principal: agua rolando, barco andando na diagonal, titulo e botoes a direita
        self.menu_boat = [load_image("menu_barco_%d.png" % (i + 1)) for i in range(4)]
        self.menu_img = {n: load_image("menu_%s.png" % n) for n in ("titulo", "botao", "botao_selecionado")}
        self.menu_water = load_image("agua_limpa.png")
        name, size, size_sel = MENU_BUTTON_FONT
        font = os.path.join(ASSETS_DIR, "fonts", name)
        self.menu_font = pygame.font.Font(font, size)
        self.menu_font_sel = pygame.font.Font(font, size_sel)
        self.record_font = pygame.font.Font(os.path.join(ASSETS_DIR, "fonts", "Rubik-Bold.ttf"), 17)  # mais limpa
        self.menu_t = 0.0
        self.sticker_cache = {}

    def options(self):
        return self.MAIN if self.mode == "menu" else self.PAUSE

    def choose(self, option):
        if option == "JOGAR":
            self.game = Game(self.screen)
            self.mode = "game"
        elif option == "COMO JOGAR":
            self.mode = "howto"
        elif option == "CRÉDITOS":
            self.mode = "credits"
        elif option == "SAIR":
            pygame.quit()
            sys.exit()
        elif option == "CONTINUAR":
            self.mode = "game"
        elif option == "MENU PRINCIPAL":
            self.mode, self.sel = "menu", 0

    def handle_event(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if self.mode == "game":
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if self.game.state == "gameover":
                    self.mode, self.sel = "menu", 0
                else:
                    self.mode, self.sel = "pause", 0
            else:
                self.game.handle_event(ev)
            return
        if self.mode in ("howto", "credits"):
            if ev.type == pygame.KEYDOWN or ev.type == pygame.MOUSEBUTTONDOWN:
                self.mode = "menu"
            return
        opts = self.options()
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % len(opts)
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % len(opts)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.choose(opts[self.sel])
            elif ev.key == pygame.K_ESCAPE:
                self.choose("SAIR" if self.mode == "menu" else "CONTINUAR")
        elif ev.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.buttons):
                if rect.collidepoint(ev.pos):
                    self.sel = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, rect in enumerate(self.buttons):
                if rect.collidepoint(ev.pos):
                    self.choose(opts[i])

    def update(self, dt):
        if self.mode == "game":
            self.game.update(dt)
        elif self.mode == "menu":
            self.menu_t += dt
        elif self.mode in ("howto", "credits"):
            self.demo.update(dt)

    def text(self, msg, font, center, color=(255, 255, 255)):
        img = font.render(msg, True, color)
        shadow = font.render(msg, True, (0, 0, 60))
        rect = img.get_rect(center=center)
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
            self.screen.blit(shadow, rect.move(ox, oy))
        self.screen.blit(img, rect)

    def draw_buttons(self, top):
        self.buttons = []
        for i, label in enumerate(self.options()):
            img = self.img["botao_selecionado" if i == self.sel else "botao"]
            rect = img.get_rect(center=(W // 2, top + i * 52))
            self.screen.blit(img, rect)
            color = (70, 40, 0) if i == self.sel else (255, 255, 255)
            txt = self.font.render(label, True, color)
            if txt.get_width() > rect.w - 24:  # texto comprido: encolhe para caber no botao
                k = (rect.w - 24) / txt.get_width()
                txt = pygame.transform.smoothscale(txt, (int(txt.get_width() * k), int(txt.get_height() * k)))
            self.screen.blit(txt, txt.get_rect(center=rect.center))
            self.buttons.append(rect)

    def draw_menu(self):
        """Menu principal: a agua rola para tras do barco (que anda na direcao
        MENU_BOAT_ANGLE), o barco balanca com a espuma animada, e a direita
        ficam o titulo, os botoes e o recorde."""
        scr, t = self.screen, self.menu_t
        tile = self.menu_water
        tw, th = tile.get_size()
        a, d = math.radians(MENU_BOAT_ANGLE), MENU_WATER_SPEED * t
        ox = int(-d * math.sin(a)) % tw  # a agua anda no sentido contrario ao do barco
        oy = int(d * math.cos(a)) % th
        for y in range(oy - th, H, th):
            for x in range(ox - tw, W, tw):
                scr.blit(tile, (x, y))
        frame = self.menu_boat[int(t * 8) % len(self.menu_boat)]
        scr.blit(frame, (0, round(math.sin(t * 2.2) * 3)))  # balanco na agua
        scr.blit(self.menu_img["titulo"], self.menu_img["titulo"].get_rect(center=(MENU_X, 74)))
        self.buttons = []
        for i, label in enumerate(self.MAIN):
            sel = i == self.sel
            img = self.menu_img["botao_selecionado" if sel else "botao"]
            rect = img.get_rect(center=(MENU_X, 157 + i * 63))
            scr.blit(img, rect)
            face = rect.inflate(0, -9).move(0, -4)  # a parte de cima (sem o relevo embaixo)
            font = self.menu_font_sel if sel else self.menu_font
            txt = font.render(label, True, (20, 19, 24) if sel else (245, 250, 252))
            if txt.get_width() > face.w - 30:  # texto comprido: encolhe para caber
                k = (face.w - 30) / txt.get_width()
                txt = pygame.transform.smoothscale(txt, (int(txt.get_width() * k), int(txt.get_height() * k)))
            scr.blit(txt, txt.get_rect(center=(face.centerx, face.centery + 1)))
            self.buttons.append(rect)
        rec = load_record()
        msg = "RECORDE  %d  ·  RIO %d" % (rec["pontos"], rec["rio"]) if rec["pontos"] else "SETAS E ENTER, OU O MOUSE"
        img = self.sticker(msg, self.record_font)
        scr.blit(img, img.get_rect(center=(MENU_X, 418)))

    def sticker(self, msg, font, ink=(20, 19, 24), line=(245, 250, 252), depth=2):
        """Texto no estilo do titulo: letra de uma cor com contorno (e relevo
        descendo) de outra. Guardado pronto, porque quase nunca muda."""
        key = (msg, font, ink, line, depth)
        if key not in self.sticker_cache:
            front = font.render(msg, True, ink)
            back = font.render(msg, True, line)
            r = 2
            img = pygame.Surface((front.get_width() + 2 * r, front.get_height() + 2 * r + depth), pygame.SRCALPHA)
            for d in range(depth, -1, -1):  # contorno (com relevo descendo)
                for i in range(16):
                    a = i * math.tau / 16
                    img.blit(back, (r + round(math.cos(a) * r), r + round(math.sin(a) * r) + d))
            img.blit(front, (r, r))
            self.sticker_cache[key] = img
        return self.sticker_cache[key]

    def draw(self):
        scr = self.screen
        if self.mode == "menu":
            self.draw_menu()
            return
        if self.mode in ("game", "pause"):
            self.game.draw()
            if self.mode == "pause":
                shade_ = pygame.Surface((W, H), pygame.SRCALPHA)
                shade_.fill((0, 20, 40, 140))
                scr.blit(shade_, (0, 0))
                panel = self.img["menu_painel"]
                scr.blit(panel, panel.get_rect(center=(W // 2, H // 2 + 10)))
                self.text("PAUSADO", self.title, (W // 2, H // 2 - 60))
                self.draw_buttons(H // 2 + 5)
            return
        self.demo.draw()
        # como jogar / creditos
        shade_ = pygame.Surface((W - 60, H - 60), pygame.SRCALPHA)
        shade_.fill((8, 35, 60, 225))
        scr.blit(shade_, (30, 30))
        y = 60
        if self.mode == "credits":
            self.text("ZERO OIL", self.title, (W // 2, y), (150, 255, 200))
            y += 44
        for line, kind in (HOWTO if self.mode == "howto" else CREDITS):
            if kind is None:
                y += 8
                self.text(line, self.font, (W // 2, y), (255, 215, 80))
                y += 34
            else:
                self.text(line, self.small, (W // 2, y))
                y += 30
        self.text("aperte qualquer tecla para voltar", self.small, (W // 2, H - 52), (190, 255, 160))


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Zero Oil")
    clock = pygame.time.Clock()
    app = App(screen)
    while True:
        dt = min(clock.tick(FPS) / 1000.0, 1 / 20)
        for ev in pygame.event.get():
            app.handle_event(ev)
        app.update(dt)
        app.draw()
        pygame.display.flip()


if __name__ == "__main__":
    main()
