import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import asyncio

class GameLogic:
    def __init__(self, db_session):
        self.db = db_session
        self.active_games = {}
        
    async def create_game(self, creator, game_type, categories=None, max_players=2, max_rounds=10):
        """Создание новой игры"""
        from models import Game, GamePlayer
        
        if categories is None:
            categories = ['acquaintance', 'flirt']
            
        game = Game(
            game_type=game_type,
            creator_id=creator.id,
            categories=categories,
            max_rounds=max_rounds,
            status='waiting',
            turn_order=[]
        )
        
        self.db.add(game)
        self.db.commit()
        self.db.refresh(game)
        
        # Добавляем создателя в игру
        game_player = GamePlayer(game_id=game.id, user_id=creator.id)
        self.db.add(game_player)
        
        creator.current_game_id = game.id
        self.db.commit()
        
        # Генерируем код приглашения для друзей
        invite_code = f"GAME{game.id:06d}"
        
        return game, invite_code
    
    async def join_game(self, user, game_id=None, invite_code=None):
        """Присоединение к игре"""
        from models import Game, GamePlayer
        
        if game_id:
            game = self.db.query(Game).filter(Game.id == game_id).first()
        elif invite_code:
            try:
                game_id = int(invite_code[4:])  # Извлекаем ID из GAME000123
                game = self.db.query(Game).filter(Game.id == game_id).first()
            except:
                return None, "Неверный код приглашения"
        else:
            return None, "Не указана игра"
            
        if not game:
            return None, "Игра не найдена"
            
        if game.status != 'waiting':
            return None, "Игра уже началась"
            
        # Проверяем, не участвует ли уже пользователь
        existing_player = self.db.query(GamePlayer).filter(
            GamePlayer.game_id == game.id,
            GamePlayer.user_id == user.id
        ).first()
        
        if existing_player:
            return game, "Вы уже в игре"
            
        # Проверяем максимальное количество игроков
        current_players = self.db.query(GamePlayer).filter(
            GamePlayer.game_id == game.id
        ).count()
        
        if current_players >= 10:  # MAX_PLAYERS_PER_GAME
            return None, "В игре уже максимальное количество игроков"
            
        # Добавляем игрока
        game_player = GamePlayer(game_id=game.id, user_id=user.id)
        self.db.add(game_player)
        
        user.current_game_id = game.id
        self.db.commit()
        
        return game, "Вы присоединились к игре"
    
    async def start_game(self, game_id):
        """Начало игры"""
        from models import Game, GamePlayer
        
        game = self.db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return False, "Игра не найдена"
            
        if game.status != 'waiting':
            return False, "Игра уже началась"
            
        # Получаем всех игроков
        players = self.db.query(GamePlayer).filter(
            GamePlayer.game_id == game.id
        ).all()
        
        if len(players) < 2:
            return False, "Недостаточно игроков"
            
        # Определяем порядок ходов
        player_ids = [p.user_id for p in players]
        random.shuffle(player_ids)
        game.turn_order = player_ids
        game.current_player_id = player_ids[0]
        game.status = 'active'
        game.started_at = datetime.utcnow()
        game.current_round = 1
        
        self.db.commit()
        
        return True, "Игра началась"
    
    async def get_next_turn(self, game_id):
        """Получение следующего хода"""
        from models import Game, GamePlayer
        
        game = self.db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return None
            
        if game.status != 'active':
            return None
            
        # Определяем следующего игрока
        current_index = game.turn_order.index(game.current_player_id)
        next_index = (current_index + 1) % len(game.turn_order)
        
        # Если следующий игрок - первый, увеличиваем раунд
        if next_index == 0:
            game.current_round += 1
            if game.current_round > game.max_rounds:
                return await self.end_game(game_id)
                
        game.current_player_id = game.turn_order[next_index]
        self.db.commit()
        
        return game.current_player_id
    
    async def get_question(self, game_id, category=None):
        """Получение случайного вопроса"""
        from models import Game, Question
        
        game = self.db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return None
            
        if category is None:
            category = random.choice(game.categories)
            
        # Ищем вопрос, который еще не использовался
        used_questions = game.used_questions or []
        
        question = self.db.query(Question).filter(
            Question.category == category,
            Question.is_active == True,
            ~Question.id.in_(used_questions) if used_questions else True
        ).order_by(Question.rating.desc()).first()
        
        if not question:
            # Если все вопросы использованы, сбрасываем список
            game.used_questions = []
            self.db.commit()
            question = self.db.query(Question).filter(
                Question.category == category,
                Question.is_active == True
            ).order_by(Question.rating.desc()).first()
            
        if question:
            # Добавляем вопрос в использованные
            used_questions.append(question.id)
            game.used_questions = used_questions
            question.times_used += 1
            self.db.commit()
            
        return question
    
    async def get_dare(self, game_id, category=None):
        """Получение случайного действия"""
        from models import Game, Dare
        
        game = self.db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return None
            
        if category is None:
            category = random.choice(game.categories)
            
        # Ищем действие, которое еще не использовалось
        used_dares = game.used_dares or []
        
        dare = self.db.query(Dare).filter(
            Dare.category == category,
            Dare.is_active == True,
            ~Dare.id.in_(used_dares) if used_dares else True
        ).order_by(Dare.rating.desc()).first()
        
        if not dare:
            # Если все действия использованы, сбрасываем список
            game.used_dares = []
            self.db.commit()
            dare = self.db.query(Dare).filter(
                Dare.category == category,
                Dare.is_active == True
            ).order_by(Dare.rating.desc()).first()
            
        if dare:
            # Добавляем действие в использованные
            used_dares.append(dare.id)
            game.used_dares = used_dares
            dare.times_used += 1
            self.db.commit()
            
        return dare
    
    async def skip_turn(self, game_id):
        """Пропуск хода"""
        from models import Game, GamePlayer
        
        game = self.db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return False
            
        # Начисляем штраф игроку
        game_player = self.db.query(GamePlayer).filter(
            GamePlayer.game_id == game.id,
            GamePlayer.user_id == game.current_player_id
        ).first()
        
        if game_player:
            game_player.score -= 10
            self.db.commit()
            
        return await self.get_next_turn(game_id)
    
    async def end_game(self, game_id):
        """Завершение игры"""
        from models import Game, GamePlayer, User
        
        game = self.db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return False
            
        game.status = 'finished'
        game.finished_at = datetime.utcnow()
        
        # Обновляем статистику игроков
        players = self.db.query(GamePlayer).filter(
            GamePlayer.game_id == game.id
        ).all()
        
        for player in players:
            user = self.db.query(User).filter(User.id == player.user_id).first()
            if user:
                user.games_played += 1
                user.current_game_id = None
                
        self.db.commit()
        
        return True
    
    async def find_random_game(self, user, preferred_gender=None):
        """Поиск случайной игры"""
        from models import Game, GamePlayer, User
        
        # Проверяем, есть ли уже ожидающие игроки
        waiting_users = self.db.query(User).filter(
            User.waiting_for_game == True,
            User.id != user.id,
            User.current_game_id == None
        ).all()
        
        if preferred_gender:
            waiting_users = [u for u in waiting_users if u.gender == preferred_gender]
            
        if waiting_users:
            # Нашли подходящего игрока
            opponent = random.choice(waiting_users)
            
            # Создаем игру
            game, invite_code = await self.create_game(
                user, 
                'random',
                user.categories
            )
            
            # Присоединяем оппонента
            await self.join_game(opponent, game_id=game.id)
            
            # Убираем флаг ожидания
            opponent.waiting_for_game = False
            user.waiting_for_game = False
            self.db.commit()
            
            return game
            
        else:
            # Ожидаем игрока
            user.waiting_for_game = True
            user.last_search = datetime.utcnow()
            self.db.commit()
            
            return None