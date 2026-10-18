"""Gera as imagens padrao do jogo na pasta assets/.

O jogo (blue_sphere.py) so desenha imagens prontas. Este script cria a arte
padrao, de duas formas:

  * sprites simples (boia, peixe, jato, manchas, placar...), desenhados com
    as primitivas do pygame;
  * quadros do barco (de costas: parado, no ar e andando), renderizados a
    partir de um modelo 3D feito a mao (sprites pre-renderizados, como nos
    jogos antigos). Os quadros tem o mesmo tamanho, e o barco.json guarda o
    ponto de apoio (onde o barco encosta na agua).

Uso:
  python gerar_assets.py           gera so os arquivos que faltam
  python gerar_assets.py --todos   recria tudo (sobrescreve a sua arte!)
  python gerar_assets.py --barco-svg  recria os quadros do barco a partir do boat2.svg
  python gerar_assets.py --agua    recria so as texturas da agua
"""
import json
import math
import os
import random
import sys

import pygame

import blue_sphere as bs  # camera, projecao e constantes do jogo

ASSETS_DIR = bs.ASSETS_DIR
BOAT_WAKE_FRAMES = 4   # quadros da animacao do barco andando (espuma)
BOAT_SCALE = 1.45      # tamanho do barco (em casas)

# superficie grande de trabalho para os renders (nada fica cortado na borda)
CANVAS = 1600
OFS_X, OFS_Y = (CANVAS - bs.W) // 2, (CANVAS - bs.H) // 2


def shade(col, k):
    return tuple(max(0, min(255, int(c * k))) for c in col)


def proj(l, f, h=0.0):
    """Projecao do jogo, deslocada para o meio da superficie de trabalho."""
    p = bs.project(bs.surface_point(l, f, h))
    return None if p is None else (p[0] + OFS_X, p[1] + OFS_Y, p[2])


def visible_face(pts, center, cam):
    """Face virada para a camera? (normal pelo produto vetorial)"""
    a, b, c = pts[0], pts[1], pts[2]
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    m = [sum(q[i] for q in pts) / len(pts) for i in range(3)]
    out = sum(nrm[i] * (m[i] - center[i]) for i in range(3))
    to_cam = sum(nrm[i] * (cam[i] - m[i]) for i in range(3))
    return to_cam * out > 0


# --- sprites simples --------------------------------------------------------------
def _rotated(surf, angle, size=96, center=(48, 62)):
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    img = pygame.transform.rotate(surf, angle)
    out.blit(img, img.get_rect(center=center))
    return out


def make_bottle():
    s = pygame.Surface((110, 40), pygame.SRCALPHA)
    pygame.draw.rect(s, (150, 220, 190, 235), (8, 6, 72, 28), border_radius=12)
    pygame.draw.polygon(s, (150, 220, 190, 235), [(76, 9), (90, 14), (90, 26), (76, 31)])
    pygame.draw.rect(s, (30, 90, 200), (89, 12, 11, 16), border_radius=3)
    pygame.draw.rect(s, (245, 245, 245), (30, 6, 28, 28))
    pygame.draw.rect(s, (220, 40, 50), (30, 15, 28, 9))
    pygame.draw.line(s, (215, 255, 240), (14, 11), (72, 11), 3)
    pygame.draw.rect(s, (70, 130, 110), (8, 6, 72, 28), 2, border_radius=12)
    return _rotated(s, 25)


def make_bag():
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    pygame.draw.arc(s, (150, 150, 145), (34, 14, 14, 26), 0, math.pi, 3)
    pygame.draw.arc(s, (150, 150, 145), (50, 12, 14, 26), 0, math.pi, 3)
    pts = [(18, 76), (12, 58), (20, 42), (34, 44), (38, 28), (50, 34), (60, 26), (66, 42),
           (80, 46), (84, 66), (74, 80), (30, 82)]
    pygame.draw.polygon(s, (236, 236, 228, 240), pts)
    pygame.draw.polygon(s, (165, 165, 160), pts, 2)
    for a, b in (((30, 52), (42, 72)), ((52, 44), (58, 70)), ((66, 54), (72, 74))):
        pygame.draw.line(s, (195, 195, 188), a, b, 2)
    return s


def make_can(body=(205, 30, 40), stripe=(255, 255, 255), shine=(255, 120, 120), back=(120, 20, 25), angle=-15):
    s = pygame.Surface((90, 40), pygame.SRCALPHA)
    pygame.draw.rect(s, body, (8, 6, 64, 28))
    pygame.draw.line(s, stripe, (12, 24), (66, 14), 4)
    pygame.draw.line(s, shine, (10, 10), (70, 10), 2)
    pygame.draw.ellipse(s, (205, 205, 215), (62, 6, 16, 28))
    pygame.draw.ellipse(s, (150, 150, 160), (66, 11, 8, 18))
    pygame.draw.ellipse(s, back, (2, 6, 14, 28))
    return _rotated(s, angle)


def make_cylinder(w, h, color, band=None):
    """Cilindro em pe visto de lado (igual de qualquer angulo)."""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(w):
        t = x / (w - 1)
        k = 0.65 + 0.5 * math.sin(math.pi * t) - 0.25 * t  # luz vindo da esquerda
        pygame.draw.line(s, shade(color, k), (x, 4), (x, h - 1))
        if band:
            pygame.draw.line(s, shade(band, k), (x, h * 0.12), (x, h * 0.22))
    pygame.draw.ellipse(s, shade(color, 0.55), (0, 0, w, 9))
    pygame.draw.ellipse(s, (35, 36, 44), (w * 0.2, 2, w * 0.6, 5))
    return s


def make_beam():
    """Feixe de luz que marca a descarga quando a cacamba esta cheia."""
    s = pygame.Surface((32, 256), pygame.SRCALPHA)
    for y in range(256):
        for x in range(32):
            edge = 1 - abs(x - 15.5) / 16
            s.set_at((x, y), (255, 235, 110, int(150 * edge * (y / 255) ** 1.5)))
    return s


def make_fish():
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    pygame.draw.polygon(s, (235, 105, 20), [(26, 51), (6, 36), (12, 51), (6, 66)])
    pygame.draw.polygon(s, (235, 105, 20), [(38, 40), (50, 26), (60, 40)])
    pygame.draw.ellipse(s, (255, 140, 30), (22, 36, 52, 30))
    pygame.draw.ellipse(s, (255, 205, 130), (30, 52, 36, 10))
    pygame.draw.arc(s, (255, 255, 255), (36, 38, 14, 26), -1.2, 1.2, 3)
    pygame.draw.circle(s, (255, 255, 255), (62, 47), 5)
    pygame.draw.circle(s, (20, 20, 20), (63, 47), 2)
    return s


def make_fish_swim():
    """Peixe nadando debaixo d'agua: silhueta escura com a barbatana de fora."""
    s = pygame.Surface((96, 72), pygame.SRCALPHA)
    mask = pygame.mask.from_surface(make_fish())
    shadow = mask.to_surface(setcolor=(15, 35, 30, 150), unsetcolor=(0, 0, 0, 0))
    s.blit(pygame.transform.smoothscale(shadow, (96, 48)), (0, 24))
    fin = [(38, 48), (57, 48), (44, 26)]
    pygame.draw.polygon(s, (235, 105, 20), fin)
    pygame.draw.polygon(s, (120, 50, 10), fin, 1)
    return s


def make_buoy():
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    red, white = (215, 30, 30), (245, 245, 245)
    pygame.draw.ellipse(s, red, (20, 64, 56, 26))
    pygame.draw.polygon(s, red, [(26, 76), (70, 76), (62, 36), (34, 36)])
    pygame.draw.polygon(s, white, [(30, 58), (66, 58), (64, 46), (32, 46)])
    pygame.draw.polygon(s, red, [(38, 37), (58, 37), (48, 20)])
    pygame.draw.line(s, (255, 130, 130), (36, 70), (39, 40), 3)
    pygame.draw.line(s, (90, 90, 95), (48, 21), (48, 9), 3)
    pygame.draw.circle(s, (255, 230, 80), (48, 8), 5)
    pygame.draw.polygon(s, (120, 10, 10), [(26, 76), (70, 76), (62, 36), (34, 36)], 1)
    return s


def make_spout():
    s = pygame.Surface((96, 144), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (200, 235, 250, 230), (12, 122, 72, 20))
    pygame.draw.polygon(s, (205, 238, 255, 230), [(36, 134), (60, 134), (55, 40), (41, 40)])
    pygame.draw.polygon(s, (245, 252, 255, 240), [(44, 134), (52, 134), (51, 44), (45, 44)])
    for x, y, r in ((48, 34, 14), (36, 42, 10), (60, 42, 10), (42, 24, 8), (56, 26, 8)):
        pygame.draw.circle(s, (225, 246, 255, 240), (x, y), r)
    for x, y in ((26, 60), (70, 66), (22, 84), (76, 90), (30, 104), (66, 110)):
        pygame.draw.circle(s, (210, 240, 255, 220), (x, y), 3)
    return s


def make_slick(seed):
    """Mancha de oleo vista de cima. A imagem inteira equivale a 1 casa."""
    size = 128
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    rnd = random.Random(seed)
    c = size / 2
    ox, oy = rnd.uniform(-8, 8), rnd.uniform(-8, 8)
    pts = []
    for i in range(12):
        a = i * math.tau / 12
        r = rnd.uniform(0.3, 0.48) * size
        pts.append((c + ox + math.cos(a) * r, c + oy + math.sin(a) * r * 0.85))
    inner = [(c + ox + (x - c - ox) * 0.55, c + oy + (y - c - oy) * 0.55) for x, y in pts]
    pygame.draw.polygon(s, (52, 56, 40), pts)
    pygame.draw.polygon(s, (112, 92, 132), pts, 4)
    pygame.draw.polygon(s, (30, 32, 25), inner)
    return s


def make_ripple():
    """Anel de onda em volta do que boia (visto de cima)."""
    s = pygame.Surface((128, 128), pygame.SRCALPHA)
    pygame.draw.circle(s, (220, 245, 255, 210), (64, 64), 62, 7)
    pygame.draw.circle(s, (255, 255, 255, 120), (64, 64), 50, 3)
    return s


def make_shadow():
    s = pygame.Surface((128, 128), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (10, 40, 60, 110), (8, 0, 112, 128))
    return s


def make_arrow():
    """Seta do guia vista de cima, apontando para cima (para a frente)."""
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    pts = [(48, 6), (90, 70), (48, 48), (6, 70)]
    pygame.draw.polygon(s, (255, 215, 60), pts)
    pygame.draw.polygon(s, (120, 80, 0), pts, 5)
    return s


def make_panel():
    s = pygame.Surface((160, 46), pygame.SRCALPHA)
    pygame.draw.rect(s, (10, 40, 60), s.get_rect(), border_radius=8)
    pygame.draw.rect(s, (255, 255, 255), s.get_rect(), 3, border_radius=8)
    return s


def make_compass():
    s = pygame.Surface((44, 44), pygame.SRCALPHA)
    pygame.draw.circle(s, (10, 40, 60), (22, 22), 21)
    pygame.draw.circle(s, (255, 225, 80), (22, 22), 21, 2)
    return s


def make_minimap_frame():
    """Moldura do minimapa (o mapa aparece no buraco de 96x96 no meio)."""
    s = pygame.Surface((108, 108), pygame.SRCALPHA)
    pygame.draw.rect(s, (10, 40, 60), s.get_rect(), border_radius=10)
    pygame.draw.rect(s, (255, 255, 255), s.get_rect(), 3, border_radius=10)
    pygame.draw.rect(s, (0, 0, 0, 0), (6, 6, 96, 96))
    pygame.draw.rect(s, (90, 205, 95), (5, 5, 98, 98), 1)
    return s


def make_compass_arrow():
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    pts = [(16, 1), (27, 16), (20, 16), (20, 28), (12, 28), (12, 16), (5, 16)]
    pygame.draw.polygon(s, (255, 225, 80), pts)
    pygame.draw.polygon(s, (120, 80, 0), pts, 2)
    return s


def make_sign():
    """Plaquinha do contador de oleo entregue (o numero e escrito pelo jogo)."""
    s = pygame.Surface((120, 40), pygame.SRCALPHA)
    pygame.draw.rect(s, (255, 245, 220), s.get_rect(), border_radius=20)
    pygame.draw.rect(s, (215, 95, 45), s.get_rect(), 3, border_radius=20)
    pygame.draw.circle(s, (240, 180, 40), (20, 20), 10)
    return s


def draw_recycle(surf, cx, cy, r, color, width):
    """Simbolo de reciclagem: tres setas em triangulo."""
    for i in range(3):
        a0 = -math.pi / 2 + i * math.tau / 3
        a1 = a0 + math.tau / 3 * 0.75
        p0 = (cx + math.cos(a0) * r, cy + math.sin(a0) * r)
        p1 = (cx + math.cos(a1) * r, cy + math.sin(a1) * r)
        pygame.draw.line(surf, color, p0, p1, width)
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        k = width + 3
        tip = (p1[0] + math.cos(ang) * k, p1[1] + math.sin(ang) * k)
        pygame.draw.polygon(surf, color, [tip, (p1[0] + math.cos(ang + 2.2) * k, p1[1] + math.sin(ang + 2.2) * k),
                                          (p1[0] + math.cos(ang - 2.2) * k, p1[1] + math.sin(ang - 2.2) * k)])


def make_station_floor():
    """Chao da estacao visto de cima, pintado na agua pelo jogo. Ocupa 3 casas
    de largura por 4 de profundidade (56 px por casa): em cima, a plataforma
    (2 casas); embaixo, a vaga de descarga (2 casas). O lado de cima e o lado
    da estacao; o jogo gira a imagem conforme a posicao dela no mapa."""
    c = bs.WATER_PPC
    w, h = 3 * c, 4 * c
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    # plataforma
    deck = pygame.Rect(3, 3, w - 6, 2 * c - 6)
    pygame.draw.rect(s, (95, 100, 112), deck.move(0, 4), border_radius=10)  # beirada (sombra)
    pygame.draw.rect(s, (182, 187, 194), deck, border_radius=10)
    for x in range(deck.x + 14, deck.right - 6, 14):  # tabuas
        pygame.draw.line(s, (166, 171, 179), (x, deck.y + 6), (x, deck.bottom - 14), 2)
    stripe = pygame.Rect(deck.x + 6, deck.bottom - 14, deck.w - 12, 9)  # faixa de atencao na frente
    pygame.draw.rect(s, (35, 35, 40), stripe)
    for x in range(stripe.x - 9, stripe.right, 12):
        pygame.draw.polygon(s, (250, 205, 40), [(x, stripe.bottom), (x + 6, stripe.bottom),
                                                (x + 15, stripe.y), (x + 9, stripe.y)])
    pygame.draw.rect(s, (35, 35, 40), (deck.x, stripe.y, 6, 9))
    pygame.draw.rect(s, (35, 35, 40), (stripe.right, stripe.y, 6, 9))
    for x in (c // 2 + 2, w - c // 2 - 2):  # simbolos de reciclagem nos cantos da frente
        draw_recycle(s, x, int(c * 1.25), 11, (50, 160, 70), 3)
    pygame.draw.rect(s, (90, 205, 95), deck, 5, border_radius=10)
    # vaga de descarga
    zone = pygame.Rect(4, 2 * c + 4, w - 8, 2 * c - 8)
    glow = pygame.Surface(zone.size, pygame.SRCALPHA)
    glow.fill((255, 225, 80, 45))
    s.blit(glow, zone)
    pts = [zone.topleft, zone.topright, zone.bottomright, zone.bottomleft]
    for e in range(4):
        (x0, y0), (x1, y1) = pts[e], pts[(e + 1) % 4]
        segs = max(4, round(math.hypot(x1 - x0, y1 - y0) / 14))
        for k in range(segs):
            a = (x0 + (x1 - x0) * k / segs, y0 + (y1 - y0) * k / segs)
            b = (x0 + (x1 - x0) * (k + 1) / segs, y0 + (y1 - y0) * (k + 1) / segs)
            pygame.draw.line(s, (225, 40, 40) if k % 2 == 0 else (250, 250, 250), a, b, 6)
    for k in range(2):  # setas pintadas apontando para a estacao
        y = zone.y + 18 + k * 34
        pygame.draw.polygon(s, (255, 255, 255, 170), [(w // 2, y), (w // 2 + 18, y + 16), (w // 2 + 8, y + 16),
                                                     (w // 2 + 8, y + 26), (w // 2 - 8, y + 26), (w // 2 - 8, y + 16),
                                                     (w // 2 - 18, y + 16)])
    return s


def make_tower():
    """Torre de reciclagem: cilindro (igual de qualquer lado), desenhada em pe."""
    w, h = 96, 200
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    body = (55, 150, 80)
    top, bottom = 58, h - 6
    for x in range(8, w - 8):  # corpo com luz vindo da esquerda
        t = (x - 8) / (w - 17)
        k = 0.62 + 0.55 * math.sin(math.pi * t) - 0.3 * t
        pygame.draw.line(s, shade(body, k), (x, top), (x, bottom))
        pygame.draw.line(s, shade((245, 245, 240), k), (x, top + 34), (x, top + 78))  # faixa branca
        pygame.draw.line(s, shade((40, 110, 60), k), (x, bottom - 14), (x, bottom))   # base
    pygame.draw.ellipse(s, shade(body, 0.7), (8, bottom - 8, w - 16, 14))
    draw_recycle(s, w // 2, top + 56, 15, (50, 160, 70), 4)
    # telhado conico
    pygame.draw.polygon(s, (40, 110, 60), [(4, top + 4), (w - 4, top + 4), (w // 2, 14)])
    pygame.draw.polygon(s, (75, 170, 100), [(4, top + 4), (w // 2 - 6, top + 4), (w // 2, 14)])
    pygame.draw.ellipse(s, (35, 95, 50), (4, top - 2, w - 8, 12))
    # luz no topo
    pygame.draw.line(s, (80, 80, 90), (w // 2, 16), (w // 2, 4), 3)
    pygame.draw.circle(s, (255, 225, 80), (w // 2, 6), 6)
    pygame.draw.circle(s, (255, 250, 210), (w // 2 - 2, 4), 2)
    return s


def make_logo():
    """Titulo do jogo (troque por um logo desenhado se quiser)."""
    font = pygame.font.SysFont("arialblack,arial", 64, bold=True)
    sub = pygame.font.SysFont("arial", 22, bold=True)
    title = "RIO LIMPO"
    w, h = 460, 150
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    shadow = font.render(title, True, (5, 30, 60))
    for ox in range(-4, 5, 2):
        for oy in range(-4, 7, 2):
            s.blit(shadow, shadow.get_rect(center=(w // 2 + ox, 56 + oy)))
    # texto com degrade (verde agua em cima, azul embaixo)
    txt = font.render(title, True, (255, 255, 255))
    grad = pygame.Surface(txt.get_size(), pygame.SRCALPHA)
    for y in range(txt.get_height()):
        t = y / txt.get_height()
        grad.fill((int(150 - 110 * t), int(255 - 60 * t), int(170 + 70 * t), 255), (0, y, txt.get_width(), 1))
    grad.blit(txt, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(grad, grad.get_rect(center=(w // 2, 56)))
    # ondinhas embaixo do titulo
    for k, col in ((0, (120, 220, 245)), (1, (60, 170, 220))):
        pts = [(x, 104 + k * 7 + 4 * math.sin(x / 18 + k)) for x in range(60, w - 60, 4)]
        pygame.draw.lines(s, col, False, pts, 4)
    line = sub.render("o barco que limpa o rio", True, (255, 245, 200))
    s.blit(sub.render("o barco que limpa o rio", True, (5, 30, 60)), line.get_rect(center=(w // 2 + 2, 134)))
    s.blit(line, line.get_rect(center=(w // 2, 132)))
    return s


def make_menu_panel():
    s = pygame.Surface((300, 260), pygame.SRCALPHA)
    pygame.draw.rect(s, (8, 35, 60, 215), s.get_rect(), border_radius=16)
    pygame.draw.rect(s, (255, 255, 255), s.get_rect(), 3, border_radius=16)
    pygame.draw.rect(s, (90, 205, 95), s.get_rect().inflate(-10, -10), 2, border_radius=12)
    return s


def make_button(selected):
    s = pygame.Surface((240, 46), pygame.SRCALPHA)
    if selected:
        pygame.draw.rect(s, (255, 205, 60), s.get_rect(), border_radius=10)
        pygame.draw.rect(s, (255, 240, 170), s.get_rect().inflate(-8, -24).move(0, -8), border_radius=6)
        pygame.draw.rect(s, (130, 80, 10), s.get_rect(), 3, border_radius=10)
    else:
        pygame.draw.rect(s, (25, 90, 130), s.get_rect(), border_radius=10)
        pygame.draw.rect(s, (200, 230, 245), s.get_rect(), 2, border_radius=10)
    return s


WATER_COLORS = {  # (fundo em cor solida, reflexo fraco por cima)
    "clean": ((46, 150, 205), (76, 172, 220)),
    "dirty": ((84, 96, 58), (100, 113, 72)),
}


def _water_noise(size, rnd, kmin, kmax, waves):
    """Ruido suave sem emendas e igual em todas as direcoes: soma de ondas
    com direcoes sorteadas (numero inteiro de voltas por textura, para emendar)."""
    import numpy as np
    y, x = np.mgrid[0:size, 0:size] / size
    n = np.zeros((size, size))
    for _ in range(waves):
        while True:
            kx, ky = rnd.randint(-kmax, kmax), rnd.randint(-kmax, kmax)
            if kmin <= math.hypot(kx, ky) <= kmax:
                break
        n += np.cos(math.tau * (kx * x + ky * y) + rnd.uniform(0, math.tau))
    return n / np.abs(n).max()


def make_water(ppc, period):
    """Texturas de agua sem emendas (limpa e poluida): cor solida com
    reflexos largos e fracos por cima. Nada de linha fina ou forma com
    direcao: igual de qualquer angulo e sem tremer quando a camera gira.
    As duas usam o mesmo desenho, para o jogo misturar uma na outra
    conforme a poluicao."""
    import numpy as np
    size = ppc * period
    rnd = random.Random(5)
    _water_noise(size, rnd, 2, 4, 14)  # (sorteio de antes: os reflexos continuam no mesmo lugar)
    ridge = 1 - np.abs(_water_noise(size, rnd, 3, 6, 18))      # reflexos: perto de 1 nas "linhas"
    glow = np.clip((ridge - 0.78) / 0.22, 0, 1) ** 2 * 0.55  # largos e fracos
    out = []
    for name in ("clean", "dirty"):
        base, light = (np.array(c, dtype=float) for c in WATER_COLORS[name])
        img = base + glow[..., None] * (light - base)
        s = pygame.Surface((size, size))
        pygame.surfarray.blit_array(s, np.clip(img, 0, 255).astype(np.uint8).transpose(1, 0, 2))
        out.append(s)
    return tuple(out)


# --- barco (modelo 3D renderizado em varios angulos) ----------------------------
def render_boat(yaw, foam=True, wake_phase=None):
    """Desenha o barco virado 'yaw' radianos em relacao a camera.
    wake_phase (0..1) liga o rastro de espuma animado e a esteira girando."""
    surf = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    S = BOAT_SCALE
    cyaw, syaw = math.cos(yaw), math.sin(yaw)
    cam = (bs.CAM_B * syaw / S, -bs.CAM_B * cyaw / S, bs.CAM_H / S)

    def P(l, f, h):
        L, F = l * cyaw + f * syaw, -l * syaw + f * cyaw
        q = proj(L * S, F * S, h * S)
        return q[0], q[1]

    def W0(l, f):
        return P(l, f, 0.0)

    def face(pts, col):
        pygame.draw.polygon(surf, col, [P(*q) for q in pts])

    def box(l0, l1, f0, f1, h0, h1, col):
        center = ((l0 + l1) / 2, (f0 + f1) / 2, (h0 + h1) / 2)
        faces = [
            ([(l0, f0, h1), (l1, f0, h1), (l1, f1, h1), (l0, f1, h1)], 1.0),
            ([(l0, f0, h0), (l1, f0, h0), (l1, f0, h1), (l0, f0, h1)], 0.85),
            ([(l0, f1, h0), (l1, f1, h0), (l1, f1, h1), (l0, f1, h1)], 0.8),
            ([(l0, f0, h0), (l0, f1, h0), (l0, f1, h1), (l0, f0, h1)], 0.7),
            ([(l1, f0, h0), (l1, f1, h0), (l1, f1, h1), (l1, f0, h1)], 0.7),
        ]
        for pts, k in faces:
            if visible_face(pts, center, cam):
                face(pts, shade(col, k))

    hull = [(-0.3, -0.5), (0.3, -0.5), (0.32, 0.25), (0.2, 0.48), (-0.2, 0.48), (-0.32, 0.25)]
    DECK, STRIPE, BOTTOM = 0.24, 0.16, 0.0

    if foam:  # espuma em volta do casco
        pygame.draw.polygon(surf, (190, 236, 248), [W0(l * 1.15, f * 1.12) for l, f in hull])
    if wake_phase is not None:  # rastro na agua
        for side in (-1, 1):
            pts = [W0(side * (0.27 + 0.4 * s), -(0.5 + 0.8 * s)) for s in (0, 0.25, 0.5, 0.75, 1.0)]
            pygame.draw.lines(surf, (225, 248, 255), False, pts, 3)
            for i in range(6):
                s = (wake_phase + i / 6) % 1.0
                x, y = W0(side * (0.2 + 0.35 * s), -(0.5 + 0.8 * s))
                pygame.draw.circle(surf, (210, 244, 255), (x, y), max(1, 5 * (1 - s)))

    center = (0.0, 0.0, DECK / 2)
    for i in range(len(hull)):
        (l0, f0), (l1, f1) = hull[i], hull[(i + 1) % len(hull)]
        top = [(l0, f0, DECK), (l1, f1, DECK)]
        low = [(l0 * 0.86, f0 * 0.9, BOTTOM), (l1 * 0.86, f1 * 0.9, BOTTOM)]
        if not visible_face([low[0], low[1], top[1], top[0]], center, cam):
            continue
        k = 0.95 if abs(f0 - f1) < 1e-6 else 0.75
        mid = [(l0 * 0.95, f0 * 0.97, STRIPE), (l1 * 0.95, f1 * 0.97, STRIPE)]
        face([low[0], low[1], mid[1], mid[0]], shade((215, 60, 40), k))
        face([mid[0], mid[1], top[1], top[0]], shade((245, 245, 245), k))
    face([(l, f, DECK) for l, f in hull], (120, 126, 136))
    face([(l * 0.85, f * 0.88, DECK) for l, f in hull], (96, 102, 112))

    # esteira coletora na proa
    face([(-0.15, 0.40, DECK + 0.02), (0.15, 0.40, DECK + 0.02), (0.15, 0.82, -0.02), (-0.15, 0.82, -0.02)],
         (60, 64, 72))
    off = wake_phase or 0.0
    for i in range(5):
        s = (i / 5 + off) % 1.0
        f = 0.40 + 0.42 * s
        h = DECK + 0.02 - (DECK + 0.04) * s
        pygame.draw.line(surf, (240, 200, 40), P(-0.14, f, h), P(0.14, f, h), 2)
    for side in (-1, 1):
        pygame.draw.line(surf, (250, 210, 50), P(side * 0.16, 0.36, DECK + 0.08), P(side * 0.16, 0.82, 0.02), 3)

    # cacamba
    box(-0.2, 0.2, 0.0, 0.32, DECK, DECK + 0.16, (60, 150, 70))
    face([(-0.17, 0.03, DECK + 0.16), (0.17, 0.03, DECK + 0.16), (0.17, 0.29, DECK + 0.16), (-0.17, 0.29, DECK + 0.16)],
         (30, 70, 35))
    rnd = random.Random(9)
    for _ in range(9):  # oleo recolhido dentro da cacamba
        x, y = P(rnd.uniform(-0.14, 0.14), rnd.uniform(0.05, 0.27), DECK + 0.17)
        pygame.draw.ellipse(surf, rnd.choice([(30, 32, 25), (52, 56, 40), (70, 60, 80)]), (x - 4, y - 2, 8, 4))

    # cabine
    box(-0.17, 0.17, -0.44, -0.16, DECK, DECK + 0.28, (238, 238, 242))
    face([(-0.11, -0.44, DECK + 0.1), (0.11, -0.44, DECK + 0.1), (0.11, -0.44, DECK + 0.22), (-0.11, -0.44, DECK + 0.22)],
         (40, 75, 125))
    top = DECK + 0.28
    pygame.draw.line(surf, (80, 80, 90), P(0.0, -0.3, top), P(0.0, -0.3, top + 0.2), 2)
    pygame.draw.circle(surf, (255, 150, 30), P(0.0, -0.3, top + 0.21), 4)
    return surf


# --- estacao (modelo 3D renderizado em varios angulos) --------------------------
def save_group(names, frames, anchor_canvas, json_name, extra=None):
    """Salva varios quadros como PNGs separados, todos recortados no mesmo
    retangulo (o menor que cabe todos), e o .json com o ponto de apoio."""
    box = None
    for f in frames:
        r = f.get_bounding_rect()
        box = r if box is None else box.union(r)
    box.inflate_ip(4, 4)
    for name, f in zip(names, frames):
        out = pygame.Surface(box.size, pygame.SRCALPHA)
        out.blit(f, (0, 0), area=box)
        pygame.image.save(out, os.path.join(ASSETS_DIR, name))
    meta = {"arquivos": names, "tamanho": list(box.size),
            "apoio": [round(anchor_canvas[0] - box.x, 1), round(anchor_canvas[1] - box.y, 1)],
            "obs": "apoio = ponto (em px, a partir do canto de cima) onde o objeto encosta na agua"}
    meta.update(extra or {})
    with open(os.path.join(ASSETS_DIR, json_name), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2, ensure_ascii=False)


BOAT_FILES = ["barco_parado.png", "barco_ar.png"] + ["barco_andando_%d.png" % (i + 1) for i in range(BOAT_WAKE_FRAMES)]
def boat_frames():
    if os.path.exists(os.path.join(ASSETS_DIR, BOAT_SVG)):
        boat_svg_frames()  # o barco vem da arte vetorizada
        return
    frames = [render_boat(0.0), render_boat(0.0, foam=False)]
    frames += [render_boat(0.0, True, i / BOAT_WAKE_FRAMES) for i in range(BOAT_WAKE_FRAMES)]
    save_group(BOAT_FILES, frames, proj(0.0, 0.0)[:2], "barco.json")


# --- barco a partir do boat2.svg (arte vetorizada) -------------------------------
BOAT_SVG = "boat2.svg"
BOAT_SVG_TOP = 2  # margem em cima do quadro (px)
BOAT_SVG_SIZE, BOAT_SVG_ANCHOR = (260, 340), (130.0, 102.7)  # quadro e apoio no barco.json
BOAT_SVG_STERN = 458.0  # linha da popa no boat2.svg (onde a esteira comeca)


def _wake_svg(phase, width, height):
    """Esteira em SVG (fica por baixo do barco): o V de ondas que se abre
    atras da popa e a espuma da helice no meio. Tudo branco semitransparente,
    sumindo com a distancia, para a cor da agua aparecer. 'phase' (0..1) anda
    um espaco entre ondas: os 4 quadros fecham o loop sem pulo."""
    cx, y0 = width / 2, BOAT_SVG_STERN
    out = ['<defs>']
    for side, name in ((-1, "l"), (1, "r")):
        out.append('<linearGradient id="arm%s" gradientUnits="userSpaceOnUse" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f">'
                   '<stop offset="0" stop-color="#fff" stop-opacity="0.38"/>'
                   '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
                   % (name, cx + side * 95, y0, cx + side * 285, height))
    out.append('<linearGradient id="wash" gradientUnits="userSpaceOnUse" x1="0" y1="%.1f" x2="0" y2="%.1f">'
               '<stop offset="0" stop-color="#fff" stop-opacity="0.5"/>'
               '<stop offset="0.35" stop-color="#fff" stop-opacity="0.22"/>'
               '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>' % (y0, height - 40))

    def fade(u, top=0.06):  # aparece debaixo da popa e some longe do barco
        return max(0.0, min(1.0, u / top)) * (1 - u) ** 1.3

    def band(center, half, waves, fill, layers):
        """Faixa macia: varias copias cada vez mais finas e semitransparentes
        (borda esfumada), com a borda ondulando e andando junto com 'phase'."""
        for scale, op in layers:
            left, right = [], []
            for i in range(25):
                t = i / 24
                (x, y), (nx, ny), h = center(t), (1.0, 0.0), half(t) * scale
                w = math.sin(2 * math.pi * (t * waves - phase)) * (3 + 9 * t)
                w2 = math.sin(2 * math.pi * (t * waves - phase) + 2.1) * (3 + 9 * t)
                left.append((x - nx * (h + w), y))
                right.append((x + nx * (h + w2), y))
            pts = left + right[::-1]
            out.append('<path d="M%s Z" fill="%s" fill-opacity="%.2f"/>'
                       % (" L".join("%.1f %.1f" % p for p in pts), fill, op))

    # ondas transversais: arcos fracos atravessando a esteira
    for k in range(5):
        u = (k + phase) / 5
        y = y0 + u * (height - y0)
        half = 95 + 190 * u
        out.append('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f" fill="none" stroke="#fff" stroke-opacity="%.3f" '
                   'stroke-width="%.1f" stroke-linecap="round"/>'
                   % (cx - half * 0.9, y - 8 * u, cx, y + 22 + 30 * u, cx + half * 0.9, y - 8 * u,
                      0.2 * fade(u, 0.15), 2 + 4 * u))
    # faixa suave ao longo de cada braco do V
    for side, name in ((-1, "l"), (1, "r")):
        sx, ex = cx + side * 95, cx + side * 285
        band(lambda t, sx=sx, ex=ex, side=side: (sx + (ex - sx) * t - side * (4 + 14 * t), y0 + (height - y0) * t),
             lambda t: 3 + 16 * t, 4, "url(#arm%s)" % name, ((1.0, 0.35), (0.6, 0.45), (0.3, 0.6)))
    # cristas do V: tracos curtos e curvos ao longo de cada braco
    n = 10
    for side in (-1, 1):
        sx, ex = cx + side * 95, cx + side * 285
        dx, dy = ex - sx, height - y0
        ln = math.hypot(dx, dy)
        dx, dy = dx / ln, dy / ln
        nx, ny = (-dy, dx) if (-dy) * side < 0 else (dy, -dx)  # normal para o meio da esteira
        for k in range(n):
            u = (k + phase) / n
            wob = math.sin(u * 23.0) * 0.25 + 1  # variacao suave (so depende da posicao)
            px, py = sx + (ex - sx) * u, y0 + dy * ln * u
            L = (16 + 58 * u) * wob
            qx, qy = px + (nx * 0.8 - dx * 0.55) * L, py + (ny * 0.8 - dy * 0.55) * L
            mx, my = (px + qx) / 2 + dx * L * 0.25, (py + qy) / 2 + dy * L * 0.25
            for w, op in ((4 + 8 * u, 0.25), (1.5 + 3 * u, 0.8)):  # brilho largo + traco fino
                out.append('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f" fill="none" stroke="#fff" '
                           'stroke-opacity="%.3f" stroke-width="%.1f" stroke-linecap="round"/>'
                           % (px, py, mx, my, qx, qy, op * fade(u), w))
    # espuma da helice: faixa clara + bolhas rolando para tras
    band(lambda t: (cx, y0 + (height - y0) * t), lambda t: 72 + 50 * t, 3, "url(#wash)",
         ((1.0, 0.3), (0.8, 0.3), (0.6, 0.35), (0.4, 0.4)))
    m = 14
    for k in range(m):
        u = (k + phase) / m
        y = y0 + u * (height - y0 - 40)
        spread = 70 + 50 * u
        for lane in range(5):
            off = math.sin(u * (9 + 4 * lane) + lane * 1.7) * 0.5 + (lane - 2) * 0.32
            x = cx + off * spread
            rx, ry = (5 + 13 * u) * (0.7 + 0.3 * math.cos(u * 17 + lane)), 3 + 7 * u
            out.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="#fff" fill-opacity="%.3f"/>'
                       % (x, y, rx, ry, 0.5 * fade(u, 0.04)))
    return "\n        ".join(out)


BOW_ROOT = 20.0           # no boat2.svg: a raiz do braco fica no alto do trilho, acima da esteira
BOW_REACH = (44.0, 34.0)  # quanto cada braco do V vai para o lado e para a frente
BOW_ARM = 14.0            # grossura do braco
BOW_STEEL = "#8a8f96"     # aco (cor solida)
BOW_YELLOW = "#d9b44f"    # faixa de seguranca na borda de dentro


def _remove_old_v(svg):
    """Tira os bracos do V do desenho original (as partes da classe cls-11
    que sobem acima de y=30); o gerador desenha bracos novos (_bow_arms_svg)."""
    import re

    def high(m):
        nums = [float(v) for v in re.findall(r"-?[\d.]+", m.group(1))]
        return "" if min(nums[1::2]) < 30 else m.group(0)
    return re.sub(r'\s*<path d="([^"]*)" class="cls-11"/>', high, svg)


def _bow_water_svg(arms, belt_top, phase):
    """Agua na frente do barco andando, em duas camadas (por baixo e por
    cima dos bracos do V). 'phase' (0..1) anda um passo da animacao: os 4
    quadros fecham o loop sem pulo.
    - por baixo: a onda de proa que se abre por fora de cada braco, as
      ondinhas em V entrando na boca e a espuma onde a agua chega na esteira;
    - por cima: a agua batendo na ponta de cada braco (meia-lua de espuma e
      gotas espirrando para a frente e para fora)."""
    under, over = [], []
    foam = 'fill="none" stroke="#ffffff" stroke-linecap="round" stroke-linejoin="round"'

    def lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    (lx, ly), (rx, _) = belt_top
    cx = (lx + rx) / 2
    tips = {}
    for side, ri, ti, to, ro, ux, uy, nx, ny, gid in arms:
        tip = lerp(ti, to, 0.5)
        tips[side] = (ti, to, tip, ux, uy, nx, ny)
        # onda de proa: espuma que sai da quina de fora da ponta e se abre para tras e para fora
        bx, by = side * 0.8, 0.6  # direcao: para fora e para tras (abre em diagonal, como onda de proa)
        bl = math.hypot(bx, by)
        bx, by = bx / bl, by / bl
        start = (to[0] + nx * 2, to[1] + ny * 2)
        for k in range(5):
            s0 = (k + phase) / 5
            s1 = s0 + 0.12
            a = (start[0] + bx * 60 * s0, start[1] + by * 60 * s0)
            b = (start[0] + bx * 60 * s1, start[1] + by * 60 * s1)
            under.append('<path d="M%.2f %.2f L%.2f %.2f" %s stroke-opacity="%.2f" stroke-width="%.1f"/>'
                         % (a[0], a[1], b[0], b[1], foam, 0.9 * (1 - s0) ** 1.2, 3.8 - 2.2 * s0))
        # meia-lua de espuma na frente da ponta (a agua batendo), por cima do braco
        r = 10.5 + 1.5 * math.sin(math.tau * phase)
        fx, fy = tip[0] + ux * 3, tip[1] + uy * 3
        ang = math.atan2(uy, ux)  # para a frente, na direcao do braco
        pts = [(fx + r * math.cos(ang + d), fy + r * math.sin(ang + d))
               for d in [math.radians(v) for v in range(-80, 81, 20)]]
        inner = [(fx + (r - 3.2) * math.cos(ang + d) + ux * 1.5, fy + (r - 3.2) * math.sin(ang + d) + uy * 1.5)
                 for d in [math.radians(v) for v in range(80, -81, -20)]]
        over.append('<path d="M%s Z" fill="#ffffff" fill-opacity="0.85"/>'
                    % " L".join("%.2f %.2f" % q for q in pts + inner))
        # gotas espirrando para a frente e para fora, sumindo
        for j in range(3):
            u = (j + phase) / 3
            d = math.radians(-35 + 35 * j) * -side  # leque para fora
            dxj = ux * math.cos(d) - uy * math.sin(d)
            dyj = ux * math.sin(d) + uy * math.cos(d)
            dist = r + 3 + 14 * u
            over.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="#ffffff" fill-opacity="%.2f"/>'
                        % (fx + dxj * dist, fy + dyj * dist, 3.0 - 1.6 * u, 0.9 * (1 - u)))
    # ondinhas em V entrando pela boca, andando das pontas ate a esteira
    tl, tr = tips[-1][0], tips[1][0]
    for k in range(3):
        t = (k + phase) / 3
        y = tl[1] + 6 + (ly - tl[1] - 4) * t
        hw = ((tr[0] - tl[0]) / 2 - 6) * (1 - t) + ((rx - lx) / 2 - 4) * t
        under.append('<path d="M%.2f %.2f Q%.2f %.2f %.2f %.2f Q%.2f %.2f %.2f %.2f" %s stroke-opacity="%.2f" stroke-width="2.2"/>'
                     % (cx - hw, y - 3, cx - hw / 2, y + 4, cx, y + 5, cx + hw / 2, y + 4, cx + hw, y - 3,
                        foam, 0.55 * math.sin(math.pi * t)))
    # espuma onde a agua chega na esteira
    wave = [(lx + 2 + (rx - lx - 4) * i / 10,
             ly + 1.5 + 1.8 * math.sin(i * 1.9 + math.tau * phase)) for i in range(11)]
    under.append('<path d="M%s" %s stroke-opacity="0.7" stroke-width="3.2"/>'
                 % (" L".join("%.2f %.2f" % q for q in wave), foam))
    return under, over


def _bow_arms_svg(belt, phase=None):
    """Os dois bracos do V na frente da esteira coletora, que guiam o oleo
    para ela: aco em cor solida, faixa amarela com listras na borda de dentro e
    sombra na agua. Com phase (andando), poe a agua em volta (_bow_water_svg)."""
    (bx0, by0, bx1, by1), pts = belt
    top = sorted((q for q in pts if q[1] < (by0 + by1) / 2), key=lambda q: q[0])
    arms = []
    for side, (rx, ry) in ((-1, top[0]), (1, top[-1])):
        ri = (rx, ry - BOW_ROOT)                                            # raiz, lado de dentro
        ti = (rx + side * BOW_REACH[0], ry - BOW_REACH[1])                  # ponta, lado de dentro
        dx, dy = ti[0] - ri[0], ti[1] - ri[1]
        ln = math.hypot(dx, dy)
        ux, uy = dx / ln, dy / ln
        nx, ny = (-uy, ux) if -uy * side > 0 else (uy, -ux)               # normal para fora
        ro = (ri[0] + nx * BOW_ARM, ri[1] + ny * BOW_ARM)
        to = (ti[0] + nx * BOW_ARM, ti[1] + ny * BOW_ARM)
        gid = None
        arms.append((side, ri, ti, to, ro, ux, uy, nx, ny, gid))
    out = []

    def poly(q, attrs):
        return '<path d="M%s Z" %s/>' % (" L".join("%.2f %.2f" % v for v in q), attrs)

    for side, ri, ti, to, ro, ux, uy, nx, ny, gid in arms:  # sombra na agua
        out.append(poly([(x + 5, y + 7) for x, y in (ri, ti, to, ro)], 'fill="#000000" fill-opacity="0.22"'))
    under, over = _bow_water_svg(arms, (top[0], top[-1]), phase) if phase is not None else ([], [])
    out += under
    for side, ri, ti, to, ro, ux, uy, nx, ny, gid in arms:
        out.append(poly((ri, ti, to, ro), 'fill="%s" stroke="#000000" stroke-width="2" stroke-linejoin="round"' % BOW_STEEL))
        w = 3.6  # faixa amarela na borda de dentro, com listras pretas
        si, so = (ri, ti), ((ri[0] + nx * w, ri[1] + ny * w), (ti[0] + nx * w, ti[1] + ny * w))
        out.append(poly((si[0], si[1], so[1], so[0]), 'fill="%s"' % BOW_YELLOW))
        for k in range(1, 6):
            t0, t1 = k / 6 - 0.035, k / 6 + 0.02
            a = (ri[0] + (ti[0] - ri[0]) * t0, ri[1] + (ti[1] - ri[1]) * t0)
            b = (ri[0] + (ti[0] - ri[0]) * t1 + nx * w, ri[1] + (ti[1] - ri[1]) * t1 + ny * w)
            out.append('<path d="M%.2f %.2f L%.2f %.2f" stroke="#1c1c22" stroke-width="2.2"/>' % (a[0], a[1], b[0], b[1]))
        out.append(poly((ri, ti, to, ro), 'fill="none" stroke="#000000" stroke-width="2" stroke-linejoin="round"'))
    out += over
    return "\n      ".join(out)


# cores do boat2.svg trocadas por tons menos saturados (antigo -> novo)
BOAT_COLORS = {
    "cc3926": "b4553f",  # vermelho da popa
    "787e88": "848a93",  # casco
    "606670": "6b7179",  # convés
    "3c9646": "5b8d63",  # cacamba
    "1e4623": "2f4a36",  # fundo da cacamba
    "cacacd": "c8c6c1",  # base da cabine
    "eeeef2": "f2efe8",  # cabine (branco quente)
    "50505a": "50545c",  # haste da luz
    "284b7d": "42607e",  # janela
    "748080": "7f8687",  # trilhos e faixas
    "606771": "636972",  # esteira
}
BOAT_OUTLINE = "#20242b"  # contorno (grafite, no lugar do preto puro)


def _restyle(svg):
    """Cores mais suaves no barco: tons menos saturados e contorno grafite.
    Cada peca continua com uma cor solida (sem degrade), como a agua."""
    import re
    for old, new in BOAT_COLORS.items():
        svg = re.sub("#" + old, "#" + new, svg, flags=re.I)
    svg = svg.replace("#000000", BOAT_OUTLINE)
    return svg


def boat_svg_text(phase=None, belt=0.0):
    """O boat2.svg sem o fundo azul e sem a esteira desenhada nele; se phase
    (0..1) for dado, poe por baixo do barco a esteira animada (_wake_svg).
    belt (0..1): quanto as faixas da esteira coletora ja andaram."""
    import re
    with open(os.path.join(ASSETS_DIR, BOAT_SVG), encoding="utf-8") as fp:
        svg = fp.read()
    width, height = map(float, re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)', svg).groups())
    svg = re.sub(r'\s*<path d="[^"]*" class="cls-1(3)?"/>', "", svg)  # tira fundo, linhas e bolhas
    svg = _remove_old_v(svg)

    def bar(m):  # faixas fixas da esteira coletora (o gerador desenha as que andam)
        nums = [float(v) for v in re.findall(r"-?[\d.]+", m.group(1))]
        ys, xs = nums[1::2], nums[0::2]
        return "" if 60 < min(ys) and max(ys) < 140 and max(xs) - min(xs) > 60 else m.group(0)
    svg = re.sub(r'\s*<path d="([^"]*)" class="cls-11"/>', bar, svg)
    belt_path = re.search(r'<path d="[^"]*" class="cls-12"/>', svg).group(0)
    belt_shape = _svg_shape(svg, "cls-12")
    svg = svg.replace(belt_path, belt_path + "\n      " + _belt_svg(belt_shape, belt)
                      + "\n      " + _bow_arms_svg(belt_shape, phase))
    for _ in range(2):  # grupos que ficaram vazios (tambem os de dentro de outro)
        svg = re.sub(r'\s*<g>\s*</g>', "", svg)
    # a luz em cima da cabine (o circulo vermelho) fica apagada; o jogo a acende piscando
    svg = re.sub(r'(<path d="[^"]*C[^"]*") class="cls-2"/>', r'\1 fill="#%02x%02x%02x"/>' % LIGHT_OFF, svg)
    svg = _restyle(svg)
    if phase is None:
        return svg
    first = svg.index("<path", svg.index('data-name="Asset 1"'))
    return svg[:first] + "<g>\n        " + _wake_svg(phase, width, height) + "\n      </g>\n      " + svg[first:]


def _svg_layer(svg, body):
    """Outro SVG com o mesmo cabecalho/viewBox de 'svg' e so o conteudo 'body'."""
    head = svg[:svg.index(">", svg.index("<svg")) + 1]
    return head + "\n" + body + "\n</svg>\n"


def _svg_shape(svg, cls, curved=None):
    """Caixa (x0, y0, x1, y1) e pontos do primeiro path da classe 'cls'
    (curved=True/False: so os paths com/sem curvas, como o circulo da luz)."""
    import re
    for d in re.findall(r'<path d="([^"]*)" class="%s"/>' % cls, svg):
        if curved is not None and curved != ("C" in d):
            continue
        nums = [float(v) for v in re.findall(r"-?[\d.]+", d)]
        pts = list(zip(nums[0::2], nums[1::2]))
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        return (min(xs), min(ys), max(xs), max(ys)), pts
    raise ValueError("forma %s nao achada no %s" % (cls, BOAT_SVG))


def _belt_svg(belt, shift):
    """Faixas da esteira coletora, descendo para a cacamba: 'shift' (0..1)
    anda um espaco entre faixas (4 quadros = 1 volta, sem pulo)."""
    (bx0, by0, bx1, by1), pts = belt
    top = sorted((q for q in pts if q[1] < (by0 + by1) / 2), key=lambda q: q[0])
    bot = sorted((q for q in pts if q[1] >= (by0 + by1) / 2), key=lambda q: q[0])
    n = int((BUCKET_TOP_Y - BELT_BAR_H - by0) // BELT_GAP)
    out = []
    for k in range(n):
        y = by0 + ((k + shift) * BELT_GAP) % (n * BELT_GAP)
        t = (y - by0) / (by1 - by0)
        xl = top[0][0] + (bot[0][0] - top[0][0]) * t
        xr = top[-1][0] + (bot[-1][0] - top[-1][0]) * t
        out.append('<path d="M%.2f %.2f L%.2f %.2f L%.2f %.2f L%.2f %.2f Z" class="cls-11"/>'
                   % (xl, y, xr, y, xr, y + BELT_BAR_H, xl, y + BELT_BAR_H))
    return "\n      ".join(out)


def _bucket_svg(inner, level, levels):
    """Oleo dentro da cacamba (vista de cima): sobe do fundo (perto da cabine)
    para a proa conforme o nivel, com a superficie ondulada. Cor solida."""
    x0, y0, x1, y1 = inner
    xl, xr, yb = x0 + 3, x1 - 3, y1 - 3
    yt = yb - (yb - y0 - 3) * level / levels
    r = min(9.0, yb - yt)
    n = 12
    wave = [(xl + (xr - xl) * i / n, yt + 2.2 * math.sin(i * 1.7 + level)) for i in range(n + 1)]
    edge = " L".join("%.2f %.2f" % q for q in wave)
    body = ('M%s L%.2f %.2f Q%.2f %.2f %.2f %.2f L%.2f %.2f Q%.2f %.2f %.2f %.2f Z'
            % (edge, xr, yb - r, xr, yb, xr - r, yb, xl + r, yb, xl, yb, xl, yb - r))
    out = ['<path d="%s" fill="%s"/>' % (body, OIL_SVG)]
    return "\n      ".join(out)


def _light_svg(light):
    """Luz da cabine acesa: brilho vermelho em volta, luz e miolo claro."""
    (x0, y0, x1, y1), _ = light
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2
    return ('<defs><radialGradient id="glow" gradientUnits="userSpaceOnUse" cx="%.2f" cy="%.2f" r="%.2f">'
            '<stop offset="0" stop-color="#ff5032" stop-opacity="0.75"/>'
            '<stop offset="1" stop-color="#ff5032" stop-opacity="0"/></radialGradient></defs>'
            '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="url(#glow)"/>'
            '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="#ff5c3c" stroke="#000000" stroke-width="2"/>'
            '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="#ffecc8"/>'
            % (cx, cy, r * 3.2, cx, cy, r * 3.2, cx, cy, r, cx - r * 0.2, cy - r * 0.2, r * 0.45))


BELT_GAP, BELT_BAR_H = 14.5, 3.0  # no boat2.svg: espaco entre as faixas da esteira e altura de cada uma
OIL_SVG = "#2b2733"  # oleo (cor solida)
LIGHT_OFF = (98, 38, 32)  # luz apagada (nos quadros)
BUCKET_TOP_Y = 145.0       # no boat2.svg: onde a esteira encontra a cacamba
BUCKET_LEVELS = 8
BOAT_EXTRA = ["cacamba_%d.png" % (i + 1) for i in range(BUCKET_LEVELS)] + ["luz_acesa.png", "gota_oleo.png"]


def boat_svg_frames():
    """Cria os quadros do barco (boat2_*.svg e barco_*.png) a partir do
    boat2.svg: parado, no ar (o mesmo desenho) e andando (com a esteira na
    agua e a esteira coletora rodando). Tambem cria as camadas que o jogo
    poe por cima: oleo na cacamba (cacamba_N), luz acesa e a gota que desce
    a esteira."""
    import io
    import re
    fw, fh = BOAT_SVG_SIZE
    ax = BOAT_SVG_ANCHOR[0]
    boat = boat_svg_text()
    with open(os.path.join(ASSETS_DIR, BOAT_SVG), encoding="utf-8") as fp:
        original = fp.read()
    width, height = map(float, re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)', boat).groups())
    k = (fh - 2 * BOAT_SVG_TOP) / height  # o desenho todo cabe na altura
    sw, sh = round(width * k), round(height * k)
    ox = round(ax - sw / 2)  # centrado no apoio

    def to_frame(x, y):  # unidade do SVG -> px no quadro
        return [round(ox + x * sw / width, 1), round(BOAT_SVG_TOP + y * sh / height, 1)]

    def save(text, name):  # SVG -> PNG do tamanho do quadro
        img = pygame.image.load_sized_svg(io.BytesIO(text.encode("utf-8")), (sw, sh))
        out = pygame.Surface((fw, fh), pygame.SRCALPHA)
        out.blit(img, (ox, BOAT_SVG_TOP))
        pygame.image.save(out, os.path.join(ASSETS_DIR, name))

    for i, png in enumerate(BOAT_FILES):
        moving = i >= 2
        text = boat_svg_text((i - 2) / BOAT_WAKE_FRAMES if moving else None,
                             (i - 2) / BOAT_WAKE_FRAMES if moving else 0.0)
        name = os.path.join(ASSETS_DIR, png.replace("barco_", "boat2_").replace(".png", ".svg"))
        with open(name, "w", encoding="utf-8") as fp:
            fp.write(text)  # a versao vetorial de cada quadro, para editar/consultar
        save(text, png)

    inner, _ = _svg_shape(original, "cls-6")
    for lvl in range(1, BUCKET_LEVELS + 1):  # oleo enchendo a cacamba
        save(_svg_layer(boat, _bucket_svg(inner, lvl, BUCKET_LEVELS)), BOAT_EXTRA[lvl - 1])
    save(_svg_layer(boat, _light_svg(_svg_shape(original, "cls-2", curved=True))), "luz_acesa.png")
    # gota de oleo que desce a esteira
    drop = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 12">'
            '<ellipse cx="8" cy="6" rx="6.5" ry="4.8" fill="%s" stroke="#20242b" stroke-width="1"/></svg>' % OIL_SVG)
    pygame.image.save(pygame.image.load_sized_svg(io.BytesIO(drop.encode("utf-8")), (12, 9)),
                      os.path.join(ASSETS_DIR, "gota_oleo.png"))

    (bx0, by0, bx1, by1), _ = _svg_shape(boat, "cls-12")
    meta = {"arquivos": BOAT_FILES, "tamanho": [fw, fh], "apoio": list(BOAT_SVG_ANCHOR),
            "esteira": [to_frame((bx0 + bx1) / 2, by0 + 4), to_frame((bx0 + bx1) / 2, BUCKET_TOP_Y + 12)],
            "cacamba": BOAT_EXTRA[:BUCKET_LEVELS], "luz": "luz_acesa.png", "gota": "gota_oleo.png",
            "obs": "apoio = ponto (em px, a partir do canto de cima) onde o objeto encosta na agua; "
                   "esteira = de onde ate onde o oleo recolhido desliza (px no quadro); "
                   "cacamba = camadas do oleo na cacamba (vazia -> cheia); luz = camada da luz acesa (pisca)"}
    with open(os.path.join(ASSETS_DIR, "barco.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=2, ensure_ascii=False)


def load_or(names, maker):
    path = os.path.join(ASSETS_DIR, names[0])
    return pygame.image.load(path) if os.path.exists(path) else maker()


# --- lista de tudo que o jogo usa ------------------------------------------------
SIMPLE = {
    "boia.png": make_buoy,
    "jato.png": make_spout,
    "peixe.png": make_fish,
    "peixe_nadando.png": make_fish_swim,
    "garrafa.png": make_bottle,
    "sacola.png": make_bag,
    "lata_vermelha.png": make_can,
    "lata_prateada.png": lambda: make_can((190, 195, 205), (30, 90, 200), (240, 240, 250), (110, 115, 125), 20),
    "tanque.png": lambda: make_cylinder(32, 80, (88, 92, 102)),
    "estacao_chao.png": make_station_floor,
    "estacao_torre.png": make_tower,
    "feixe_luz.png": make_beam,
    "mancha_1.png": lambda: make_slick(1),
    "mancha_2.png": lambda: make_slick(2),
    "mancha_3.png": lambda: make_slick(3),
    "mancha_4.png": lambda: make_slick(4),
    "onda.png": make_ripple,
    "sombra.png": make_shadow,
    "seta_guia.png": make_arrow,
    "painel.png": make_panel,
    "bussola.png": make_compass,
    "bussola_seta.png": make_compass_arrow,
    "placa_contador.png": make_sign,
    "logo.png": make_logo,
    "menu_painel.png": make_menu_panel,
    "botao.png": lambda: make_button(False),
    "botao_selecionado.png": lambda: make_button(True),
    "minimapa.png": make_minimap_frame,
}
GROUPS = {"barco.json": (BOAT_FILES + (BOAT_EXTRA if os.path.exists(os.path.join(ASSETS_DIR, BOAT_SVG)) else []),
                         boat_frames)}
WATER = ("agua_limpa.png", "agua_poluida.png")


def missing():
    names = list(SIMPLE) + list(WATER) + [n for js, (files, _) in GROUPS.items() for n in files + [js]]
    return [n for n in names if not os.path.exists(os.path.join(ASSETS_DIR, n))]


def generate(force=False, log=print):
    """Cria os arquivos que faltam (ou todos, com force=True)."""
    os.makedirs(ASSETS_DIR, exist_ok=True)

    def need(name):
        return force or not os.path.exists(os.path.join(ASSETS_DIR, name))

    for name, maker in SIMPLE.items():
        if need(name):
            pygame.image.save(maker(), os.path.join(ASSETS_DIR, name))
            log("  " + name)
    if any(need(n) for n in WATER):
        for name, img in zip(WATER, make_water(bs.WATER_PPC, bs.WATER_PERIOD)):
            if need(name):
                pygame.image.save(img, os.path.join(ASSETS_DIR, name))
                log("  " + name)
    for js, (files, maker) in GROUPS.items():
        if any(need(n) for n in files + [js]):
            maker()
            log("  " + ", ".join(files + [js]))


if __name__ == "__main__":
    pygame.init()
    print("Gerando assets em", ASSETS_DIR)
    if "--barco-svg" in sys.argv or "--agua" in sys.argv:
        if "--barco-svg" in sys.argv:
            boat_svg_frames()
        if "--agua" in sys.argv:
            for name, img in zip(WATER, make_water(bs.WATER_PPC, bs.WATER_PERIOD)):
                pygame.image.save(img, os.path.join(ASSETS_DIR, name))
    else:
        generate(force="--todos" in sys.argv)
    print("Pronto.")
