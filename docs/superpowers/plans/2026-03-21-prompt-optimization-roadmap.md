# Prompt 优化路线图

> 基于当前成果：Supervisor +19.2%, Discovery +17.8%

## 当前覆盖

| Prompt                      | DSPy 模块                | 编译    | 状态       |
| :-------------------------- | :----------------------- | :------ | :--------- |
| `supervisor.yaml`           | ✅ SupervisorRouterModule | ✅ 86.4% | **已完成** |
| `discovery/filter_and_rank` | ✅ FilterRankModule       | ✅ 97.5% | **已完成** |
| `discovery/expand_query`    | ❌                        | —       | 待改造     |
| `extraction/generate_notes` | ❌                        | —       | 待改造     |
| `extraction/cross_compare`  | ❌                        | —       | 待改造     |
| `ideation/analyze_gaps`     | ❌                        | —       | 待改造     |
| `critique/supporter_review` | ❌                        | —       | 待改造     |
| `critique/critic_review`    | ❌                        | —       | 待改造     |
| `checkpoint_eval`           | ❌                        | —       | 低优先     |

---

## 短期（1-2 周）

### S1. 合并 feat/agent-optimization 到 main
- 执行 `finishing-a-development-branch` 流程
- 确保 `uv sync` 正常（optimization 为可选 extra）

### S2. 扩展到高价值节点

按 **调用频率 × 输出质量敏感度** 排序：

| 优先级 | 节点                               | 理由                               | 预估收益 |
| :----- | :--------------------------------- | :--------------------------------- | :------- |
| P0     | `expand_query`                     | 每次搜索必经，查询质量直接影响召回 | 高       |
| P1     | `generate_notes`                   | 精读核心，用户直接看到输出质量     | 高       |
| P1     | `analyze_gaps`                     | 创意核心，gap 质量决定后续方向     | 中-高    |
| P2     | `critic_review`                    | 审稿质量影响最终产出               | 中       |
| P3     | `cross_compare` / `build_glossary` | 辅助型，低频                       | 低       |

每个节点改造模式相同：
1. 定义 `dspy.Signature` + `dspy.Module`
2. 写对抗性数据生成器
3. 定义 metric 函数
4. 编译 + 注册到 `ModuleRegistry`

---

## 中期（1 个月）

### M1. HITL 数据飞轮

```
用户使用 → HITL 反馈入库 → 积累 N 条 → 自动触发重编译 → 模型更新
         ↑                                                    ↓
         └────────────────── 产出质量提升 ─────────────────────┘
```

- `discovery_feedback` 表已就绪，需要前端交互累积数据
- 阈值策略：每积累 50 条新反馈，Celery 定时任务触发重编译
- 编译后自动比对新旧 compiled JSON 的 eval 分数，score 下降时拒绝替换

### M2. Prompt 版本管理

| 字段            | 说明                    |
| :-------------- | :---------------------- |
| `prompt_name`   | 如 `supervisor_routing` |
| `version`       | 自增版本号              |
| `compiled_json` | 编译产物                |
| `eval_score`    | 验证集分数              |
| `is_active`     | 是否为当前活跃版本      |
| `created_at`    | 编译时间                |

支持一键回滚到上一版本。

---

## 长期（2-3 个月）

### L1. 模型蒸馏 (Teacher-Student)

```
gemini-2.5-pro (teacher, 高质量但慢)
      ↓ 生成 gold labels
gemini-2.5-flash (student, 编译目标)
      ↓ DSPy 编译
compiled prompt (线上推理)
```

- 当 pro 模型 API 可用时，用 pro 生成更高质量的标注数据
- 用 flash 模型做编译目标，兼顾质量和延迟

### L2. A/B 测试框架

- 线上按用户 ID hash 分流：50% YAML 路径，50% DSPy 路径
- 收集指标：用户满意度（HITL 选择率）、任务完成率、响应延迟
- 统计显著时自动切流

### L3. 跨工作流联合优化

- 单节点优化是局部最优，pipeline 级优化需要端到端 metric
- 例如：`expand_query` → `filter_rank` 联合优化，以最终用户选中率为目标
