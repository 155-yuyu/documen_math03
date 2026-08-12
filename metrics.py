"""
metrics.py - 评价指标计算模块
功能：成本、碳排、峰值净购电、负荷波动、分区域指标
"""

import numpy as np
from data_loader import REGIONS, N_REGIONS, T_TOTAL, T_MAIN


def compute_metrics(all_sol, data, time_range=None):
    """计算四项指标"""
    if time_range is None:
        time_range = (0, T_MAIN)
    t0, t1 = time_range
    sl = slice(t0, t1)

    total_cost = 0.0
    total_carbon = 0.0
    region_net = np.zeros((N_REGIONS, t1 - t0))

    for ri in range(N_REGIONS):
        if ri not in all_sol:
            continue
        sol = all_sol[ri]
        total_cost += np.sum(
            sol['p_buy'][sl] * data['electricity_price'][ri, sl] -
            sol['p_sell'][sl] * data['sell_price'][ri, sl])
        total_carbon += np.sum(
            sol['p_buy'][sl] * data['carbon_intensity'][ri, sl])
        region_net[ri] = sol['p_net'][sl]

    # 系统净购电
    sys_net = np.sum(region_net, axis=0)  # [t1-t0]
    peak_net = np.max(sys_net) if len(sys_net) > 0 else 0
    fluctuation = np.sum(np.abs(np.diff(sys_net))) if len(sys_net) > 1 else 0

    return {
        'total_cost': total_cost,
        'total_carbon': total_carbon,
        'peak_net_import': peak_net,
        'fluctuation': fluctuation,
    }


def compute_region_metrics(all_sol, data, time_range=None):
    """分区域指标"""
    if time_range is None:
        time_range = (0, T_MAIN)
    t0, t1 = time_range
    sl = slice(t0, t1)

    results = {}
    for ri in range(N_REGIONS):
        if ri not in all_sol:
            continue
        r = REGIONS[ri]
        sol = all_sol[ri]

        cost = np.sum(
            sol['p_buy'][sl] * data['electricity_price'][ri, sl] -
            sol['p_sell'][sl] * data['sell_price'][ri, sl])
        carbon = np.sum(
            sol['p_buy'][sl] * data['carbon_intensity'][ri, sl])
        peak_net = np.max(sol['p_net'][sl])
        avg_net = np.mean(sol['p_net'][sl])
        renewable_used = np.sum(
            sol['p_ren_dir'][sl] + sol['p_ren_ch'][sl] + sol['p_ren_sell'][sl])
        renewable_total = np.sum(data['available_renewable'][ri, sl])
        util = renewable_used / renewable_total if renewable_total > 0 else 0

        results[r] = {
            'cost': cost,
            'carbon': carbon,
            'peak_net_import': peak_net,
            'avg_net_import': avg_net,
            'renewable_utilization': util,
            'total_charge': np.sum(sol['p_charge'][sl]),
            'total_discharge': np.sum(sol['p_discharge'][sl]),
            'total_curtailment': np.sum(sol['p_curt'][sl]),
            'avg_soc': np.mean(sol['soc'][sl]),
            'final_soc': sol['soc'][t1-1],
        }
    return results


def compare_metrics(baseline, optimized):
    """对比基准与优化"""
    comp = {}
    for key in ['total_cost', 'total_carbon', 'peak_net_import', 'fluctuation']:
        b = baseline[key]
        o = optimized[key]
        change = (o - b) / abs(b) * 100 if b != 0 else 0
        comp[key] = {'baseline': b, 'optimized': o, 'change_pct': change}
    return comp


def get_baseline_solution(data):
    """从基准数据构建解字典(用于统一接口)"""
    all_sol = {}
    for ri in range(N_REGIONS):
        all_sol[ri] = {
            'p_ren_dir': data['baseline_used_renewable'][ri],
            'p_ren_ch': data['baseline_renewable_charge'][ri],
            'p_ren_sell': data['baseline_grid_sell'][ri] * 0,  # baseline sell混合
            'p_grid_ch': data['baseline_charge'][ri] - data['baseline_renewable_charge'][ri],
            'p_dis_load': data['baseline_discharge'][ri] * 0,  # 需要分解
            'p_dis_sell': data['baseline_discharge'][ri] * 0,
            'p_curt': data['baseline_curtailment'][ri],
            'p_charge': data['baseline_charge'][ri],
            'p_discharge': data['baseline_discharge'][ri],
            'p_buy': data['baseline_grid_buy'][ri],
            'p_sell': data['baseline_grid_sell'][ri],
            'p_net': data['baseline_net_import'][ri],
            'soc': data['baseline_soc'][ri],
        }
        # 分解discharge
        # baseline: discharge用于负荷或售电, 但基准无售电则全部供负荷
        if data['max_grid_export'][ri] == 0:
            all_sol[ri]['p_dis_load'] = data['baseline_discharge'][ri]
        else:
            # 部分售电: grid_sell可能来自新能源或放电
            sell_from_ren = np.minimum(data['baseline_grid_sell'][ri],
                                       data['available_renewable'][ri])
            all_sol[ri]['p_dis_sell'] = np.maximum(
                data['baseline_grid_sell'][ri] - sell_from_ren, 0)
            all_sol[ri]['p_dis_load'] = data['baseline_discharge'][ri] - all_sol[ri]['p_dis_sell']
            all_sol[ri]['p_ren_sell'] = sell_from_ren
            all_sol[ri]['p_grid_load'] = np.maximum(
                data['facility_load'][ri] - all_sol[ri]['p_ren_dir'] - all_sol[ri]['p_dis_load'], 0)
            all_sol[ri]['p_buy'] = all_sol[ri]['p_grid_load'] + all_sol[ri]['p_grid_ch']
            all_sol[ri]['p_sell'] = all_sol[ri]['p_ren_sell'] + all_sol[ri]['p_dis_sell']
            all_sol[ri]['p_net'] = all_sol[ri]['p_buy'] - all_sol[ri]['p_sell']
    return all_sol
