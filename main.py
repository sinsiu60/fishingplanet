"""1인칭 낚시 게임 진입점."""
import sys

from src.core.game import Game


def main() -> None:
    # 자동 테스트: python main.py --frames 120
    max_frames = None
    if "--frames" in sys.argv:
        max_frames = int(sys.argv[sys.argv.index("--frames") + 1])
    Game(max_frames=max_frames).run()


if __name__ == "__main__":
    main()
