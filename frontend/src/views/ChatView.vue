<template>
  <div class="app-container">
    <!-- 侧边栏 -->
    <div class="sidebar">
      <div class="sidebar-header">
        <h2>🤖 智能客服</h2>
        <p>Multi-Agent · 7×24h 在线</p>
      </div>
      <div class="conv-list">
        <div class="conv-item" :class="{ active: !currentSessionId }" @click="newChat()" style="font-weight:600;">
          <span class="title">💬 新对话</span>
        </div>
        <div v-for="s in sessions" :key="s.id" class="conv-item"
             :class="{ active: sameId(s.id, currentSessionId) }" @click="switchChat(s.id)">
          <span class="title">{{ s.title || '(空)' }}</span>
          <span class="del" @click.stop="deleteConv(s.id)" title="删除">✕</span>
        </div>
      </div>
      <div class="sidebar-footer">
        💡 快速体验
        <button class="scene" @click="quickAsk('蓝牙连不上怎么办')">🔧 蓝牙连接问题</button>
        <button class="scene" @click="quickAsk('帮我查一下订单 ORD001')">📦 查询订单</button>
        <button class="scene" @click="quickAsk('推荐一款 1000 以内的手表')">🛍️ 产品推荐</button>
      </div>

      <!-- 账号操作独立成区，不混在"快速体验"里 -->
      <div class="sidebar-account">
        <button class="logout-btn" @click="logout()">🚪 退出登录</button>
      </div>
    </div>

    <!-- 主区域 -->
    <div class="main">
      <div class="topbar">
        <div class="agent-avatar">{{ topbar.emoji }}</div>
        <div class="agent-info">
          <h3>{{ topbar.name }}</h3>
          <span>在线</span>
        </div>
      </div>

      <div class="chat-area" ref="chatArea" @scroll="onScroll">
        <!-- 空状态：说清楚每个 Agent 能做什么，而不是只喊"随时待命" -->
        <div v-if="!messages.length && !booting" class="empty-state">
          <div class="empty-icon">🤖</div>
          <h3>智能客服助手</h3>
          <p>5 个专业 Agent 随时待命</p>
          <div class="capability-list">
            <div v-for="c in CAPABILITIES" :key="c.name" class="capability">
              <span class="cap-icon">{{ c.icon }}</span>
              <b>{{ c.name }}</b>
              <span class="cap-desc">{{ c.desc }}</span>
            </div>
          </div>
          <!-- 点示例只填入输入框（不直接发），缺的参数由用户自己补 -->
          <div class="empty-hints">
            <button class="empty-hint" @click="fillInput('我的设备出现了问题：')">🔧 故障排查</button>
            <button class="empty-hint" @click="fillInput('帮我查一下订单，订单号是 ')">📦 查询订单</button>
            <button class="empty-hint" @click="fillInput('帮我推荐一款 ')">🛍️ 产品推荐</button>
          </div>
          <p class="empty-tip">点击示例会填入输入框，补全后发送</p>
        </div>

        <MessageItem v-for="m in messages" :key="m._id" :message="m">
          <template #meta>
            <template v-if="m.role === 'assistant' && m.intent">
              <span class="intent-badge" :class="m.intent">
                {{ intentLabel(m.intent).icon }} {{ intentLabel(m.intent).text }}
              </span>
              <span class="conf-text" v-if="m.confidence">意图把握 {{ Math.round(m.confidence * 100) }}%</span>
            </template>
          </template>
          <template #footer>
            <div class="escalation-alert" v-if="m.escalated">
              ⚠️ {{ m.escalationReason || '建议转人工客服进一步处理' }}
            </div>
          </template>
        </MessageItem>
      </div>

      <button v-if="showScrollBtn" class="scroll-bottom" @click="scrollBottom" title="回到底部">↓</button>

      <ChatInput v-model="input" :disabled="sending" @send="send" />

      <div class="status-bar">
        <span>{{ status }}</span>
        <span>{{ agentName }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import request from '../api/request'
import MessageItem from '../components/MessageItem.vue'
import ChatInput from '../components/ChatInput.vue'

const router = useRouter()
const route = useRoute()

const sessions = ref([])
const messages = ref([])
// 初始值直接取自 URL（同步，不用等网络）：否则首屏会先高亮"新对话"，
// 等接口回来才跳到真正的会话上，看起来像闪了一下
const currentSessionId = ref(route.params.sessionId ? String(route.params.sessionId) : null)
const input = ref('')
const sending = ref(false)
const status = ref('已连接 · 5 个 Agent 就绪')
const agentName = ref('')
const topbar = ref({ emoji: '🤖', name: '智能客服助手' })
const chatArea = ref(null)
const showScrollBtn = ref(false)
const booting = ref(true)   // 首次加载中：压住空状态，避免它闪一下再被消息替换

// 消息的本地唯一键（原先用数组下标做 key，加出现动画会渲染错位）
let msgSeq = 0
const nextId = () => ++msgSeq

// 会话 id 统一按字符串比较：来自路由参数的是 string、来自接口的是 number，
// 不统一会导致"刷新后侧边栏选中态丢失"（5 !== "5"）
const sameId = (a, b) => a != null && b != null && String(a) === String(b)

const INTENT_LABELS = {
  chitchat:        { icon: '💬', text: '前台接待', emoji: '👋' },
  tech_support:    { icon: '🔧', text: '技术支持', emoji: '💻' },
  order_service:   { icon: '📦', text: '订单服务', emoji: '📋' },
  web_search:      { icon: '🌐', text: '联网搜索', emoji: '🔍' },
  product_consult: { icon: '🛍️', text: '产品顾问', emoji: '💡' },
  escalate:        { icon: '🔄', text: '转人工',   emoji: '📞' },
}

const intentLabel = (key) => INTENT_LABELS[key] || { icon: '🤖', text: key, emoji: '🤖' }

// 空状态的能力清单：让用户知道每个 Agent 具体能做什么
// （对应 INTENT_LABELS 里的 5 个 Agent + 转人工兜底）
const CAPABILITIES = [
  { icon: '💬', name: '前台接待', desc: '问候闲聊、识别你的意图' },
  { icon: '🔧', name: '技术支持', desc: '故障排查、使用帮助' },
  { icon: '📦', name: '订单服务', desc: '查询订单状态、跟踪物流' },
  { icon: '🛍️', name: '产品顾问', desc: '产品推荐、参数与价格' },
  { icon: '🌐', name: '联网搜索', desc: '商品行情、外部实时信息' },
  { icon: '🔄', name: '转人工',   desc: '无法处理时转接人工客服' },
]

/** 把示例问题填进输入框（不发送），聚焦后光标停在末尾，用户接着补参数即可 */
function fillInput(text) {
  input.value = text
  nextTick(() => {
    const el = document.querySelector('.input-area input')
    if (el) {
      el.focus()
      el.setSelectionRange(text.length, text.length)
    }
  })
}

function scrollBottom() {
  nextTick(() => {
    if (chatArea.value) chatArea.value.scrollTop = chatArea.value.scrollHeight
  })
}

// 离底部超过 120px 才显示"回到底部"
function onScroll() {
  const el = chatArea.value
  if (!el) return
  showScrollBtn.value = el.scrollHeight - el.scrollTop - el.clientHeight > 120
}

async function loadSessions() {
  const resp = await request.get('/sessions', { params: { page: 1, size: 50 } })
  sessions.value = resp.data.data.list
}

function newChat() {
  currentSessionId.value = null
  messages.value = []
  status.value = '已连接 · 5 个 Agent 就绪'
  agentName.value = ''
  topbar.value = { emoji: '🤖', name: '智能客服助手' }
  // 从 /chat/xxx 点"新对话"时把 URL 也退回去，否则地址栏还停在旧会话上
  if (route.params.sessionId) router.replace('/chat')
}

async function switchChat(id) {
  // 已经在这个会话上、且消息加载过了，才跳过重复请求。
  // 必须带上 messages 判断：刷新时 currentSessionId 已从 URL 预置过，
  // 只看 id 相等就会直接 return，历史消息永远加载不出来
  if (sameId(id, currentSessionId.value) && messages.value.length) return
  status.value = '加载中...'
  try {
    const resp = await request.get(`/sessions/${id}`)
    const data = resp.data.data
    // 必须在请求成功后再赋值：原来是先赋值再请求，失败时 ID 会残留成错值，
    // 上地址栏之后会直接暴露成"URL 是错的、还显示加载失败"
    // 统一存字符串，和侧边栏列表项（数字 id）比较时才对得上
    currentSessionId.value = String(id)
    // 数据库只存 intent 不存 confidence：历史不显示把握度（避免假数据），
    // 实时对话时的把握度来自 SSE intent 事件（内存中，刷新后消失，正常）
    messages.value = data.messages.map((m) => ({
      _id: nextId(),
      role: m.role,
      content: m.content,
      intent: m.intent,
    }))
    status.value = `对话: ${data.session.title || id}`
    // 把 URL 同步成当前会话，否则点侧边栏切走后一刷新又跳回旧会话
    if (!sameId(route.params.sessionId, id)) {
      router.replace('/chat/' + id)
    }
  } catch (e) {
    currentSessionId.value = null
    messages.value = []
    status.value = e.response?.status === 403 ? '无权访问该会话' : '会话不存在或加载失败'
    router.replace('/chat')
  }
  scrollBottom()
}

async function deleteConv(id) {
  if (!confirm('确定删除该对话？')) return
  try {
    await request.delete(`/sessions/${id}`)
    // 用 sameId 比较：id 来自列表项是数字，currentSessionId 里存的是字符串，
    // 用 === 永远不相等 → 删掉当前对话后聊天区不会清空
    if (sameId(currentSessionId.value, id)) newChat()
    loadSessions()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

function quickAsk(text) {
  input.value = text
  send()
}

function logout() {
  localStorage.removeItem('token')
  router.push('/login')
}

async function send() {
  if (sending.value) return
  const q = input.value.trim()
  if (!q) return
  sending.value = true
  input.value = ''
  status.value = '处理中...'

  // 用户消息上屏
  messages.value.push({ _id: nextId(), role: 'user', content: q })
  // AI 占位气泡：必须用 reactive（直接改原始对象 Vue 渲染不到，这是之前"画面上没有"的根因）
  const aiMsg = reactive({
    _id: nextId(), role: 'assistant', content: '', streaming: true, intent: null,
    progress: '正在处理...',   // 进度行文案，随 SSE 的 progress 事件更新
  })
  messages.value.push(aiMsg)
  scrollBottom()

  try {
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({
        message: q,
        session_id: currentSessionId.value,
      }),
    })

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let answer = ''
    let intent = ''
    let pendingEvent = null
    let buf = ''   // 跨 chunk 缓冲：SSE 行可能被切成两半，最后不完整的行留到下一个 chunk

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()   // 保留最后可能不完整的行
      for (const line of lines) {
        // 网关原样透传 Python SSE 格式（"data: " 带空格），严格解析
        if (line.startsWith('event:')) {
          pendingEvent = line.slice(6).trim()
        } else if (line.startsWith('data: ') && pendingEvent) {
          const data = JSON.parse(line.slice(6))
          const event = pendingEvent
          pendingEvent = null
          if (event === 'progress') {
            // 回答出完后的收尾步骤（质量检查）放底部状态栏 —— 这时候回答已经能读了，
            // 正文下面还转圈反而像没做完；其余等待阶段的进度放进度行（显眼、不阻塞阅读）
            if (data.status && data.status.includes('检查回复质量')) {
              status.value = data.status
            } else {
              aiMsg.progress = data.status
            }
          } else if (event === 'intent') {
            intent = data.intent
            aiMsg.intent = data.intent
            aiMsg.confidence = data.confidence
            const info = intentLabel(data.intent)
            topbar.value = { emoji: info.emoji, name: info.text }
            agentName.value = `${info.icon} ${info.text}`
          } else if (event === 'done') {
            aiMsg.escalated = data.escalated
            aiMsg.escalationReason = data.escalation_reason
            aiMsg.progress = null
            const info = intentLabel(intent)
            status.value = data.quality_score ? `质量 ${Math.round(data.quality_score * 100)} 分` : '完成'
            agentName.value = info.icon ? `${info.icon} ${info.text}` : ''
            currentSessionId.value = String(data.session_id)
            // URL 同步：会话 id 是首条消息发出后才由后端生成的，这时候才写进地址栏
            if (!sameId(route.params.sessionId, data.session_id)) {
              router.replace('/chat/' + data.session_id)
            }
            loadSessions()
          }
        } else if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          answer += data.token
          aiMsg.content = answer
          aiMsg.streaming = false
          aiMsg.progress = null   // 开始出内容了，进度行让位
        }
      }
      scrollBottom()
    }
    // 流结束：处理缓冲里残留的最后一行（无换行结尾）
    if (buf.startsWith('data: ')) {
      const data = JSON.parse(buf.slice(6))
      if (data.token) {
        answer += data.token
        aiMsg.content = answer
        aiMsg.streaming = false
      }
    }
  } catch (e) {
    aiMsg.content = '❌ AI 服务暂时不可用，请稍后再试'
    aiMsg.streaming = false
    aiMsg.progress = null
    status.value = '请求失败'
  } finally {
    sending.value = false
    scrollBottom()
  }
}

onMounted(async () => {
  await loadSessions()
  // 地址栏里带了会话 id（刷新 / 直接粘贴链接）就恢复它，否则开新会话
  const id = route.params.sessionId
  if (id) await switchChat(id)
  else newChat()
  booting.value = false
})
</script>
