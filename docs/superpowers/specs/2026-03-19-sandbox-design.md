# 容器化沙箱架构设计

> Research Copilot 的隔离代码执行环境，负责安全运行 Agent 生成的 Python 代码并捕获执行结果。

## 一、设计目标

- **安全隔离**：代码在无外网、资源受限的一次性容器中执行，保护宿主机安全
- **简单可靠**：纯 Python + Docker SDK 直调，无额外中间件
- **可扩展**：Protocol 抽象接口，未来可替换为 Jupyter 交互式、多语言、第三方沙箱等实现
- **确定性清理**：容器必定被销毁，异常情况有孤儿清理兜底

---

## 二、技术决策记录

| 决策项             | 选择                                                   | 排除方案                 | 理由                                                |
| ------------------ | ------------------------------------------------------ | ------------------------ | --------------------------------------------------- |
| 实现语言           | Python                                                 | Rust + Python            | MVP 并发量低，Rust 增加双语言维护成本，无收益       |
| Docker Daemon 位置 | 与 LangGraph Server 同机                               | 独立 Worker / 第三方服务 | 最简单，同时满足私有化和云端部署                    |
| 容器启动策略       | 冷启动（Cold Start）                                   | 预热池（Warm Pool）      | HITL 确认步骤天然掩盖 1-2s 启动延迟，无需复杂池管理 |
| 代码交换方式       | Docker SDK API（put_archive / exec_run / get_archive） | 容器内 HTTP Server       | 更简单，无需等服务 ready，镜像更轻                  |
| 执行模式           | 同步阻塞                                               | Celery 异步              | LangGraph 节点支持长运行，科研场景并发低            |

---

## 三、数据模型

### 3.1 ExecutionRequest — 执行请求

| 字段            | 类型             | 默认值 | 说明                              |
| --------------- | ---------------- | ------ | --------------------------------- |
| code            | str              | —      | Python 代码字符串                 |
| timeout_seconds | int              | 600    | 超时时间（秒），默认 10 分钟      |
| input_files     | dict[str, bytes] | {}     | 可选注入的数据文件 {文件名: 内容} |

### 3.2 ExecutionResult — 执行结果

| 字段             | 类型             | 说明                                   |
| ---------------- | ---------------- | -------------------------------------- |
| success          | bool             | 是否正常退出（exit_code == 0）         |
| exit_code        | int              | 进程退出码                             |
| stdout           | str              | 标准输出                               |
| stderr           | str              | 错误输出                               |
| output_files     | dict[str, bytes] | 产出文件 {文件名: 内容}（图表 PNG 等） |
| duration_seconds | float            | 实际执行耗时                           |

### 3.3 CodeExecutor — 抽象接口

```python
class CodeExecutor(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
```

上层 Agent 只依赖此协议，不感知底层实现。

---

## 四、容器生命周期

### 4.1 完整流程

```
Agent 调用 executor.execute(request)
    │
    ▼
┌─ Step 1: 创建容器 ──────────────────────────────────────────┐
│  docker.containers.create(                                   │
│    image = "research-copilot-sandbox:latest"                 │
│    network_disabled = True        ← 禁网                    │
│    mem_limit = "4g"               ← 内存上限                │
│    nano_cpus = 2_000_000_000      ← 2 核                    │
│    storage_opt = {"size": "1g"}   ← 磁盘上限                │
│    read_only = False              ← 需要写 /output/         │
│    user = "sandbox"               ← 非 root 用户运行        │
│    labels = {"app": "research-copilot", "role": "sandbox"}   │
│  )                                                           │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌─ Step 2: 注入代码与数据 ────────────────────────────────────┐
│  container.put_archive("/workspace/", tar(script.py))        │
│  container.put_archive("/workspace/data/", tar(input_files)) │
│  容器内结构：                                                │
│    /workspace/script.py          ← Agent 生成的代码          │
│    /workspace/data/              ← 注入的数据文件            │
│    /output/                      ← 约定产出目录（空）        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌─ Step 3: 启动执行 ─────────────────────────────────────────┐
│  container.start()                                          │
│  container.exec_run("python /workspace/script.py")          │
│  同步等待，超时 600s 后 container.kill()                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─ Step 4: 提取结果 ─────────────────────────────────────────┐
│  stdout, stderr ← exec_run 返回值                           │
│  output_tar ← container.get_archive("/output/")             │
│  解包 tar → output_files: dict[str, bytes]                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─ Step 5: 强制销毁（finally） ──────────────────────────────┐
│  container.stop(timeout=5)                                   │
│  container.remove(force=True)                                │
│  无论成功失败，容器必须被清除                                │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
                  返回 ExecutionResult
```

### 4.2 资源约束

| 维度 | 值      | Docker 参数                     |
| ---- | ------- | ------------------------------- |
| 网络 | 禁止    | `network_disabled=True`         |
| CPU  | 2 核    | `nano_cpus=2_000_000_000`       |
| 内存 | 4 GB    | `mem_limit="4g"`                |
| 超时 | 10 分钟 | 应用层计时 + `container.kill()` |
| 磁盘 | 1 GB    | `storage_opt={"size": "1g"}`    |

### 4.3 容器内用户权限

以 `sandbox` 非 root 用户运行，限制容器内的权限升级风险。

---

## 五、沙箱 Docker 镜像

路径：`deployment/sandbox_image/Dockerfile`

```dockerfile
FROM python:3.11-slim

RUN useradd -m -s /bin/bash sandbox

RUN pip install --no-cache-dir \
    numpy pandas scipy matplotlib seaborn \
    scikit-learn torch torchvision \
    statsmodels networkx sympy

RUN mkdir /workspace /output && \
    chown sandbox:sandbox /workspace /output

USER sandbox
WORKDIR /workspace
```

设计要点：
- 基于 `python:3.11-slim`，镜像约 2-3 GB（主要是 PyTorch）
- 预装库固定，运行时不可 `pip install`（禁网 + 安全）
- 增加库需修改 Dockerfile 重新构建

---

## 六、错误处理

### 6.1 两层错误处理架构

```
                    Agent 节点层（nodes.py）
                    负责"智能重试"
                    ┌────────────────────────────┐
                    │ 1. 调用 executor.execute()  │
                    │ 2. 若 success=False:        │
                    │    LLM 读 stderr 反思重写   │
                    │    重新调用（max 3 轮）     │
                    │ 3. 超过重试上限 → 报告失败  │
                    └─────────────┬──────────────┘
                                  │
                    DockerExecutor 层（sandbox_manager.py）
                    负责"机械保障"
                    ┌─────────────▼──────────────┐
                    │ - 超时 → kill + 返回 stderr │
                    │ - 容器创建失败 → 直接抛异常 │
                    │ - 容器销毁失败 → 日志告警   │
                    │   + 后台清理守护任务兜底     │
                    └────────────────────────────┘
```

### 6.2 错误分类与处理策略

| 错误类型                    | 处理方         | 行为                                                                                                             |
| --------------------------- | -------------- | ---------------------------------------------------------------------------------------------------------------- |
| 代码运行报错（exit_code≠0） | Agent 节点     | LLM 反思 + 重写代码，重新执行（max 3 轮）                                                                        |
| 执行超时（>10 min）         | DockerExecutor | `container.kill()`，返回 `ExecutionResult(success=False, stderr="Execution timed out")`                          |
| Docker Daemon 不可用        | DockerExecutor | 抛 `SandboxUnavailableError`，Agent 层不重试                                                                     |
| 容器销毁失败                | DockerExecutor | 日志告警 + 后台清理任务定期扫描孤儿容器。Sandbox Metrics 详见 [可观测性设计](2026-03-19-observability-design.md) |

### 6.3 孤儿容器清理

所有沙箱容器创建时打标签：`{"app": "research-copilot", "role": "sandbox"}`。后台定时任务扫描带此标签且存活超过 15 分钟的容器，强制清理。

---

## 七、与 Agent Workflow 集成

### 7.1 Execution WF 子图编排

```
                    ExecutionState
                    ├── code: str
                    ├── execution_result: ExecutionResult | None
                    ├── retry_count: int (max=3)
                    └── user_approved: bool

┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│ generate_code│────►│ ask_approval │────►│ sandbox_execute   │
│ (LLM 生成)   │     │ (interrupt)  │     │ (DockerExecutor)  │
└──────────────┘     └──────────────┘     └────────┬──────────┘
       ▲                                           │
       │              ┌──────────────┐             │
       └──────────────│ reflect_retry│◄────────────┘
         retry_count  │ (LLM 读stderr│  success=False
         < 3          │  反思重写代码)│
                      └──────────────┘
                             │ retry_count >= 3
                             ▼
                      ┌──────────────┐
                      │ report_failure│
                      └──────────────┘
```

流程说明：
1. **generate_code** — LLM 根据实验方案生成 Python 代码
2. **ask_approval** — `interrupt()` 挂起，前端展示代码给用户确认
3. **sandbox_execute** — 用户确认后，调用 `DockerExecutor.execute()`
4. 若失败 → **reflect_retry** — LLM 读 stderr，反思并重写代码，回到 step 3
5. 3 次仍失败 → **report_failure** — 输出错误报告，告知用户

### 7.2 与其他 Workflow 的关系

| Workflow      | 与沙箱的关系                           |
| ------------- | -------------------------------------- |
| **Ideation**  | 产出实验方案，作为 Execution WF 的输入 |
| **Execution** | 直接调用 DockerExecutor 执行代码       |
| **Critique**  | 审查 Execution 产出的结果和代码质量    |
| **Publish**   | 引用 Execution 产出的图表和数据        |

---

## 八、模块文件结构

```
backend/
├── services/
│   └── sandbox_manager.py      # CodeExecutor Protocol + DockerExecutor 实现
│
├── agent/
│   ├── tools/
│   │   └── sandbox_tool.py     # LangGraph Tool 封装（调用 services 层）
│   └── workflows/
│       └── 4_execution/
│           ├── state.py        # ExecutionState 定义
│           ├── nodes.py        # generate_code / sandbox_execute / reflect_retry
│           └── graph.py        # subgraph 编排（含 interrupt + max_retries 循环）
│
deployment/
└── sandbox_image/
    └── Dockerfile              # 科研 Python 沙箱镜像
```

---

## 九、未来扩展点

| 扩展场景                    | 实现方式                                                       | 改动范围                                      |
| --------------------------- | -------------------------------------------------------------- | --------------------------------------------- |
| **Jupyter 交互式执行**      | 新增 `JupyterExecutor` 实现 `CodeExecutor` Protocol            | 只加 `services/jupyter_executor.py`，上层不改 |
| **多语言（R/Julia）**       | 新增沙箱镜像 + `ExecutionRequest` 加 `language` 字段           | 新 Dockerfile + Request 加一个字段            |
| **预热池**                  | 新增 `WarmPoolExecutor` 包装 `DockerExecutor`                  | 加一层代理，上层不改                          |
| **第三方沙箱（E2B/Modal）** | 新增 `E2BExecutor` 实现 `CodeExecutor` Protocol                | 只加一个实现类                                |
| **异步执行**                | Celery Worker 调用 `DockerExecutor`，Agent 用 interrupt/resume | 不改 DockerExecutor，改调用方式               |

所有扩展均为**加新类**，不修改现有代码，符合开闭原则。

---

## 十、技术选型汇总

| 组件         | 选择                                | 理由                                     |
| ------------ | ----------------------------------- | ---------------------------------------- |
| 容器运行时   | Docker                              | 成熟稳定，Docker SDK for Python 原生支持 |
| 容器管理     | Docker SDK for Python (`docker` 包) | 纯 Python，与项目技术栈一致              |
| 沙箱基础镜像 | python:3.11-slim                    | 轻量，预装科学计算库                     |
| 接口抽象     | Python Protocol (typing)            | 零运行时开销，类型检查友好               |
