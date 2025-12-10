from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    gender = Column(String)  # male/female/other
    age = Column(Integer)
    language = Column(String, default='ru')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Subscription
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime)
    subscription_id = Column(String)
    
    # Stats
    games_played = Column(Integer, default=0)
    truth_answered = Column(Integer, default=0)
    dares_completed = Column(Integer, default=0)
    rating = Column(Float, default=1000.0)
    
    # Preferences
    preferred_gender = Column(String)
    min_age = Column(Integer, default=18)
    max_age = Column(Integer, default=60)
    categories = Column(JSON, default=['acquaintance', 'flirt'])
    
    # Current state
    current_game_id = Column(Integer, ForeignKey('games.id'), nullable=True)
    waiting_for_game = Column(Boolean, default=False)
    last_search = Column(DateTime)
    
    current_game = relationship("Game", foreign_keys=[current_game_id])

class Game(Base):
    __tablename__ = 'games'
    
    id = Column(Integer, primary_key=True)
    game_type = Column(String)  # friend, random, private
    status = Column(String, default='waiting')  # waiting, active, finished
    categories = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    
    # Players
    players = relationship("User", secondary="game_players", backref="games")
    current_player_id = Column(Integer, ForeignKey('users.id'))
    creator_id = Column(Integer, ForeignKey('users.id'))
    
    # Game state
    current_round = Column(Integer, default=0)
    max_rounds = Column(Integer, default=10)
    turn_order = Column(JSON)  # List of player IDs
    used_questions = Column(JSON, default=[])
    used_dares = Column(JSON, default=[])
    
    creator = relationship("User", foreign_keys=[creator_id])

class GamePlayer(Base):
    __tablename__ = 'game_players'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    joined_at = Column(DateTime, default=datetime.utcnow)
    score = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

class Question(Base):
    __tablename__ = 'questions'
    
    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
    category = Column(String, nullable=False)
    difficulty = Column(Integer, default=1)  # 1-5
    language = Column(String, default='ru')
    is_active = Column(Boolean, default=True)
    rating = Column(Float, default=0.0)
    times_used = Column(Integer, default=0)

class Dare(Base):
    __tablename__ = 'dares'
    
    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
    category = Column(String, nullable=False)
    difficulty = Column(Integer, default=1)  # 1-5
    language = Column(String, default='ru')
    requires_proof = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    rating = Column(Float, default=0.0)
    times_used = Column(Integer, default=0)

class Payment(Base):
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    amount = Column(Float)
    currency = Column(String, default='RUB')
    provider_payment_id = Column(String)
    status = Column(String)  # pending, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    user = relationship("User")