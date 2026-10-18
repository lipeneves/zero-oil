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
  python gerar_assets.py --barco-svg  recria os quadros do barco a partir do barco-cartoon.svg
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


# --- barco a partir do barco-cartoon.svg (arte vetorizada) -----------------------
BOAT_SVG = "barco-cartoon.svg"
BOAT_SVG_TOP = 2  # margem em cima do quadro (px)
BOAT_SVG_SIZE, BOAT_SVG_ANCHOR = (260, 340), (130.0, 102.7)  # quadro e apoio no barco.json
BOAT_SVG_STERN = 458.0  # linha da popa no desenho (onde a esteira comeca)
# o barco e desenhado nesta area (unidades do SVG); a esteira na agua usa o resto
BOAT_SVG_CANVAS = (586.828, 853.758)
BOAT_SVG_FIT = (0.92, 184.4, 89.9)  # escala e deslocamento (x, y) do barco-cartoon.svg dentro da area


def _wake_svg(phase, width, height):
    """Agua mexendo em volta do barco andando (fica por baixo do barco), no
    estilo cartoon: arquinhos de agua entrando na boca do coletor, riscos de
    velocidade rentes ao casco, espuma branca em nuvem no motor (com uma
    sombra ciano por baixo) e rastros ciano finos e ondulados que se abrem
    para tras. 'phase' (0..1) anda um passo da
    animacao: os 4 quadros fecham o loop sem pulo."""
    cx = width / 2
    out = []

    def cloud(blobs, grow=0.0):
        """Espuma: circulos brancos sobre circulos ciano um pouco maiores e
        mais baixos (a sombra), como nos jogos cartoon."""
        shade = ['<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x, y + 4, r + 4 + grow, FOAM_SHADE)
                 for x, y, r in blobs]
        white = ['<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x, y, r, FOAM_WHITE) for x, y, r in blobs]
        out.extend(shade + white)

    # agua entrando no coletor: arquinhos que chegam na boca do U e encolhem la dentro
    (mx0, my0), (mx1, my1) = WAKE_MOUTH
    mcx = (mx0 + mx1) / 2
    for k in range(3):
        t = (k + phase) / 3
        y = my0 - 14 + (my1 - my0 + 8) * t
        hw = (mx1 - mx0) / 2 * (0.7 - 0.35 * t)
        out.append('<path d="M%.1f %.1f Q%.1f %.1f %.1f %.1f" fill="none" stroke="%s" stroke-opacity="%.2f" '
                   'stroke-width="%.1f" stroke-linecap="round"/>'
                   % (mcx - hw, y + 3, mcx, y - 3, mcx + hw, y + 3, FOAM_WHITE, 0.4 * math.sin(math.pi * t), 2.5 - t))
    # riscos de velocidade rentes ao casco, deslizando para tras
    (sy0, sy1), sx = WAKE_SIDES
    for side in (-1, 1):
        for k in range(3):
            t = (k + phase + 0.5 * (side > 0)) / 3 % 1
            y = sy0 + (sy1 - sy0) * t
            x = cx + side * (sx + 6 * t)
            out.append('<path d="M%.1f %.1f L%.1f %.1f" fill="none" stroke="%s" stroke-opacity="%.2f" '
                       'stroke-width="3.5" stroke-linecap="round"/>'
                       % (x, y, x + side * 2, y + 30, FOAM_WHITE, 0.9 * math.sin(math.pi * t)))

    # (os rastros atras da popa ficam numa camada a parte: _trail_svg)
    # espuma no motor (a helice batendo a agua)
    y0 = BOAT_SVG_STERN
    blobs = []
    for i in range(7):
        u = i / 6
        pulse = math.sin(math.tau * (phase + u))
        blobs.append((cx - 42 + 84 * u, y0 + 26 + 6 * abs(u - 0.5) * -2 + 3 * pulse, 11 + 3 * pulse))
    cloud(blobs, grow=-1)
    return "\n        ".join(out)


def _trail_svg(phase, width, height, bend):
    """Rastros na agua atras do barco: poucas faixas ciano longas e onduladas
    saindo da popa, abrindo um pouco e sumindo. 'bend' (graus) curva os
    rastros: rente a popa eles seguem o barco e, mais longe, viram para o
    lado ate apontar 'bend' graus (positivo = para a direita do quadro), como
    o caminho que o barco fez antes de virar."""
    cx, y0 = width / 2, BOAT_SVG_STERN
    length = height - y0 - 20
    b = math.radians(bend)
    m = 24
    # linha do meio: angulo cresce ao longo do rastro (curva) e depois segue reto
    mid, ang = [(cx, y0 + 20)], [0.0]
    for k in range(1, m + 1):
        a = b * min(1.0, 1.5 * (k - 0.5) / m)
        x, y = mid[-1]
        mid.append((x + math.sin(a) * length / m, y + math.cos(a) * length / m))
        ang.append(a)
    out = []
    for off, spread, w in ((-46, 2.2, 9), (-14, 1.6, 7), (16, 1.6, 7), (48, 2.2, 9)):
        pts = []
        for k in range(m + 1):
            t = k / m
            wig = 7 * t * math.sin(math.tau * (t * 2.5 - phase) + off)
            side = off * (1 + (spread - 1) * t) + wig   # distancia da linha do meio (para o lado)
            pts.append((mid[k][0] + math.cos(ang[k]) * side, mid[k][1] - math.sin(ang[k]) * side))
        for k in range(m):                                     # pedacos seguidos, cada vez mais apagados
            t = k / m
            op = 0.8 * min(1.0, (t + 0.04) / 0.12) * (1 - t) ** 1.1
            out.append('<path d="M%.1f %.1f L%.1f %.1f" fill="none" stroke="%s" stroke-opacity="%.2f" '
                       'stroke-width="%.1f" stroke-linecap="round"/>'
                       % (pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1], WAKE_TRAIL, op, w * (1 - 0.45 * t)))
    return "\n".join(out)


TRAIL_BENDS = list(range(-90, 91, 15))  # curvas pre-desenhadas do rastro (graus)
TRAIL_PAD = 70                          # margem dos lados do quadro do rastro (px), para a curva caber
FOAM_WHITE = "#ffffff"
FOAM_SHADE = "#8fe7ee"   # sombra ciano da espuma
WAKE_TRAIL = "#bff6f7"   # rastros atras do barco
WAKE_MOUTH = ((240.0, 44.0), (347.0, 64.0))  # boca do coletor (cantos, unidades do quadro SVG)
WAKE_SIDES = ((190.0, 400.0), 113.0)          # riscos dos lados: de onde ate onde (y) e distancia do meio


BOAT_OUTLINE = "#20242b"  # contorno (grafite, no lugar do preto puro)


def _fit_boat_svg(svg):
    """Poe o desenho do barco-cartoon.svg na area BOAT_SVG_CANVAS (escala e
    desloca os pontos de cada path), deixando espaco para a esteira atras."""
    import re
    s, dx, dy = BOAT_SVG_FIT
    k = [0]

    def num(m):
        v = float(m.group(0))
        k[0] += 1
        return "%.2f" % (v * s + (dx if k[0] % 2 else dy))

    def path(m):
        k[0] = 0
        return 'd="%s"' % re.sub(r"-?[\d.]+", num, m.group(1))
    svg = re.sub(r'(?<![\w-])d="([^"]*)"', path, svg)
    svg = re.sub(r"stroke-width:([\d.]+)", lambda m: "stroke-width:%.2f" % (float(m.group(1)) * s), svg)
    return re.sub(r'viewBox="[^"]*"', 'viewBox="0 0 %g %g"' % BOAT_SVG_CANVAS, svg, count=1)


def boat_svg_text(phase=None):
    """O barco-cartoon.svg na area do quadro, com a luz apagada e o contorno
    grafite; se phase (0..1) for dado, poe por baixo do barco a esteira
    animada na agua (_wake_svg)."""
    import re
    with open(os.path.join(ASSETS_DIR, BOAT_SVG), encoding="utf-8") as fp:
        svg = _fit_boat_svg(fp.read())
    width, height = BOAT_SVG_CANVAS
    # a luz em cima da cabine fica apagada; o jogo a acende piscando
    svg = re.sub(r'(<path id="luz" d="[^"]*") class="[^"]*"/>',
                 r'\g<1> fill="#%02x%02x%02x" stroke="#000000" stroke-width="3.7"/>' % LIGHT_OFF, svg)
    svg = svg.replace("#000000", BOAT_OUTLINE)
    if phase is None:
        return svg
    first = svg.index("<path", svg.index("<g id="))
    return svg[:first] + "<g>\n        " + _wake_svg(phase, width, height) + "\n      </g>\n      " + svg[first:]


def _svg_layer(svg, body):
    """Outro SVG com o mesmo cabecalho/viewBox de 'svg' e so o conteudo 'body'."""
    head = svg[:svg.index(">", svg.index("<svg")) + 1]
    return head + "\n" + body + "\n</svg>\n"


def _svg_shape(svg, ident):
    """Caixa (x0, y0, x1, y1) e pontos do path com id 'ident' (no SVG ja
    encaixado no quadro)."""
    import re
    m = re.search(r'<path id="%s" d="([^"]*)"' % ident, svg)
    if not m:
        raise ValueError('forma id="%s" nao achada no %s' % (ident, BOAT_SVG))
    nums = [float(v) for v in re.findall(r"-?[\d.]+", m.group(1))]
    pts = list(zip(nums[0::2], nums[1::2]))
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    return (min(xs), min(ys), max(xs), max(ys)), pts


def _bucket_svg(inner, wall, level, levels):
    """Oleo no bau aberto de tras, enchendo como um bau de verdade. Pela boca
    ('inner') se ve o fundo e, em cima, a parede de dentro do lado da cabine
    ('wall'; a altura dela na tela e a altura do bau). O oleo primeiro cobre
    o fundo e depois sobe: a superficie vai subindo pela parede ate a borda.
    Superficie com borda ondulada, brilho e cor solida."""
    x0, y0, x1, y1 = inner
    _, wy0, _, wy1 = wall
    xl, xr, yb = x0 + 2, x1 - 2, y1 - 2
    top = wy1 - (wy1 - wy0 - 3) * level / levels      # a superficie sobe pela parede
    r = 7.0
    n = 12
    wave = [(xl + (xr - xl) * i / n, top + 1.8 * math.sin(i * 1.7 + level)) for i in range(n + 1)]
    edge = " L".join("%.2f %.2f" % q for q in wave)
    body = ('M%s L%.2f %.2f Q%.2f %.2f %.2f %.2f L%.2f %.2f Q%.2f %.2f %.2f %.2f Z'
            % (edge, xr, yb - r, xr, yb, xr - r, yb, xl + r, yb, xl, yb, xl, yb - r))
    out = ['<path d="%s" fill="%s"/>' % (body, OIL_SVG),
           '<path d="M%s" fill="none" stroke="%s" stroke-width="2.5" stroke-linecap="round"/>' % (edge, OIL_SHINE),
           '<path d="M%.2f %.2f L%.2f %.2f M%.2f %.2f L%.2f %.2f" fill="none" stroke="%s" stroke-width="3" '
           'stroke-linecap="round" stroke-opacity="0.8"/>'                 # reflexos na superficie
           % (xl + 10, top + 9, xl + (xr - xl) * 0.4, top + 9,
              xl + (xr - xl) * 0.55, top + 20, xl + (xr - xl) * 0.7, top + 20, OIL_SHINE)]
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


OIL_SVG = "#2b2733"  # oleo (cor solida)
OIL_SHINE = "#6a6280"  # brilho na superficie do oleo
LIGHT_OFF = (98, 38, 32)  # luz apagada (nos quadros)
BUCKET_LEVELS = 8
BOAT_EXTRA = ["cacamba_%d.png" % (i + 1) for i in range(BUCKET_LEVELS)] + ["luz_acesa.png", "gota_oleo.png"]


def boat_svg_frames():
    """Cria os quadros do barco (barco_*.svg e barco_*.png) a partir do
    barco-cartoon.svg: parado, no ar (o mesmo desenho) e andando (com a
    esteira na agua). Tambem cria as camadas que o jogo poe por cima: oleo
    enchendo o bau de tras (cacamba_N; no SVG, id="cacamba" e a boca do bau
    e id="cacamba_parede" a parede de dentro que aparece), luz acesa
    (id="luz") e a gota de oleo."""
    import io
    fw, fh = BOAT_SVG_SIZE
    ax = BOAT_SVG_ANCHOR[0]
    boat = boat_svg_text()
    width, height = BOAT_SVG_CANVAS
    k = (fh - 2 * BOAT_SVG_TOP) / height  # o desenho todo cabe na altura
    sw, sh = round(width * k), round(height * k)
    ox = round(ax - sw / 2)  # centrado no apoio

    def save(text, name):  # SVG -> PNG do tamanho do quadro
        img = pygame.image.load_sized_svg(io.BytesIO(text.encode("utf-8")), (sw, sh))
        out = pygame.Surface((fw, fh), pygame.SRCALPHA)
        out.blit(img, (ox, BOAT_SVG_TOP))
        pygame.image.save(out, os.path.join(ASSETS_DIR, name))

    for i, png in enumerate(BOAT_FILES):
        moving = i >= 2
        text = boat_svg_text((i - 2) / BOAT_WAKE_FRAMES if moving else None)
        with open(os.path.join(ASSETS_DIR, png.replace(".png", ".svg")), "w", encoding="utf-8") as fp:
            fp.write(text)  # a versao vetorial de cada quadro, para editar/consultar
        save(text, png)

    # rastros curvados (o jogo escolhe a curva pelo quanto o barco esta virando):
    # folha com uma linha por curva e uma coluna por quadro da animacao
    pad, padu = TRAIL_PAD, TRAIL_PAD * width / sw
    tw = fw + 2 * pad
    sheet = pygame.Surface((tw * BOAT_WAKE_FRAMES, fh * len(TRAIL_BENDS)), pygame.SRCALPHA)
    for r, bend in enumerate(TRAIL_BENDS):
        for c in range(BOAT_WAKE_FRAMES):
            text = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g 0 %g %g">\n%s\n</svg>\n'
                    % (-padu, width + 2 * padu, height, _trail_svg(c / BOAT_WAKE_FRAMES, width, height, bend)))
            img = pygame.image.load_sized_svg(io.BytesIO(text.encode("utf-8")), (sw + 2 * pad, sh))
            sheet.blit(img, (c * tw + ox, r * fh + BOAT_SVG_TOP))
    pygame.image.save(sheet, os.path.join(ASSETS_DIR, "rastro.png"))

    inner, _ = _svg_shape(boat, "cacamba")
    wall, _ = _svg_shape(boat, "cacamba_parede")
    for lvl in range(1, BUCKET_LEVELS + 1):  # oleo enchendo o bau
        save(_svg_layer(boat, _bucket_svg(inner, wall, lvl, BUCKET_LEVELS)), BOAT_EXTRA[lvl - 1])
    save(_svg_layer(boat, _light_svg(_svg_shape(boat, "luz"))), "luz_acesa.png")
    # gota de oleo (o jogo so usa se o barco.json tiver "esteira")
    drop = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 12">'
            '<ellipse cx="8" cy="6" rx="6.5" ry="4.8" fill="%s" stroke="#20242b" stroke-width="1"/></svg>' % OIL_SVG)
    pygame.image.save(pygame.image.load_sized_svg(io.BytesIO(drop.encode("utf-8")), (12, 9)),
                      os.path.join(ASSETS_DIR, "gota_oleo.png"))

    meta = {"arquivos": BOAT_FILES, "tamanho": [fw, fh], "apoio": list(BOAT_SVG_ANCHOR),
            "cacamba": BOAT_EXTRA[:BUCKET_LEVELS], "luz": "luz_acesa.png", "gota": "gota_oleo.png",
            "rastro": {"arquivo": "rastro.png", "curvas": TRAIL_BENDS, "margem": TRAIL_PAD},
            "obs": "apoio = ponto (em px, a partir do canto de cima) onde o objeto encosta na agua; "
                   "cacamba = camadas do oleo no bau (vazio -> cheio); luz = camada da luz acesa (pisca); "
                   "rastro = folha dos rastros atras do barco andando (linha = curva em graus, "
                   "coluna = quadro da animacao; cada quadro tem 'margem' px a mais de cada lado)"}
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
