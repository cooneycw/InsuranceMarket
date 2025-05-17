import ast
import redis
from config_secrets import get_secrets, DEV
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src_code.models.models import IndivGames, Players, MktgSales, Financials, Industry, Valuation, Triangles, ClaimTrends, Indications, Decisions, Decisionsns, ChatMessage


class Config:
    def __init__(self, verbosity=False):
        self.redis_host = '192.168.5.156'
        self.redis_port = 6379
        self.redis_db = 0
        self.redis_obj = redis.StrictRedis(host=self.redis_host, port=self.redis_port, db=self.redis_db)
        self.flush_db = True
        if self.flush_db:
            self.redis_obj.flushdb()
        self.secret_dict = ast.literal_eval(get_secrets())
        self.clients = 200000
        self.companies = 6
        self.init_years = 5
        self.sim_years = 35
        self.curr_year = 2025
        self.orig_year = self.curr_year - self.init_years
        self.end_year = self.curr_year + self.sim_years
        # market
        self.mkt_features = dict()
        self.mkt_features['trend_cl'] = 1.0
        self.mkt_features['capital_ratio_prem_init'] = 1.5
        self.mkt_features['sel_loss_trend_margin_init'] = 0.0
        self.mkt_features['indic_wts'] = [.25, .25, .20, .15, .15]
        self.mkt_features['pv_index'] = 1.00
        self.mkt_features['inv_rate'] = 0.03
        self.mkt_features['div_ratio'] = 0.10
        self.mkt_features['devl_years'] = 2
        self.mkt_features['indic_years'] = 5
        self.mkt_features['expense_inflation'] = 0.02
        self.mkt_features['expense_inflation_var'] = 0.005
        self.mkt_features['claim_triangle_years'] = 5
        self.mkt_features['claim_infl_cl_init'] = 0.03
        self.mkt_features['claim_infl_bi_init'] = 0.045
        self.mkt_features['claim_infl_cl_drift'] = 0.03
        self.mkt_features['claim_infl_bi_drift'] = 0.05
        self.mkt_features['claim_shock_prob'] = 0.225
        self.mkt_features['claim_shock_infl_cl'] = 0.03
        self.mkt_features['claim_shock_infl_bi'] = 0.04
        self.mkt_features['claim_shock_infl_var'] = 0.01
        self.mkt_features['claim_reform_prob'] = 0.9
        self.mkt_features['claim_reform_threshold'] = 0.07
        self.mkt_features['claim_reform_infl_cl'] = -0.06
        self.mkt_features['claim_reform_infl_bi'] = -0.15
        self.mkt_features['claim_reform_infl_var'] = 0.02
        self.mkt_features['claim_autoreg_cl'] = 0.10
        self.mkt_features['claim_autoreg_bi'] = 0.10
        self.mkt_features['claim_epsilon'] = 0.10
        self.mkt_features['prem_init'] = 1525
        self.mkt_features['renewal_prem_infl_init'] = 0.02
        self.mkt_features['shop_base'] = 0.28 # was 0.35 originally
        self.mkt_features['shop_slpe'] = -6.0 # was -8.0 originally
        self.mkt_features['shop_sens'] = 2.0
        self.mkt_features['lottery_mult'] = 2.9
        self.mkt_features['lottery_prem_wt'] = 0.025
        self.mkt_features['price_srvc'] = 0.35 # was 0.25
        self.mkt_features['price_sens'] = 0.2 # was 0.2
        self.mkt_features['irr_rate'] = 0.105
        # client
        self.client_features = dict()
        self.client_features['credit_prop'] = 0.30
        self.client_features['terr_prop'] = 0.20
        self.client_features['terr_chg_min'] = 0.005
        self.client_features['terr_chg_max'] = 0.015
        self.client_features['credit_chg_min'] = 0.005
        self.client_features['credit_chg_max'] = 0.025
        # expenses
        self.init_expenses = dict()
        self.init_expenses['exp_fixed'] = 0.085
        self.init_expenses['init_clients'] = self.clients
        self.init_expenses['exp_fixed_lrg_scale'] = 0.5
        self.init_expenses['exp_fixed_sml_scale'] = 5
        self.init_expenses['exp_fixed_sml_size'] = 0.5
        self.init_expenses['exp_fixed_lrg_size'] = 5
        self.init_expenses['exp_expos'] = 15
        self.init_expenses['exp_ratio_prem'] = 0.15
        # claim
        self.claim_features = dict()
        self.claim_features['freq_cl'] = 0.055
        self.claim_features['freq_red_cl_credit'] = 0.25
        self.claim_features['freq_red_cl_terr'] = 0.20
        self.claim_features['freq_red_cl_credit_terr'] = 0.30
        self.claim_features['freq_bi'] = 0.0028
        self.claim_features['freq_red_bi_credit'] = 0.35
        self.claim_features['freq_red_bi_terr'] = 0.15
        self.claim_features['freq_red_bi_credit_terr'] = 0.40
        self.claim_features['sev_cl'] = 10750
        self.claim_features['sev_cl_coeff_of_var'] = 1.6
        self.claim_features['sev_bi'] = 168500
        self.claim_features['sev_bi_coeff_of_var'] = 1.212
        self.claim_features['sev_limit'] = 1000000
        # reserving
        self.resv_features = dict()
        self.resv_features['paid_cl'] = [0.4, 0.6, 1.0]
        self.resv_features['paid_cl_var'] = 0.05
        self.resv_features['paid_bi'] = [0.15, 0.35, 0.6]
        self.resv_features['paid_bi_var'] = 0.05
        self.resv_features['closed_cl'] = 0.75
        self.resv_features['closed_cl_var'] = 0.05
        self.resv_features['resv_cl_var'] = 0.14
        self.resv_features['resv_bi_var'] = 0.18
        self.resv_features['resv_cl_var_limit'] = 0.18
        self.resv_features['resv_bi_var_limit'] = 0.35
        self.resv_features['pfad_cl'] = 0.03
        self.resv_features['pfad_bi'] = 0.1
        # regulatory
        self.reg_features = dict()
        self.reg_features['mct_upr'] = 0.3
        self.reg_features['mct_resv'] = 0.2
        self.reg_features['mct_capital_reqd'] = 1.8
        self.reg_features['mct_minimum'] = 1.0
        # default decisions
        self.init_decisions = dict()
        self.init_decisions['sel_aa_margin'] = 15
        self.init_decisions['sel_aa_margin_min'] = 8
        self.init_decisions['sel_aa_margin_max'] = 15

        self.init_decisions['sel_avg_prem'] = self.mkt_features['prem_init']
        self.init_decisions['sel_exp_ratio_mktg'] = 0
        self.init_decisions['sel_exp_ratio_mktg_min'] = 0
        self.init_decisions['sel_exp_ratio_mktg_max'] = 5

        self.init_decisions['sel_exp_ratio_data'] = 0
        self.init_decisions['sel_exp_ratio_data_min'] = 0
        self.init_decisions['sel_exp_ratio_data_max'] = 3

        self.init_decisions['sel_loss_trend_margin'] = 0
        self.init_decisions['sel_loss_trend_margin_min'] = -3
        self.init_decisions['sel_loss_trend_margin_max'] = 3

        self.init_decisions['sel_profit_margin_min'] = 0
        self.init_decisions['sel_profit_margin_init'] = 5
        self.init_decisions['sel_profit_margin_max'] = 8
        self.init_decisions['sel_profit_margin'] = self.init_decisions['sel_profit_margin_init']

        self.DEV = DEV
        self.verbose = False
        if self.DEV == 'True':
            self.DEBUG = True
            self.verbose = True

        # print(self.secret_dict)
        self.POSTGRES_NAME = self.secret_dict['POSTGRES_DB']
        self.POSTGRES_USER = self.secret_dict['POSTGRES_USER']
        self.POSTGRES_PASSWORD = self.secret_dict['POSTGRES_PASSWORD']
        self.POSTGRES_PORT = self.secret_dict['POSTGRES_PORT']
        self.POSTGRES_HOST = self.secret_dict['POSTGRES_HOST']

        if self.DEBUG:
            self.POSTGRES_PORT = self.secret_dict['POSTGRES_PORT_DEV']
            self.POSTGRES_HOST = self.secret_dict['POSTGRES_HOST_DEV']

        self._db_url = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_NAME}"
        self.engine = create_engine(self._db_url)

        self.Session = sessionmaker(bind=self.engine)
        self.IndivGames = IndivGames
        self.Players = Players
        self.MktgSales = MktgSales
        self.Financials = Financials
        self.Industry = Industry
        self.Valuation = Valuation
        self.Triangles = Triangles
        self.ClaimTrends = ClaimTrends
        self.Indications = Indications
        self.Decisions = Decisions
        self.Decisionsns = Decisionsns  # ns = "not selected"
        self.ChatMessage = ChatMessage
