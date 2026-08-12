"""
lp_model.py - LP模型构建与求解模块
功能：构建稀疏LP，显式SOC变量，HiGHS求解
变量布局: 每小时7个变量 (6决策 + 1 SOC), 每区域 7*2407=16849
"""

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog
from data_loader import REGIONS, N_REGIONS, T_TOTAL, T_MAIN

# 变量索引: 每小时7个变量
# 0: p_ren_dir   1: p_ren_ch    2: p_ren_sell
# 3: p_grid_ch   4: p_dis_load  5: p_dis_sell
# 6: SOC
NV = 7  # vars per hour


def _vidx(t, v):
    """变量索引"""
    return t * NV + v


def build_region_lp(data, region_idx, objective='cost'):
    """构建单区域LP，返回(c, A_ub, b_ub, A_eq, b_eq, bounds, n_vars)"""
    r = region_idx
    T = T_TOTAL
    n_vars = T * NV  # 16849

    fac_load = data['facility_load'][r, :]
    avail_ren = data['available_renewable'][r, :]
    price = data['electricity_price'][r, :]
    sell_price = data['sell_price'][r, :]
    carbon_int = data['carbon_intensity'][r, :]

    cap = data['storage_cap'][r]
    min_soc = data['min_soc'][r]
    init_soc = data['init_soc'][r]
    max_ch = data['max_charge'][r]
    max_dis = data['max_discharge'][r]
    eta_ch = data['eta_ch'][r]
    eta_dis = data['eta_dis'][r]
    max_buy = data['max_grid_import'][r]
    max_sell = data['max_grid_export'][r]
    sell_limit = data['sell_limit'][r]

    # ==================== 目标函数 ====================
    c = np.zeros(n_vars)
    if objective == 'cost':
        for t in range(T):
            c[_vidx(t, 0)] = -price[t]
            c[_vidx(t, 3)] = price[t]
            c[_vidx(t, 4)] = -price[t]
            c[_vidx(t, 2)] = -sell_price[t]
            c[_vidx(t, 5)] = -sell_price[t]
    elif objective == 'carbon':
        for t in range(T):
            c[_vidx(t, 0)] = -carbon_int[t]
            c[_vidx(t, 3)] = carbon_int[t]
            c[_vidx(t, 4)] = -carbon_int[t]

    # ==================== 等式约束: SOC动态 ====================
    eq_rows, eq_cols, eq_vals, b_eq = [], [], [], []
    eq_ptr = 0

    for t in range(T):
        # SOC[t] - SOC[t-1] - eta_ch*(v1+v3) + (v4+v5)/eta_dis = rhs
        # t=0: rhs = init_soc, SOC[t-1]=init_soc (implicit)
        # t>0: rhs = 0, SOC[t-1] is variable
        eq_rows.append(eq_ptr); eq_cols.append(_vidx(t, 6)); eq_vals.append(1.0)  # SOC[t]
        eq_rows.append(eq_ptr); eq_cols.append(_vidx(t, 1)); eq_vals.append(-eta_ch)  # v1
        eq_rows.append(eq_ptr); eq_cols.append(_vidx(t, 3)); eq_vals.append(-eta_ch)  # v3
        eq_rows.append(eq_ptr); eq_cols.append(_vidx(t, 4)); eq_vals.append(1.0/eta_dis)  # v4
        eq_rows.append(eq_ptr); eq_cols.append(_vidx(t, 5)); eq_vals.append(1.0/eta_dis)  # v5

        if t == 0:
            b_eq.append(init_soc)  # SOC[0] = init_soc + ...
        else:
            eq_rows.append(eq_ptr); eq_cols.append(_vidx(t-1, 6)); eq_vals.append(-1.0)  # SOC[t-1]
            b_eq.append(0.0)
        eq_ptr += 1

    A_eq = sp.csr_matrix((eq_vals, (eq_rows, eq_cols)), shape=(eq_ptr, n_vars))
    b_eq_arr = np.array(b_eq)

    # ==================== 不等式约束 ====================
    ub_rows, ub_cols, ub_vals, b_ub = [], [], [], []
    ub_ptr = 0

    for t in range(T):
        def add_ub(vars_coefs, rhs):
            nonlocal ub_ptr
            for v, coef in vars_coefs:
                ub_rows.append(ub_ptr); ub_cols.append(_vidx(t, v)); ub_vals.append(coef)
            b_ub.append(rhs)
            ub_ptr += 1

        # C1: v0+v1+v2 <= avail_ren
        add_ub([(0, 1), (1, 1), (2, 1)], avail_ren[t])
        # C2: v0+v4 <= fac_load
        add_ub([(0, 1), (4, 1)], fac_load[t])
        # C6: v1+v3 <= max_ch
        add_ub([(1, 1), (3, 1)], max_ch)
        # C7: v4+v5 <= max_dis
        add_ub([(4, 1), (5, 1)], max_dis)
        # C8: -v0-v4+v3 <= max_buy - fac_load
        add_ub([(0, -1), (4, -1), (3, 1)], max_buy - fac_load[t])
        # C9: v2+v5 <= max_sell
        add_ub([(2, 1), (5, 1)], max_sell)
        # C10: v2 <= sell_limit
        add_ub([(2, 1)], sell_limit)
        # SOC上界: SOC[t] <= cap
        add_ub([(6, 1)], cap)
        # SOC下界: -SOC[t] <= -min_soc
        add_ub([(6, -1)], -min_soc)

    # 终端SOC: -SOC[T-1] <= -init_soc
    ub_rows.append(ub_ptr); ub_cols.append(_vidx(T-1, 6)); ub_vals.append(-1.0)
    b_ub.append(-init_soc)
    ub_ptr += 1

    A_ub = sp.csr_matrix((ub_vals, (ub_rows, ub_cols)), shape=(ub_ptr, n_vars))
    b_ub_arr = np.array(b_ub)

    # 变量边界
    bounds = [(0, None)] * n_vars

    return c, A_ub, b_ub_arr, A_eq, b_eq_arr, bounds, n_vars


def solve_region_lp(data, region_idx, objective='cost'):
    """求解单区域LP"""
    c, A_ub, b_ub, A_eq, b_eq, bounds, n_vars = build_region_lp(data, region_idx, objective)
    result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                     bounds=bounds, method='highs')
    if not result.success:
        print(f"[警告] {REGIONS[region_idx]} LP失败({objective}): {result.message}")
        return None
    return result.x.reshape(T_TOTAL, NV)


def solve_all_regions(data, objective='cost'):
    """求解所有区域(独立)"""
    results = {}
    for ri in range(N_REGIONS):
        print(f"  {REGIONS[ri]} ({objective})...", end=' ')
        x = solve_region_lp(data, ri, objective)
        if x is not None:
            results[ri] = x
            print("OK")
    return results


def solve_weighted(data, weights):
    """加权多目标求解(各区域独立)"""
    w_cost, w_carbon = weights[0], weights[1]
    results = {}
    for ri in range(N_REGIONS):
        r = ri
        T = T_TOTAL
        n_vars = T * NV
        fac_load = data['facility_load'][r, :]
        price = data['electricity_price'][r, :]
        sell_price = data['sell_price'][r, :]
        carbon_int = data['carbon_intensity'][r, :]

        norm_cost = np.mean(price) * np.mean(fac_load) * T
        norm_carbon = np.mean(carbon_int) * np.mean(fac_load) * T

        c = np.zeros(n_vars)
        for t in range(T):
            cc = w_cost / norm_cost
            cv = w_carbon / norm_carbon
            c[_vidx(t, 0)] = -price[t] * cc - carbon_int[t] * cv
            c[_vidx(t, 3)] = price[t] * cc + carbon_int[t] * cv
            c[_vidx(t, 4)] = -price[t] * cc - carbon_int[t] * cv
            c[_vidx(t, 2)] = -sell_price[t] * cc
            c[_vidx(t, 5)] = -sell_price[t] * cc

        _, A_ub, b_ub, A_eq, b_eq, bounds, _ = build_region_lp(data, ri, 'cost')
        result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                         bounds=bounds, method='highs')
        if result.success:
            results[ri] = result.x.reshape(T_TOTAL, NV)
            print(f"  {REGIONS[ri]} 加权求解OK")
        else:
            print(f"  {REGIONS[ri]} 加权求解失败")
    return results


def extract_solution(data, region_idx, x):
    """从解中提取物理量 [T]"""
    r = region_idx
    eta_ch = data['eta_ch'][r]
    eta_dis = data['eta_dis'][r]
    init_soc = data['init_soc'][r]

    sol = {
        'p_ren_dir': x[:, 0],
        'p_ren_ch': x[:, 1],
        'p_ren_sell': x[:, 2],
        'p_grid_ch': x[:, 3],
        'p_dis_load': x[:, 4],
        'p_dis_sell': x[:, 5],
        'soc': x[:, 6],
    }
    sol['p_curt'] = np.maximum(
        data['available_renewable'][r, :] - sol['p_ren_dir'] - sol['p_ren_ch'] - sol['p_ren_sell'], 0)
    sol['p_grid_load'] = np.maximum(
        data['facility_load'][r, :] - sol['p_ren_dir'] - sol['p_dis_load'], 0)
    sol['p_charge'] = sol['p_ren_ch'] + sol['p_grid_ch']
    sol['p_discharge'] = sol['p_dis_load'] + sol['p_dis_sell']
    sol['p_buy'] = sol['p_grid_load'] + sol['p_grid_ch']
    sol['p_sell'] = sol['p_ren_sell'] + sol['p_dis_sell']
    sol['p_net'] = sol['p_buy'] - sol['p_sell']

    return sol


def get_all_solutions(data, region_solutions):
    """从多区域解字典提取全部物理量"""
    all_sol = {}
    for ri in range(N_REGIONS):
        if ri in region_solutions:
            all_sol[ri] = extract_solution(data, ri, region_solutions[ri])
    return all_sol
