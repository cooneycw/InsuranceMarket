import pytz
import time
from datetime import datetime, timedelta
from copy import deepcopy
from src_code.admin.admin import Admin
from src_code.models.db_utils import load_players, update_status, load_decisions, load_decisions_unlocked, load_decisions_locked, load_decisions_ns, save_updated_decisions, update_mktgsales, update_financials, update_industry, update_valuation, update_indications, update_decisions, update_decisions_not_selected, update_triangles, update_claimtrends, get_game_difficulty
from src_code.game.game_utils import messages, process_indications
from src_code.market.market import Market


class Game:
    @staticmethod
    def get_current_time():
        current_time = datetime.now(pytz.UTC)
        return current_time

    def __init__(self, config, game_id, game_parameters):
        self.game_id = game_id
        self.time_limit_minutes = 12.0
        self.config = config
        self.market = None
        self.game_parameters = game_parameters
        self.pre_game_required = True
        self.orig_year = deepcopy(config.orig_year)
        self.curr_year = deepcopy(config.curr_year)
        self.players = load_players(self.game_id, self.config.Session, self.config.Players)
        self.game_admin = Admin(self.game_id, self.config.clients)
        self.decisions_time_stamp = None
        self.decisions_game_stage = None
        
        # Get game difficulty and set appropriate decision ranges
        self.game_difficulty = get_game_difficulty(config, game_id)
        self.decision_ranges = config.get_decisions_for_difficulty(self.game_difficulty)

    def update_game_stage(self):
        if self.curr_year < self.orig_year + self.config.init_years - 1:
            self.decisions_game_stage = 'pre-game'
        else:
            self.decisions_game_stage = 'decisions'

    def get_game_stage(self):
        return self.decisions_game_stage

    def update_time_stamp(self):
        current_time = self.get_current_time()
        future_time = current_time + timedelta(minutes=self.time_limit_minutes, seconds=10)
        decisions_time_stamp = dict()

        decisions_time_stamp['current_time'] = current_time.isoformat()
        decisions_time_stamp['future_time'] = future_time.isoformat()
        self.decisions_time_stamp = decisions_time_stamp

    def get_time_stamp(self):
        return self.decisions_time_stamp

    def start(self):
        update_status(self.game_admin.game_id, self.config.Session, self.config.IndivGames, new_status='running')
        messages(self.config, self.game_admin.game_id, f'Commencing game: {self.game_admin.game_id}')

        if self.pre_game_required:
            self.init_market()
            self.pre_game()

        # commence post pre-game logic here (i.e. await decisions and then begin execution).
        self.game_flow()

        update_status(self.game_id, self.config.Session, self.config.IndivGames, new_status='completed')
        messages(self.config, self.game_admin.game_id, f'Game Over: {self.game_admin.game_id}')

    def init_market(self):
        self.market = Market(self.game_admin.clients_per_company,
                             self.orig_year,
                             self.players,
                             self.config.mkt_features,
                             self.config.client_features,
                             self.config.init_expenses,
                             self.config.claim_features,
                             self.config.resv_features,
                             self.config.reg_features,
                             self.decision_ranges)
        self.market.init_capital(self.orig_year)
        self.market.process_mktg(self.orig_year)
        self.market.process_mktg_ind(self.orig_year)

    def game_flow(self):
        #  commence game once pre-processing of clients and claims is completed
        while self.curr_year < (self.config.orig_year + self.config.sim_years + self.config.init_years):
            time_stamp = self.get_time_stamp()
            deadline = datetime.fromisoformat(time_stamp['future_time'])
            decisions_received = False
            while deadline > self.get_current_time() and decisions_received is False:
                decision_records_locked = load_decisions_locked(self.game_id, self.config.Session, self.config.Decisions, self.curr_year-1)
                if not decision_records_locked:
                    time.sleep(5)
                else:
                    decisions_received = True

            decision_records = load_decisions(self.game_id, self.config.Session, self.config.Decisions, self.curr_year-1)
            if not decisions_received:  # time expired and decisions not received
                decision_records_unlocked = load_decisions_unlocked(self.game_id, self.config.Session, self.config.Decisions, self.curr_year-1)
                decision_records_ns = load_decisions_ns(self.game_id, self.config.Session, self.config.Decisionsns, self.curr_year-1)

                if len(decision_records_unlocked) > 0:
                    # Replace the unlocked decisions with decision_records_ns based on player_id_id equality
                    for i, decision_record in enumerate(decision_records):
                        if decision_record['decisions_locked'] is True:
                            continue
                        for ns_record in decision_records_ns:
                            if decision_record['player_name'] == ns_record['player_name']:
                                decision_records[i]['sel_profit_margin'] = ns_record['sel_profit_margin']
                                decision_records[i]['sel_loss_trend_margin'] = ns_record['sel_loss_trend_margin']
                                decision_records[i]['sel_exp_ratio_mktg'] = ns_record['sel_exp_ratio_mktg']
                                decision_records[i]['sel_avg_prem'] = ns_record['sel_avg_prem']
                                decision_records[i]['decisions_locked'] = True
                                break

            # update the market decision records (so that quotation and marketing can occur)
            save_updated_decisions(self.game_id, self.config.Session, self.config.Decisions, self.curr_year-1, decision_records)
            self.market.update_decisions(self.curr_year-1, decision_records)
            messages(self.config, self.game_id, f'Processing Decisions.  Simulating year: {self.curr_year}')
            print(f'process_post_decision_renewals: {self.curr_year}')
            self.market.process_post_decision_renewals(self.curr_year)
            self.market.process_mktg(self.curr_year)
            self.market.process_mktg_ind(self.curr_year)
            self.market.process_shopping(self.curr_year, self.decision_ranges['sel_exp_ratio_mktg_min'], self.decision_ranges['sel_exp_ratio_mktg_max'])
            self.market.process_in_force_ind(self.curr_year)
            self.market.process_claims(self.curr_year)
            self.market.process_financials(self.curr_year)
            self.market.process_in_force_ind(self.curr_year)
            financial_data = self.market.get_financials(self.curr_year)
            financial_indication_data = [None] * len(financial_data)

            fdos = [self.market.get_financials(yr) for yr in range(self.curr_year - 4, self.curr_year + 1, 1)]
            financial_indication_data = [[fdos[year_idx][player_idx][2].in_force for year_idx in range(len(fdos))] for player_idx in range(len(financial_data))]
            claims_data = self.market.get_claim_triangles(self.curr_year)
            indication_data = self.market.get_indications(self.curr_year)
            decision_data = self.market.get_decisions(self.curr_year)
            claim_trends = self.market.get_claim_trend()
            update_claimtrends(self.config, self.game_id, self.curr_year, claim_trends)
            self.update_time_stamp()
            self.update_game_stage()
            for player_i, player in enumerate(self.players):
                update_mktgsales(self.config, self.game_id, player['player_id_id'], player['player_name'], self.curr_year,
                                 financial_data[player_i][2])
                update_financials(self.config, self.game_id, player['player_id_id'], player['player_name'], self.curr_year,
                                  financial_data[player_i][2])
                update_industry(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                  self.curr_year,
                                  financial_data[player_i][2])
                update_valuation(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                 self.curr_year,
                                 financial_data[player_i][2])
                update_triangles(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                self.curr_year,
                                claims_data[player_i][2])
                update_indications(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                   self.curr_year, self.time_limit_minutes,
                                   indication_data[player_i][2])
                curr_avg_prem, sel_avg_prem, decisions = process_indications(self.config, self.game_id,
                                                                           player['player_id_id'], player['player_name'],
                                                                           player['player_type'], player['profile'],
                                                                           self.curr_year, self.config.orig_year,
                                                                           self.config.init_years,
                                                                           claim_trends,
                                                                           claims_data[player_i][2],
                                                                           financial_data[player_i][2],
                                                                           financial_indication_data[player_i],
                                                                           indication_data[player_i][2],
                                                                           decision_data[player_i][2],
                                                                           self.game_difficulty)
                update_decisions(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                 self.curr_year,
                                 decision_data[player_i][2], curr_avg_prem, sel_avg_prem, decisions,
                                 self.get_time_stamp(), self.get_game_stage())
                if player['player_type'] == 'user':
                    _, sel_avg_prem_default, decisions_default = process_indications(self.config, self.game_id,
                                                                                 player['player_id_id'],
                                                                                 player['player_name'],
                                                                                 player['player_type'],
                                                                                 player['profile'],
                                                                                 self.curr_year, self.config.orig_year,
                                                                                 self.config.init_years,
                                                                                 claim_trends,
                                                                                 claims_data[player_i][2],
                                                                                 financial_data[player_i][2],
                                                                                 financial_indication_data[player_i],
                                                                                 indication_data[player_i][2],
                                                                                 decision_data[player_i][2],
                                                                                 selected=False,
                                                                                 game_difficulty=self.game_difficulty)
                    update_decisions_not_selected(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                 self.curr_year,
                                 sel_avg_prem_default, decisions_default)
            self.update_curr_year()
            messages(self.config, self.game_id, f'Report data prepared for year: {self.curr_year-1}')
            for player_i, player in enumerate(self.players):
                if financial_data[player_i][2].pass_capital_test == 'Fail':
                    messages(self.config, self.game_id, f'OSFI reports company {player["player_name"]} is under investigation...')
            messages(self.config, self.game_id, f'Review decisions.')

    def pre_game(self):
        # initiate pre-game calculations to prepare data for game start (i.e. to enable actuarial calculations)
        self.curr_year = self.config.orig_year
        while self.curr_year < (self.config.orig_year + self.config.init_years):
            messages(self.config, self.game_id, f'Pre-processing year: {self.curr_year}')
            print(f'process_mktg: {self.curr_year}')
            self.market.process_mktg(self.curr_year)
            print(f'process_mktg_ind: {self.curr_year}')
            self.market.process_mktg_ind(self.curr_year)
            if self.curr_year != self.config.orig_year:
                print(f'process_shopping: {self.curr_year}')
                self.market.process_shopping(self.curr_year, self.decision_ranges['sel_exp_ratio_mktg_min'], self.decision_ranges['sel_exp_ratio_mktg_max'])
                self.market.process_in_force_ind(self.curr_year)
            print(f'process_claims: {self.curr_year}')
            self.market.process_claims(self.curr_year)
            print(f'process_financials: {self.curr_year}')
            self.market.process_financials(self.curr_year)
            self.market.process_in_force_ind(self.curr_year)
            financial_data = self.market.get_financials(self.curr_year)
            financial_indication_data = [None] * len(financial_data)
            if self.curr_year >= self.config.orig_year + self.config.init_years - 1:
                fdos = [self.market.get_financials(yr) for yr in range(self.curr_year - 4, self.curr_year + 1, 1)]
                financial_indication_data = [[fdos[year_idx][player_idx][2].in_force for year_idx in range(len(fdos))] for player_idx in range(len(financial_data))]
            claims_data = self.market.get_claim_triangles(self.curr_year)
            indication_data = self.market.get_indications(self.curr_year)
            decision_data = self.market.get_decisions(self.curr_year)

            # update Django dbase for market trends
            claim_trends = self.market.get_claim_trend()
            update_claimtrends(self.config, self.game_id, self.curr_year, claim_trends)
            # update Django dbase for player outcomes
            self.update_time_stamp()
            self.update_game_stage()
            for player_i, player in enumerate(self.players):
                update_mktgsales(self.config, self.game_id, player['player_id_id'], player['player_name'], self.curr_year,
                                 financial_data[player_i][2])
                update_financials(self.config, self.game_id, player['player_id_id'], player['player_name'], self.curr_year,
                                  financial_data[player_i][2])
                update_industry(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                  self.curr_year,
                                  financial_data[player_i][2])
                update_valuation(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                 self.curr_year,
                                 financial_data[player_i][2])
                update_triangles(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                self.curr_year,
                                claims_data[player_i][2])
                update_indications(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                   self.curr_year, self.time_limit_minutes,
                                   indication_data[player_i][2])
                curr_avg_prem, sel_avg_prem, decisions = process_indications(self.config, self.game_id,
                                                                           player['player_id_id'], player['player_name'],
                                                                           player['player_type'], player['profile'],
                                                                           self.curr_year, self.config.orig_year,
                                                                           self.config.init_years,
                                                                           claim_trends,
                                                                           claims_data[player_i][2],
                                                                           financial_data[player_i][2],
                                                                           financial_indication_data[player_i],
                                                                           indication_data[player_i][2],
                                                                           decision_data[player_i][2],
                                                                           self.game_difficulty)
                update_decisions(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                 self.curr_year,
                                 decision_data[player_i][2], curr_avg_prem, sel_avg_prem, decisions,
                                 self.get_time_stamp(), self.get_game_stage())
                if player['player_type'] == 'user':
                    _, sel_avg_prem_default, decisions_default = process_indications(self.config, self.game_id,
                                                                                 player['player_id_id'],
                                                                                 player['player_name'],
                                                                                 player['player_type'],
                                                                                 player['profile'],
                                                                                 self.curr_year, self.config.orig_year,
                                                                                 self.config.init_years,
                                                                                 claim_trends,
                                                                                 claims_data[player_i][2],
                                                                                 financial_data[player_i][2],
                                                                                 financial_indication_data[player_i],
                                                                                 indication_data[player_i][2],
                                                                                 decision_data[player_i][2],
                                                                                 selected=False,
                                                                                 game_difficulty=self.game_difficulty)
                    update_decisions_not_selected(self.config, self.game_id, player['player_id_id'], player['player_name'],
                                 self.curr_year,
                                 sel_avg_prem_default, decisions_default)
            messages(self.config, self.game_id, f'Report data prepared for year: {self.curr_year}')
            self.update_curr_year()

            if self.curr_year != (self.config.orig_year + self.config.init_years):
                print(f'process_pre_game_renewal: {self.curr_year}')
                self.market.process_pre_game_renewal(self.curr_year)

        self.end_pre_game()

    def end_pre_game(self):
        self.pre_game_required = False
        messages(self.config, self.game_id, f'Pre-processing complete.')
        messages(self.config, self.game_id, f'Review decisions.')

    def update_curr_year(self):
        self.curr_year += 1
        self.config.mkt_features['pv_index'] = self.config.mkt_features['pv_index'] * (1 + self.config.mkt_features['irr_rate'])

        print(f'process_expense_inflation: {self.curr_year}')
        self.market.process_expense_inflation(self.curr_year)
        print(f'process_claim_inflation: {self.curr_year}')
        self.market.process_claim_inflation(self.curr_year)
        if self.market.get_bi_reform(self.curr_year):
            messages(self.config, self.game_id, f'after observing {self.curr_year - 1} costs.')
            messages(self.config, self.game_id, f'Injury reform to address claim cost trends')
            messages(self.config, self.game_id, f'Government officials implement Bodily')
        if self.market.get_cl_reform(self.curr_year):
            messages(self.config, self.game_id, f'after observing {self.curr_year - 1} costs.')
            messages(self.config, self.game_id, f'product reform to address claim cost trends')
            messages(self.config, self.game_id, f'Government officials implement Collision')
        print(f'process_clients: {self.curr_year}')
        self.market.process_clients(self.curr_year)

