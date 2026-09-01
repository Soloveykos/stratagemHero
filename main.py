import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

try:
    import msvcrt
    import winsound
except ImportError:
    msvcrt = None
    winsound = None


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
RESET = "\033[0m"
START_LEVEL_TIME = 42
MIN_LEVEL_TIME = 16
TIME_PENALTY = 4
COMMANDS_PER_LEVEL = 10
MAX_STORED_SCORES = 100
SCORES_FILE = Path(__file__).with_name("high_scores.json")

DIRECTIONS = ("UP", "DOWN", "LEFT", "RIGHT")
SYMBOLS = {"UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→"}
KEYS = {"w": "UP", "s": "DOWN", "a": "LEFT", "d": "RIGHT"}
ARROW_KEYS = {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}
PROTOCOLS = (
    ("AURORA LANCE", "✦"),
    ("ION MORTAR", "◉"),
    ("NOVA DRONE", "✧"),
    ("EMBER POD", "◆"),
    ("TITAN WALKER", "▰"),
    ("VORTEX BEACON", "◎"),
    ("PULSE BARRAGE", "≋"),
    ("SABLE SHIELD", "⬡"),
    ("COMET STRIKE", "☄"),
    ("BASILISK TURRET", "▣"),
    ("SPECTER SCOUT", "◌"),
    ("MANTIS MINEFIELD", "✹"),
    ("CIPHER SATELLITE", "◈"),
    ("THUNDER COIL", "⚡"),
    ("RIFT GATE", "⌁"),
    ("HELIOS ARRAY", "☀"),
    ("ATLAS DROP", "▲"),
    ("ECHO RELAY", "◍"),
    ("FALCON WING", "◢"),
    ("QUASAR NET", "⊹"),
    ("WARDEN CORE", "⬢"),
    ("ORBITAL FORGE", "⚙"),
    ("LUMEN FIELD", "☼"),
    ("VECTOR SWARM", "❖"),
)


def clear_screen():
    print("\033[2J\033[H", end="")


def beep(frequency, duration):
    if winsound:
        winsound.Beep(frequency, duration)


def score_key(record):
    return record["score"], record["level"], record["commands"], record["best_combo"]


def load_scores():
    try:
        with SCORES_FILE.open(encoding="utf-8") as score_file:
            raw_scores = json.load(score_file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(raw_scores, list):
        return []

    required_keys = ("score", "level", "commands", "best_combo", "recorded_at")
    return [
        record
        for record in raw_scores
        if isinstance(record, dict)
        and all(key in record for key in required_keys)
        and all(isinstance(record[key], int) for key in required_keys[:-1])
        and isinstance(record["recorded_at"], str)
    ]


def record_score(game):
    scores = load_scores()
    scores.append(
        {
            "score": game.score,
            "level": game.level,
            "commands": game.completed,
            "best_combo": game.best_combo,
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    scores.sort(key=score_key, reverse=True)
    scores = scores[:MAX_STORED_SCORES]
    try:
        with SCORES_FILE.open("w", encoding="utf-8") as score_file:
            json.dump(scores, score_file, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return scores[:3]


class CommandArray:
    def __init__(self):
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.completed = 0
        self.level = 1
        self.completed_in_level = 0
        self.time_penalty = 0
        self.sequence = []
        self.protocol = None
        self.loadout = []
        self.progress = 0
        self.message = "AWAITING DEPLOYMENT"
        self.level_started_at = None
        self.start_level()

    @property
    def level_time_limit(self):
        return max(MIN_LEVEL_TIME, START_LEVEL_TIME - (self.level - 1) * 3)

    @property
    def time_left(self):
        if self.level_started_at is None:
            return self.level_time_limit
        elapsed = time.monotonic() - self.level_started_at
        return max(0, self.level_time_limit - elapsed - self.time_penalty)

    @property
    def is_over(self):
        return self.level_started_at is not None and self.time_left <= 0

    def start_level(self):
        self.completed_in_level = 0
        self.time_penalty = 0
        self.level_started_at = None
        self.next_sequence()

    def deploy_level(self):
        self.level_started_at = time.monotonic()
        self.message = f"LEVEL {self.level} ACTIVE"

    def sequence_length(self):
        base_length = 3 + (self.level - 1) // 2
        roll = random.random()
        if roll < 0.15:
            return base_length + 3
        if roll < 0.45:
            return base_length + 1
        return base_length

    def next_sequence(self):
        length = self.sequence_length()
        self.sequence = [random.choice(DIRECTIONS) for _ in range(length)]
        self.protocol = random.choice(PROTOCOLS)
        alternatives = [protocol for protocol in PROTOCOLS if protocol != self.protocol]
        self.loadout = [self.protocol, *random.sample(alternatives, 5)]
        random.shuffle(self.loadout)
        self.progress = 0

    def submit(self, direction):
        if self.is_over:
            return None
        expected = self.sequence[self.progress]
        if direction == expected:
            self.progress += 1
            beep(880, 25)
            if self.progress == len(self.sequence):
                time_bonus = int(self.time_left * 2)
                earned = 100 * self.level + self.combo * 25 + time_bonus
                self.score += earned
                self.combo += 1
                self.best_combo = max(self.best_combo, self.combo)
                self.completed += 1
                self.completed_in_level += 1
                self.message = f"COMMAND ACCEPTED: +{earned}"
                beep(1400, 80)
                if self.completed_in_level == COMMANDS_PER_LEVEL:
                    self.level += 1
                    self.start_level()
                    return "level_complete"
                else:
                    self.next_sequence()
        else:
            self.combo = 0
            self.time_penalty += TIME_PENALTY
            self.progress = 0
            self.message = f"INPUT REJECTED: -{TIME_PENALTY} SECONDS. RETRY."
            beep(180, 120)
        return None

    def render(self):
        clear_screen()
        remaining = self.time_left
        timer_color = RED if remaining <= 10 else YELLOW if remaining <= 20 else GREEN
        print(f"{GREEN}COMMAND ARRAY{RESET}  {DIM}TERMINAL ARCADE{RESET}")
        print("=" * 56)
        print(f"TIME {timer_color}{remaining:05.1f}/{self.level_time_limit:02d}{RESET}  LEVEL {self.level:02d}  SCORE {self.score:05d}")
        print(f"COMMANDS {self.completed_in_level}/{COMMANDS_PER_LEVEL}    COMBO x{self.combo}    BEST x{self.best_combo}")
        print()
        protocol_name, protocol_icon = self.protocol
        print(f"CALLING {CYAN}{protocol_icon} {protocol_name}{RESET}")
        icons = []
        for name, icon in self.loadout:
            color = CYAN if (name, icon) == self.protocol else DIM
            icons.append(f"{color}[{icon}]{RESET}")
        print("TACTICAL RACK: " + " ".join(icons))
        print()
        blocks = []
        for index, direction in enumerate(self.sequence):
            if index < self.progress:
                blocks.append(f"{GREEN}[{SYMBOLS[direction]}]{RESET}")
            elif index == self.progress:
                blocks.append(f"{CYAN}[{SYMBOLS[direction]}]{RESET}")
            else:
                blocks.append(f"{DIM}[{SYMBOLS[direction]}]{RESET}")
        for start in range(0, len(blocks), 8):
            row = blocks[start : start + 8]
            row_width = len(row) * 4 - 1
            print(" " * max(0, (56 - row_width) // 2) + " ".join(row))
        print()
        print(f"{YELLOW}{self.message}{RESET}")
        print("=" * 56)
        print("Use ARROW KEYS or W A S D.  Q: quit")


def read_key(wait=False):
    if msvcrt:
        while wait and not msvcrt.kbhit():
            time.sleep(0.02)
        if not msvcrt.kbhit():
            return None
        key = msvcrt.getwch().lower()
        if key in ("\x00", "\xe0"):
            return ARROW_KEYS.get(msvcrt.getwch())
        return KEYS.get(key, key)
    key = input("Key: ").strip().lower()[:1]
    return KEYS.get(key, key)


def show_level_briefing(game):
    clear_screen()
    print(f"{GREEN}LEVEL {game.level:02d} // TACTICAL DEPLOYMENT{RESET}\n")
    print(f"COMPLETE {COMMANDS_PER_LEVEL} STRATAGEMS")
    print(f"TIME ALLOCATION: {game.level_time_limit} SECONDS")
    print(f"COMMAND RANGE: {3 + (game.level - 1) // 2}-{6 + (game.level - 1) // 2} ARROWS")
    print("\nLong command signatures can appear at any level.")
    print("Press ENTER or SPACE to deploy. Q to quit.")
    while True:
        key = read_key(wait=True)
        if key == "q":
            return False
        if key in ("\r", " "):
            return True


def show_result(game):
    leaders = record_score(game)
    clear_screen()
    print(f"{RED}TIME EXPIRED{RESET}\n")
    print(f"LEVEL REACHED: {game.level}")
    print(f"FINAL SCORE: {game.score}")
    print(f"COMMANDS COMPLETED: {game.completed}")
    print(f"BEST COMBO: x{game.best_combo}")
    print(f"\n{CYAN}TOP 3 LEADERS{RESET}")
    print("RK  SCORE   LVL  CMDS  COMBO")
    for rank, record in enumerate(leaders, 1):
        print(
            f"{rank:>2}  {record['score']:05d}   {record['level']:02d}"
            f"   {record['commands']:02d}    x{record['best_combo']}"
        )
    print("\nPress R to run another session, or Q to quit.")


def play():
    game = CommandArray()
    while True:
        if not show_level_briefing(game):
            return False
        game.deploy_level()
        while not game.is_over:
            game.render()
            key = read_key()
            if key == "q":
                return False
            if key in DIRECTIONS and game.submit(key) == "level_complete":
                break
            time.sleep(0.04)
        if game.is_over:
            break
    show_result(game)
    while True:
        key = read_key(wait=True)
        if key == "r":
            return True
        if key == "q":
            return False
        time.sleep(0.04)


def main():
    os.system("")
    while play():
        pass


if __name__ == "__main__":
    main()
