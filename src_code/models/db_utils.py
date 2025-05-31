import pytz
from datetime import datetime, timedelta
from typing import List, Dict


def query_to_dict_list(session, model_class) -> List[Dict]:
    query_result = session.query(model_class).all()
    list_of_dicts = []

    for record in query_result:
        record_dict = {}
        for column in model_class.__table__.columns:
            record_dict[column.name] = getattr(record, column.name)
        list_of_dicts.append(record_dict)

    return list_of_dicts


def load_games(Session, IndivGames):
    session = Session()
    all_games = query_to_dict_list(session, IndivGames)
    session.close()
    return all_games


def load_players(game_id, Session, Players):
    session = Session()
    all_players = query_to_dict_list(session, Players)
    session.close()
    game_players = [player for player in all_players if player['game_id'] == game_id]
    return game_players


def load_decisions_locked(game_id, Session, Decisions, year):
    session = Session()
    all_decisions = query_to_dict_list(session, Decisions)
    session.close()

    game_decisions = [decision for decision in all_decisions if
                      decision['game_id'] == game_id and decision['year'] == year]

    # Check if all players have decisions_locked == True
    if all(decision['decisions_locked'] for decision in game_decisions):
        return game_decisions
    else:
        return []  # Return an empty list if the condition is not met


def load_decisions(game_id, Session, Decisions, year):
    session = Session()
    all_decisions = query_to_dict_list(session, Decisions)
    session.close()

    game_decisions = [decision for decision in all_decisions if
                      decision['game_id'] == game_id and decision['year'] == year]

    return game_decisions


def save_updated_decisions(game_id, Session, Decisions, year, decision_records):
    session = Session()

    for decision_record in decision_records:
        # Find the corresponding decision in the database by player_name
        db_record = (
            session.query(Decisions)
            .filter_by(game_id=game_id, player_name=decision_record['player_name'], year=year)
            .first()
        )

        if db_record:
            # Update the attributes with new values
            db_record.sel_profit_margin = decision_record['sel_profit_margin']
            db_record.sel_loss_trend_margin = decision_record['sel_loss_trend_margin']
            db_record.sel_exp_ratio_mktg = decision_record['sel_exp_ratio_mktg']
            db_record.sel_avg_prem = decision_record['sel_avg_prem']
            db_record.decisions_locked = decision_record['decisions_locked']

        # Commit the changes to the database
    session.commit()
    session.close()


def load_decisions_unlocked(game_id, Session, Decisions, year):
    session = Session()
    all_decisions = query_to_dict_list(session, Decisions)
    session.close()

    game_decisions = [decision for decision in all_decisions if
                      decision['game_id'] == game_id and decision['year'] == year and decision['decisions_locked'] is False]

    return game_decisions


def load_decisions_ns(game_id, Session, Decisionsns, year):
    session = Session()
    all_decisions = query_to_dict_list(session, Decisionsns)
    session.close()

    game_decisionsns = [decision for decision in all_decisions if
                      decision['game_id'] == game_id and decision['year'] == year]

    return game_decisionsns


def update_status(game_id, Session, IndivGames, new_status):
    session = Session()
    game = session.query(IndivGames).filter(IndivGames.game_id == game_id).first()
    game.status = new_status
    session.commit()
    session.close()


def update_mktgsales(config, game_id, player_id_id, player_name, year, financial_data):
    session = config.Session()
    if financial_data.in_force != 0:
        avg_prem = financial_data.ann_prem / financial_data.in_force
    else:
        avg_prem = 0
    mktg_data = config.MktgSales(
                     game_id=game_id,
                     player_id_id=player_id_id,
                     player_name=player_name,
                     year=year,
                     beg_in_force=financial_data.beg_in_force,
                     quotes=financial_data.quotes,
                     sales=financial_data.sales,
                     canx=financial_data.canx,
                     avg_prem=avg_prem,
                     mktg_expense=financial_data.mktg_var_expenses,
                     mktg_expense_ind=financial_data.mktg_var_expenses_ind,
                     end_in_force=financial_data.in_force,
                     in_force_ind=financial_data.in_force_ind,
                     )
    session.add(mktg_data)
    session.commit()
    session.close()


def update_financials(config, game_id, player_id_id, player_name, year, financial_data):
    session = config.Session()
    fin_data = config.Financials(
                    game_id=game_id,
                    player_id_id=player_id_id,
                    player_name=player_name,
                    year=year,
                    written_premium=financial_data.ann_prem,
                    in_force=financial_data.in_force,
                    inv_income=financial_data.invest_income,
                    annual_expenses=financial_data.annual_expenses,
                    ay_losses=financial_data.ay_losses,
                    py_devl=financial_data.py_devl,
                    clm_bi=financial_data.clm_bi,
                    clm_cl=financial_data.clm_cl,
                    profit=financial_data.profit,
                    dividend_paid=financial_data.dividend_paid,
                    capital=financial_data.capital,
                    capital_ratio=financial_data.mct_ratio,
                    capital_test=financial_data.pass_capital_test,
                    )
    session.add(fin_data)
    session.commit()
    session.close()


def update_industry(config, game_id, player_id_id, player_name, year, financial_data):
    session = config.Session()
    ind_data = config.Industry(
                    game_id=game_id,
                    player_id_id=player_id_id,
                    player_name=player_name,
                    year=year,
                    written_premium=financial_data.ann_prem,
                    annual_expenses=financial_data.annual_expenses,
                    cy_losses=financial_data.cy_losses,
                    profit=financial_data.profit,
                    capital=financial_data.capital,
                    capital_ratio=financial_data.mct_ratio,
                    capital_test=financial_data.pass_capital_test,
                    )
    session.add(ind_data)
    session.commit()
    session.close()


def update_valuation(config, game_id, player_id_id, player_name, year, financial_data):
    session = config.Session()
    val_data = config.Valuation(
                                game_id=game_id,
                                player_id_id=player_id_id,
                                player_name=player_name,
                                year=year,
                                beg_in_force=financial_data.beg_in_force,
                                in_force=financial_data.in_force,
                                start_capital=financial_data.start_capital,
                                excess_capital=(financial_data.excess_capital-financial_data.dividend_paid),
                                capital=financial_data.capital,
                                dividend_paid=financial_data.dividend_paid,
                                profit=financial_data.profit,
                                pv_index=config.mkt_features['pv_index'],
                                inv_rate=config.mkt_features['inv_rate'],
                                irr_rate=config.mkt_features['irr_rate'],
                                )
    session.add(val_data)
    session.commit()
    session.close()


def update_triangles(config, game_id, player_id_id, player_name, year, claim_triangles):
    if claim_triangles['triangles'] is None:
        return
    session = config.Session()
    tri_data = config.Triangles(
                                game_id=game_id,
                                player_id_id=player_id_id,
                                player_name=player_name,
                                year=year,
                                triangles=claim_triangles,
                                )
    session.add(tri_data)
    session.commit()
    session.close()


def update_claimtrends(config, game_id, year, claim_trends):
    session = config.Session()
    ct_data = config.ClaimTrends(
                                 game_id=game_id,
                                 year=year,
                                 claim_trends=claim_trends,
    )
    session.add(ct_data)
    session.commit()
    session.close()


def update_indications(config, game_id, player_id_id, player_name, year, time_limit_minutes, indication_data):
    if indication_data is None:
        return
    session = config.Session()
    indic_data = config.Indications(
                                    game_id=game_id,
                                    player_id_id=player_id_id,
                                    player_name=player_name,
                                    year=year,
                                    indication_data=indication_data,
    )
    session.add(indic_data)
    session.commit()
    session.close()


def update_decisions(config, game_id, player_id_id, player_name, year, decision_data, curr_avg_prem, sel_avg_prem, decisions, time_stamp, game_stage):
    session = config.Session()

    dec_data = config.Decisions(
                                game_id=game_id,
                                player_id_id=player_id_id,
                                player_name=player_name,
                                year=year,
                                sel_aa_margin=decision_data.sel_aa_margin,
                                sel_aa_margin_min=decision_data.sel_aa_margin_min,
                                sel_aa_margin_max=decision_data.sel_aa_margin_max,
                                sel_exp_ratio_mktg=decisions['sel_exp_ratio_mktg'],
                                sel_exp_ratio_mktg_min=decision_data.sel_exp_ratio_mktg_min,
                                sel_exp_ratio_mktg_max=decision_data.sel_exp_ratio_mktg_max,
                                sel_exp_ratio_data=decision_data.sel_exp_ratio_data,
                                sel_exp_ratio_data_min=decision_data.sel_exp_ratio_data_min,
                                sel_exp_ratio_data_max=decision_data.sel_exp_ratio_data_max,
                                sel_profit_margin=decisions['sel_profit_margin'],
                                sel_profit_margin_min=decision_data.sel_profit_margin_min,
                                sel_profit_margin_max=decision_data.sel_profit_margin_max,
                                sel_loss_trend_margin=decisions['sel_loss_trend_margin'],
                                sel_loss_trend_margin_min=decision_data.sel_loss_trend_margin_min,
                                sel_loss_trend_margin_max=decision_data.sel_loss_trend_margin_max,
                                curr_avg_prem=curr_avg_prem,
                                sel_avg_prem=sel_avg_prem,
                                decisions_locked=decisions['decisions_locked'],
                                decisions_game_stage=game_stage,
                                decisions_time_stamp=time_stamp,
                                )
    session.add(dec_data)
    session.commit()
    session.close()


def update_decisions_not_selected(config, game_id, player_id_id, player_name, year, sel_avg_prem_default, decisions_default):
    session = config.Session()
    dec_not_selected_data = config.Decisionsns(
                                game_id=game_id,
                                player_id_id=player_id_id,
                                player_name=player_name,
                                year=year,
                                sel_profit_margin=decisions_default['sel_profit_margin'],
                                sel_loss_trend_margin=decisions_default['sel_loss_trend_margin'],
                                sel_exp_ratio_mktg=decisions_default['sel_exp_ratio_mktg'],
                                sel_avg_prem=sel_avg_prem_default,
                                )
    session.add(dec_not_selected_data)
    session.commit()
    session.close()


def write_message(config, game_id, msg):
    session = config.Session()
    ny_time = datetime.now(pytz.timezone('America/New_York'))
    message = config.ChatMessage(
        from_user_id=None,
        game_id=game_id,
        content=msg,
        timestamp=ny_time,
    )
    session.add(message)
    session.commit()
    session.close()


def test_sql(Session, Players):
    session = Session()
    all_players_records = session.query(Players).all()

    # Convert to list of dictionaries
    all_players_list = [{
        'id': record.id,
        'game_id': record.game_id,
        'player_id_id': record.player_id_id,
        'player_name': record.player_name,
        'player_id_display': record.player_id_display,
        'player_type': record.player_type,
        'profile': record.profile
    } for record in all_players_records]

    for player in all_players_list:
        print(player)

    session.close()


def get_game_difficulty(config, game_id):
    """Get the game difficulty setting from the game initiator's preferences"""
    session = config.Session()
    
    # Get the game to find the initiator
    game = session.query(config.IndivGames).filter_by(game_id=game_id).first()
    if not game:
        session.close()
        return 'Novice'  # Default fallback
    
    # Get the initiator's game preferences
    game_prefs = session.query(config.GamePrefs).filter_by(user_id=game.initiator_id).first()
    session.close()
    
    if game_prefs and game_prefs.game_difficulty:
        return game_prefs.game_difficulty
    else:
        return 'Novice'  # Default fallback
