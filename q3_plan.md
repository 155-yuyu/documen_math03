# 问题三：储能协同优化模型 — 建模方案

## 1 问题分析

### 1.1 问题描述

在给定任务调度和逐时负荷的基础上，建立储能协同优化模型，设计储能充放电策略，分析储能系统对运行成本、碳排放、区域峰值净购电功率和负荷波动程度的影响。

### 1.2 问题定位

| 维度 | 说明 |
|------|------|
| 问题类型 | 线性规划（LP）——储能充放电调度优化 |
| 输入 | 给定IT负荷（Baseline_AI_IT_Load + NonAI_IT_Load）、逐时电力参数（电价、售电价、碳强度、可用新能源）、储能参数 |
| 决策变量 | 储能充放电功率、购售电量、新能源分配策略 |
| 不变量 | 任务调度、任务迁移、开工时段（已在问题二确定） |
| 优化目标 | 运行成本、碳排放、峰值净购电、负荷波动 |
| 时间域 | 0–2406小时（主时域0–2399，收尾2400–2405，终端结算2406） |

### 1.3 与问题二的核心区别

| 对比维度 | 问题二 | 问题三 |
|----------|--------|--------|
| 优化对象 | 任务迁移 + 开工时段 | 储能充放电 + 购售电 + 新能源分配 |
| IT负荷 | 由任务调度计算 | 给定（Baseline_AI_IT_Load + NonAI_IT_Load） |
| 储能策略 | 固定（使用基准值） | 优化对象 |
| 问题性质 | 大规模组合优化（NP-hard） | 线性规划（多项式可解） |
| 规模 | 50,000任务 × 6区域 | 6区域 × 2,407小时 |

### 1.4 问题特点

1. **纯连续优化**：所有决策变量均为连续功率值（MW），无整数/组合变量
2. **线性结构**：SOC动态、功率平衡、目标函数均为线性关系 → 标准LP
3. **多区域解耦**：各区域储能独立运行，无跨区域传输 → 可并行求解
4. **时间耦合**：SOC动态方程将相邻时间步关联
5. **终端约束**：SOC(2406) ≥ InitialSOC → 需考虑全时域优化

---

## 2 数据集分析

### 2.1 储能参数表

| 区域 | 容量(MWh) | MinSOC(MWh) | 初始SOC(MWh) | 最大充(MW) | 最大放(MW) | 充电效率 | 放电效率 | 最大购电(MW) | 最大售电(MW) | 售电限制(MW) |
|------|----------|-------------|-------------|-----------|-----------|---------|---------|------------|------------|------------|
| RegionA | 350 | 35 | 157.5 | 100 | 100 | 0.93 | 0.92 | 550 | 0 | 0 |
| RegionB | 320 | 32 | 144.0 | 90 | 90 | 0.93 | 0.92 | 520 | 0 | 0 |
| RegionC | 300 | 30 | 135.0 | 85 | 85 | 0.93 | 0.92 | 510 | 0 | 0 |
| RegionD | 900 | 90 | 405.0 | 260 | 260 | 0.94 | 0.93 | 510 | 180 | 180 |
| RegionE | 820 | 82 | 370.0 | 240 | 240 | 0.94 | 0.93 | 370 | 220 | 220 |
| RegionF | 850 | 85 | 382.5 | 250 | 250 | 0.94 | 0.93 | 340 | 220 | 220 |

**关键观察**：
- 东部区域（A/B/C）：无售电能力（MaxGridExport=0），只能购电和自用
- 西部区域（D/E/F）：具备售电能力，D限制180MW，E/F限制220MW
- 初始SOC均为容量的45%
- 充电效率0.93-0.94，放电效率0.92-0.93

### 2.2 给定IT负荷特征

| 区域 | PUE | IT负荷均值(MW) | 设施负荷均值(MW) | 新能源均值(MW) | 电价均值(元/MWh) | 碳强度均值 |
|------|-----|--------------|----------------|--------------|----------------|----------|
| RegionA | 1.35 | 337.5 | 455.6 | 799.8 | 707.5 | 0.578 |
| RegionB | 1.35 | 333.7 | 450.5 | 799.8 | 678.0 | 0.542 |
| RegionC | 1.38 | 332.2 | 458.4 | 799.8 | 658.3 | 0.514 |
| RegionD | 1.28 | 353.1 | 452.0 | 799.8 | 422.5 | 0.393 |
| RegionE | 1.25 | 353.1 | 441.4 | 799.8 | 373.4 | 0.206 |
| RegionF | 1.27 | 353.3 | 449.7 | 799.8 | 393.0 | 0.240 |

### 2.3 基准运行验证

**SOC动态方程验证**（最大误差 < 0.005）：
```
SOC[r,t] = SOC[r,t-1] + η_ch[r] × ChargePower[r,t] - DischargePower[r,t] / η_dis[r]
```

**功率平衡方程验证**（最大误差 < 0.0002）：
```
FacilityLoad + ChargePower = UsedRenewable + RenewableCharge + GridPurchase + DischargePower
```

**新能源平衡方程验证**（最大误差 < 0.0002）：
```
AvailableRenewable = UsedRenewable + RenewableCharge + GridSell + Curtailment
```

### 2.4 基准全系统指标（主时域0-2399）

| 区域 | 运行成本(万元) | 碳排放(tCO2) | 净购电范围(MW) |
|------|------------|------------|--------------|
| RegionA | 62,302 | 581,270 | 178–497 |
| RegionB | 57,212 | 519,699 | 178–468 |
| RegionC | 54,636 | 483,818 | 176–455 |
| RegionD | 8,618 | 262,961 | -180–283 |
| RegionE | -2,570 | 84,556 | -220–166 |
| RegionF | 36 | 113,056 | -220–153 |
| **总计** | **180,234** | **2,045,359** | — |

---

## 3 数学模型

### 3.1 集合与索引

| 符号 | 含义 |
|------|------|
| $\mathcal{R} = \{A, B, C, D, E, F\}$ | 区域集合 |
| $\mathcal{T} = \{0, 1, \ldots, 2406\}$ | 时间步集合 |
| $\mathcal{T}_{\text{main}} = \{0, \ldots, 2399\}$ | 主运行时域 |
| $\mathcal{T}_{\text{close}} = \{2400, \ldots, 2405\}$ | 收尾时域 |
| $t_{\text{end}} = 2406$ | 终端结算时点 |

### 3.2 输入参数

**逐时给定参数**（来自region_time_data.xlsx）：

| 符号 | 含义 | 单位 |
|------|------|------|
| $L^{\text{IT}}_{r,t}$ | 给定IT负荷 = $L^{\text{AI}}_{r,t} + L^{\text{NonAI}}_{r,t}$ | MW |
| $L^{\text{fac}}_{r,t}$ | 设施负荷 = $L^{\text{IT}}_{r,t} \times \text{PUE}_r$ | MW |
| $\pi_{r,t}$ | 购电电价 | 元/MWh |
| $\sigma_{r,t}$ | 售电电价 | 元/MWh |
| $e_{r,t}$ | 碳排放强度 | tCO2/MWh |
| $R_{r,t}$ | 可用新能源出力 | MW |

**储能参数**（来自storage_information.xlsx）：

| 符号 | 含义 | 单位 |
|------|------|------|
| $\overline{E}_r$ | 储能容量 | MWh |
| $\underline{E}_r$ | 最小SOC | MWh |
| $E^{\text{init}}_r$ | 初始SOC | MWh |
| $\overline{P}^{\text{ch}}_r$ | 最大充电功率 | MW |
| $\overline{P}^{\text{dis}}_r$ | 最大放电功率 | MW |
| $\eta^{\text{ch}}_r$ | 充电效率 | 无量纲 |
| $\eta^{\text{dis}}_r$ | 放电效率 | 无量纲 |
| $\overline{P}^{\text{buy}}_r$ | 最大购电功率 | MW |
| $\overline{P}^{\text{sell}}_r$ | 最大售电功率 | MW |
| $\overline{P}^{\text{sell,ren}}_r$ | 新能源售电限制 | MW |

### 3.3 决策变量

每区域每小时8个连续决策变量：

| 变量 | 含义 | 单位 |
|------|------|------|
| $p^{\text{ren,dir}}_{r,t}$ | 新能源直接供电（→负荷） | MW |
| $p^{\text{ren,ch}}_{r,t}$ | 新能源充电（→储能） | MW |
| $p^{\text{ren,sell}}_{r,t}$ | 新能源售电（→电网） | MW |
| $p^{\text{curt}}_{r,t}$ | 弃风弃光 | MW |
| $p^{\text{grid,ch}}_{r,t}$ | 电网充电（→储能） | MW |
| $p^{\text{grid,load}}_{r,t}$ | 电网供电（→负荷） | MW |
| $p^{\text{dis,load}}_{r,t}$ | 放电供负荷（→负荷） | MW |
| $p^{\text{dis,sell}}_{r,t}$ | 放电售电（→电网） | MW |

**派生变量**（由决策变量计算）：

| 变量 | 计算式 |
|------|--------|
| 总充电功率 $P^{\text{ch}}_{r,t}$ | $p^{\text{ren,ch}}_{r,t} + p^{\text{grid,ch}}_{r,t}$ |
| 总放电功率 $P^{\text{dis}}_{r,t}$ | $p^{\text{dis,load}}_{r,t} + p^{\text{dis,sell}}_{r,t}$ |
| 总购电 $P^{\text{buy}}_{r,t}$ | $p^{\text{grid,load}}_{r,t} + p^{\text{grid,ch}}_{r,t}$ |
| 总售电 $P^{\text{sell}}_{r,t}$ | $p^{\text{ren,sell}}_{r,t} + p^{\text{dis,sell}}_{r,t}$ |
| SOC $E_{r,t}$ | $E_{r,t-1} + \eta^{\text{ch}}_r \cdot P^{\text{ch}}_{r,t} - P^{\text{dis}}_{r,t} / \eta^{\text{dis}}_r$ |
| 净购电 $P^{\text{net}}_{r,t}$ | $P^{\text{buy}}_{r,t} - P^{\text{sell}}_{r,t}$ |

**决策变量总数**：$6 \times 2407 \times 8 = 115{,}536$，加上SOC派生变量 $6 \times 2407 = 14{,}442$，总计约13万。

### 3.4 约束条件

#### C1. 新能源平衡
$$p^{\text{ren,dir}}_{r,t} + p^{\text{ren,ch}}_{r,t} + p^{\text{ren,sell}}_{r,t} + p^{\text{curt}}_{r,t} = R_{r,t}, \quad \forall r \in \mathcal{R}, t \in \mathcal{T}$$

#### C2. 负荷供电平衡
$$p^{\text{ren,dir}}_{r,t} + p^{\text{grid,load}}_{r,t} + p^{\text{dis,load}}_{r,t} = L^{\text{fac}}_{r,t}, \quad \forall r \in \mathcal{R}, t \in \mathcal{T}$$

#### C3. SOC动态方程
$$E_{r,t} = E_{r,t-1} + \eta^{\text{ch}}_r \cdot (p^{\text{ren,ch}}_{r,t} + p^{\text{grid,ch}}_{r,t}) - \frac{p^{\text{dis,load}}_{r,t} + p^{\text{dis,sell}}_{r,t}}{\eta^{\text{dis}}_r}$$

初始条件：$E_{r,-1} = E^{\text{init}}_r$

#### C4. SOC上下限约束
$$\underline{E}_r \leq E_{r,t} \leq \overline{E}_r, \quad \forall r \in \mathcal{R}, t \in \mathcal{T}$$

#### C5. SOC终端约束
$$E_{r, t_{\text{end}}} \geq E^{\text{init}}_r, \quad \forall r \in \mathcal{R}$$

#### C6. 充电功率约束
$$0 \leq p^{\text{ren,ch}}_{r,t} + p^{\text{grid,ch}}_{r,t} \leq \overline{P}^{\text{ch}}_r$$

#### C7. 放电功率约束
$$0 \leq p^{\text{dis,load}}_{r,t} + p^{\text{dis,sell}}_{r,t} \leq \overline{P}^{\text{dis}}_r$$

#### C8. 购电功率约束
$$0 \leq p^{\text{grid,load}}_{r,t} + p^{\text{grid,ch}}_{r,t} \leq \overline{P}^{\text{buy}}_r$$

#### C9. 售电功率约束
$$0 \leq p^{\text{ren,sell}}_{r,t} + p^{\text{dis,sell}}_{r,t} \leq \overline{P}^{\text{sell}}_r$$

#### C10. 新能源售电限制
$$0 \leq p^{\text{ren,sell}}_{r,t} \leq \overline{P}^{\text{sell,ren}}_r$$

#### C11. 非负约束
$$p^{\text{ren,dir}}_{r,t}, p^{\text{ren,ch}}_{r,t}, p^{\text{ren,sell}}_{r,t}, p^{\text{curt}}_{r,t}, p^{\text{grid,ch}}_{r,t}, p^{\text{grid,load}}_{r,t}, p^{\text{dis,load}}_{r,t}, p^{\text{dis,sell}}_{r,t} \geq 0$$

---

## 4 目标函数

### 4.1 主目标：运行成本最小化

$$\min F_1 = \sum_{r \in \mathcal{R}} \sum_{t \in \mathcal{T}} \left[ P^{\text{buy}}_{r,t} \cdot \pi_{r,t} - P^{\text{sell}}_{r,t} \cdot \sigma_{r,t} \right]$$

### 4.2 辅助目标1：碳排放最小化

$$\min F_2 = \sum_{r \in \mathcal{R}} \sum_{t \in \mathcal{T}} P^{\text{buy}}_{r,t} \cdot e_{r,t}$$

### 4.3 辅助目标2：峰值净购电功率最小化

$$\min F_3 = \max_{t \in \mathcal{T}} \sum_{r \in \mathcal{R}} P^{\text{net}}_{r,t}$$

可通过引入辅助变量 $P^{\text{peak}}$ 线性化：
$$\min F_3 = P^{\text{peak}}, \quad \text{s.t.} \sum_r P^{\text{net}}_{r,t} \leq P^{\text{peak}}, \forall t$$

### 4.4 辅助目标3：负荷波动最小化

以净购电功率的逐时差分绝对值之和衡量：
$$\min F_4 = \sum_{t=1}^{|\mathcal{T}|} \left| \sum_r P^{\text{net}}_{r,t} - \sum_r P^{\text{net}}_{r,t-1} \right|$$

可通过引入辅助变量 $\delta_t \geq 0$ 线性化：
$$\min F_4 = \sum_t \delta_t, \quad \text{s.t.} \pm\left(\sum_r P^{\text{net}}_{r,t} - \sum_r P^{\text{net}}_{r,t-1}\right) \leq \delta_t$$

### 4.5 多目标综合

采用加权求和法，归一化后组合：

$$\min F = w_1 \frac{F_1}{F_1^{\text{norm}}} + w_2 \frac{F_2}{F_2^{\text{norm}}} + w_3 \frac{F_3}{F_3^{\text{norm}}} + w_4 \frac{F_4}{F_4^{\text{norm}}}$$

---

## 5 模型选择与求解策略

### 5.1 模型性质判定

| 判据 | 结论 |
|------|------|
| 变量类型 | 全部连续 → LP |
| 目标函数 | 线性（加权求和后仍线性） | 
| 约束类型 | 等式（平衡）+ 不等式（上下限）→ 标准LP |
| 问题规模 | ~13万变量，~5万约束 → 大规模稀疏LP |
| 可解性 | 多项式时间，HiGHS/CBC可精确求解 |

### 5.2 求解策略

**分层求解方案**：

1. **成本最优解**：以 $F_1$ 为单一目标求解 → 获得成本下界
2. **碳排最优解**：以 $F_2$ 为单一目标求解 → 获得碳排下界
3. **峰值最优解**：以 $F_3$ 为单一目标求解 → 获得峰值下界
4. **波动最优解**：以 $F_4$ 为单一目标求解 → 获得波动下界
5. **加权Pareto分析**：6组权重策略扫描 → Pareto前沿
6. **基准对比**：与region_time_data基准策略逐项对比

### 5.3 求解工具

- **求解器**：`scipy.optimize.linprog` (HiGHS solver)
- **矩阵格式**：稀疏矩阵（`scipy.sparse.csr_matrix`）
- **变量消减**：利用等式约束消去 $p^{\text{curt}}$ 和 $p^{\text{grid,load}}$，将8变量减为6变量
- **区域解耦**：各区域独立求解（成本/碳排目标），系统级目标（峰值/波动）需联合求解

### 5.4 变量消减策略

利用等式约束消去部分变量：

1. 由C1（新能源平衡）：$p^{\text{curt}}_{r,t} = R_{r,t} - p^{\text{ren,dir}}_{r,t} - p^{\text{ren,ch}}_{r,t} - p^{\text{ren,sell}}_{r,t}$
2. 由C2（负荷平衡）：$p^{\text{grid,load}}_{r,t} = L^{\text{fac}}_{r,t} - p^{\text{ren,dir}}_{r,t} - p^{\text{dis,load}}_{r,t}$

消减后剩余6个决策变量：$p^{\text{ren,dir}}, p^{\text{ren,ch}}, p^{\text{ren,sell}}, p^{\text{grid,ch}}, p^{\text{dis,load}}, p^{\text{dis,sell}}$

需额外施加消去变量的非负约束：
- $p^{\text{curt}} \geq 0$ → $p^{\text{ren,dir}} + p^{\text{ren,ch}} + p^{\text{ren,sell}} \leq R_{r,t}$
- $p^{\text{grid,load}} \geq 0$ → $p^{\text{ren,dir}} + p^{\text{dis,load}} \leq L^{\text{fac}}_{r,t}$

---

## 6 影响分析框架

### 6.1 对比维度

| 指标 | 基准值 | 优化方向 | 评价方法 |
|------|--------|---------|---------|
| 运行成本 | 180,234万元 | 最小化 | 直接对比 |
| 碳排放 | 2,045,359 tCO2 | 最小化 | 直接对比 |
| 峰值净购电 | ~2,394 MW | 最小化 | max_t Σ P_net |
| 负荷波动 | 基准逐时差分 | 最小化 | Σ|ΔP_net| |

### 6.2 分析内容

1. **成本优化效果**：电价套利（谷充峰放）、新能源消纳提升
2. **碳排优化效果**：低碳时段多充电、高碳时段多放电
3. **峰值削减效果**：放电削峰、充电填谷
4. **波动平抑效果**：储能平滑净购电曲线
5. **分区域影响**：东西部区域差异分析
6. **SOC轨迹分析**：优化前后SOC变化对比

---

## 7 程序结构设计

```
03_模型程序/
├── data_loader.py      # 数据加载与预处理
├── lp_model.py         # LP模型构建与求解
├── metrics.py          # 指标计算（成本/碳排/峰值/波动）
├── visualization.py     # 可视化（SOC轨迹/负荷曲线/对比图）
└── main.py             # 主程序（串联全流程）
```

### 7.1 各模块功能

| 模块 | 功能 |
|------|------|
| `data_loader.py` | 加载region_time_data + storage_information + GPU_information，构建numpy数组 |
| `lp_model.py` | 构建稀疏LP（变量/约束/目标），调用HiGHS求解 |
| `metrics.py` | 计算四项指标 + 分区域指标 |
| `visualization.py` | SOC轨迹图、净购电曲线图、对比柱状图、Pareto前沿图 |
| `main.py` | 基准计算 → 成本最优 → 碳排最优 → Pareto分析 → 保存结果 |

---

## 8 时域处理

| 时段 | 小时范围 | 处理方式 |
|------|---------|---------|
| 主运行时域 | 0–2399 | 完整优化，IT负荷=AI+NonAI |
| 收尾时域 | 2400–2405 | 参与优化，IT负荷=剩余AI+NonAI |
| 终端结算 | 2406 | 仅结算SOC终端状态，SOC(2406)≥InitialSOC |

**总时间步**：2407步（0–2406），全时域参与LP求解。
