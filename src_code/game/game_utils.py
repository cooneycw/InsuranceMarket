import pandas as pd
import numpy as np
import copy
import math
import random
from src_code.models.db_utils import write_message, get_game_difficulty
from sklearn.linear_model import LinearRegression


def messages(config, game_id, msg):
    if config.verbose:
        print(f'Game: {game_id} - ' + msg)
    write_message(config, game_id, msg)


def process_default_decisions(config, game_id, player_id, player_name, year):
    cwc = 0


def process_indications(config, game_id, player_id, player_name, player_type, profile, year, orig_year, init_years, claimtrend_dict, claims_data_dict,
                        financial_data, financial_indication_data, indication_data_dict, decision_data, selected=True, game_difficulty=None):
    decisions = dict()
    decisions_locked = False

    if financial_data.in_force != 0:
        curr_avg_prem = round(financial_data.ann_prem / financial_data.in_force, 2)
    else:
        curr_avg_prem = 0

    if year < orig_year + init_years - 1:
        sel_avg_prem = curr_avg_prem
        decisions_locked = True
        decisions['decisions_locked'] = decisions_locked
        decisions['sel_profit_margin'] = decision_data.sel_profit_margin
        decisions['sel_exp_ratio_mktg'] = decision_data.sel_exp_ratio_mktg
        decisions['sel_loss_trend_margin'] = decision_data.sel_loss_trend_margin
        return curr_avg_prem, sel_avg_prem, decisions
    else:
        devl_data = indication_data_dict['devl_data']
        wts = indication_data_dict['indic_wts']
        fixed_exp = indication_data_dict['fixed_exp']
        prem_var_cost = indication_data_dict['prem_var_cost']
        expos_var_cost = indication_data_dict['expos_var_cost']
        pass_capital_test = indication_data_dict['pass_capital_test']
        clm_yrs = indication_data_dict['acc_yrs']
        acc_yrs = [f'Acc Yr {acc_yr}' for acc_yr in clm_yrs]
        devl_mths = indication_data_dict['devl_mths']

        # Get game difficulty if not provided
        if game_difficulty is None:
            game_difficulty = get_game_difficulty(config, game_id)
        
        is_novice = game_difficulty == 'Novice'

        # test player type for assumptions:
        if pass_capital_test == 'Fail':
            if is_novice:
                sel_profit_margin = 100  # 10.0% for novice penalty
                sel_loss_trend_margin = 0     # No loss trend complexity for novice
            else:
                sel_profit_margin = 80  # 8.0% for non-novice penalty
                sel_loss_trend_margin = 20    # 2.0% loss trend penalty for non-novice
            sel_mktg_expense = 0
            if player_type == 'user':
                decisions_locked = False
            else:
                decisions_locked = True
        else:
            if player_type == 'user' and selected is True:
                sel_profit_margin = 50
                sel_loss_trend_margin = 0
                sel_mktg_expense = 0
                decisions_locked = False
            else:
                if profile == 'growth':
                    sel_profit_margin = random.randint(10, 50)  # Reverted to original range
                    sel_loss_trend_margin = random.randint(0, 10)    # Reverted to original range
                    sel_mktg_expense = random.randint(0, 50)
                    decisions_locked = True
                elif profile == 'profitability':
                    sel_profit_margin = random.randint(30, 70)  # Reverted to original range
                    sel_loss_trend_margin = random.randint(0, 10)     # Reverted to original range
                    sel_mktg_expense = random.randint(0, 20)
                    decisions_locked = True
                elif profile == 'balanced':
                    sel_profit_margin = random.randint(20, 60)  # Reverted to original range
                    sel_loss_trend_margin = random.randint(0, 10)     # Reverted to original range
                    sel_mktg_expense = random.randint(0, 30)
                    decisions_locked = True

        decisions['decisions_locked'] = decisions_locked
        decisions['sel_profit_margin'] = sel_profit_margin
        decisions['sel_exp_ratio_mktg'] = sel_mktg_expense
        decisions['sel_loss_trend_margin'] = sel_loss_trend_margin

        reform_fact = []
        for yr in reversed(clm_yrs):
            reform_fact.append(claimtrend_dict['bi_reform'][yr] or claimtrend_dict['cl_reform'][yr])

        df = pd.DataFrame(columns=acc_yrs, index=devl_mths)
        for i, devl_mth in enumerate(devl_mths):
            df.loc[devl_mth] = devl_data[i]

        transposed_df = df.T

        fact_labels = ['Age-to-Age']
        fact_devl_mths = copy.deepcopy(devl_mths)
        fact_devl_mths[0] = None
        fact_df = pd.DataFrame(columns=fact_labels, index=fact_devl_mths)

        for i, fact_devl_mth in enumerate(fact_devl_mths):
            if fact_devl_mth == fact_devl_mths[0]:
                fact_df.iloc[0, 0] = 0
            if fact_devl_mth == fact_devl_mths[1]:
                numerator = sum(transposed_df.values[0:len(acc_yrs[:-1])][:, 1])
                denominator = sum(transposed_df.values[0:len(acc_yrs[:-1])][:, 0])
                if denominator == 0:
                    denominator = 1
                fact_df.iloc[1, 0] = numerator / denominator
            if fact_devl_mth == fact_devl_mths[2]:
                numerator = sum(transposed_df.values[0:len(acc_yrs[:-2])][:, 2])
                denominator = sum(transposed_df.values[0:len(acc_yrs[:-2])][:, 1])
                if denominator == 0:
                    denominator = 1
                fact_df.iloc[2, 0] = numerator / denominator
                fact_df.iloc[1, 0] = fact_df.iloc[1, 0] * fact_df.iloc[2, 0]

        cols = ['Actual Paid', 'Devl Factor', 'Ultimate Incurred', 'In-Force', 'Loss Cost', 'Trend Adj', 'Reform Adj',
                'Weights',
                'Adj Loss Cost', 'Fixed Expenses', 'Expos Var Expenses', 'Prem Var Expenses']
        display_yrs = [f'Acc Yr {acc_yr}' for acc_yr in clm_yrs]
        display_yrs.reverse()
        display_df = pd.DataFrame(columns=display_yrs, index=cols)
        i = 0
        est_values = None
        for categ, row in display_df.iterrows():
            if categ == 'Actual Paid':
                for j in range(len(acc_yrs)):
                    display_df.iloc[i, j] = df.iloc[min(j, len(devl_mths) - 1), len(acc_yrs) - j - 1]
            elif categ == 'Devl Factor':
                for k in range(len(acc_yrs)):
                    if k < 2:
                        display_df.iloc[i, k] = fact_df.iloc[k + 1].values[0]
                    else:
                        display_df.iloc[i, k] = 1
            elif categ == 'Ultimate Incurred':
                for l in range(len(acc_yrs)):
                    display_df.iloc[i, l] = display_df.iloc[i - 2, l] * display_df.iloc[i - 1, l]
            elif categ == 'In-Force':
                for m in range(len(acc_yrs)):
                    display_df.iloc[i, m] = financial_indication_data[len(acc_yrs) - m - 1]
                in_force = display_df.iloc[i, 0]
            elif categ == 'Loss Cost':
                for n in range(len(acc_yrs)):
                    denom = display_df.iloc[i - 1, n]
                    if denom != 0:
                        display_df.iloc[i, n] = display_df.iloc[i - 2, n] / denom
                    else:
                        display_df.iloc[i, n] = 0
                lcost = [(clm_yrs[len(clm_yrs) - q - 1], float(lc)) for q, lc in enumerate(display_df.iloc[i].values)]
                est_values = perform_logistic_regression_indication(lcost, reform_fact, sel_loss_trend_margin)

            elif categ == 'Trend Adj':
                for o in range(len(acc_yrs)):
                    display_df.iloc[i, o] = est_values['trend'][o]
            elif categ == 'Reform Adj':
                for p in range(len(acc_yrs)):
                    display_df.iloc[i, p] = est_values['reform'][p]
            elif categ == 'Weights':
                for q in range(len(acc_yrs)):
                    display_df.iloc[i, q] = wts[q]
            elif categ == 'Adj Loss Cost':
                for r in range(len(acc_yrs)):
                    display_df.iloc[i, r] = display_df.iloc[i-4, r] * display_df.iloc[i-3, r] * display_df.iloc[i-2, r]
                wtd_lcost = sum(display_df.iloc[i] * display_df.iloc[i - 1])
                wtd_i = i
            elif categ == 'Fixed Expenses':
                for s in range(len(acc_yrs)):
                    display_df.iloc[i, s] = 0
            elif categ == 'Expos Var Expenses':
                for t in range(len(acc_yrs)):
                    display_df.iloc[i, t] = 0
            elif categ == 'Prem Var Expenses':
                for u in range(len(acc_yrs)):
                    display_df.iloc[i, u] = 0

            i += 1

        display_df.insert(0, max(clm_yrs) + 1, '')
        display_df.iloc[wtd_i, 0] = round(wtd_lcost, 2)
        if in_force != 0:
            fixed_cost = fixed_exp / in_force
            display_df.iloc[wtd_i + 1, 0] = round(fixed_cost, 2)
        else:
            fixed_cost = 0
            display_df.iloc[wtd_i + 1, 0] = 0
        display_df.iloc[wtd_i + 2, 0] = round(expos_var_cost, 2)
        display_df.iloc[wtd_i + 3, 0] = round(prem_var_cost * 100, 1)

        sel_avg_prem = round(((wtd_lcost + expos_var_cost + fixed_cost) / (1 - prem_var_cost - (int(sel_mktg_expense) / 1000) - (int(sel_profit_margin) / 1000))), 2)

        return curr_avg_prem, sel_avg_prem, decisions


def perform_logistic_regression_indication(data, reform_fact, sel_loss_cost_margin):
    df = pd.DataFrame(data, columns=['Year', 'Value'])

    non_zero_avg = df[df['Value'] != 0]['Value'].mean()

    # Replace 0 values in the "Value" column with the calculated average
    df['Value'] = df['Value'].replace(0, non_zero_avg)

    df['Ln_Value'] = np.log(df['Value'])
    proj_year = max(df['Year'].values) + 1
    est = dict()
    acc_yrs = list(df.Year.values)
    reform = False

    if sum(reform_fact) != len(reform_fact) and sum(reform_fact) > 0:
        new_reform_fact = [0] * len(reform_fact)
        for i in range(len(reform_fact)):
            if reform_fact[i] == 1:
                reform = True
            if reform:
                new_reform_fact[0:i + 1] = [1] * (i + 1)
                break
        df['Reform'] = new_reform_fact

    if reform:
        feature_names = ['Year', 'Reform']
    else:
        feature_names = ['Year']

    X = df[feature_names]
    y = df['Ln_Value']

    model = LinearRegression(fit_intercept=True)
    try:
        model.fit(X, y)
    except:
        cwc = 0
    exp_list = [(1 + .001 * int(sel_loss_cost_margin)) ** (1 + max(acc_yrs) - yr) for yr in acc_yrs]

    if reform:
        pred_df = df.drop(columns=['Ln_Value', 'Value'])
        new_df_a = copy.deepcopy(pred_df)
        new_df_a['Reform'] = 1
        new_df_b = copy.deepcopy(pred_df)
        new_df_b['Reform'] = 0
        new_df_c = {'Year': proj_year, 'Reform': 1}

        pred_data = [new_df_a, new_df_b, pd.DataFrame(new_df_c, columns=feature_names, index=[0])]
        pred_out = []
        for pred_dat in pred_data:
            temp = model.predict(pred_dat)
            pred_dat['predicted_value'] = np.exp(temp)
            pred_out.append(pred_dat)

        keys = ['trend', 'reform']

        for key in keys:
            est[key] = list()
            if key == 'trend':
                numer = pred_out[2]['predicted_value'][0]
            for q, acc_yr in enumerate(acc_yrs):
                if key == 'trend':
                    denom = pred_out[0][pred_out[0]['Year'] == acc_yr]['predicted_value'].values[0]
                elif key == 'reform':
                    if pred_df[pred_df['Year'] == acc_yr]['Reform'].values[0] == 1:
                        est[key].append(1)
                        continue
                    else:
                        numer = pred_out[0][pred_out[1]['Year'] == acc_yr]['predicted_value'].values[0]
                        denom = pred_out[1][pred_out[1]['Year'] == acc_yr]['predicted_value'].values[0]
                if denom != 0:
                    est[key].append(numer/denom * exp_list[q])
                else:
                    est[key].append(0)
        return est
    else:
        new_df_a = df.drop(columns=['Ln_Value', 'Value'])
        new_df_c = {'Year': proj_year, 'Reform': 1}

        pred_data = [new_df_a, pd.DataFrame(new_df_c, columns=['Year'], index=[0])]
        pred_out = []
        for pred_dat in pred_data:
            temp = model.predict(pred_dat)
            pred_dat['predicted_value'] = np.exp(temp)
            pred_out.append(pred_dat)

        keys = ['trend']

        for key in keys:
            est[key] = list()
            if key == 'trend':
                numer = pred_out[1]['predicted_value'][0]
            for q, acc_yr in enumerate(acc_yrs):
                if key == 'trend':
                    denom = pred_out[0][pred_out[0]['Year'] == acc_yr]['predicted_value'].values[0]
                if denom != 0:
                    est[key].append(numer/denom * exp_list[q])
                else:
                    est[key].append(0)

        est['reform'] = [1] * len(data)
        return est


def random_indicator(probability_x):
    if random.random() < probability_x:
        return True
    else:
        return False
