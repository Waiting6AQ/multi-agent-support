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
             :class="{ active: s.id === currentSessionId }" @click="switchChat(s.id)">
          <span class="title">{{ s.title || '(空)' }}</span>
          <span class="del" @click.stop="deleteConv(s.id)" title="删除">✕</span>
        </div>
      </div>
      <div class="sidebar-footer">
        💡 快速体验
        <button class="scene" @click="quickAsk('蓝牙连不上怎么办')">🔧 蓝牙连接问题</button>
        <button class="scene" @click="quickAsk('帮我查一下订单 ORD001')">📦 查询订单</button>
        <button class="scene" @click="quickAsk('推荐一款 1000 以内的手表')">🛍️ 产品推荐</button>
        <button class="scene" @click="logout()">🚪 退出登录</button>
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

      <div class="chat-area" ref="chatArea">
        <div v-for="(m, i) in messages" :key="i">
          <div class="time-divider" v-if="i === 0">{{ m.role === 'user' ? '—— 当前会话 ——' : '' }}</div>
          <div class="msg" :class="m.role">
            <div class="avatar">{{ m.role === 'user' ? '👤' : '🤖' }}</div>
            <div class="content-wrapper">
              <div class="meta-row" v-if="m.role === 'assistant' && m.intent">
                <span class="intent-badge" :class="m.intent">{{ intentLabel(m.intent).icon }} {{ intentLabel(m.intent).text }}</span>
                <span class="conf-text" v-if="m.confidence">意图把握 {{ Math.round(m.confidence * 100) }}%</span>
              </div>
              <div class="bubble md-body" :class="{ 'progress-text': m.streaming }"
                   v-html="m.content ? renderMd(m.content) : '...'"></div>
              <div class="escalation-alert" v-if="m.escalated">⚠️ {{ m.escalationReason || '建议转人工客服进一步处理' }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="input-area">
        <input v-model="input" placeholder="输入你的问题..." @keydown.enter="send" :disabled="sending" />
        <button @click="send" :disabled="sending" title="发送">➤</button>
      </div>
      <div class="status-bar">
        <span>{{ status }}</span>
        <span>{{ agentName }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import request from '../api/request'
import { renderMd } from '../utils/md'

const router = useRouter()

const sessions = ref([])
const messages = ref([])
const currentSessionId = ref(null)
const input = ref('')
const sending = ref(false)
const status = ref('已连接 · 5 个 Agent 就绪')
const agentName = ref('')
const topbar = ref({ emoji: '🤖', name: '智能客服助手' })
const chatArea = ref(null)

const INTENT_LABELS = {
  chitchat:        { icon: '💬', text: '前台接待', emoji: '👋' },
  tech_support:    { icon: '🔧', text: '技术支持', emoji: '💻' },
  order_service:   { icon: '📦', text: '订单服务', emoji: '📋' },
  web_search:      { icon: '🌐', text: '联网搜索', emoji: '🔍' },
  product_consult: { icon: '🛍️', text: '产品顾问', emoji: '💡' },
  escalate:        { icon: '🔄', text: '转人工',   emoji: '📞' },
}

const intentLabel = (key) => INTENT_LABELS[key] || { icon: '🤖', text: key, emoji: '🤖' }

function scrollBottom() {
  nextTick(() => {
    if (chatArea.value) chatArea.value.scrollTop = chatArea.value.scrollHeight
  })
}

async function loadSessions() {
  const resp = await request.get('/sessions', { params: { page: 1, size: 50 } })
  sessions.value = resp.data.data.list
}

function newChat() {
  currentSessionId.value = null
  messages.value = [{
    role: 'assistant',
    content: '你好！我是智能客服助手 👋\n\n直接告诉我你的问题，我会自动转接给最合适的 Agent 为你服务～',
  }]
  status.value = '已连接 · 5 个 Agent 就绪'
  agentName.value = ''
  topbar.value = { emoji: '🤖', name: '智能客服助手' }
  scrollBottom()
}

async function switchChat(id) {
  currentSessionId.value = id
  status.value = '加载中...'
  try {
    const resp = await request.get(`/sessions/${id}`)
    const data = resp.data.data
    // 数据库只存 intent 不存 confidence：历史不显示把握度（避免假数据），
    // 实时对话时的把握度来自 SSE intent 事件（内存中，刷新后消失，正常）
    messages.value = data.messages.map((m) => ({
      role: m.role,
      content: m.content,
      intent: m.intent,
    }))
    status.value = `对话: ${data.session.title || id}`
  } catch (e) {
    status.value = '加载失败'
  }
  scrollBottom()
}

async function deleteConv(id) {
  if (!confirm('确定删除该对话？')) return
  try {
    await request.delete(`/sessions/${id}`)
    if (currentSessionId.value === id) newChat()
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
  messages.value.push({ role: 'user', content: q })
  // AI 占位气泡：必须用 reactive（直接改原始对象 Vue 渲染不到，这是之前"画面上没有"的根因）
  const aiMsg = reactive({ role: 'assistant', content: '', streaming: true, intent: null })
  messages.value.push(aiMsg)
  scrollBottom()

  try {
    console.log('[send] 开始发送', q)
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
    console.log('[send] fetch 返回', resp.status)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let answer = ''
    let intent = ''
    let pendingEvent = null
    let buf = ''   // 跨 chunk 缓冲：SSE 行可能被切成两半，最后不完整的行留到下一个 chunk

    while (true) {
      const { done, value } = await reader.read()
      if (done) { console.log('[send] 流结束'); break }
      buf += decoder.decode(value, { stream: true })
      console.log('[SSE chunk]', JSON.stringify(buf.slice(-120)))
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
            status.value = data.status
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
            const info = intentLabel(intent)
            status.value = data.quality_score ? `质量 ${Math.round(data.quality_score * 100)} 分` : '完成'
            agentName.value = info.icon ? `${info.icon} ${info.text}` : ''
            currentSessionId.value = data.session_id
            loadSessions()
          }
        } else if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          answer += data.token
          aiMsg.content = answer
          aiMsg.streaming = false
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
    status.value = '请求失败'
  } finally {
    sending.value = false
    scrollBottom()
  }
}

onMounted(() => {
  newChat()
  loadSessions()
})
</script>
