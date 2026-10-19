"""Ligacao do Zero Oil com o console T-TEA (chao interativo).

O T-TEA (https://github.com/larvattea/ttea) projeta o jogo no chao e acompanha
o jogador com uma webcam e o MediaPipe. Ele abre o jogo com o proprio Python e
estes argumentos:

  --lang pt_BR  --player_id 3  --professional_id 1

Quando eles chegam, o jogo roda no "modo T-TEA": tela cheia no projetor
calibrado, recorde e opcoes por jogador, cada corrida registrada para o
profissional e o barco controlado pelos pes, pisando nas marcacoes (PADS)
projetadas na parte de baixo da tela (o rio continua por baixo delas):

  Pegadas (no meio, embaixo)      ficar parado nelas comeca a andar
  Setas (dos lados das pegadas)   virar o barco para esse lado
  Parar em cima de um botao       escolher nos menus (o anel em volta dos pes enche)

Basta um pe na marcacao. Cada pisada vale uma vez: para repetir, tire o pe e
pise de novo.

O teclado e o mouse continuam funcionando (para o profissional). Sem os
argumentos o jogo roda como antes, so no teclado.

Para testar sem o console montado (sem camera, projetor nem calibracao), o
mouse faz o papel dos pes: --simular-pes (ou a variavel de ambiente
ZEROOIL_SIMULAR_PES=1, que vale tambem quando o jogo e aberto pelo T-TEA). A
seta do mouse e onde o jogador esta pisando; o jogo abre numa janela comum.

A camera e o MediaPipe ficam numa thread separada: a deteccao leva dezenas de
milissegundos por quadro e o jogo continua a 60 quadros por segundo.
"""
import argparse
import csv
import logging
import os
import threading
import time
from datetime import datetime

GAME_FOLDER = "zerooil"  # pasta dos dados do jogo dentro dos dados do T-TEA
CONTROL_W, CONTROL_H = 640, 480  # espaco da imagem da camera em que a calibracao e feita
PREVIEW_WINDOW = "Zero Oil - camera"

# --- controle pelos pes ----------------------------------------------------------
# No console a tela cresce PANEL_H para baixo e o rio vai junto (ver
# zero_oil.set_screen_height): o barco desce para BOAT_Y e as marcacoes ficam
# na parte de baixo, sem cobrir o caminho do barco.
GAME_H = 480
PANEL_H = 190
# marcacoes (em pixels da tela inteira): centro (x, y) e tamanho (largura, altura).
# As setas ficam um passo (uns 50 cm numa projecao de 2,5 m) para cada lado das
# pegadas e deixam o canto de baixo livre para o minimapa.
PADS = {
    "left": ((190, GAME_H + 130), (124, 88)),
    "right": ((450, GAME_H + 130), (124, 88)),
}
STAND_SPOT = ((320, GAME_H + 134), (132, 84))  # pegadas: parado aqui, o barco sai andando
BOAT_Y = 400        # linha da tela onde o barco encosta na agua (fora do console: 309)
PAD_MARGIN = 10     # folga em volta das marcacoes (a deteccao do pe nao e exata)
LOST_AFTER = 0.5    # sem ver o jogador por este tempo (s), os pes somem da tela
START_HOLD = 1.0    # parado nas pegadas por este tempo (s), o barco sai sozinho
DWELL_TIME = 1.5    # tempo (s) parado em cima de um botao para escolher

log = logging.getLogger("zerooil")


def parse_args(argv=None):
    """Argumentos que o T-TEA passa; os desconhecidos sao ignorados."""
    parser = argparse.ArgumentParser(description="Zero Oil")
    parser.add_argument("--lang", default="pt_BR", help="idioma da plataforma (o jogo e so em portugues)")
    parser.add_argument("--player_id", type=int, default=None, help="jogador escolhido no T-TEA")
    parser.add_argument("--professional_id", type=int, default=None, help="profissional que acompanha")
    parser.add_argument("--sem-camera", dest="camera", action="store_false",
                        help="modo T-TEA sem a camera (so teclado), para testar")
    parser.add_argument("--simular-pes", dest="simulate", action="store_true",
                        help="o mouse faz o papel dos pes, sem o console montado")
    args, _ = parser.parse_known_args(argv)
    args.simulate = args.simulate or os.environ.get("ZEROOIL_SIMULAR_PES", "") not in ("", "0")
    if args.simulate and args.player_id is None:  # simulacao fora do T-TEA: jogador de teste
        args.player_id, args.professional_id = 0, args.professional_id or 0
    return args


def pad_rect(spec, margin=0):
    """(x, y, largura, altura) de uma marcacao dada por centro e tamanho."""
    (x, y), (w, h) = spec
    return (x - w / 2 - margin, y - h / 2 - margin, w + 2 * margin, h + 2 * margin)


def inside(rect, point):
    x, y, w, h = rect
    return x <= point[0] <= x + w and y <= point[1] <= y + h


class Console:
    """Dados do T-TEA para o jogo: tela e camera calibradas, pasta de dados,
    controle pelos pes e o registro das corridas.

    Parameters
    ----------
    args : argparse.Namespace
        Resultado de parse_args, com player_id preenchido.
    game_w, game_h : int
        Tamanho da tela do jogo fora do console. No console (canvas_size) ela
        tem mais PANEL_H embaixo, para as marcacoes; o pygame amplia tudo.
    """

    def __init__(self, args, game_w, game_h):
        from ttea.model import Calibration, CalibrationPoint
        from ttea.service import CalibrationService
        from ttea.util import PathConfig

        self.args = args
        self.player_id = args.player_id
        self.professional_id = args.professional_id
        self.path_config = PathConfig
        logging.basicConfig(filename=self.data_file("zerooil.log"), level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        log.info("Zero Oil no T-TEA: jogador %s, profissional %s", self.player_id, self.professional_id)

        cal = CalibrationService()
        hw = cal.find_by_id_calibration(Calibration.ID_VALUE)
        size = cal.get_screen_size() if hw else None
        self.screen_index = hw.screen_position if hw else 0
        self.screen_size = (size["width"], size["height"]) if size else (game_w, game_h)
        self.fullscreen = cal.is_fullscreen() if hw else True

        # tela -> jogo: o pygame amplia a tela do console mantendo a proporcao
        # (faixas pretas nas sobras)
        self.canvas_size = (game_w, game_h + PANEL_H)
        cw, ch = self.canvas_size
        sw, sh = self.screen_size
        self.scale = min(sw / cw, sh / ch)
        self.offset = ((sw - cw * self.scale) / 2, (sh - ch * self.scale) / 2)

        self.tracker = None
        point = cal.find_by_id_calibration_point(CalibrationPoint.ID_VALUE)
        if args.simulate:
            log.info("simulando os pes com o mouse")
            self.fullscreen = False  # janela comum, para usar o mouse
            self.screen_index = 0
            self.tracker = MouseFeet()
        elif not args.camera:
            log.info("camera desligada (--sem-camera)")
        elif hw is None or point is None:
            log.warning("sem calibracao no T-TEA: o jogo fica so no teclado")
        else:
            corners = [(point.pointx1, point.pointy1), (point.pointx2, point.pointy2),
                       (point.pointx3, point.pointy3), (point.pointx4, point.pointy4)]
            model = cal.get_mediapipe_model_embedded() if cal.is_raspberry_pi() else cal.get_mediapipe_model_desktop()
            try:
                self.tracker = FeetTracker(
                    camera_index=hw.camera_position,
                    backend=cal.get_opencv_capture_backend(),
                    model_path=PathConfig.model(model),
                    detection=cal.get_mediapipe_detection_position(),
                    presence=cal.get_mediapipe_detection_presence(),
                    tracking=cal.get_mediapipe_detection_tracking(),
                    corners=corners,
                    to_game=self.screen_to_game,
                    control_size=(CONTROL_W, CONTROL_H),
                    screen_size=self.screen_size,
                )
                self.tracker.start()
            except Exception:  # sem camera ou sem MediaPipe: o jogo continua no teclado
                log.exception("nao deu para ligar a camera")
                self.tracker = None

        # estado do controle pelos pes
        self.feet = []            # posicao de cada pe na tela do jogo (vazia sem jogador)
        self.pointer = None       # meio dos pes (os menus usam um ponto so), ou None
        self.pressed = {name: False for name in PADS}  # marcacoes com um pe em cima
        self.present_t = 0.0      # ha quanto tempo o jogador esta parado nas pegadas
        self.preview = True       # janela com a imagem da camera (para o profissional)
        self.preview_frame_id = -1

    # ---- arquivos ----
    def data_file(self, name):
        """Arquivo na pasta de dados do jogo dentro dos dados do T-TEA."""
        return self.path_config.game_save(GAME_FOLDER, name)

    def record_file(self):
        return self.data_file("recorde_jogador_%s.json" % self.player_id)

    def config_file(self):
        return self.data_file("config.json")

    def save_run(self, game, reason):
        """Uma linha por corrida em corridas.csv, para o profissional."""
        path = self.data_file("corridas.csv")
        row = {
            "data": datetime.fromtimestamp(game.run_start).strftime("%Y-%m-%d"),
            "inicio": datetime.fromtimestamp(game.run_start).strftime("%H:%M:%S"),
            "duracao_s": round(time.time() - game.run_start),
            "jogador_id": self.player_id,
            "profissional_id": self.professional_id,
            "pontos": game.score,
            "rio": game.river,
            "rios_limpos": game.river - 1 + (game.state == "clear"),
            "oleo_entregue": game.delivered,
            "batidas": game.crashes,
            "curvas": game.turns,
            "pulos": game.jumps,
            "recorde": int(game.new_record),
            "fim": reason,
        }
        new = not os.path.exists(path)
        try:
            with open(path, "a", newline="", encoding="utf-8") as fp:
                out = csv.DictWriter(fp, fieldnames=list(row), delimiter=";")
                if new:
                    out.writeheader()
                out.writerow(row)
        except OSError:
            log.exception("nao deu para gravar a corrida")

    # ---- janela ----
    def open_display(self, pygame):
        """Janela do console no projetor calibrado (tela cheia sem trocar a
        resolucao), do tamanho canvas_size."""
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE)
        if isinstance(self.tracker, FeetTracker):  # criada antes do jogo, senao ela rouba o foco depois
            import cv2
            cv2.namedWindow(PREVIEW_WINDOW)
        try:
            screen = pygame.display.set_mode(self.canvas_size, flags, display=self.screen_index)
        except pygame.error:  # monitor da calibracao desligado: abre no principal
            log.warning("monitor %s indisponivel", self.screen_index)
            screen = pygame.display.set_mode(self.canvas_size, flags)
        try:  # o T-TEA fica na frente quando abre o jogo: traz a janela do jogo para o teclado
            from ttea.games.kartea.gameutil import regain_focus
            regain_focus()
        except Exception:
            log.info("sem regain_focus do T-TEA")
        return screen

    def screen_to_game(self, x, y):
        """Pixel da tela (projetor) -> pixel da tela do console."""
        return ((x - self.offset[0]) / self.scale, (y - self.offset[1]) / self.scale)

    # ---- controle pelos pes ----
    def update(self, dt):
        """Le a ultima deteccao. Devolve os comandos deste quadro ("left",
        "right"): cada marcacao vale uma vez por pisada."""
        if self.tracker is None:
            return []
        self.feet = self.tracker.latest()
        n = len(self.feet)
        self.pointer = (sum(x for x, _ in self.feet) / n, sum(y for _, y in self.feet) / n) if n else None
        commands = []
        for name, spec in PADS.items():
            rect = pad_rect(spec, PAD_MARGIN)
            down = any(inside(rect, foot) for foot in self.feet)
            if down and not self.pressed[name]:
                commands.append(name)
            self.pressed[name] = down
        if self.pressed["left"] and self.pressed["right"]:  # um pe em cada seta: nao vira
            commands = [c for c in commands if c not in ("left", "right")]
        return commands

    def present(self, dt):
        """True quando o jogador esta parado nas pegadas (sem pisar nas
        marcacoes) por START_HOLD."""
        spot = pad_rect(STAND_SPOT, PAD_MARGIN)
        if self.pointer is None or any(self.pressed.values()) or not inside(spot, self.pointer):
            self.present_t = 0.0
        else:
            self.present_t += dt
        return self.present_t >= START_HOLD

    def show_preview(self):
        """Imagem da camera com os pes e a area calibrada (no monitor do profissional)."""
        if not isinstance(self.tracker, FeetTracker) or not self.preview:
            return
        import cv2
        frame, frame_id = self.tracker.preview()
        if frame is not None and frame_id != self.preview_frame_id:
            self.preview_frame_id = frame_id
            cv2.imshow(PREVIEW_WINDOW, frame)
        cv2.waitKey(1)

    def toggle_preview(self):
        if not isinstance(self.tracker, FeetTracker):
            return
        import cv2
        self.preview = not self.preview
        if not self.preview:
            cv2.destroyWindow(PREVIEW_WINDOW)

    def close(self):
        if self.tracker is not None:
            self.tracker.stop()
        try:
            import cv2
            cv2.destroyAllWindows()
        except Exception:
            log.info("sem janela da camera para fechar")


class MouseFeet:
    """Simulacao dos pes com o mouse (mesma interface do FeetTracker): a seta
    do mouse e um pe pisando no chao."""

    def start(self):
        pass

    def stop(self):
        pass

    def latest(self):
        import pygame
        return [pygame.mouse.get_pos()] if pygame.mouse.get_focused() else []  # seta fora: sem jogador


class FeetTracker(threading.Thread):
    """Camera + MediaPipe numa thread: posicao de cada pe na tela do jogo.

    Cada pe e o calcanhar, levado da imagem da camera para a tela pela
    calibracao do T-TEA (mesma conta do KarTEA).
    """

    HEELS = (29, 30)

    def __init__(self, camera_index, backend, model_path, detection, presence, tracking,
                 corners, to_game, control_size, screen_size):
        super().__init__(daemon=True, name="zerooil-camera")
        import cv2
        import numpy as np

        self.cv2, self.np = cv2, np
        self.camera_index, self.backend = camera_index, backend
        self.model_path = model_path
        self.confidence = (detection, presence, tracking)
        self.corners = corners
        self.to_game = to_game
        cw, ch = control_size
        sw, sh = screen_size
        self.control = control_size
        # imagem da camera (area calibrada) -> imagem de controle -> tela
        dst = np.float32([[0, 0], [cw, 0], [0, ch], [cw, ch]])
        self.matrix = cv2.getPerspectiveTransform(np.float32(corners), dst)
        self.ratio = (sw / cw, sh / ch)

        self.lock = threading.Lock()
        self.running = True
        self.feet = []
        self.seen_at = 0.0
        self.frame = None
        self.frame_id = 0

    def latest(self):
        """Posicao de cada pe (vazia se o jogador sumiu ha mais de LOST_AFTER)."""
        with self.lock:
            return list(self.feet) if time.time() - self.seen_at < LOST_AFTER else []

    def preview(self):
        with self.lock:
            return self.frame, self.frame_id

    def stop(self):
        self.running = False
        self.join(timeout=2)

    def run(self):
        try:
            self.loop()
        except Exception:
            log.exception("a camera parou")

    def loop(self):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        cv2 = self.cv2
        detection, presence, tracking = self.confidence
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=self.model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=detection,
            min_pose_presence_confidence=presence,
            min_tracking_confidence=tracking,
        )
        cap = cv2.VideoCapture(self.camera_index, self.backend)
        if not cap.isOpened():
            log.error("camera %s nao abriu", self.camera_index)
            return
        last_ms = 0
        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            while self.running:
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.01)
                    continue
                frame = cv2.flip(frame, 1)  # a calibracao do T-TEA e feita na imagem espelhada
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                now = time.time()
                ms = max(last_ms + 1, int(now * 1000))  # o modo VIDEO quer tempos crescentes
                last_ms = ms
                result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ms)
                marks = result.pose_landmarks[0] if result.pose_landmarks else None
                self.process(frame, marks, now)
        cap.release()

    def process(self, frame, marks, now):
        cv2 = self.cv2
        h, w = frame.shape[:2]
        feet = None
        if marks is not None:
            feet = [self.to_game(*self.camera_to_screen(marks[i].x, marks[i].y)) for i in self.HEELS]
            for i in self.HEELS:
                cv2.circle(frame, (int(marks[i].x * w), int(marks[i].y * h)), 7, (0, 220, 255), -1)
        sx, sy = w / self.control[0], h / self.control[1]
        quad = [(int(x * sx), int(y * sy)) for x, y in self.corners]
        for a, b in ((0, 1), (1, 3), (3, 2), (2, 0)):  # area calibrada
            cv2.line(frame, quad[a], quad[b], (0, 255, 0), 2)
        with self.lock:
            if feet is not None:
                self.feet, self.seen_at = feet, now
            self.frame = frame
            self.frame_id += 1

    def camera_to_screen(self, x, y):
        """Ponto normalizado (0 a 1) da camera -> pixel da tela (como o KarTEA)."""
        cw, ch = self.control
        p = self.np.float32([[[x * cw, y * ch]]])
        px, py = self.cv2.perspectiveTransform(p, self.matrix)[0][0]
        return px * self.ratio[0], py * self.ratio[1]
