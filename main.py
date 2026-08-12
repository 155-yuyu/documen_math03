"""
main.py - 储能协同优化模型主程序
问题三：面向算电协同的多目标调度优化研究

流程：
1. 加载数据 + 基准指标
2. 成本最优LP求解
3. 碳排最优LP求解
4. 6组加权Pareto分析
5. 保存结果(Excel+图表)
"""

import os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_loader import load_all_data, compute_baseline_metrics, REGIONS, T_MAIN
from lp_model import solve_all_regions, solve_weighted, extract_solution, get_all_solutions
from metrics import compute_metrics, compute_region_metrics, compare_metrics, get_baseline_solution
from visualization import (
    plot_soc_trajectory, plot_net_import, plot_comparison,
    plot_region_comparison, plot_pareto, plot_charge_discharge
)

DATA_DIR = r'D:\数学建模\26数学建模暑期模拟训练\第二次训练题目（三选一）\C题 面向算电协同的多目标调度优化研究'
PROJECT_DIR = r'D:\mathematical-modeling-researcher\数学建模项目_问题三_储能协同优化'
RESULT_DIR = os.path.join(PROJECT_DIR, '04_实验结果')
os.makedirs(RESULT_DIR, exist_ok=True)


def run_single_objective(data, objective, label):
    """运行单目标优化"""
    print(f"\n{'='*60}")
    print(f"{label} (目标: {objective})")
    print(f"{'='*60}")
    t0 = time.time()
    solutions = solve_all_regions(data, objective)
    t1 = time.time()
    print(f"求解耗时: {t1-t0:.1f}s")

    all_sol = get_all_solutions(data, solutions)
    metrics = compute_metrics(all_sol, data)
    region_metrics = compute_region_metrics(all_sol, data)

    print(f"\n--- {label} 指标 ---")
    print(f"运行成本: {metrics['total_cost']/1e4:.2f} 万元")
    print(f"碳排放: {metrics['total_carbon']:.2f} tCO2")
    print(f"峰值净购电: {metrics['peak_net_import']:.1f} MW")
    print(f"负荷波动: {metrics['fluctuation']:.1f}")

    return all_sol, metrics, region_metrics


def run_pareto(data, baseline_metrics):
    """多权重Pareto分析"""
    print(f"\n{'='*60}")
    print("Pareto前沿分析 (多权重扫描)")
    print(f"{'='*60}")

    configs = [
        (0.70, 0.10, 0.10, 0.10, "成本优先"),
        (0.10, 0.70, 0.10, 0.10, "碳排优先"),
        (0.10, 0.10, 0.70, 0.10, "峰值优先(近似)"),
        (0.10, 0.10, 0.10, 0.70, "波动优先(近似)"),
        (0.25, 0.25, 0.25, 0.25, "均衡策略"),
        (0.40, 0.30, 0.15, 0.15, "成本-碳排均衡"),
    ]

    pareto_points = []
    pareto_results = []

    for w1, w2, w3, w4, label in configs:
        print(f"\n  --- {label} ---")
        weights = (w1, w2, w3, w4)
        solutions = solve_weighted(data, weights)
        all_sol = get_all_solutions(data, solutions)
        metrics = compute_metrics(all_sol, data)

        pareto_points.append((
            metrics['total_cost'],
            metrics['total_carbon'],
            metrics['peak_net_import'],
            metrics['fluctuation'],
            label
        ))
        pareto_results.append({
            'label': label,
            'weights': weights,
            'all_sol': all_sol,
            'metrics': metrics,
        })
        print(f"  成本={metrics['total_cost']/1e4:.0f}万, 碳排={metrics['total_carbon']:.0f}t, "
              f"峰值={metrics['peak_net_import']:.0f}MW, 波动={metrics['fluctuation']:.0f}")

    return pareto_points, pareto_results


def save_results(data, baseline_metrics, baseline_region,
                 cost_sol, cost_metrics, cost_region,
                 carbon_sol, carbon_metrics, carbon_region,
                 pareto_points, pareto_results):
    """保存全部结果"""
    print(f"\n{'='*60}")
    print("保存结果文件")
    print(f"{'='*60}")

    baseline_sol = get_baseline_solution(data)

    # ==================== Excel ====================
    with pd.ExcelWriter(os.path.join(RESULT_DIR, 'result.xlsx'),
                        engine='openpyxl') as writer:
        # 1. 指标对比
        comp = compare_metrics(baseline_metrics, cost_metrics)
        data_rows = [
            {'指标': '运行成本(元)', '基准': baseline_metrics['total_cost'],
             '成本最优': cost_metrics['total_cost'],
             '碳排最优': carbon_metrics['total_carbon'] if False else None,
             '变化率(%)': comp['total_cost']['change_pct']},
            {'指标': '碳排放(tCO2)', '基准': baseline_metrics['total_carbon'],
             '成本最优': cost_metrics['total_carbon'],
             '碳排最优': carbon_metrics['total_carbon'],
             '变化率(%)': None},
            {'指标': '峰值净购电(MW)', '基准': baseline_metrics['peak_net_import'],
             '成本最优': cost_metrics['peak_net_import'],
             '碳排最优': carbon_metrics['peak_net_import'],
             '变化率(%)': None},
            {'指标': '负荷波动', '基准': baseline_metrics['fluctuation'],
             '成本最优': cost_metrics['fluctuation'],
             '碳排最优': carbon_metrics['fluctuation'],
             '变化率(%)': None},
        ]
        pd.DataFrame(data_rows).to_excel(writer, sheet_name='指标对比', index=False)

        # 2. 分区域指标
        region_data = []
        for r in REGIONS:
            region_data.append({
                '区域': r,
                '基准成本(万元)': baseline_region[r]['cost']/1e4,
                '成本最优(万元)': cost_region[r]['cost']/1e4,
                '碳排最优(万元)': carbon_region[r]['cost']/1e4,
                '基准碳排放(tCO2)': baseline_region[r]['carbon'],
                '成本最优碳排放(tCO2)': cost_region[r]['carbon'],
                '碳排最优碳排放(tCO2)': carbon_region[r]['carbon'],
                '基准新能源利用率(%)': baseline_region[r]['renewable_utilization']*100,
                '成本最优利用率(%)': cost_region[r]['renewable_utilization']*100,
                '碳排最优利用率(%)': carbon_region[r]['renewable_utilization']*100,
                '基准峰值净购电(MW)': baseline_region[r]['peak_net_import'],
                '成本最优峰值(MW)': cost_region[r]['peak_net_import'],
                '碳排最优峰值(MW)': carbon_region[r]['peak_net_import'],
            })
        pd.DataFrame(region_data).to_excel(writer, sheet_name='分区域指标', index=False)

        # 3. Pareto分析
        if pareto_results:
            pareto_data = []
            for pr in pareto_results:
                m = pr['metrics']
                pareto_data.append({
                    '策略': pr['label'],
                    '权重': str(pr['weights']),
                    '运行成本(万元)': m['total_cost']/1e4,
                    '碳排放(tCO2)': m['total_carbon'],
                    '峰值净购电(MW)': m['peak_net_import'],
                    '负荷波动': m['fluctuation'],
                })
            pd.DataFrame(pareto_data).to_excel(writer, sheet_name='Pareto分析', index=False)

        # 4. 逐时调度数据(成本最优, 前240小时示例)
        hour_data = []
        for t in range(240):
            row = {'小时': t}
            for ri, r in enumerate(REGIONS):
                sol = cost_sol[ri]
                row[f'{r}_充电(MW)'] = sol['p_charge'][t]
                row[f'{r}_放电(MW)'] = sol['p_discharge'][t]
                row[f'{r}_SOC(MWh)'] = sol['soc'][t]
                row[f'{r}_净购电(MW)'] = sol['p_net'][t]
            hour_data.append(row)
        pd.DataFrame(hour_data).to_excel(writer, sheet_name='逐时调度(成本最优)', index=False)

    print(f"[保存] result.xlsx")

    # ==================== 图表 ====================
    plot_soc_trajectory(baseline_sol, cost_sol, data,
                        os.path.join(RESULT_DIR, 'soc_trajectory.png'))
    plot_net_import(baseline_sol, cost_sol,
                    os.path.join(RESULT_DIR, 'net_import.png'))
    plot_comparison(baseline_metrics, cost_metrics,
                    os.path.join(RESULT_DIR, 'comparison.png'))
    plot_region_comparison(baseline_region, cost_region,
                           os.path.join(RESULT_DIR, 'region_comparison.png'))
    plot_charge_discharge(cost_sol,
                          os.path.join(RESULT_DIR, 'charge_discharge.png'))
    if pareto_points:
        plot_pareto(pareto_points, os.path.join(RESULT_DIR, 'pareto_frontier.png'))

    print(f"[保存] 所有图表已保存至 {RESULT_DIR}")


def main():
    print(f"{'='*60}")
    print("储能协同优化模型 — 问题三")
    print("面向算电协同的多目标调度优化研究")
    print(f"{'='*60}")

    # 1. 加载数据
    print("\n[1/5] 加载数据...")
    data = load_all_data(DATA_DIR)

    # 2. 基准指标
    print("\n[2/5] 基准指标...")
    baseline_metrics = compute_baseline_metrics(data)
    baseline_sol = get_baseline_solution(data)
    baseline_region = compute_region_metrics(baseline_sol, data)
    print(f"运行成本: {baseline_metrics['total_cost']/1e4:.2f} 万元")
    print(f"碳排放: {baseline_metrics['total_carbon']:.2f} tCO2")
    print(f"峰值净购电: {baseline_metrics['peak_net_import']:.1f} MW")
    print(f"负荷波动: {baseline_metrics['fluctuation']:.1f}")

    # 3. 成本最优 + 碳排最优
    print("\n[3/5] 单目标优化...")
    cost_sol, cost_metrics, cost_region = run_single_objective(data, 'cost', '成本最优')
    carbon_sol, carbon_metrics, carbon_region = run_single_objective(data, 'carbon', '碳排最优')

    # 4. Pareto分析
    print("\n[4/5] Pareto前沿分析...")
    pareto_points, pareto_results = run_pareto(data, baseline_metrics)

    # 5. 保存结果
    print("\n[5/5] 保存结果...")
    save_results(data, baseline_metrics, baseline_region,
                 cost_sol, cost_metrics, cost_region,
                 carbon_sol, carbon_metrics, carbon_region,
                 pareto_points, pareto_results)

    # 最终摘要
    print(f"\n{'='*60}")
    print("最终结果摘要")
    print(f"{'='*60}")
    print(f"{'指标':<20} {'基准':>15} {'成本最优':>15} {'碳排最优':>15}")
    print("-"*70)
    print(f"{'运行成本(万元)':<20} {baseline_metrics['total_cost']/1e4:>15.2f} "
          f"{cost_metrics['total_cost']/1e4:>15.2f} {carbon_metrics['total_cost']/1e4:>15.2f}")
    print(f"{'碳排放(tCO2)':<20} {baseline_metrics['total_carbon']:>15.0f} "
          f"{cost_metrics['total_carbon']:>15.0f} {carbon_metrics['total_carbon']:>15.0f}")
    print(f"{'峰值净购电(MW)':<20} {baseline_metrics['peak_net_import']:>15.1f} "
          f"{cost_metrics['peak_net_import']:>15.1f} {carbon_metrics['peak_net_import']:>15.1f}")
    print(f"{'负荷波动':<20} {baseline_metrics['fluctuation']:>15.0f} "
          f"{cost_metrics['fluctuation']:>15.0f} {carbon_metrics['fluctuation']:>15.0f}")
    print(f"{'='*60}")
    print(f"\n结果文件保存在: {RESULT_DIR}")


if __name__ == '__main__':
    main()
