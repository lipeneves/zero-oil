"""Copia o Zero Oil para a pasta de jogos do console TTEA.

  python instalar_ttea.py C:/caminho/do/ttea          (raiz do repositorio do TTEA)
  python instalar_ttea.py C:/.../exergames            (ou direto a pasta de jogos)

O TTEA lista cada pasta de jogos que tem um metadata.json; o jogo fica em
<jogos>/zerooil. Rodar de novo atualiza o codigo e a arte. O TTEA guarda os
dados do jogo (recordes por jogador, opcoes, corridas.csv, zerooil.log) nessa
mesma pasta: eles nao sao apagados nem trocados pelos daqui.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["zero_oil.py", "gerar_assets.py", "console_ttea.py", "metadata.json"]
OLD_FILES = ["blue_sphere.py"]  # nomes antigos: apagados de uma instalacao anterior
FOLDER = "zerooil"


def games_dir(path):
    inner = os.path.join(path, "src", "ttea", "games")  # repositorio do TTEA (modo dev)
    return inner if os.path.isdir(inner) else path


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit(__doc__)
    dest = os.path.join(games_dir(sys.argv[1]), FOLDER)
    os.makedirs(dest, exist_ok=True)
    for name in OLD_FILES:
        old = os.path.join(dest, name)
        if os.path.isfile(old):
            os.remove(old)
    for name in FILES:
        shutil.copy2(os.path.join(HERE, name), dest)
    shutil.copytree(os.path.join(HERE, "assets"), os.path.join(dest, "assets"), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.vectorcraft", "__pycache__"))
    print("Zero Oil instalado em", dest)


if __name__ == "__main__":
    main()
