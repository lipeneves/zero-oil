"""Painel de ajustes do Zero Oil (Ctrl+D): muda parametros do jogo com ele
rodando, para testar sem mexer no codigo.

Jogar no teclado e com os pes no console TTEA pede ajustes diferentes (no
chao o jogador demora mais para reagir), entao os parametros do JOGO tem um
perfil para cada controle: TECLADO e PES. Vale o perfil do controle em uso; no
console, Tab troca o controle (e o perfil). Os do CONSOLE (marcacoes, tempos
dos pes) so aparecem com o console (ou na simulacao, --simular-pes).

  Setas cima/baixo     escolher o parametro
  Setas lados          mudar (Shift: 5 passos de uma vez)
  Del / Backspace      voltar ao padrao (Shift: todos os da secao)
  P                    pausar / continuar o jogo
  Tab                  trocar o controle: pes ou teclado (so no console)
  Ctrl+D               fechar

Com o painel aberto o teclado e dele; os pes (ou o mouse da simulacao)
continuam jogando. Cada mudanca e gravada em ajustes.json (so o que difere do
padrao, com o nome da constante do codigo) e volta na proxima vez que o jogo
abrir.
"""
import json
import logging
import os

import pygame

log = logging.getLogger("zerooil")

# (constante, rotulo, minimo, maximo, passo)
GAME_PARAMS = [
    ("SPEED_START", "velocidade inicial", 1.0, 10.0, 0.25),
    ("SPEED_MAX", "velocidade máxima", 1.0, 15.0, 0.25),
    ("SPEED_GAIN", "aceleração (por segundo)", 0.0, 0.3, 0.005),
    ("SPEED_RIVER", "a mais por rio", 0.0, 1.0, 0.05),
    ("TURN_TIME", "tempo da curva (s)", 0.06, 1.0, 0.02),
    ("TURN_SLOW", "velocidade na curva", 0.1, 1.0, 0.05),
    ("TURN_BRAKE", "freia antes (casas)", 0.0, 1.0, 0.05),
    ("TURN_RECOVER", "retoma depois (s)", 0.0, 2.0, 0.05),
    ("CAM_FOLLOW", "câmera segue", 2.0, 40.0, 1.0),
    ("CAM_ZOOM", "zoom da câmera (+ perto)", 0.5, 2.0, 0.05),
    ("BOAT_Y", "barco: linha na tela (- sobe)", 200, 600, 5),
    ("LIVES_START", "barcos no início (corrida nova)", 1, 5, 1),
]
CONSOLE_PARAMS = [
    ("PAD_W", "largura das setas", 40, 300, 4),
    ("PAD_H", "altura das setas", 30, 190, 4),
    ("PAD_GAP", "setas: distância do meio", 60, 500, 5),
    ("PAD_Y", "altura das marcações", 400, 650, 5),
    ("STAND_W", "largura das pegadas", 40, 300, 4),
    ("STAND_H", "altura das pegadas", 30, 190, 4),
    ("PAD_MARGIN", "folga da detecção (px)", 0, 80, 2),
    ("START_HOLD", "parado para sair (s)", 0.2, 4.0, 0.1),
    ("DWELL_TIME", "parado para escolher (s)", 0.3, 5.0, 0.1),
    ("LOST_AFTER", "pés somem sem ver (s)", 0.1, 3.0, 0.1),
]
PROFILES = {False: "teclado", True: "pes"}  # App.feet -> perfil do JOGO

W_PANEL = 310
ROW_H = 19
BG = (16, 22, 30, 215)
INK = (232, 240, 246)
DIM = (140, 156, 170)
CHANGED = (242, 214, 130)  # como o botao selecionado
SELECTED = (60, 86, 110)


class Panel:
    """Painel de ajustes por cima da tela do jogo.

    Parameters
    ----------
    app : App
        Telas do jogo (zero_oil.App): o controle em uso (feet), o console e a partida.
    game_module, console_module : module
        Onde ficam as constantes do JOGO (zero_oil) e do CONSOLE (console_ttea).
    path : str
        Arquivo dos ajustes gravados (ajustes.json).
    """

    def __init__(self, app, game_module, console_module, path):
        self.app = app
        self.path = path
        # modulo de cada constante: a do JOGO fica no zero_oil ou, como a linha do
        # barco (que vale tambem fora do console), no console_ttea
        self.owner = {name: game_module if hasattr(game_module, name) else console_module
                      for name, *_ in GAME_PARAMS + CONSOLE_PARAMS}
        self.defaults = {name: getattr(module, name) for name, module in self.owner.items()}
        self.view = (self.defaults["BOAT_Y"], self.defaults["CAM_ZOOM"])  # camera montada agora
        self.values = {"teclado": {}, "pes": {}, "console": {}}  # so o que difere do padrao
        self.open = False
        self.frozen = False  # P: o jogo para (o painel continua mudando)
        self.sel = 0
        font = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts", "Rubik-Bold.ttf")
        self.font = pygame.font.Font(font, 13)
        self.small = pygame.font.Font(font, 11)
        self.load()
        self.apply()

    # ---- valores ----
    def rows(self):
        """(secao, spec) de cada linha: o JOGO no perfil em uso e, com o console, o CONSOLE."""
        rows = [(self.profile(), spec) for spec in GAME_PARAMS]
        if self.app.console:
            rows += [("console", spec) for spec in CONSOLE_PARAMS]
        return rows

    def profile(self):
        return PROFILES[self.app.feet]

    def value(self, section, name):
        return self.values[section].get(name, self.defaults[name])

    def set_value(self, section, spec, value):
        name, _, lo, hi, step = spec
        value = min(hi, max(lo, value))
        value = int(round(value)) if isinstance(self.defaults[name], int) else round(value, 4)
        if value == self.defaults[name]:
            self.values[section].pop(name, None)
        else:
            self.values[section][name] = value
        self.apply()
        self.save()

    def apply(self):
        """Poe os valores nas constantes do jogo: o JOGO do perfil em uso e o CONSOLE."""
        for name, *_ in GAME_PARAMS:
            setattr(self.owner[name], name, self.value(self.profile(), name))
        for name, *_ in CONSOLE_PARAMS:
            setattr(self.owner[name], name, self.value("console", name))
        view = (self.value(self.profile(), "BOAT_Y"), self.value(self.profile(), "CAM_ZOOM"))
        if view != self.view:  # barco em outra linha ou zoom: a camera e montada de novo
            self.view = view
            self.app.relayout()
        if self.app.console:  # marcacoes em outro lugar ou tamanho: monta e desenha de novo
            self.app.console.layout_pads()
            for key in [k for k in self.app.sticker_cache if k[0] == "pad"]:
                del self.app.sticker_cache[key]

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as fp:
                saved = json.load(fp)
        except (OSError, ValueError):
            return
        specs = {"console": CONSOLE_PARAMS, "teclado": GAME_PARAMS, "pes": GAME_PARAMS}
        for section, params in specs.items():
            for name, _, lo, hi, _ in params:
                value = saved.get(section, {}).get(name)
                if isinstance(value, (int, float)) and value != self.defaults[name]:
                    self.values[section][name] = min(hi, max(lo, value))

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as fp:
                json.dump(self.values, fp, indent=2, ensure_ascii=False)
        except OSError:
            log.exception("nao deu para gravar os ajustes")

    # ---- teclado ----
    def toggle(self):
        self.open = not self.open
        if not self.open:
            self.frozen = False

    def handle_event(self, ev):
        """Teclas do painel aberto. Devolve True quando o evento e dele (todas as teclas)."""
        if ev.type == pygame.KEYUP:
            return True
        if ev.type != pygame.KEYDOWN:
            return False
        rows = self.rows()
        self.sel %= len(rows)
        section, spec = rows[self.sel]
        shift = ev.mod & pygame.KMOD_SHIFT
        if ev.key in (pygame.K_UP, pygame.K_DOWN):
            self.sel = (self.sel + (1 if ev.key == pygame.K_DOWN else -1)) % len(rows)
        elif ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            steps = (5 if shift else 1) * (1 if ev.key == pygame.K_RIGHT else -1)
            self.set_value(section, spec, self.value(section, spec[0]) + steps * spec[4])
        elif ev.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if shift:
                self.values[section].clear()
                self.apply()
                self.save()
            else:
                self.set_value(section, spec, self.defaults[spec[0]])
        elif ev.key == pygame.K_p:
            self.frozen = not self.frozen
        elif ev.key == pygame.K_TAB and self.app.console:
            self.app.toggle_feet()  # o perfil do JOGO troca junto
        return True

    # ---- desenho ----
    def text(self, surf, msg, pos, color=INK, font=None, anchor="topleft"):
        img = (font or self.font).render(msg, True, color)
        surf.blit(img, img.get_rect(**{anchor: pos}))

    def draw(self, screen):
        if not self.open:
            return
        rows = self.rows()
        self.sel %= len(rows)
        heads = 2 if self.app.console else 1
        game = self.app.game if self.app.mode == "game" else None
        height = 46 + (len(rows) + heads) * ROW_H + 52 + (16 if game else 0)
        box = pygame.Surface((W_PANEL, height), pygame.SRCALPHA)
        box.fill(BG)
        x0, x1 = 10, W_PANEL - 10
        title = "AJUSTES" + ("  ·  JOGO PAUSADO" if self.frozen else "")
        self.text(box, title, (x0, 8), CHANGED if self.frozen else INK)
        control = "pés (console)" if self.app.feet else "teclado"
        self.text(box, "controle em uso: %s" % control, (x0, 26), DIM, self.small)
        y = 46
        last = None
        for i, (section, (name, label, lo, hi, step)) in enumerate(rows):
            if section != last:
                head = "CONSOLE (marcações e pés)" if section == "console" else "JOGO · perfil %s" % {"pes": "PÉS"}.get(section, section.upper())
                self.text(box, head, (x0, y + 3), DIM, self.small)
                y += ROW_H
                last = section
            value = self.value(section, name)
            if i == self.sel:
                pygame.draw.rect(box, SELECTED, (4, y, W_PANEL - 8, ROW_H), border_radius=4)
            changed = name in self.values[section]
            self.text(box, label, (x0 + 4, y + 2), INK if i == self.sel else DIM if not changed else CHANGED)
            places = len(("%g" % step).partition(".")[2])
            shown = ("%d" if places == 0 else "%%.%df" % places) % value
            if i == self.sel:
                shown = "< %s >" % shown
            self.text(box, shown, (x1, y + 2), CHANGED if changed else INK, anchor="topright")
            y += ROW_H
        if game:
            info = "agora: %.2f casas/s  ·  rio %d" % (game.speed, game.river)
            self.text(box, info, (x0, y + 4), DIM, self.small)
            y += 16
        helps = ["setas: escolhe e muda  ·  Shift: 5x  ·  Del: padrão",
                 "P: pausa  ·  %sCtrl+D: fecha" % ("Tab: pés/teclado  ·  " if self.app.console else ""),
                 "amarelo = fora do padrão (gravado em ajustes.json)"]
        for line in helps:
            self.text(box, line, (x0, y + 6), DIM, self.small)
            y += 15
        screen.blit(box, (12, 64))
