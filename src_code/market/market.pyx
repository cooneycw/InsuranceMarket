# market.pyx
import random
import pandas as pd
import numpy as np
import copy
import math
from libc.stdlib cimport rand, RAND_MAX
from libc.math cimport sqrt, log
from cpython.dict cimport PyDict_New, PyDict_SetItem


cdef int global_client_id = 0  # This acts as a static variable for the market class
cdef int global_claim_id = 0


cdef class ClientAnnualData:
    cdef public int year
    cdef public int pr_company
    cdef public int company
    cdef public int shop
    cdef public list quote_companies
    cdef public list quote_premiums
    cdef public double shop_prob
    cdef public int prclm_age12
    cdef public int prclm_age24
    cdef public int prclm_age36
    cdef public double annual_prem
    cdef public double renewal_prem
    cdef public double freq_cl
    cdef public double freq_bi
    cdef public double freq_ratio_bi_cl
    cdef public int client_terr
    cdef public int client_credit
    cdef public int client_terr_credit
    cdef public int clm_cnt_cl
    cdef public int clm_cnt_bi
    cdef public list claim_list

    def __init__(self, year, company, ann_prem, client_terr, client_credit, client_terr_credit, claim_features, claim_trend):
        self.year = year
        self.pr_company = -1
        self.company = company
        self.annual_prem = ann_prem
        self.client_terr = client_terr
        self.client_credit = client_credit
        self.client_terr_credit = client_terr_credit
        self.renewal_prem = 0
        self.quote_companies = list()
        self.quote_premiums = list()
        self.shop = 0
        self.shop_prob = 0
        self.prclm_age12 = 0
        self.prclm_age24 = 0
        self.prclm_age36 = 0

        self.freq_cl = claim_features['freq_cl']
        self.freq_bi = claim_features['freq_bi']
        if self.client_terr_credit == 1:
            self.freq_cl = self.freq_cl * (1 - claim_features['freq_red_cl_credit_terr'])
            self.freq_bi = self.freq_bi * (1 - claim_features['freq_red_bi_credit_terr'])
        elif self.client_terr == 1:
            self.freq_cl = self.freq_cl * (1 - claim_features['freq_red_cl_terr'])
            self.freq_bi = self.freq_bi * (1 - claim_features['freq_red_bi_terr'])
        elif self.client_credit == 1:
            self.freq_cl = self.freq_cl * (1 - claim_features['freq_red_cl_terr'])
            self.freq_bi = self.freq_bi * (1 - claim_features['freq_red_bi_credit'])

        self.freq_ratio_bi_cl = self.freq_bi / self.freq_cl

        self.claim_list = list()

        self.clm_cnt_cl = np.random.poisson(self.freq_cl)
        self.clm_cnt_bi = 0
        for i in range(self.clm_cnt_cl):
            self.clm_cnt_bi = random_indicator(self.freq_ratio_bi_cl)
            self.claim_list.append(ClaimData(year, self.clm_cnt_bi, claim_features, claim_trend))

    def update_prior_company(self, old_company):
        self.pr_company = old_company

    def update_company(self, new_company, new_ann_prem):
        self.company = new_company
        self.annual_prem = new_ann_prem

    def update_claim_indicators(self, claim_indic_12, claim_indic_24, claim_indic_36):
        if claim_indic_36 > 0:
            self.prclm_age36 = 1
        if claim_indic_24 > 0:
            self.prclm_age24 = 1
        if claim_indic_12 > 0:
            self.prclm_age12 = 1

    def update_renewal_prem(self, renewal_prem):
        self.renewal_prem = renewal_prem

    def generate_client_quote_packet(self, quote_level):
        quote_data = dict()
        quote_data['quote_level'] = quote_level

        if quote_level == 0:
            pass
        elif quote_level == 1:
            quote_data['prclm_age12'] = self.prclm_age12
            quote_data['prclm_age24'] = self.prclm_age24
            quote_data['prclm_age36'] = self.prclm_age36

        return quote_data

cdef class ClaimData:
    cdef public int clm_year
    cdef public int claim_id
    cdef public int clm_limit
    cdef public double clm_sev_cl
    cdef public double clm_sev_cl_coeff_of_var
    cdef public double clm_sev_bi
    cdef public double clm_sev_bi_coeff_of_var
    cdef public double clm_amt_cl
    cdef public double clm_amt_bi

    @staticmethod
    def increment_claim_id():
        global global_claim_id
        global_claim_id += 1

    @staticmethod
    def get_claim_id():
        ClaimData.increment_claim_id()
        return global_claim_id - 1

    def __init__(self, int year, int clm_bi, dict claim_features, claim_trend):
        self.claim_id = self.get_claim_id()
        self.clm_year = year
        self.clm_sev_cl = claim_features['sev_cl'] * claim_trend['cl_trend_ind'][year]
        self.clm_sev_cl_coeff_of_var = claim_features['sev_cl_coeff_of_var']
        self.clm_sev_bi = claim_features['sev_bi'] * claim_trend['bi_trend_ind'][year]
        self.clm_sev_bi_coeff_of_var = claim_features['sev_bi_coeff_of_var']
        self.clm_limit = claim_features['sev_limit']
        # simulate claim severities
        self.clm_amt_cl = simulate_claim(self.clm_sev_cl, self.clm_sev_cl_coeff_of_var, self.clm_limit)
        if clm_bi > 0:
            self.clm_amt_bi = simulate_claim(self.clm_sev_bi, self.clm_sev_bi_coeff_of_var, self.clm_limit)
        else:
            self.clm_amt_bi = 0

    def get_claim_data(self):
        ret_dict = dict()
        ret_dict['claim_id'] = self.claim_id
        ret_dict['clm_year'] = self.clm_year
        ret_dict['clm_amt_cl'] = self.clm_amt_cl
        ret_dict['clm_amt_bi'] = self.clm_amt_bi

        return ret_dict


cdef class Client:
    cdef public int client_id  # Using 'public' allows Python code to access this attribute
    cdef public int player_id
    cdef public dict init_client_features
    cdef public dict init_claim_features
    cdef public int init_client_terr
    cdef public int init_client_credit
    cdef public int init_client_terr_credit
    cdef public int client_terr
    cdef public int client_credit
    cdef public int client_terr_credit
    cdef public double terr_prop
    cdef public double credit_prop
    cdef public double terr_chg_min
    cdef public double terr_chg_max
    cdef public double credit_chg_min
    cdef public double credit_chg_max
    cdef public dict annual_data

    def __init__(self, int id, int player_id, int year, ann_prem, dict init_client_features, dict init_claim_features, dict claim_trend):
        self.client_id = id
        self.player_id = player_id
        self.annual_data = dict()
        self.init_client_features = init_client_features
        self.init_claim_features = init_claim_features
        self.terr_prop = init_client_features['terr_prop']
        self.terr_chg_min = init_client_features['terr_chg_min']
        self.terr_chg_max = init_client_features['terr_chg_max']
        self.credit_prop = init_client_features['credit_prop']
        self.credit_chg_min = init_client_features['credit_chg_min']
        self.credit_chg_max = init_client_features['credit_chg_max']
        self.init_client_terr = random_indicator(self.terr_prop)
        self.init_client_credit = random_indicator(self.credit_prop)
        self.init_client_terr_credit = self.init_client_terr * self.init_client_credit
        self.client_terr = copy.deepcopy(self.init_client_terr)
        self.client_credit = copy.deepcopy(self.init_client_credit)
        self.client_terr_credit = copy.deepcopy(self.init_client_terr_credit)
        obj = ClientAnnualData(year, player_id, ann_prem, self.client_terr, self.client_credit, self.client_terr_credit, init_claim_features, claim_trend)
        self.annual_data[year] = obj

    def age_clients(self, new_year, terr_chg, credit_chg):
        if self.client_terr == 0:
            self.client_terr = random_indicator(terr_chg)
        if self.client_credit == 1:
            self.client_credit = 1 - random_indicator(credit_chg)
        self.client_terr_credit = self.client_terr * self.client_credit

    def new_client_year(self, new_year, ann_prem, oco, claim_trend):
        old_company = oco.company
        if len(oco.claim_list) > 0:
            new_clm_age_12 = 1
        else:
            new_clm_age_12 = 0
        new_clm_age_24 = oco.prclm_age12
        new_clm_age_36 = oco.prclm_age24
        new_client_annual_obj = ClientAnnualData(new_year, self.player_id, ann_prem, self.client_terr, self.client_credit, self.client_terr_credit, self.init_claim_features, claim_trend)
        new_client_annual_obj.update_claim_indicators(new_clm_age_12, new_clm_age_24, new_clm_age_36)
        new_client_annual_obj.update_prior_company(old_company)
        self.annual_data[new_year] = new_client_annual_obj


cdef class ClientListData:
    cdef public int year
    cdef public set client_set

    def __init__(self, year):
        self.year = year
        self.client_set = set()

    def add_client_id_to_set(self, client_id):
        self.client_set.add(client_id)

    def remove_client_id_from_set(self, client_id):
        self.client_set.remove(client_id)

    def get_company_client_set(self):
        return self.client_set


cdef class CompanyFinancialData:
    cdef public int year
    cdef public int in_force
    cdef public int in_force_ind
    cdef public int beg_in_force
    cdef public int quotes
    cdef public int sales
    cdef public int canx
    cdef public str pass_capital_test
    cdef public double capital
    cdef public double start_capital
    cdef public double excess_capital
    cdef public double start_assets
    cdef public double ann_prem
    cdef public double ann_prem_prior
    cdef public double paid_losses
    cdef public double reserves
    cdef public double reserves_py
    cdef public double cy_losses
    cdef public double ay_losses
    cdef public double ay_losses_24
    cdef public double ay_losses_36
    cdef public double py_devl
    cdef public double total_losses
    cdef public double annual_expenses
    cdef public double stat_cap_reqd
    cdef public double mct_ratio
    cdef public double invest_income
    cdef public double dividend_paid
    cdef public double assets
    cdef public double liabilities

    cdef public double fixed_expenses
    cdef public double expos_var_expenses
    cdef public double mktg_var_expenses
    cdef public double mktg_var_expenses_ind
    cdef public double data_var_expenses
    cdef public double prem_var_expenses
    cdef public int clm_cl
    cdef public int clm_bi
    cdef public int closed_cl
    cdef public int closed_bi
    cdef public double paid_cl
    cdef public double paid_bi
    cdef public double resv_cl
    cdef public double resv_bi
    cdef public double resv_pfad_cl
    cdef public double resv_pfad_bi
    cdef public double profit
    cdef public int quote_level
    cdef public double expense_inflation_index

    def __init__(self, year, expense_inflation_index):
        self.year = year
        self.ann_prem = 0
        self.ann_prem_prior = 0
        self.beg_in_force = 0
        self.in_force = 0
        self.in_force_ind = 0
        self.quotes = 0
        self.sales = 0
        self.canx = 0
        self.capital = 0
        self.start_capital = 0
        self.excess_capital = 0
        self.stat_cap_reqd = 0
        self.start_assets = 0
        self.pass_capital_test = 'Fail'
        self.mct_ratio = 0
        self.dividend_paid = 0
        self.assets = 0
        self.liabilities = 0
        self.paid_losses = 0
        self.reserves = 0
        self.reserves_py = 0
        self.cy_losses = 0
        self.py_devl = 0
        self.ay_losses = 0
        self.fixed_expenses = 0
        self.expos_var_expenses = 0
        self.mktg_var_expenses = 0
        self.mktg_var_expenses_ind = 0
        self.data_var_expenses = 0
        self.prem_var_expenses = 0
        self.annual_expenses = 0
        self.invest_income = 0
        self.profit = 0
        self.clm_cl = 0
        self.clm_bi = 0
        self.paid_cl = 0
        self.paid_bi = 0
        self.resv_cl = 0
        self.resv_bi = 0
        self.resv_pfad_cl = 0
        self.resv_pfad_bi = 0
        self.quote_level = 0
        self.expense_inflation_index = expense_inflation_index

cdef class CompanyDecisionData:
    cdef public int year
    cdef public bint locked
    cdef public int sel_aa_margin
    cdef public int sel_aa_margin_min
    cdef public int sel_aa_margin_max
    cdef public int sel_exp_ratio_mktg
    cdef public int sel_exp_ratio_mktg_min
    cdef public int sel_exp_ratio_mktg_max
    cdef public int sel_exp_ratio_data
    cdef public int sel_exp_ratio_data_min
    cdef public int sel_exp_ratio_data_max
    cdef public int sel_loss_trend_margin
    cdef public int sel_loss_trend_margin_min
    cdef public int sel_loss_trend_margin_max
    cdef public int sel_profit_margin
    cdef public int sel_profit_margin_min
    cdef public int sel_profit_margin_max
    cdef public double sel_avg_prem

    def __init__(self, int year, dict init_decisions):
        self.year = year
        self.sel_aa_margin = init_decisions['sel_aa_margin']
        self.sel_aa_margin_min = init_decisions['sel_aa_margin_min']
        self.sel_aa_margin_max = init_decisions['sel_aa_margin_max']
        self.sel_exp_ratio_mktg = init_decisions['sel_exp_ratio_mktg']
        self.sel_exp_ratio_mktg_min = init_decisions['sel_exp_ratio_mktg_min']
        self.sel_exp_ratio_mktg_max = init_decisions['sel_exp_ratio_mktg_max']
        self.sel_exp_ratio_data = init_decisions['sel_exp_ratio_data']
        self.sel_exp_ratio_data_min = init_decisions['sel_exp_ratio_data_min']
        self.sel_exp_ratio_data_max = init_decisions['sel_exp_ratio_data_max']
        self.sel_loss_trend_margin = init_decisions['sel_loss_trend_margin']
        self.sel_loss_trend_margin_min = init_decisions['sel_loss_trend_margin_min']
        self.sel_loss_trend_margin_max = init_decisions['sel_loss_trend_margin_max']
        self.sel_profit_margin = init_decisions['sel_profit_margin']
        self.sel_profit_margin_min = init_decisions['sel_profit_margin_min']
        self.sel_profit_margin_max = init_decisions['sel_profit_margin_max']
        self.sel_avg_prem = init_decisions['sel_avg_prem']
        self.locked=False

    def set_sel_avg_prem(self, calc_sel_avg_prem):
        self.sel_avg_prem = calc_sel_avg_prem

    def lock_decisions(self):
        self.locked=True

    def get_sel_exp_ratio_mktg(self):
        # print(f'self.year: {self.year}  self.sel_exp_ratio_mktg: {self.sel_exp_ratio_mktg}')
        return self.sel_exp_ratio_mktg

    def set_sel_exp_ratio_mktg(self, sel_exp_ratio_mktg):
        self.sel_exp_ratio_mktg = sel_exp_ratio_mktg

    def set_sel_profit_margin(self, sel_profit_margin):
        self.sel_profit_margin = sel_profit_margin

    def set_sel_loss_trend_margin(self, sel_loss_trend_margin):
        self.sel_loss_trend_margin = sel_loss_trend_margin

    def set_sel_avg_prem(self, sel_avg_prem):
        self.sel_avg_prem = sel_avg_prem


cdef class CompanyClaimData:
    cdef public int cal_year
    cdef public int acc_year
    cdef public int client_id
    cdef public int claim_id
    cdef public int clm_age_yrs
    cdef public int clm_age_mths
    cdef public int clm_cl
    cdef public int clm_bi
    cdef public int closed_cl
    cdef public int closed_bi
    cdef public double paid_ratio_cl
    cdef public double paid_ratio_bi
    cdef public double paid_cl
    cdef public double paid_bi
    cdef public double resv_cl_est
    cdef public double resv_bi_est
    cdef public double resv_cl
    cdef public double resv_bi
    cdef public double resv_pfad_cl
    cdef public double resv_pfad_bi
    cdef public dict claim_data

    def __init__(self, int year, int client_id, int claim_id, sel_aa_margin, dict resv_features, dict claim_data):
        self.cal_year = year
        self.client_id = client_id
        self.claim_id = claim_id
        self.acc_year = claim_data['clm_year']
        self.clm_age_yrs = (self.cal_year - self.acc_year) + 1
        self.clm_age_mths = self.clm_age_yrs * 12
        if claim_data['clm_amt_cl'] > 0:
            self.clm_cl = 1
        else:
            self.clm_cl = 0
        if claim_data['clm_amt_bi'] > 0:
            self.clm_bi = 1
        else:
            self.clm_bi = 0

        if self.clm_age_mths == 12:
            closed_cl_test = max(0.01, trunc_normal_c(resv_features['closed_cl'], resv_features['closed_cl_var'], 0.99999))
            self.closed_cl = self.clm_cl * random_indicator(closed_cl_test)
            self.closed_bi = 0
        elif self.clm_age_mths == 24:
            self.closed_cl = self.clm_cl
            self.closed_bi = 0
        elif self.clm_age_mths == 36:
            self.closed_cl = 1
            self.closed_bi = self.clm_bi

        if self.closed_cl == 0:
            self.paid_ratio_cl = max(0.01, trunc_normal_c(resv_features['paid_cl'][self.clm_age_yrs - 1], resv_features['paid_cl_var'], 0.98))
            self.paid_cl = self.paid_ratio_cl * claim_data['clm_amt_cl']
            self.resv_cl_est = max(0.01, trunc_normal_c(1, resv_features['resv_cl_var'], 2))
            self.resv_cl = (1 - self.paid_ratio_cl) * self.resv_cl_est * claim_data['clm_amt_cl']
        else:
            self.paid_ratio_cl = 1
            self.paid_cl = claim_data['clm_amt_cl']
            self.resv_cl_est = 0
            self.resv_cl = 0

        if self.closed_bi == 0 and self.clm_bi == 1:
            self.paid_ratio_bi = max(0.01, trunc_normal_c(resv_features['paid_bi'][self.clm_age_yrs - 1], resv_features['paid_bi_var'], 1))
            self.paid_bi = self.paid_ratio_bi * claim_data['clm_amt_bi']
            self.resv_bi_est = max(0.01, trunc_normal_c(1, resv_features['resv_bi_var'], 2))
            self.resv_bi = (1 - self.paid_ratio_bi) * self.resv_bi_est * claim_data['clm_amt_bi']
        else:
            self.paid_ratio_bi = 1
            self.paid_bi = claim_data['clm_amt_bi']
            self.resv_bi_est = 0
            self.resv_bi = 0

        self.resv_cl = (1 + 0.01 * sel_aa_margin) * self.resv_cl
        self.resv_bi = (1 + 0.01 * sel_aa_margin) * self.resv_bi
        self.resv_pfad_cl = resv_features['pfad_cl'] * self.resv_cl
        self.resv_pfad_bi = resv_features['pfad_bi'] * self.resv_bi
        self.claim_data = claim_data

    def print_claim_reserves(self):
        print(f'claim_id: {self.claim_id} age: {self.clm_age_yrs} paid_cl: {self.paid_cl} resv_cl: {self.resv_cl} pfad_cl: {self.resv_pfad_cl} paid_bi: {self.paid_bi} resv_bi: {self.resv_bi} resv_pfad: {self.resv_pfad_bi}')

cdef class Company:
    cdef public int player_id
    cdef public str player_name
    cdef public str player_type
    cdef public str player_profile
    cdef public int orig_year
    cdef public dict annual_data
    cdef public dict mkt_features
    cdef public dict init_expenses
    cdef public dict resv_features
    cdef public dict reg_features
    cdef public dict init_decisions
    cdef public object get_client_from_market

    def __init__(self, int player_id, str player_name, str player_type, str player_profile, get_client_obj_method, int orig_year, dict mkt_features, dict init_expenses, dict resv_features, dict reg_features, dict init_decisions, expense_inflation_index):
        self.player_id = player_id
        self.player_name = player_name
        self.player_type = player_type
        self.player_profile = player_profile
        self.get_client_from_market = get_client_obj_method
        self.orig_year = orig_year
        self.annual_data = dict()
        self.mkt_features = mkt_features
        self.init_expenses = init_expenses
        self.resv_features = resv_features
        self.reg_features = reg_features
        self.init_decisions = init_decisions
        self.annual_data[orig_year] = dict()
        self.annual_data[orig_year]['client_list_data'] = ClientListData(orig_year)
        self.annual_data[orig_year]['financial_data'] = CompanyFinancialData(orig_year, expense_inflation_index)
        self.annual_data[orig_year]['claim_data'] = list()
        self.annual_data[orig_year]['claim_triangle_data'] = None
        self.annual_data[orig_year]['indication_data'] = None
        # print(f'init {self.player_name}  orig_year: {orig_year}')
        self.annual_data[orig_year]['decision_data'] = CompanyDecisionData(orig_year, init_decisions)

    def update_annual_data(self, year, expense_inflation_index):
        new_year = year + 1
        old_client_set = copy.deepcopy(self.annual_data[year]['client_list_data'].get_company_client_set())
        self.annual_data[new_year] = dict()
        self.annual_data[new_year]['client_list_data'] = ClientListData(new_year)
        self.annual_data[new_year]['client_list_data'].client_set = old_client_set
        self.annual_data[new_year]['financial_data'] = CompanyFinancialData(new_year, expense_inflation_index)
        self.annual_data[new_year]['claim_data'] = list()
        self.annual_data[new_year]['claim_triangle_data'] = None
        self.annual_data[new_year]['indication_data'] = None
        # print(f'update_annual_data - {self.player_name}  year: {year}  new_year:{new_year}')
        self.annual_data[new_year]['decision_data'] = CompanyDecisionData(new_year, self.init_decisions)
        # update balance sheet (fdo = financial_data_object)
        old_fdo = self.annual_data[year]['financial_data']
        new_fdo = self.annual_data[new_year]['financial_data']
        new_fdo.ann_prem_prior = old_fdo.ann_prem
        new_fdo.start_capital = old_fdo.capital
        new_fdo.start_assets = old_fdo.assets
        new_fdo.reserves_py = old_fdo.reserves
        new_fdo.beg_in_force = old_fdo.in_force
        # update decision data (ddo = decision_data_object)
        new_ddo = self.annual_data[new_year]['decision_data']
        new_ddo.sel_avg_prem = self.init_decisions['sel_avg_prem']

    def add_company_client(self, year, client_id):
        self.annual_data[year]['client_list_data'].add_client_id_to_set(client_id)

    def remove_company_client(self, year, client_id):
        self.annual_data[year]['client_list_data'].remove_client_id_from_set(client_id)

    def process_init_capital(self, year):
        capital_ratio = self.mkt_features['capital_ratio_prem_init']
        prem_init = self.mkt_features['prem_init']
        financial_data_obj = self.annual_data[year]['financial_data']
        client_set = self.annual_data[year]['client_list_data'].client_set
        start_capital = prem_init / self.mkt_features['capital_ratio_prem_init']

        financial_data_obj.ann_prem_prior = prem_init * len(client_set)
        financial_data_obj.beg_in_force = len(client_set)
        financial_data_obj.start_capital = start_capital * len(client_set)
        financial_data_obj.start_assets = start_capital * len(client_set)

    def update_decisions(self, year, decisions):
        decision_obj = self.annual_data[year]['decision_data']
        decision_obj.set_sel_exp_ratio_mktg(decisions['sel_exp_ratio_mktg'])
        decision_obj.set_sel_profit_margin(decisions['sel_profit_margin'])
        decision_obj.set_sel_loss_trend_margin(decisions['sel_loss_trend_margin'])
        decision_obj.set_sel_avg_prem(decisions['sel_avg_prem'])
        decision_obj.lock_decisions()

    def process_mktg(self, year):
        old_year = year - 1
        annual_data = self.annual_data.get(old_year, None)
        if annual_data is None:
            exp_ratio_mktg = 0
        else:
            decision_obj = annual_data['decision_data']
            exp_ratio_mktg = decision_obj.get_sel_exp_ratio_mktg()
        financial_data_obj = self.annual_data[year]['financial_data']
        # print(f'process_mktg {self.player_name} - year: {year} exp_ratio_mktg: {exp_ratio_mktg} ann_prem_prior: {financial_data_obj.ann_prem_prior}')
        financial_data_obj.mktg_var_expenses = (.001 * exp_ratio_mktg) * financial_data_obj.ann_prem_prior

    def get_company_quote_level(self, year):
        financial_data_obj = self.annual_data[year]['financial_data']
        return financial_data_obj.quote_level

    def record_quote(self, year):
        financial_data_obj = self.annual_data[year]['financial_data']
        financial_data_obj.quotes += 1

    def record_sale(self, year):
        financial_data_obj = self.annual_data[year]['financial_data']
        financial_data_obj.sales += 1

    def record_canx(self, year):
        financial_data_obj = self.annual_data[year]['financial_data']
        financial_data_obj.canx += 1

    def get_mktg_spend_company(self, year):
        financial_data_obj = self.annual_data[year]['financial_data']
        return financial_data_obj.mktg_var_expenses

    def get_ann_prem_prior_company(self, year):
        financial_data_obj = self.annual_data[year]['financial_data']
        return financial_data_obj.ann_prem_prior

    def get_mktg_spend_ind(self, year):
        financial_data_obj = self.annual_data[year]['financial_data']
        return financial_data_obj.mktg_var_expenses_ind

    def process_mktg_ind(self, year, mktg_spend_ind):
        financial_data_obj = self.annual_data[year]['financial_data']
        financial_data_obj.mktg_var_expenses_ind = mktg_spend_ind

    def process_claim_reserves(self, year, sel_aa_margin, resv_features):
        number_of_acc_yrs = self.mkt_features['devl_years'] + 1
        acc_years = [year - x for x in range(number_of_acc_yrs)]
        # print(f'clm_years: {clm_years} year: {year} number_of_clm_yrs: {number_of_clm_yrs}')
        for acc_year in acc_years:
            # Check if acc_year is less than the processing year.
            if acc_year < year and (year - acc_year) < number_of_acc_yrs:
                self.update_claim_reserves(acc_year, year, sel_aa_margin, resv_features, number_of_acc_yrs)
            elif acc_year == year:
                client_set = self.annual_data[year]['client_list_data'].get_company_client_set()
                for client_id in client_set:
                    client_obj = self.get_client_from_market(client_id)
                    claim_list = client_obj.annual_data[year].claim_list
                    for claim in claim_list:
                        clm_obj = CompanyClaimData(year, client_id, claim.claim_id, sel_aa_margin, resv_features, claim.get_claim_data())
                        self.annual_data[year]['claim_data'].append(clm_obj)

    def update_claim_reserves(self, acc_year, year, sel_aa_margin, resv_features, number_of_acc_yrs):
        annual_data = self.annual_data.get(acc_year, None)
        if annual_data is None:
            pass
        else:
            clm_list = self.annual_data[acc_year]['claim_data']
            for clm in clm_list:
                if (year - clm.acc_year) < number_of_acc_yrs:
                    # print(f'clm: {year} {acc_year} {clm.clm_age_yrs} {clm.claim_id} {clm.client_id} {clm.claim_data} {clm.acc_year}')
                    # clm.print_claim_reserves()
                    if (year - clm.acc_year) == clm.clm_age_yrs:
                        clm_obj = CompanyClaimData(year, clm.client_id, clm.claim_id, sel_aa_margin, resv_features, clm.claim_data)
                        # clm_obj.print_claim_reserves()
                        self.annual_data[year]['claim_data'].append(clm_obj)

    def claim_financial_summary(self, int year):
        devl_years = self.mkt_features['devl_years']
        number_of_acc_yrs = devl_years + 1
        acc_years = [year - x for x in range(number_of_acc_yrs)]
        #print(f'year: {year} acc_years: {acc_years}')

        claim_data_list_curr_yr = self.annual_data[year]['claim_data']
        claim_data_list_prior_yr = None

        financial_data_obj = self.annual_data[year]['financial_data']

        test_prior_yr = self.annual_data.get(year-1)

        # Aggregate claim data
        for claim_data in claim_data_list_curr_yr:
            if (claim_data.cal_year == year) and (claim_data.acc_year == year):
                # print(f'adding ay...{year} claim_data.cal_year: {claim_data.cal_year} claim_data.acc_year: {claim_data.acc_year}')
                # print(f'{claim_data.claim_id} {claim_data.clm_age_yrs} {claim_data.paid_cl} {claim_data.paid_bi} {claim_data.resv_cl} {claim_data.resv_bi} {claim_data.resv_pfad_cl} {claim_data.resv_pfad_bi}')
                financial_data_obj.clm_cl += claim_data.clm_cl
                financial_data_obj.clm_bi += claim_data.clm_bi
                financial_data_obj.paid_cl += claim_data.paid_cl
                financial_data_obj.paid_bi += claim_data.paid_bi
                financial_data_obj.resv_cl += claim_data.resv_cl
                financial_data_obj.resv_bi += claim_data.resv_bi
                financial_data_obj.resv_pfad_cl += claim_data.resv_pfad_cl
                financial_data_obj.resv_pfad_bi += claim_data.resv_pfad_bi

        financial_data_obj.paid_losses = (financial_data_obj.paid_cl +
                                             financial_data_obj.paid_bi)

        financial_data_obj.reserves = (financial_data_obj.resv_cl +
                                          financial_data_obj.resv_bi +
                                          financial_data_obj.resv_pfad_cl +
                                          financial_data_obj.resv_pfad_bi
                                          )

        financial_data_obj.ay_losses = (financial_data_obj.paid_losses +
                                        financial_data_obj.reserves)

        # print(f'year: {year} number_of_acc_years: {number_of_acc_yrs}')
        for claim_data in claim_data_list_curr_yr:
            if (claim_data.cal_year == year) and (claim_data.acc_year < year) and (claim_data.acc_year > (year - number_of_acc_yrs)):
                # print(f'adding...py {year} claim_data.cal_year: {claim_data.cal_year} claim_data.acc_year: {claim_data.acc_year}')
                # print(f'{claim_data.claim_id} {claim_data.clm_age_yrs} {claim_data.paid_cl} {claim_data.paid_bi} {claim_data.resv_cl} {claim_data.resv_bi} {claim_data.resv_pfad_cl} {claim_data.resv_pfad_bi}')
                financial_data_obj.py_devl += claim_data.paid_cl
                financial_data_obj.py_devl += claim_data.paid_bi
                financial_data_obj.py_devl += claim_data.resv_cl
                financial_data_obj.py_devl += claim_data.resv_bi
                financial_data_obj.py_devl += claim_data.resv_pfad_cl
                financial_data_obj.py_devl += claim_data.resv_pfad_bi

        if test_prior_yr is None:
            pass
        else:
            claim_data_list_prior_yr = test_prior_yr['claim_data']
            for claim_data in claim_data_list_prior_yr:
                if (claim_data.cal_year == (year - 1)) and (claim_data.acc_year < year and (claim_data.acc_year > (year - number_of_acc_yrs))):
                    # print(f'subtracting...py {year-1} claim_data.cal_year: {claim_data.cal_year} claim_data.acc_year: {claim_data.acc_year}')
                    # print(f'{claim_data.claim_id} {claim_data.clm_age_yrs} {claim_data.paid_cl} {claim_data.paid_bi} {claim_data.resv_cl} {claim_data.resv_bi} {claim_data.resv_pfad_cl} {claim_data.resv_pfad_bi}')
                    financial_data_obj.py_devl -= claim_data.paid_cl
                    financial_data_obj.py_devl -= claim_data.paid_bi
                    financial_data_obj.py_devl -= claim_data.resv_cl
                    financial_data_obj.py_devl -= claim_data.resv_bi
                    financial_data_obj.py_devl -= claim_data.resv_pfad_cl
                    financial_data_obj.py_devl -= claim_data.resv_pfad_bi

        # print(f'cy_losses: {financial_data_obj.ay_losses} py_devl: {financial_data_obj.py_devl}')
        financial_data_obj.cy_losses = (financial_data_obj.ay_losses +
                                        financial_data_obj.py_devl)

    def calc_fixed_expenses(self, year, in_force, inflation_factor):
        orig_clients = self.init_expenses['init_clients']
        lrg_factor = self.init_expenses['exp_fixed_lrg_scale']
        sml_factor = self.init_expenses['exp_fixed_sml_scale']

        upper_limit = self.init_expenses['exp_fixed_lrg_size']
        lower_limit = self.init_expenses['exp_fixed_sml_size']
        base = self.init_expenses['exp_fixed'] * inflation_factor * self.mkt_features['prem_init'] * in_force
        curr_scale = in_force / orig_clients
        lrg_adj = 1/math.exp(lrg_factor * (1 - min(upper_limit, (in_force/orig_clients))))
        sml_adj = 1/math.exp(sml_factor * (lower_limit - min(lower_limit, (in_force / orig_clients))))
        fixed_expenses = base * lrg_adj * sml_adj
        # print(f'base: {base} fixed_expenses: {fixed_expenses} in_force: {in_force} lrg_adj: {lrg_adj} sml_adj: {sml_adj}')
        return fixed_expenses

    def expense_financial_summary(self, int year):
        financial_data_obj = self.annual_data[year]['financial_data']
        client_list_obj = self.annual_data[year]['client_list_data']
        decisions = self.annual_data[year]['decision_data']
        financial_data_obj.in_force = len(client_list_obj.client_set)
        financial_data_obj.fixed_expenses = self.calc_fixed_expenses(year, financial_data_obj.in_force, financial_data_obj.expense_inflation_index)
        financial_data_obj.expos_var_expenses = (self.init_expenses['exp_expos'] * financial_data_obj.expense_inflation_index) * len(client_list_obj.client_set)
        for client_id in client_list_obj.client_set:
            client_obj = self.get_client_from_market(client_id)
            prem = client_obj.annual_data[year].annual_prem
            financial_data_obj.ann_prem += prem

            financial_data_obj.data_var_expenses += (0.01 * decisions.sel_exp_ratio_data) * prem
            financial_data_obj.prem_var_expenses += self.init_expenses['exp_ratio_prem'] * prem
        financial_data_obj.annual_expenses = (financial_data_obj.mktg_var_expenses +
                                              financial_data_obj.data_var_expenses +
                                              financial_data_obj.expos_var_expenses +
                                              financial_data_obj.prem_var_expenses +
                                              financial_data_obj.fixed_expenses
                                              )

    def fs_financial_summary(self, int year):
        financial_data_obj = self.annual_data[year]['financial_data']
        div_ratio = self.mkt_features['div_ratio']
        inv_rate = self.mkt_features['inv_rate']
        mct_upr = self.reg_features['mct_upr']
        mct_resv = self.reg_features['mct_resv']
        mct_cap_reqd = self.reg_features['mct_capital_reqd']

        financial_data_obj.invest_income = inv_rate * (financial_data_obj.start_assets + 0.5 * (financial_data_obj.reserves + financial_data_obj.reserves_py))
        financial_data_obj.profit = financial_data_obj.ann_prem + financial_data_obj.invest_income - financial_data_obj.annual_expenses - financial_data_obj.cy_losses

        financial_data_obj.stat_cap_reqd = ((mct_upr * financial_data_obj.ann_prem) + (mct_resv * financial_data_obj.reserves)) * mct_cap_reqd
        financial_data_obj.excess_capital = (financial_data_obj.start_capital + financial_data_obj.profit) - financial_data_obj.stat_cap_reqd

        if financial_data_obj.excess_capital < 0:
            financial_data_obj.dividend_paid = 0
            financial_data_obj.pass_capital_test = 'Fail'
        else:
            financial_data_obj.dividend_paid = min((div_ratio * financial_data_obj.start_capital), financial_data_obj.excess_capital)
            financial_data_obj.pass_capital_test = 'Pass'

        financial_data_obj.assets = financial_data_obj.start_capital + financial_data_obj.profit + financial_data_obj.reserves - financial_data_obj.dividend_paid
        financial_data_obj.liabilities = financial_data_obj.reserves
        financial_data_obj.capital = financial_data_obj.start_capital + financial_data_obj.profit - financial_data_obj.dividend_paid

        if financial_data_obj.capital == 0:
            financial_data_obj.mct_ratio = 0
        else:
            financial_data_obj.mct_ratio = (financial_data_obj.capital / (financial_data_obj.stat_cap_reqd / mct_cap_reqd))

    def indication_financial_summary(self, int year):
        indic_years = self.mkt_features['indic_years']
        indic_years_list = [year - x for x in range(indic_years)]
        financial_data_test = self.annual_data.get(min(indic_years_list))

        if financial_data_test is None:
            return
        else:
            fdo = self.annual_data[year]['financial_data']
            indication_data = dict()
            indication_data['indic_wts'] = self.mkt_features['indic_wts']
            claim_triangle = self.annual_data[year].get('claim_triangle_data', None)
            indication_data['acc_yrs'] = claim_triangle['acc_yrs']
            indication_data['devl_mths'] = [(yr + 1) * 12 for yr in claim_triangle['devl_yrs']]
            indication_data['devl_data'] = claim_triangle['paid_to']
            indication_data['in_force'] = fdo.in_force
            indication_data['prem_var_cost'] = self.init_expenses['exp_ratio_prem']
            if fdo.in_force != 0:
                indication_data['expos_var_cost'] = fdo.expos_var_expenses / fdo.in_force
            else:
                indication_data['expos_var_cost'] = 0
            indication_data['fixed_exp'] = fdo.fixed_expenses
            indication_data['pass_capital_test'] = fdo.pass_capital_test
            indication_data['inv_rate'] = self.mkt_features['inv_rate']
            indication_data['capital'] = fdo.capital
            indication_data['mct_ratio'] = fdo.mct_ratio
            indication_data['mct_capital_reqd'] = self.reg_features['mct_capital_reqd']
            indication_data['prem_surplus'] = self.mkt_features['capital_ratio_prem_init']
            self.annual_data[year]['indication_data'] = indication_data

    def process_renewals(self, year):
        new_year = year + 1
        ddo = self.annual_data[year]['decision_data']
        # print(f'company name: {self.player_name} year: {year}  ddo: {ddo}')
        clo = self.annual_data[year]['client_list_data']
        quote_data = dict()
        quote_data['quote_level'] = self.get_company_quote_level(year)
        for client_id in clo.client_set:
            client_obj = self.get_client_from_market(client_id)
            nco = client_obj.annual_data[new_year]
            renewal_prem = self.generate_quote(new_year, quote_data)
            #if self.player_name == 'cooneycw':
            #    print(f'company: {self.player_name}  renewal_prem: {renewal_prem}')
            nco.update_renewal_prem(renewal_prem)

    def generate_quote(self, year, quote_data_packet):
        if quote_data_packet['quote_level'] == 0: # quote level 0 is pre-game
            decision_obj = self.annual_data[year-1]['decision_data']  # decision data impacting current year is from last year's decision cycle
            quote = round(decision_obj.sel_avg_prem, 2)
        elif quote_data_packet['quote_level'] == 1:
            decision_obj = self.annual_data[year-1]['decision_data']
            print(f'need to use decision data to formulate a premium... quote_level: {quote_data_packet}')
        return quote

    def process_sale(self, year, client_id):
        self.add_company_client(year, client_id)
        self.record_sale(year)

    def process_canx(self, year, client_id):
        self.remove_company_client(year, client_id)
        self.record_canx(year)

    def process_claim_triangles(self, year, mkt_features):
        ret_dict = dict()
        triangle_years = self.mkt_features['claim_triangle_years']
        acc_years = [year - x + 1 for x in range(triangle_years, 0, -1)]
        min_acc_yr = min(acc_years)

        number_of_devl_yrs = mkt_features['devl_years'] + 1
        ret_dict['acc_yrs'] = acc_years
        ret_dict['devl_yrs'] = [yr for yr in range(number_of_devl_yrs)]
        paid_triangle_bi = [[0] * triangle_years for _ in range(number_of_devl_yrs)]
        paid_triangle_cl = [[0] * triangle_years for _ in range(number_of_devl_yrs)]
        paid_triangle_to = [[0] * triangle_years for _ in range(number_of_devl_yrs)]
        incd_triangle_bi = [[0] * triangle_years for _ in range(number_of_devl_yrs)]
        incd_triangle_cl = [[0] * triangle_years for _ in range(number_of_devl_yrs)]
        incd_triangle_to = [[0] * triangle_years for _ in range(number_of_devl_yrs)]

        for acc_yr in acc_years:
            annual_data = self.annual_data.get(acc_yr, None)
            if annual_data is None:
                return None
            else:
                clm_list = self.annual_data[acc_yr]['claim_data']
                for clm in clm_list:
                    paid_triangle_bi[clm.clm_age_yrs - 1][clm.acc_year - min_acc_yr] += clm.paid_bi
                    paid_triangle_cl[clm.clm_age_yrs - 1][clm.acc_year - min_acc_yr] += clm.paid_cl
                    paid_triangle_to[clm.clm_age_yrs - 1][clm.acc_year - min_acc_yr] += clm.paid_bi + clm.paid_cl

                    incd_triangle_bi[clm.clm_age_yrs - 1][clm.acc_year - min_acc_yr] += clm.paid_bi + clm.resv_bi
                    incd_triangle_cl[clm.clm_age_yrs - 1][clm.acc_year - min_acc_yr] += clm.paid_cl + clm.resv_cl
                    incd_triangle_to[clm.clm_age_yrs - 1][clm.acc_year - min_acc_yr] += clm.paid_bi + clm.paid_cl + clm.resv_bi + clm.resv_cl

        ret_dict['paid_bi'] = paid_triangle_bi
        ret_dict['paid_cl'] = paid_triangle_cl
        ret_dict['paid_to'] = paid_triangle_to

        ret_dict['incd_bi'] = incd_triangle_bi
        ret_dict['incd_cl'] = incd_triangle_cl
        ret_dict['incd_to'] = incd_triangle_to

        self.annual_data[year]['claim_triangle_data'] = ret_dict

cdef class Market:
    cdef public int orig_year
    cdef public dict client_dict
    cdef public list company_list
    cdef public dict claim_trend
    cdef public dict expense_inflation
    cdef public dict mkt_features
    cdef public dict init_client_features
    cdef public dict init_claim_features
    cdef public dict init_expenses
    cdef public dict resv_features
    cdef public dict reg_features
    cdef public dict init_decisions

    @staticmethod
    def increment_client_id():
        global global_client_id
        global_client_id += 1

    @staticmethod
    def get_client_id():
        Market.increment_client_id()
        return global_client_id - 1

    def __init__(self, int client_cnt, int orig_year, players, dict mkt_features, dict init_client_features, dict init_expenses, dict init_claim_features,
                 dict resv_features, dict reg_features, dict init_decisions):
        self.orig_year = orig_year
        self.client_dict = dict()
        self.company_list = list()
        self.mkt_features = mkt_features
        self.claim_trend = self.init_claim_trend()
        self.expense_inflation = self.init_expense_inflation()
        self.init_client_features = init_client_features
        self.init_expenses = init_expenses
        self.init_claim_features = init_claim_features
        self.resv_features = resv_features
        self.reg_features = reg_features
        self.init_decisions = init_decisions
        # create companies
        for player_id, player in enumerate(players):
            self.company_list.append(Company(player_id, player['player_name'], player['player_type'], player['profile'], self.get_client_obj, orig_year, mkt_features, init_expenses, resv_features, reg_features, init_decisions, self.get_expense_inflation_index(orig_year)))
        # create clients and assign to companies
        ann_prem = self.mkt_features['prem_init']
        for player_id, player in enumerate(players):
            for _ in range(client_cnt):
                client_id = Market.get_client_id()
                client_obj = Client(client_id, player_id, orig_year, ann_prem, init_client_features, init_claim_features, self.claim_trend)
                self.client_dict[client_id] = client_obj
                self.company_list[player_id].add_company_client(orig_year, client_id)

    def init_claim_trend(self):
        claim_trend = dict()
        claim_trend['cl_trend'] = dict()
        claim_trend['cl_trend_ind'] = dict()
        claim_trend['cl_reform'] = dict()
        claim_trend['cl_shock'] = dict()
        claim_trend['cl_trend'][self.orig_year] = self.mkt_features['claim_infl_cl_init']
        claim_trend['cl_trend_ind'][self.orig_year] = 1 + claim_trend['cl_trend'][self.orig_year]
        claim_trend['cl_reform'][self.orig_year] = 0
        claim_trend['cl_shock'][self.orig_year] = 0

        claim_trend['bi_trend'] = dict()
        claim_trend['bi_trend_ind'] = dict()
        claim_trend['bi_reform'] = dict()
        claim_trend['bi_shock'] = dict()
        claim_trend['bi_trend'][self.orig_year] = self.mkt_features['claim_infl_bi_init']
        claim_trend['bi_trend_ind'][self.orig_year] = 1 + claim_trend['bi_trend'][self.orig_year]
        claim_trend['bi_reform'][self.orig_year] = 0
        claim_trend['bi_shock'][self.orig_year] = 0
        return claim_trend

    def init_expense_inflation(self):
        expense_inflation = dict()
        expense_inflation['inflation_rate'] = dict()
        expense_inflation['inflation_index'] = dict()

        expense_inflation['inflation_rate'][self.orig_year] = 0.0
        expense_inflation['inflation_index'][self.orig_year] = 1.0

        return expense_inflation

    def process_expense_inflation(self, int new_year):
        old_year = new_year - 1
        infl_index = self.expense_inflation['inflation_index'][old_year]
        infl_rate = normal_c(self.mkt_features['expense_inflation'], self.mkt_features['expense_inflation_var'])
        self.expense_inflation['inflation_rate'][new_year] = infl_rate
        self.expense_inflation['inflation_index'][new_year] = (1+infl_rate) * infl_index

    def process_claim_inflation(self, int new_year):
        old_year = new_year - 1
        cl_shock = random_indicator(self.mkt_features['claim_shock_prob'])
        prior_reform = self.get_reform_last(old_year)
        #  print(f'year: {new_year}  prior_reform: {prior_reform}')
        if self.claim_trend['cl_trend'][old_year] > self.mkt_features['claim_reform_threshold'] and prior_reform == False:
            self.claim_trend['cl_reform'][new_year] = random_indicator(self.mkt_features['claim_reform_prob'])
        else:
            self.claim_trend['cl_reform'][new_year] = 0

        self.claim_trend['cl_shock'][new_year] =cl_shock
        self.claim_trend['cl_trend'][new_year] = ((self.mkt_features['claim_infl_cl_drift'] +
                                                   (self.claim_trend['cl_shock'][new_year] *
                                                    normal_c(self.mkt_features['claim_shock_infl_cl'],
                                                                   self.mkt_features['claim_shock_infl_var']))
                                                   ) +
                                                   (self.claim_trend['cl_reform'][new_year] *
                                                    normal_c(self.mkt_features['claim_reform_infl_cl'],
                                                                   self.mkt_features['claim_reform_infl_var'])
                                                   ) +
                                                   (self.claim_trend['cl_trend'][old_year] * self.mkt_features['claim_autoreg_cl']) +
                                                   (self.mkt_features['claim_epsilon'] * normal_c(0, self.mkt_features['claim_epsilon']))
                                                  )
        self.claim_trend['cl_trend_ind'][new_year] = self.claim_trend['cl_trend_ind'][old_year] * (1 + self.claim_trend['cl_trend'][new_year])

        bi_shock = random_indicator(self.mkt_features['claim_shock_prob'])
        if self.claim_trend['bi_trend'][old_year] > self.mkt_features['claim_reform_threshold'] and prior_reform == False:
            self.claim_trend['bi_reform'][new_year] = random_indicator(self.mkt_features['claim_reform_prob'])
        else:
            self.claim_trend['bi_reform'][new_year] = 0
        self.claim_trend['bi_shock'][new_year] = bi_shock
        self.claim_trend['bi_trend'][new_year] = ((self.mkt_features['claim_infl_bi_drift'] +
                                                   (self.claim_trend['bi_shock'][new_year] *
                                                    normal_c(self.mkt_features['claim_shock_infl_bi'],
                                                                   self.mkt_features['claim_shock_infl_var'])
                                                    ) +
                                                   (self.claim_trend['bi_reform'][new_year] *
                                                    normal_c(self.mkt_features['claim_reform_infl_bi'],
                                                                   self.mkt_features['claim_reform_infl_var'])
                                                    )) +
                                                   (self.claim_trend['bi_trend'][old_year] * self.mkt_features['claim_autoreg_bi']) +
                                                   (self.mkt_features['claim_epsilon'] * normal_c(0, self.mkt_features['claim_epsilon']))
                                                   )
        self.claim_trend['bi_trend_ind'][new_year] = self.claim_trend['bi_trend_ind'][old_year] * (1 + self.claim_trend['bi_trend'][new_year])

    def get_claim_trend(self):
        return self.claim_trend

    def get_reform_last(self, int year):
        yrs = list(self.claim_trend['bi_reform'].keys())
        yrs.sort(reverse=True)
        # print(f'get_reform_last yrs: {yrs}  {self.claim_trend["bi_reform"]} {self.claim_trend["cl_reform"]}')
        i = 0
        for yr in yrs:
            if self.claim_trend['bi_reform'][yr] == 1 or self.claim_trend['cl_reform'][yr] == 1:
                return True
            i += 1
            if i == 4:
                return False

    def get_bi_reform(self, int year):
        reform = False
        if self.claim_trend['bi_reform'][year] == 1:
            reform = True
        return reform

    def get_cl_reform(self, int year):
        reform = False
        if self.claim_trend['cl_reform'][year] == 1:
            reform = True
        return reform

    def get_expense_inflation_index(self, int year):
        return self.expense_inflation['inflation_index'][year]

    def get_client_obj(self, client_id):
        return self.client_dict[client_id]

    def init_capital(self, int year):
        for company in self.company_list:
            company.process_init_capital(year)

    def process_shopping(self, int new_year, sel_exp_ratio_mktg_min, sel_exp_ratio_mktg_max):
        old_year = new_year - 1
        sel_exp_ratio_mktg_min = 0.01 * sel_exp_ratio_mktg_min
        sel_exp_ratio_mktg_max = 0.01 * sel_exp_ratio_mktg_max
        shop_base = self.mkt_features['shop_base']
        shop_slpe_increase = self.mkt_features['shop_slpe_increase']
        shop_slpe_decrease = self.mkt_features['shop_slpe_decrease']
        shop_sens =  self.mkt_features['shop_sens']
        mktg_spend_ind = self.get_mktg_spend_ind(new_year)
        ann_prem_prior_ind = self.get_ann_prem_prior_ind(new_year)

        for client_id in self.client_dict.keys():
            client_obj = self.get_client_obj(client_id)
            nco = client_obj.annual_data[new_year]
            oco = client_obj.annual_data[old_year]

            # print(f'annual premium: {client_id} {oco.annual_prem} {nco.renewal_prem} {nco.company} {nco.pr_company}')

            nco.shop_prob = shop_ratio_c(old_price=oco.annual_prem, new_price=nco.renewal_prem,
                                         sel_exp_ratio_mktg_max=sel_exp_ratio_mktg_max,
                                         sel_exp_ratio_mktg_min=sel_exp_ratio_mktg_min,
                                         shop_base=shop_base,
                                         shop_slpe_increase=shop_slpe_increase,
                                         shop_slpe_decrease=shop_slpe_decrease,
                                         shop_sens=shop_sens,
                                         sum_ind_mktg_spend=mktg_spend_ind,
                                         sum_ind_prem=ann_prem_prior_ind)

            nco.shop = random_indicator(nco.shop_prob)
            if nco.shop == 0:
                nco.company = oco.company
                nco.annual_prem = nco.renewal_prem
            elif nco.shop == 1:
                marketing = self.get_mktg_spend_by_company(new_year)
                wprem = self.get_ann_prem_prior_by_company(new_year)
                lottery_mult = self.mkt_features['lottery_mult']
                lottery_prem_wt = self.mkt_features['lottery_prem_wt']
                lottery_adj_prem_wt = len(wprem) / 25 * lottery_prem_wt
                quotes = lottery_c(marketing=marketing,
                                   wprem=wprem,
                                   lottery_mult=lottery_mult,
                                   lottery_prem_wt=lottery_adj_prem_wt,
                                   company=nco.company)
                nco.quote_companies = quotes

                quote_premiums = copy.deepcopy(quotes)
                price_compare = copy.deepcopy(quotes)
                for company_i, company in enumerate(self.company_list):
                    if quote_premiums[company_i] == 1:
                        if company_i == nco.pr_company:
                            quote_premiums[company_i] = nco.renewal_prem
                        else:
                            company.record_quote(new_year)
                            quote_data = nco.generate_client_quote_packet(company.get_company_quote_level(new_year))
                            quote_premiums[company_i] = company.generate_quote(new_year, quote_data)
                        # print(f'Client: {client_obj.client_id} Premium quote for company {company_i} - {quote_premiums[company_i]}')

                price_srvc = self.mkt_features['price_srvc']
                price_sens = self.mkt_features['price_sens']
                new_company, new_price = compare_price_c(prices=quote_premiums,
                                                         quotes=price_compare,
                                                         price_srvc=price_srvc,
                                                         price_sens=price_sens)

                nco.company = new_company
                nco.annual_prem = new_price
                if nco.company != nco.pr_company:
                    self.company_list[nco.company].process_sale(new_year, client_obj.client_id)
                    self.company_list[nco.pr_company].process_canx(new_year, client_obj.client_id)

                # print(f'companies: {price_compare}')
                # print(f'premium quotes: {quote_premiums}')
                # print(f'new_company: {new_company}')
                # print(f'new_price: {new_price}')

    def process_mktg(self, int year):
        for company in self.company_list:
            company.process_mktg(year)

    def process_mktg_ind(self, int year):
        mktg_spend_ind = 0
        for company in self.company_list:
            mktg_spend_ind += company.annual_data[year]['financial_data'].mktg_var_expenses
        for company in self.company_list:
            company.process_mktg_ind(year, mktg_spend_ind)

    # perform claim initialization
    def process_claims(self, int year):
        for company in self.company_list:
            sel_aa_margin = company.annual_data[year]['decision_data'].sel_aa_margin
            company.process_claim_reserves(year, sel_aa_margin, self.resv_features)

    def process_financials(self, int year):
        for company in self.company_list:
            company.claim_financial_summary(year)
            company.process_claim_triangles(year, self.mkt_features)
            company.expense_financial_summary(year)
            company.fs_financial_summary(year)
            company.indication_financial_summary(year)
            company.update_annual_data(year, self.get_expense_inflation_index(year))

    def process_clients(self, int new_year):
        old_year = new_year - 1
        terr_chg_test = random_between(self.init_client_features['terr_chg_min'], self.init_client_features['terr_chg_max'])
        credit_chg_test = random_between(self.init_client_features['credit_chg_min'], self.init_client_features['credit_chg_max'])

        for client_id in self.client_dict.keys():
            client_obj = self.get_client_obj(client_id)
            oco = client_obj.annual_data[old_year]
            ann_prem = 0
            new_client_features = client_obj.init_client_features
            new_claim_features = client_obj.init_claim_features
            # modfiy client_features / claim_features for drift later
            client_obj.age_clients(new_year, terr_chg_test, credit_chg_test)
            client_obj.new_client_year(new_year, ann_prem, oco, self.claim_trend)

    def process_pre_game_renewal(self, int new_year):
        old_year = new_year - 1
        # print(f'process_pre_game_renewal: {new_year} {old_year}')
        inflation = 1 + self.mkt_features['renewal_prem_infl_init']
        for company in self.company_list:
            new_ddo = company.annual_data[new_year]['decision_data']
            old_ddo = company.annual_data[old_year]['decision_data']
            new_ddo.sel_avg_prem = old_ddo.sel_avg_prem * inflation

        for client_id in self.client_dict.keys():
            client_obj = self.get_client_obj(client_id)
            nco = client_obj.annual_data[new_year]
            quote_data = dict()
            quote_data['quote_level'] = 0
            renewal_prem = self.company_list[nco.pr_company].generate_quote(new_year, quote_data)
            nco.update_renewal_prem(renewal_prem)

    def process_post_decision_renewals(self, int year):
        dec_year = year - 1
        for company in self.company_list:
            company.process_renewals(dec_year)

    def get_client_dict(self):
        return self.client_dict

    def get_companies(self):
        return self.company_list

    def get_mktg_spend_by_company(self, year):
        mktg_spend_by_company = []
        for company in self.company_list:
            mktg_spend_by_company.append(company.get_mktg_spend_company(year))
        return mktg_spend_by_company

    def get_ann_prem_prior_by_company(self, year):
        ann_prem_prior_by_company = []
        for company in self.company_list:
            ann_prem_prior_by_company.append(company.get_ann_prem_prior_company(year))
        return ann_prem_prior_by_company

    def process_in_force_ind(self, year):
        in_force_by_company = []
        for company in self.company_list:
            fdo = company.annual_data[year]['financial_data']
            in_force_by_company.append(fdo.in_force)
        in_force_ind = sum(in_force_by_company)
        for company in self.company_list:
            fdo = company.annual_data[year]['financial_data']
            fdo.in_force_ind = in_force_ind

    def get_mktg_spend_ind(self, year):
        mktg_spend_ind = 0
        for company in self.company_list:
            mktg_spend_ind += company.get_mktg_spend_company(year)
        return mktg_spend_ind

    def get_ann_prem_prior_ind(self, year):
        ann_prem_prior_ind = 0
        for company in self.company_list:
            ann_prem_prior_ind += company.get_ann_prem_prior_company(year)
        return ann_prem_prior_ind

    def get_financials(self, int year):
        company_data = list()
        for company in self.company_list:
            player_id = company.player_id
            player_name = company.player_name
            company_data.append((player_id, player_name, company.annual_data[year]['financial_data']))
        return company_data

    def get_decisions(self, int year):
        company_data = list()
        for company in self.company_list:
            player_id = company.player_id
            player_name = company.player_name
            decision_data = company.annual_data[year]['decision_data']
            company_data.append((player_id, player_name, decision_data))
        return company_data

    def update_decisions(self, int year, decisions):
        for company in self.company_list:
            for decision in decisions:
                if company.player_name == decision['player_name']:
                    company.update_decisions(year, decision)
                    break

    def get_indications(self, int year):
        company_data = list()
        for company in self.company_list:
            player_id = company.player_id
            player_name = company.player_name
            indication_data = company.annual_data[year]['indication_data']
            company_data.append((player_id, player_name, indication_data))

        return company_data

    def get_claim_triangles(self, int year):
        company_triangle_data = list()
        for company in self.company_list:
            triangle_data = dict()
            player_id = company.player_id
            player_name = company.player_name
            triangle_data['triangles'] = company.annual_data[year]['claim_triangle_data']
            company_triangle_data.append((player_id, player_name, triangle_data))
        return company_triangle_data


cdef random_indicator(double threshold):
    cdef double random_value
    random_value = rand() / <double> RAND_MAX
    return 1 if random_value < threshold else 0


cdef double random_between(double a, double b):
    cdef double random_value
    random_value = rand() / (<double> RAND_MAX + 1.0)
    return a + (b - a) * random_value


cdef double simulate_claim(double mean, double coeff_of_var, int limit):
    cdef double claim_amount
    cdef double stddev, variance_log, logmean

    stddev = coeff_of_var * mean
    variance_log = log((stddev / mean) ** 2 + 1)
    stddev_log = sqrt(variance_log)
    logmean = log(mean) - 0.5 * (stddev_log ** 2)

    claim_amount = np.random.lognormal(logmean, stddev_log)
    return claim_amount if claim_amount < limit else limit


cdef double trunc_normal_c(float mu, float sigma, float limit):
    cdef double uncapped_norm = np.random.normal(mu, sigma)
    return min(uncapped_norm, limit)


cdef double normal_c(float mu, float sigma):
    cdef double uncapped_norm = np.random.normal(mu, sigma)
    return uncapped_norm

cdef float shop_ratio_c(float old_price, float new_price,
                        float sel_exp_ratio_mktg_max, float sel_exp_ratio_mktg_min,
                        float shop_base, float shop_slpe_increase, float shop_slpe_decrease, float shop_sens,
                        float sum_ind_mktg_spend, float sum_ind_prem):
    cdef float rate_change = (new_price / old_price) - 1
    cdef float effective_slpe

    if rate_change >= 0:
        effective_slpe = shop_slpe_increase
    else:
        effective_slpe = shop_slpe_decrease

    cdef float logistic_value = shop_base / (1 + math.exp(-1 * effective_slpe * (-1 * rate_change)))
    cdef float shop_value = 1 + (shop_sens - 1) * math.log(
        1 + ((sum_ind_mktg_spend / sum_ind_prem) - sel_exp_ratio_mktg_min) / (
                    sel_exp_ratio_mktg_max - sel_exp_ratio_mktg_min))
    cdef float final_value = logistic_value * shop_value

    return final_value


cdef list lottery_c(list marketing, list wprem, double lottery_mult, double lottery_prem_wt, company):
    cdef int i, max_i
    cdef double sum_tot
    cdef list lottery
    cdef list outcome
    cdef double test_val

    sum_tot = 0
    max_i = len(marketing)
    lottery = [0.0] * max_i
    outcome = [0] * max_i

    for i in range(max_i):
        if wprem[i] == 0:
            wprem[i] = 1
        lottery[i] = (marketing[i] + wprem[i] * lottery_prem_wt) / wprem[i]
        sum_tot += lottery[i]

    sum_tot /= lottery_mult

    for i in range(max_i):
        test_val = random.uniform(0, sum_tot)
        if lottery[i] >= test_val:
            outcome[i] = 1

    outcome[company] = 0

    # Check if all entries in outcome are zero
    if not any(outcome[:company] + outcome[company + 1:]):
        while True:
            random_index = random.randint(0, max_i - 1)
            if random_index != company:  # Ensure the random index is not the company index
                outcome[random_index] = 1
                break

    outcome[company] = 1

    return outcome


cdef (int, double) compare_price_c(list prices, list quotes, float price_srvc, float price_sens):
    cdef int winning_company = -1
    cdef double winning_price = 99999999.0
    cdef int i
    cdef double mu = np.mean(prices)
    cdef double limit = price_sens
    cdef list service_value_rand = np.random.normal(0, price_srvc, len(prices)).tolist()
    cdef list final_service_value = []
    cdef list noise_value = np.random.normal(0, .01, len(prices)).tolist()
    # Calculate final service value within the specified limit
    for ind, value in enumerate(service_value_rand):
        adjusted_value = (mu * max(min(value, abs(limit)), -abs(limit))) + noise_value[ind]
        final_service_value.append(adjusted_value)

    # print(f'final_service_value: {final_service_value}')
    # Adjust prices without adding noise
    compare_price = [price + service_value for price, service_value in zip(prices, final_service_value)]
    # print(f'compare_price: {compare_price} prices: {prices}')
    # Determine the winning company with the lowest adjusted price among those with non-zero quotes
    for i in range(len(prices)):
        if quotes[i] == 1 and compare_price[i] < winning_price:
            winning_price = compare_price[i]
            winning_company = i
    # print(f'quotes: {quotes}')
    # print(f'winning_company: {winning_company} winning_price: {prices[winning_company]}')

    return winning_company, prices[winning_company]
