"""
data_loader.py - 数据加载与预处理模块
功能：加载全部Excel数据，构建numpy数组
"""

import pandas as pd
import numpy as np
import os

# ==================== 全局常量 ====================
REGIONS = ['RegionA', 'RegionB', 'RegionC', 'RegionD', 'RegionE', 'RegionF']
REGION_TO_IDX = {r: i for i, r in enumerate(REGIONS)}
N_REGIONS = 6
T_TOTAL = 2407  # 0-2406
T_MAIN = 2400   # 0-2399为主时域


def load_all_data(data_dir):
    """加载全部数据文件，返回数据字典"""
    data = {}

    # ==================== 1. GPU_information.xlsx ====================
    gpu_info = pd.read_excel(os.path.join(data_dir, 'GPU_information.xlsx'),
                             sheet_name='GPU中心基础情况')
    data['gpu_info'] = gpu_info
    data['pue'] = np.array(
        [gpu_info.loc[gpu_info['Region'] == r, 'PUE'].values[0] for r in REGIONS],
        dtype=np.float64)
    print(f"[GPU信息] PUE: {data['pue']}")

    # ==================== 2. storage_information.xlsx ====================
    storage = pd.read_excel(os.path.join(data_dir, 'dataset',
                           'storage_information.xlsx'),
                           sheet_name='storage_information')
    data['storage'] = storage
    data['storage_cap'] = np.array(
        [storage.loc[storage['Region'] == r, 'StorageCapacity_MWh'].values[0] for r in REGIONS])
    data['min_soc'] = np.array(
        [storage.loc[storage['Region'] == r, 'MinSOC_MWh'].values[0] for r in REGIONS])
    data['init_soc'] = np.array(
        [storage.loc[storage['Region'] == r, 'InitialSOC_MWh'].values[0] for r in REGIONS])
    data['max_charge'] = np.array(
        [storage.loc[storage['Region'] == r, 'MaxChargePower_MW'].values[0] for r in REGIONS])
    data['max_discharge'] = np.array(
        [storage.loc[storage['Region'] == r, 'MaxDischargePower_MW'].values[0] for r in REGIONS])
    data['eta_ch'] = np.array(
        [storage.loc[storage['Region'] == r, 'ChargeEfficiency'].values[0] for r in REGIONS])
    data['eta_dis'] = np.array(
        [storage.loc[storage['Region'] == r, 'DischargeEfficiency'].values[0] for r in REGIONS])
    data['max_grid_import'] = np.array(
        [storage.loc[storage['Region'] == r, 'MaxGridImport_MW'].values[0] for r in REGIONS])
    data['max_grid_export'] = np.array(
        [storage.loc[storage['Region'] == r, 'MaxGridExport_MW'].values[0] for r in REGIONS])
    data['sell_limit'] = np.array(
        [storage.loc[storage['Region'] == r, 'SellLimit_MW'].values[0] for r in REGIONS])

    print(f"[储能信息] 容量: {data['storage_cap']}")
    print(f"  初始SOC: {data['init_soc']}")
    print(f"  最大充放电: {data['max_charge']} / {data['max_discharge']}")

    # ==================== 3. region_time_data.xlsx ====================
    rtd = pd.read_excel(os.path.join(data_dir, 'dataset',
                        'region_time_data.xlsx'),
                        sheet_name='region_time_data')
    data['rtd'] = rtd

    # 构建2D数组 [6, 2407]
    def build_array(col_name):
        arr = np.zeros((N_REGIONS, T_TOTAL))
        for ri, r in enumerate(REGIONS):
            subset = rtd[rtd['Region'] == r].sort_values('Hour')
            hours = subset['Hour'].values.astype(int)
            vals = subset[col_name].values
            arr[ri, hours] = vals
        return arr

    data['electricity_price'] = build_array('ElectricityPrice_CNY_per_MWh')
    data['sell_price'] = build_array('SellPrice_CNY_per_MWh')
    data['carbon_intensity'] = build_array('CarbonIntensity_tCO2_per_MWh')
    data['available_renewable'] = build_array('AvailableRenewable_MW')
    data['nonai_it_load'] = build_array('NonAI_IT_Load_MW')
    data['baseline_ai_it_load'] = build_array('Baseline_AI_IT_Load_MW')
    data['baseline_soc'] = build_array('SOC_MWh')
    data['baseline_charge'] = build_array('ChargePower_MW')
    data['baseline_discharge'] = build_array('DischargePower_MW')
    data['baseline_grid_buy'] = build_array('GridPurchase_MW')
    data['baseline_grid_sell'] = build_array('GridSell_MW')
    data['baseline_used_renewable'] = build_array('UsedRenewable_MW')
    data['baseline_renewable_charge'] = build_array('RenewableCharge_MW')
    data['baseline_curtailment'] = build_array('Curtailment_MW')
    data['baseline_net_import'] = build_array('NetGridImport_MW')

    # IT负荷 = AI + NonAI
    data['it_load'] = data['baseline_ai_it_load'] + data['nonai_it_load']
    # 设施负荷 = IT负荷 × PUE
    data['facility_load'] = data['it_load'] * data['pue'][:, None]

    print(f"[区域时间数据] {len(rtd)}条记录加载完成")
    print(f"  电价范围: [{data['electricity_price'].min():.1f}, {data['electricity_price'].max():.1f}]")
    print(f"  设施负荷均值: {data['facility_load'].mean(axis=1)}")

    return data


def compute_baseline_metrics(data):
    """计算基准策略指标"""
    t_range = slice(0, T_MAIN)
    cost = np.sum(
        data['baseline_grid_buy'][:, t_range] * data['electricity_price'][:, t_range] -
        data['baseline_grid_sell'][:, t_range] * data['sell_price'][:, t_range])
    carbon = np.sum(
        data['baseline_grid_buy'][:, t_range] * data['carbon_intensity'][:, t_range])
    net_import = data['baseline_net_import'][:, t_range]
    peak_net = np.max(np.sum(net_import, axis=0))
    # 负荷波动 = sum|delta|
    total_net = np.sum(net_import, axis=0)
    fluctuation = np.sum(np.abs(np.diff(total_net)))

    return {
        'total_cost': cost,
        'total_carbon': carbon,
        'peak_net_import': peak_net,
        'fluctuation': fluctuation,
    }


if __name__ == '__main__':
    data_dir = r'D:\数学建模\26数学建模暑期模拟训练\第二次训练题目（三选一）\C题 面向算电协同的多目标调度优化研究'
    data = load_all_data(data_dir)
    baseline = compute_baseline_metrics(data)
    print(f"\n=== 基准指标 ===")
    print(f"运行成本: {baseline['total_cost']/1e4:.2f} 万元")
    print(f"碳排放: {baseline['total_carbon']:.2f} tCO2")
    print(f"峰值净购电: {baseline['peak_net_import']:.1f} MW")
    print(f"负荷波动: {baseline['fluctuation']:.1f}")
