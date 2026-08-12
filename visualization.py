"""
visualization.py - 可视化模块
功能：SOC轨迹图、净购电曲线、对比柱状图、Pareto前沿
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

REGIONS = ['RegionA', 'RegionB', 'RegionC', 'RegionD', 'RegionE', 'RegionF']
REGION_COLORS = {
    'RegionA': '#FF6B6B', 'RegionB': '#FF8E72', 'RegionC': '#FFB347',
    'RegionD': '#4ECDC4', 'RegionE': '#95E1A3', 'RegionF': '#6BCB77'
}


def plot_soc_trajectory(baseline_sol, opt_sol, data, output_path, t_start=0, t_end=240):
    """SOC轨迹对比图"""
    fig, axes = plt.subplots(3, 2, figsize=(16, 12), sharex=True)
    fig.suptitle(f'SOC轨迹对比 (第{t_start}-{t_end-1}小时)', fontsize=16, fontweight='bold')
    hours = np.arange(t_start, t_end)

    for ri, r in enumerate(REGIONS):
        ax = axes[ri // 2][ri % 2]
        ax.plot(hours, baseline_sol[ri]['soc'][t_start:t_end],
                color='#95A5A6', linewidth=1, label='基准', alpha=0.7)
        ax.plot(hours, opt_sol[ri]['soc'][t_start:t_end],
                color=REGION_COLORS[r], linewidth=1, label='优化', alpha=0.8)
        ax.axhline(y=data['init_soc'][ri], color='green', linestyle=':', alpha=0.5, label='初始SOC')
        ax.axhline(y=data['min_soc'][ri], color='red', linestyle='--', alpha=0.3, label='最小SOC')
        ax.axhline(y=data['storage_cap'][ri], color='blue', linestyle='--', alpha=0.3, label='容量上限')
        ax.set_ylabel('SOC (MWh)', fontsize=10)
        ax.set_title(f'{r} (容量{int(data["storage_cap"][ri])}MWh)', fontsize=11)
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)

    axes[2][0].set_xlabel('小时', fontsize=11)
    axes[2][1].set_xlabel('小时', fontsize=11)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[可视化] SOC轨迹图已保存")


def plot_net_import(baseline_sol, opt_sol, output_path, t_start=0, t_end=480):
    """系统净购电曲线对比"""
    fig, ax = plt.subplots(figsize=(16, 6))
    hours = np.arange(t_start, t_end)

    base_net = np.sum([baseline_sol[ri]['p_net'][t_start:t_end] for ri in range(6)], axis=0)
    opt_net = np.sum([opt_sol[ri]['p_net'][t_start:t_end] for ri in range(6)], axis=0)

    ax.plot(hours, base_net, color='#95A5A6', linewidth=1, label='基准', alpha=0.7)
    ax.plot(hours, opt_net, color='#E74C3C', linewidth=1, label='优化', alpha=0.8)
    ax.fill_between(hours, base_net, opt_net, alpha=0.2, color='#E74C3C')
    ax.set_xlabel('小时', fontsize=12)
    ax.set_ylabel('净购电功率 (MW)', fontsize=12)
    ax.set_title(f'系统净购电曲线对比 (第{t_start}-{t_end-1}小时)', fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[可视化] 净购电曲线图已保存")


def plot_comparison(baseline_metrics, opt_metrics, output_path):
    """基准vs优化对比柱状图"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('储能优化效果对比', fontsize=16, fontweight='bold')

    labels = ['基准', '优化']
    colors = ['#95A5A6', '#E74C3C']

    # 1. 运行成本
    ax = axes[0][0]
    vals = [baseline_metrics['total_cost'] / 1e4, opt_metrics['total_cost'] / 1e4]
    bars = ax.bar(labels, vals, color=colors, width=0.5)
    ax.set_ylabel('成本 (万元)', fontsize=11)
    ax.set_title('运行成本', fontsize=13)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, b.get_height()+50, f'{v:.0f}', ha='center', fontsize=11)

    # 2. 碳排放
    ax = axes[0][1]
    vals = [baseline_metrics['total_carbon'], opt_metrics['total_carbon']]
    bars = ax.bar(labels, vals, color=['#95A5A6', '#27AE60'], width=0.5)
    ax.set_ylabel('碳排放 (tCO2)', fontsize=11)
    ax.set_title('碳排放', fontsize=13)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, b.get_height()+500, f'{v:.0f}', ha='center', fontsize=11)

    # 3. 峰值净购电
    ax = axes[1][0]
    vals = [baseline_metrics['peak_net_import'], opt_metrics['peak_net_import']]
    bars = ax.bar(labels, vals, color=['#95A5A6', '#3498DB'], width=0.5)
    ax.set_ylabel('峰值净购电 (MW)', fontsize=11)
    ax.set_title('峰值净购电功率', fontsize=13)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, b.get_height()+10, f'{v:.1f}', ha='center', fontsize=11)

    # 4. 负荷波动
    ax = axes[1][1]
    vals = [baseline_metrics['fluctuation'], opt_metrics['fluctuation']]
    bars = ax.bar(labels, vals, color=['#95A5A6', '#F39C12'], width=0.5)
    ax.set_ylabel('负荷波动', fontsize=11)
    ax.set_title('负荷波动程度', fontsize=13)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, b.get_height()+500, f'{v:.0f}', ha='center', fontsize=11)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[可视化] 对比图已保存")


def plot_region_comparison(baseline_region, opt_region, output_path):
    """分区域对比图"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('分区域储能优化效果', fontsize=16, fontweight='bold')
    x = np.arange(len(REGIONS))
    width = 0.35

    # 1. 成本
    ax = axes[0][0]
    b_vals = [baseline_region[r]['cost']/1e4 for r in REGIONS]
    o_vals = [opt_region[r]['cost']/1e4 for r in REGIONS]
    ax.bar(x - width/2, b_vals, width, label='基准', color='#95A5A6')
    ax.bar(x + width/2, o_vals, width, label='优化', color='#E74C3C')
    ax.set_xticks(x); ax.set_xticklabels(REGIONS, rotation=30)
    ax.set_ylabel('成本 (万元)'); ax.set_title('分区域运行成本')
    ax.legend(); ax.grid(alpha=0.3)

    # 2. 碳排
    ax = axes[0][1]
    b_vals = [baseline_region[r]['carbon'] for r in REGIONS]
    o_vals = [opt_region[r]['carbon'] for r in REGIONS]
    ax.bar(x - width/2, b_vals, width, label='基准', color='#95A5A6')
    ax.bar(x + width/2, o_vals, width, label='优化', color='#27AE60')
    ax.set_xticks(x); ax.set_xticklabels(REGIONS, rotation=30)
    ax.set_ylabel('碳排放 (tCO2)'); ax.set_title('分区域碳排放')
    ax.legend(); ax.grid(alpha=0.3)

    # 3. 新能源利用率
    ax = axes[1][0]
    b_vals = [baseline_region[r]['renewable_utilization']*100 for r in REGIONS]
    o_vals = [opt_region[r]['renewable_utilization']*100 for r in REGIONS]
    ax.bar(x - width/2, b_vals, width, label='基准', color='#95A5A6')
    ax.bar(x + width/2, o_vals, width, label='优化', color='#F39C12')
    ax.set_xticks(x); ax.set_xticklabels(REGIONS, rotation=30)
    ax.set_ylabel('利用率 (%)'); ax.set_title('新能源利用率')
    ax.legend(); ax.grid(alpha=0.3)

    # 4. 峰值净购电
    ax = axes[1][1]
    b_vals = [baseline_region[r]['peak_net_import'] for r in REGIONS]
    o_vals = [opt_region[r]['peak_net_import'] for r in REGIONS]
    ax.bar(x - width/2, b_vals, width, label='基准', color='#95A5A6')
    ax.bar(x + width/2, o_vals, width, label='优化', color='#3498DB')
    ax.set_xticks(x); ax.set_xticklabels(REGIONS, rotation=30)
    ax.set_ylabel('峰值净购电 (MW)'); ax.set_title('分区域峰值净购电')
    ax.legend(); ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[可视化] 分区域对比图已保存")


def plot_pareto(pareto_points, output_path):
    """Pareto前沿图"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Pareto前沿分析', fontsize=16, fontweight='bold')

    costs = [p[0]/1e4 for p in pareto_points]
    carbons = [p[1] for p in pareto_points]
    peaks = [p[2] for p in pareto_points]
    flucs = [p[3] for p in pareto_points]
    labels = [p[4] for p in pareto_points]

    ax = axes[0]
    ax.scatter(costs, carbons, c=range(len(pareto_points)), cmap='viridis', s=100, zorder=5)
    for i, l in enumerate(labels):
        ax.annotate(l, (costs[i], carbons[i]), fontsize=8, xytext=(5, 5), textcoords='offset points')
    ax.set_xlabel('运行成本 (万元)'); ax.set_ylabel('碳排放 (tCO2)')
    ax.set_title('成本-碳排放权衡'); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.scatter(peaks, flucs, c=range(len(pareto_points)), cmap='viridis', s=100, zorder=5)
    for i, l in enumerate(labels):
        ax.annotate(l, (peaks[i], flucs[i]), fontsize=8, xytext=(5, 5), textcoords='offset points')
    ax.set_xlabel('峰值净购电 (MW)'); ax.set_ylabel('负荷波动')
    ax.set_title('峰值-波动权衡'); ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[可视化] Pareto前沿图已保存")


def plot_charge_discharge(opt_sol, output_path, t_start=0, t_end=240):
    """充放电策略图"""
    fig, axes = plt.subplots(3, 2, figsize=(16, 12), sharex=True)
    fig.suptitle(f'优化后充放电策略 (第{t_start}-{t_end-1}小时)', fontsize=16, fontweight='bold')
    hours = np.arange(t_start, t_end)

    for ri, r in enumerate(REGIONS):
        ax = axes[ri // 2][ri % 2]
        ax.bar(hours, opt_sol[ri]['p_charge'][t_start:t_end],
               color='#3498DB', alpha=0.7, label='充电', width=1.0)
        ax.bar(hours, -opt_sol[ri]['p_discharge'][t_start:t_end],
               color='#E74C3C', alpha=0.7, label='放电', width=1.0)
        ax.axhline(y=0, color='black', linewidth=0.5)
        ax.set_ylabel('功率 (MW)'); ax.set_title(r)
        ax.legend(fontsize=8); ax.grid(alpha=0.3)

    axes[2][0].set_xlabel('小时'); axes[2][1].set_xlabel('小时')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[可视化] 充放电策略图已保存")
