# Chat 语音输入功能设计

为 Chat 模块的 `InputArea` 添加语音输入能力，采用混合 STT 架构：浏览器端 Web Speech API 作为默认实时引擎，Groq Whisper API 作为高精度后端回退引擎。

## 核心决策

| 维度     | 决策                                                    |
| -------- | ------------------------------------------------------- |
| STT 架构 | 混合：Web Speech API（默认）+ Groq Whisper（回退/精确） |
| 交互方式 | Toggle（点击开始/停止），转写结果填入 textarea 可编辑   |
| 后端服务 | Groq Whisper API（`whisper-large-v3-turbo`，免费额度）  |
| 前端抽象 | 单一 `useVoiceInput` hook 统一两种引擎                  |
| 引擎选择 | 自动检测 Web Speech API 可用性，不可用时回退 Groq       |

## 架构概览

```
InputArea.tsx
├── 📎 附件按钮
├── 🎙 语音按钮 ← 新增
├── 📝 Textarea
└── ➤ 发送按钮

useVoiceInput(engine?)
├── WebSpeechEngine   ← navigator.webkitSpeechRecognition
│   └── 实时 interim results → textarea
└── GroqWhisperEngine ← MediaRecorder → POST /api/stt/transcribe
    └── 录音结束后一次性返回文本 → textarea
```

## 状态机

```
         点击麦克风           点击停止
  idle ──────────► recording ──────────► transcribing ──► idle
   ▲                  │                      │
   │                  │ (Web Speech:         │ 转写文本
   │                  │  实时更新 textarea)   │ 填入 textarea
   │                  ▼                      │
   └──── error ◄── 权限拒绝/API 失败 ◄───────┘
```

**状态枚举：** `idle` | `recording` | `transcribing` | `error`

> Web Speech API 模式下 `recording` 期间实时更新 textarea（interim results），`transcribing` 阶段几乎瞬间完成。Groq 模式下 `transcribing` 阶段包含网络上传 + API 调用。

## 前端设计

### `useVoiceInput` Hook

```typescript
interface VoiceInputState {
  status: 'idle' | 'recording' | 'transcribing' | 'error'
  interimText: string      // Web Speech 实时中间结果
  finalText: string        // 最终转写文本
  error: string | null
  engineType: 'web-speech' | 'groq-whisper'
}

interface VoiceInputActions {
  startRecording: () => Promise<void>  // 请求麦克风权限 + 开始录音
  stopRecording: () => void            // 停止录音，触发转写
  cancelRecording: () => void          // 取消录音，丢弃数据
}

function useVoiceInput(
  onTranscript: (text: string) => void,  // 转写完成回调，追加到 textarea
  engine?: 'web-speech' | 'groq-whisper' // 可选强制指定引擎
): VoiceInputState & VoiceInputActions
```

**引擎选择逻辑：**
1. 若调用方传入 `engine` 参数，使用指定引擎
2. 否则检测 `window.webkitSpeechRecognition || window.SpeechRecognition`
3. 可用则使用 Web Speech API，否则回退 Groq Whisper

**录音采集（Groq 模式）：**
- 使用 `MediaRecorder` API 录制音频
- 格式：`audio/webm;codecs=opus`（浏览器原生支持，Groq 兼容）
- 停止时合并 `Blob` 并上传

**Web Speech API 模式：**
- `SpeechRecognition.continuous = true`（持续识别直到手动停止）
- `SpeechRecognition.interimResults = true`（启用中间结果实时预览）
- `SpeechRecognition.lang` 跟随 i18n locale（`zh-CN` / `en-US`）
- `onresult` 事件中区分 `isFinal` 和 interim，分别更新 `finalText` / `interimText`

### `InputArea.tsx` 修改

在附件按钮和 textarea 之间新增麦克风按钮：

```
[📎 附件] [🎙 语音] [────── Textarea ──────] [➤ 发送]
```

**按钮状态映射：**

| 状态           | 图标      | 样式         | 行为                      |
| -------------- | --------- | ------------ | ------------------------- |
| `idle`         | `Mic`     | 默认 ghost   | 点击 → `startRecording()` |
| `recording`    | `MicOff`  | 红色脉冲动画 | 点击 → `stopRecording()`  |
| `transcribing` | `Loader2` | 旋转动画     | disabled                  |
| `error`        | `MicOff`  | 错误色       | 点击 → 重试               |

**录音指示器：** `recording` 状态时在 textarea 上方显示一个小条：
- 红色圆点脉冲 + "正在录音..." 文字 + 录音时长计时器
- 使用项目现有的 `animate-[pulse-glow_2s_ease-in-out_infinite]` 动画风格

**文本追加逻辑：**
- `onTranscript` 回调将转写文本追加到当前 textarea 的 `value` 末尾（非覆盖）
- 用户可在发送前自由编辑

### i18n 新增 Keys

```typescript
voice: {
  recording: '正在录音...' / 'Recording...'
  transcribing: '转写中...' / 'Transcribing...'
  micPermissionDenied: '麦克风权限被拒绝' / 'Microphone permission denied'
  sttUnavailable: '语音识别不可用，已切换至精确模式' / 'Speech recognition unavailable, switched to precise mode'
  error: '语音识别失败' / 'Voice recognition failed'
}
```

## 后端设计

### `POST /api/stt/transcribe`

**新增路由文件：** `backend/api/routers/stt.py`

```python
router = APIRouter(prefix="/api/stt", tags=["stt"])

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile,
    language: str = "zh",
    current_user: User = Depends(get_current_user),
) -> TranscribeResponse:
    """接收音频文件，调用 Groq Whisper 转写为文本。"""
```

**请求：** `multipart/form-data`
- `file`: 音频文件（webm/opus）
- `language`: 语言代码，默认 `zh`

**响应：**
```json
{
  "text": "转写后的文本内容",
  "language": "zh",
  "duration_seconds": 12.5
}
```

### Groq Client

**新增：** `backend/clients/groq_stt.py`

使用 `httpx` 直接调用 Groq API（OpenAI 兼容格式），避免引入 `groq` SDK 依赖：

```python
async def transcribe(
    audio_data: bytes,
    filename: str,
    language: str = "zh",
    model: str = "whisper-large-v3-turbo",
) -> TranscribeResult:
    """调用 Groq Whisper API 转写音频。"""
```

**API Endpoint：** `https://api.groq.com/openai/v1/audio/transcriptions`

### 配置扩展

`backend/core/config.py` 的 `Settings` 新增：

```python
# --- Groq STT ---
groq_api_key: str | None = None
groq_stt_model: str = "whisper-large-v3-turbo"
```

`.env.example` 新增：

```env
# ============= Groq STT =============
GROQ_API_KEY=gsk_xxx
GROQ_STT_MODEL=whisper-large-v3-turbo
```

## 错误处理

| 场景                  | 前端行为                                                  |
| --------------------- | --------------------------------------------------------- |
| 用户拒绝麦克风权限    | 显示 toast 提示 `micPermissionDenied`，状态回到 `idle`    |
| Web Speech API 不可用 | 自动回退 Groq，显示一次性提示 `sttUnavailable`            |
| Groq API 调用失败     | 状态设为 `error`，显示错误信息，允许重试                  |
| 网络中断              | 录音继续，上传时报错，保留录音 Blob 允许重试              |
| 录音时长超过 5 分钟   | 自动停止并触发转写                                        |
| `GROQ_API_KEY` 未配置 | 后端返回 `503 Service Unavailable`，前端仅使用 Web Speech |

## 文件清单

| 操作       | 文件路径                                   |
| ---------- | ------------------------------------------ |
| **NEW**    | `frontend/src/hooks/useVoiceInput.ts`      |
| **MODIFY** | `frontend/src/features/chat/InputArea.tsx` |
| **MODIFY** | `frontend/src/i18n/locales/zh.ts`          |
| **MODIFY** | `frontend/src/i18n/locales/en.ts`          |
| **NEW**    | `backend/api/routers/stt.py`               |
| **NEW**    | `backend/api/schemas/stt.py`               |
| **NEW**    | `backend/clients/groq_stt.py`              |
| **MODIFY** | `backend/core/config.py`                   |
| **MODIFY** | `backend/main.py`（注册 stt router）       |
| **MODIFY** | `.env.example`                             |

## 验证计划

### 自动化测试

1. **后端单测** — `tests/api/test_stt.py`
   - Mock Groq API，验证 `/api/stt/transcribe` 返回正确 JSON
   - 验证未配置 `GROQ_API_KEY` 时返回 503
   - 验证非法音频格式返回 400

2. **前端 Hook 测试** — 使用浏览器开发工具手动验证
   - Web Speech API 模式：Chrome 中测试实时转写
   - Groq 回退模式：Firefox/Safari 中测试（可能不支持 Web Speech）

### 手动验证

1. 打开 Chat 页面，确认麦克风按钮可见
2. 点击麦克风按钮 → 浏览器弹出权限请求 → 允许
3. 开始说话 → textarea 实时显示中间结果（Chrome）
4. 点击停止 → 最终文本填入 textarea
5. 编辑文本 → 点击发送 → 消息正常发送
6. 在不支持 Web Speech API 的浏览器中测试 Groq 回退
