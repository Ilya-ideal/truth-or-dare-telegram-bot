import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from colorama import init as colorama_init, Fore
from questions_actions import QUESTIONS, DARES

colorama_init(autoreset=True)


@dataclass
class GameState:
    id: int
    game_type: str
    categories: List[str]
    players: List[int] = field(default_factory=list)
    started: bool = False
    host_id: Optional[int] = None
    invite_code: Optional[str] = None
    current_player: Optional[int] = None
    max_rounds: int = 10
    max_players: int = 10
    moves_done: int = 0


class GameLogic:
    def __init__(self, db):
        self.db = db
        self.games: Dict[int, GameState] = {}
        self.user_to_game: Dict[int, int] = {}
        self.invite_to_game: Dict[str, int] = {}
        self.waiting_random: List[Dict] = []
        self.next_game_id = 1
        print(Fore.CYAN + "[GAME] Логика игр инициализирована")

    def _generate_game_id(self) -> int:
        game_id = self.next_game_id
        self.next_game_id += 1
        return game_id

    def _default_categories(self) -> List[str]:
        return ["acquaintance", "flirt"]

    def _generate_invite_code(self) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        while True:
            code = "".join(random.choices(alphabet, k=6))
            if code not in self.invite_to_game:
                return code

    def get_game_by_id(self, game_id: int) -> Optional[GameState]:
        return self.games.get(game_id)

    def get_game_for_user(self, telegram_id: int) -> Optional[GameState]:
        game_id = self.user_to_game.get(telegram_id)
        if not game_id:
            return None
        return self.games.get(game_id)

    def create_friend_game(
        self,
        creator_telegram_id: int,
        categories: Optional[List[str]] = None,
        max_rounds: int = 10,
        max_players: int = 10,
    ) -> GameState:
        if categories is None or not categories:
            categories = self._default_categories()
        game_id = self._generate_game_id()
        state = GameState(
            id=game_id,
            game_type="friend",
            categories=categories,
            players=[creator_telegram_id],
            started=False,
            host_id=creator_telegram_id,
            max_rounds=max_rounds,
            max_players=max(2, min(max_players, 10)),
        )
        invite_code = self._generate_invite_code()
        state.invite_code = invite_code
        self.games[game_id] = state
        self.user_to_game[creator_telegram_id] = game_id
        self.invite_to_game[invite_code] = game_id
        print(Fore.GREEN + f"[GAME] Создана приватная комната #{game_id} код={invite_code}")
        return state

    def join_friend_game(self, invite_code: str, user_telegram_id: int) -> tuple[bool, str, Optional[GameState]]:
        game_id = self.invite_to_game.get(invite_code)
        if not game_id:
            return False, "Игра по этому коду не найдена", None
        state = self.games.get(game_id)
        if not state:
            return False, "Игра уже завершена", None
        if user_telegram_id in state.players:
            return False, "Ты уже в этой игре", state
        if len(state.players) >= state.max_players:
            return False, f"В этой комнате уже {state.max_players} игроков", None
        state.players.append(user_telegram_id)
        self.user_to_game[user_telegram_id] = game_id
        print(Fore.GREEN + f"[GAME] Игрок {user_telegram_id} присоединился к комнате #{game_id}")
        return True, "Вы присоединились к игре", state

    async def find_random_game(
        self,
        user_telegram_id: int,
        categories: Optional[List[str]] = None,
        search_gender: Optional[str] = None,
        search_age_min: Optional[int] = None,
        search_age_max: Optional[int] = None,
        user_gender: Optional[str] = None,
        user_age: Optional[int] = None,
        is_premium: bool = False,
    ) -> Optional[GameState]:
        if categories is None or not categories:
            categories = self._default_categories()
        existing = self.get_game_for_user(user_telegram_id)
        if existing and existing.started:
            print(Fore.YELLOW + f"[GAME] Пользователь {user_telegram_id} уже в игре #{existing.id}")
            return existing

        def _fits_preferences(candidate):
            gender_ok = True
            opponent_gender = candidate.get("gender")
            if search_gender and opponent_gender:
                if search_gender != "Любой" and opponent_gender != search_gender:
                    gender_ok = False
            age_ok = True
            opp_age = candidate.get("age")
            if opp_age is not None:
                if search_age_min is not None and opp_age < search_age_min:
                    age_ok = False
                if search_age_max is not None and opp_age > search_age_max:
                    age_ok = False
            user_fits_candidate = True
            cand_pref_gender = candidate.get("search_gender")
            if cand_pref_gender and cand_pref_gender != "Любой" and user_gender:
                user_fits_candidate = user_gender == cand_pref_gender
            cand_age_min = candidate.get("search_age_min")
            cand_age_max = candidate.get("search_age_max")
            if user_age is not None:
                if cand_age_min is not None and user_age < cand_age_min:
                    user_fits_candidate = False
                if cand_age_max is not None and user_age > cand_age_max:
                    user_fits_candidate = False
            candidate_cats = candidate.get("categories") or self._default_categories()
            selected_categories = categories or self._default_categories()
            intersection = [c for c in selected_categories if c in candidate_cats]
            return gender_ok and age_ok and user_fits_candidate and bool(intersection)

        match_index = None
        ordered_waiting = sorted(
            enumerate(self.waiting_random),
            key=lambda item: (not item[1].get("is_premium"), item[0]),
        )
        for idx, opponent in ordered_waiting:
            if opponent["user_id"] == user_telegram_id:
                continue
            if _fits_preferences(opponent):
                match_index = idx
                break

        if match_index is not None:
            opponent = self.waiting_random.pop(match_index)
            opponent_id = opponent["user_id"]
            opp_cats = opponent.get("categories") or self._default_categories()
            game_id = self._generate_game_id()
            merged = [c for c in categories if c in opp_cats] or self._default_categories()
            state = GameState(
                id=game_id,
                game_type="random",
                categories=merged,
                players=[opponent_id, user_telegram_id],
                started=True,
                max_rounds=10,
            )
            self.games[game_id] = state
            self.user_to_game[opponent_id] = game_id
            self.user_to_game[user_telegram_id] = game_id
            self.set_initial_turn(game_id)
            print(Fore.GREEN + f"[GAME] Случайная игра #{game_id} между {opponent_id} и {user_telegram_id}")
            return state

        waiting_payload = {
            "user_id": user_telegram_id,
            "categories": categories,
            "search_gender": search_gender or "Любой",
            "search_age_min": search_age_min,
            "search_age_max": search_age_max,
            "gender": user_gender,
            "age": user_age,
            "is_premium": is_premium,
        }
        if is_premium:
            self.waiting_random.insert(0, waiting_payload)
        else:
            self.waiting_random.append(waiting_payload)
        print(Fore.YELLOW + f"[GAME] Игрок {user_telegram_id} в ожидании соперника (премиум={is_premium})")
        return None

    def cancel_random_wait(self, user_telegram_id: int) -> bool:
        for idx, opponent in enumerate(list(self.waiting_random)):
            if opponent.get("user_id") == user_telegram_id:
                self.waiting_random.pop(idx)
                print(Fore.YELLOW + f"[GAME] Игрок {user_telegram_id} отменил поиск соперника")
                return True
        return False

    def set_initial_turn(self, game_id: int) -> Optional[int]:
        state = self.games.get(game_id)
        if not state or not state.players:
            return None
        state.current_player = random.choice(state.players)
        print(Fore.CYAN + f"[GAME] Первый ход в игре #{game_id} у {state.current_player}")
        return state.current_player

    def next_turn_random(self, game_id: int) -> Optional[int]:
        state = self.games.get(game_id)
        if not state or not state.players:
            return None
        state.moves_done += 1
        if state.moves_done >= state.max_rounds:
            print(Fore.CYAN + f"[GAME] Лимит раундов в игре #{game_id} достигнут")
            return None
        if len(state.players) == 1:
            state.current_player = state.players[0]
            return state.current_player
        candidates = [p for p in state.players if p != state.current_player]
        if not candidates:
            candidates = state.players
        state.current_player = random.choice(candidates)
        print(Fore.CYAN + f"[GAME] Следующий ход в игре #{game_id} у {state.current_player}")
        return state.current_player

    def finish_game(self, game_id: int):
        state = self.games.pop(game_id, None)
        if not state:
            return
        for uid in state.players:
            self.user_to_game.pop(uid, None)
        if state.invite_code:
            self.invite_to_game.pop(state.invite_code, None)
        print(Fore.CYAN + f"[GAME] Игра #{game_id} завершена")

    def get_task(self, game_id: int, kind: str) -> str:
        state = self.games.get(game_id)
        if not state:
            return "Игра не найдена"
        categories = state.categories or self._default_categories()
        category = random.choice(categories)
        if kind == "truth":
            pool = QUESTIONS.get(category) or []
        else:
            pool = DARES.get(category) or []
        if not pool:
            return "Заданий для этой категории пока нет"
        return random.choice(pool)
