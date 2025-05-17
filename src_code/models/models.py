from sqlalchemy import Column, Integer, String, DECIMAL, ForeignKey, DateTime, Boolean, UniqueConstraint, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON


APP_NAME = 'Pricing'
Base = declarative_base()


class User(Base):
    __tablename__ = 'auth_user'  # This should match the actual table name for the User model in your Django database.

    id = Column(Integer, primary_key=True)
    username = Column(String)

    # Add other fields if necessary.
    game_prefs = relationship("GamePrefs", uselist=False, back_populates="user")


class GamePrefs(Base):
    __tablename__ = f'{APP_NAME}_gameprefs'

    user_id = Column(Integer, ForeignKey('auth_user.id'), primary_key=True)
    sel_type_01 = Column(Integer)
    sel_type_02 = Column(Integer)
    sel_type_03 = Column(Integer)
    human_player_cnt = Column(Integer, default=1)
    game_observable = Column(Boolean)
    timestamp = Column(DateTime)

    user = relationship("User", back_populates="game_prefs")


class IndivGames(Base):
    __tablename__ = f'{APP_NAME}_indivgames'

    game_id = Column(String, primary_key=True, unique=True)
    initiator_id = Column(Integer, ForeignKey('auth_user.id'))
    initiator_name = Column(String(128))
    timestamp = Column(DateTime)
    status = Column(String(19), default="active")
    human_player_cnt = Column(Integer, default=1)
    game_observable = Column(Boolean, default=False)

    players = relationship("Players", back_populates="game")


class Players(Base):
    __tablename__ = f'{APP_NAME}_players'

    id = Column(Integer, primary_key=True)  # Automatic primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'))
    player_name = Column(String(128))
    player_id_display = Column(Integer)
    player_type = Column(String(16))  # Corrected the column definition here
    profile = Column(String(16))  # Corrected the column definition here

    game = relationship("IndivGames", back_populates="players")


class MktgSales(Base):
    __tablename__ = f'{APP_NAME}_mktgsales'  # use your actual app name here
    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    player_name = Column(String(128))
    year = Column(Integer)
    beg_in_force = Column(DECIMAL(16, 0))  # using Decimal type for financial calculations
    quotes = Column(DECIMAL(16, 0))
    sales = Column(DECIMAL(16, 0))
    canx = Column(DECIMAL(16, 0))
    avg_prem = Column(DECIMAL(18, 2))
    mktg_expense = Column(DECIMAL(18, 2))
    mktg_expense_ind = Column(DECIMAL(18, 2))
    end_in_force = Column(DECIMAL(16, 0))
    in_force_ind = Column(DECIMAL(16, 0))


class Financials(Base):
    __tablename__ = f'{APP_NAME}_financials'  # use your actual app name here

    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    player_name = Column(String(128))
    year = Column(Integer)
    written_premium = Column(DECIMAL(18, 2))  # using Decimal type for financial calculations
    in_force = Column(DECIMAL(16, 0))
    inv_income = Column(DECIMAL(18, 2))
    annual_expenses = Column(DECIMAL(18, 2))
    ay_losses = Column(DECIMAL(18, 2))
    py_devl = Column(DECIMAL(18, 2))
    clm_bi = Column(DECIMAL(16, 0))
    clm_cl = Column(DECIMAL(16, 0))
    profit = Column(DECIMAL(18, 2))
    dividend_paid = Column(DECIMAL(18, 2))
    capital = Column(DECIMAL(18, 2))
    capital_ratio = Column(DECIMAL(18, 5))
    capital_test = Column(String(4))


class Industry(Base):
    __tablename__ = f'{APP_NAME}_industry'  # use your actual app name here

    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    player_name = Column(String(128))
    year = Column(Integer)
    written_premium = Column(DECIMAL(18, 2))  # using Decimal type for financial calculations
    annual_expenses = Column(DECIMAL(18, 2))
    cy_losses = Column(DECIMAL(18, 2))
    profit = Column(DECIMAL(18, 2))
    capital = Column(DECIMAL(18, 2))
    capital_ratio = Column(DECIMAL(18, 5))
    capital_test = Column(String(4))


class Valuation(Base):
    __tablename__ = f'{APP_NAME}_valuation'  # use your actual app name here

    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    player_name = Column(String(128))
    year = Column(Integer)
    beg_in_force = Column(DECIMAL(16, 0))  # using Decimal type for financial calculations
    in_force = Column(DECIMAL(16, 0))
    start_capital = Column(DECIMAL(18, 2))
    excess_capital = Column(DECIMAL(18, 2))
    capital = Column(DECIMAL(18, 2))
    dividend_paid = Column(DECIMAL(18, 2))
    profit = Column(DECIMAL(18, 2))
    pv_index = Column(DECIMAL(18, 6))
    inv_rate = Column(DECIMAL(18, 6))
    irr_rate = Column(DECIMAL(18, 6))


class Triangles(Base):
    __tablename__ = f'{APP_NAME}_triangles'  # use your actual app name here

    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    player_name = Column(String(128))
    year = Column(Integer)
    triangles = Column(JSON)  # using Decimal type for financial calculations


class ClaimTrends(Base):
    __tablename__ = f'{APP_NAME}_claimtrends'  # use your actual app name here

    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    year = Column(Integer)
    claim_trends = Column(JSON)


class Indications(Base):
    __tablename__ = f'{APP_NAME}_indications'  # use your actual app name here

    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    player_name = Column(String(128))
    year = Column(Integer)
    indication_data = Column(JSON)


class Decisions(Base):
    __tablename__ = f'{APP_NAME}_decisions'  # use your actual app name here

    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    player_name = Column(String(128))
    year = Column(Integer)
    sel_aa_margin = Column(Integer)
    sel_aa_margin_min = Column(Integer)
    sel_aa_margin_max = Column(Integer)
    sel_exp_ratio_mktg = Column(Integer)
    sel_exp_ratio_mktg_min = Column(Integer)
    sel_exp_ratio_mktg_max = Column(Integer)
    sel_exp_ratio_data = Column(Integer)
    sel_exp_ratio_data_min = Column(Integer)
    sel_exp_ratio_data_max = Column(Integer)
    sel_profit_margin = Column(Integer)
    sel_profit_margin_min = Column(Integer)
    sel_profit_margin_max = Column(Integer)
    sel_loss_trend_margin = Column(Integer)
    sel_loss_trend_margin_min = Column(Integer)
    sel_loss_trend_margin_max = Column(Integer)
    sel_avg_prem = Column(DECIMAL(18, 2))
    decisions_locked = Column(Boolean)
    decisions_game_stage = Column(String(128))
    decisions_time_stamp = Column(JSON)
    curr_avg_prem = Column(DECIMAL(18, 2))


class Decisionsns(Base):
    __tablename__ = f'{APP_NAME}_decisionsns'  # use your actual app name here

    id = Column(Integer, primary_key=True)  # Every table should have a primary key
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))
    player_id_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    player_name = Column(String(128))
    year = Column(Integer)
    sel_profit_margin = Column(Integer)
    sel_loss_trend_margin = Column(Integer)
    sel_exp_ratio_mktg = Column(Integer)
    sel_avg_prem = Column(DECIMAL(18, 2))


class ChatMessage(Base):
    __tablename__ = f'{APP_NAME}_chatmessage'

    sequence_number = Column(Integer, primary_key=True, autoincrement=True)  # Auto-incrementing primary key
    timestamp = Column(DateTime)
    content = Column(Text)

    from_user_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    game_id = Column(String, ForeignKey(f'{APP_NAME}_indivgames.game_id'))

    # Relationships for foreign keys
    from_user = relationship("User", backref="from_user")  # This is equivalent to related_name in Django
    game = relationship("IndivGames", backref="chat_messages")  # This is equivalent to related_name in Django

    def __repr__(self):
        return f"<ChatMessage(sequence_number={self.sequence_number}, timestamp={self.timestamp}, from_user_id={self.from_user_id}, game_id={self.game_id}, content='{self.content}')>"
