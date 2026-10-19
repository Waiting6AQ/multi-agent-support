<template>
  <div class="admin-panel">
    <p class="admin-note">
      这些 FAQ 由<strong>技术支持 Agent</strong> 检索；订单、产品类问题会路由到各自的业务服务，不受影响。
    </p>

    <div class="admin-toolbar">
      <input v-model="keyword" type="text" placeholder="按问题 / 答案 / 分类筛选" />
      <span class="spacer"></span>
      <button class="admin-btn" @click="openCreate()">+ 新增 FAQ</button>
    </div>

    <div v-if="loading" class="admin-hint">加载中...</div>
    <div v-else-if="error" class="admin-hint is-error">{{ error }}</div>
    <div v-else-if="!filtered.length" class="admin-hint">
      {{ faqs.length ? '没有匹配的 FAQ' : '还没有 FAQ，点击右上角新增' }}
    </div>

    <div v-else class="admin-table-card">
      <table class="admin-table">
        <thead>
          <tr>
            <th class="col-cat">分类</th>
            <th>问题</th>
            <th>答案</th>
            <th class="col-ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in filtered" :key="f.id">
            <td class="cell-cat">{{ f.category }}</td>
            <td class="cell-question">{{ f.question }}</td>
            <td>
              <div class="cell-answer" :title="f.answer">{{ f.answer }}</div>
            </td>
            <td class="col-ops">
              <button class="admin-link-btn" @click="openEdit(f)">编辑</button>
              <button class="admin-link-btn is-danger" @click="remove(f)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增 / 编辑弹窗 -->
    <div v-if="editing" class="modal-mask" @click.self="closeEditor()">
      <div class="modal">
        <h2>{{ editing.id ? '编辑 FAQ' : '新增 FAQ' }}</h2>

        <label class="field">
          分类
          <input v-model="form.category" type="text" placeholder="常见问题" />
        </label>

        <label class="field">
          问题
          <textarea v-model="form.question" rows="2" placeholder="用户会怎么问"></textarea>
        </label>

        <label class="field">
          答案
          <textarea v-model="form.answer" rows="6" placeholder="客服应该怎么答"></textarea>
        </label>

        <p v-if="formError" class="form-error">{{ formError }}</p>

        <div class="modal-actions">
          <button class="admin-ghost-btn" @click="closeEditor()">取消</button>
          <button class="admin-btn" :disabled="saving" @click="save()">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import request from '../api/request'

const faqs = ref([])
const loading = ref(true)
const error = ref('')
const keyword = ref('')

// null = 弹窗关闭；否则 { id: number | null }
const editing = ref(null)
const form = reactive({ question: '', answer: '', category: '' })
const formError = ref('')
const saving = ref(false)

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return faqs.value
  return faqs.value.filter((f) =>
    [f.question, f.answer, f.category].some((v) => (v || '').toLowerCase().includes(k))
  )
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const resp = await request.get('/faqs')
    faqs.value = resp.data.data.faqs || []
  } catch (e) {
    error.value = e.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = { id: null }
  Object.assign(form, { question: '', answer: '', category: '常见问题' })
  formError.value = ''
}

function openEdit(f) {
  editing.value = { id: f.id }
  Object.assign(form, { question: f.question, answer: f.answer, category: f.category })
  formError.value = ''
}

function closeEditor() {
  if (saving.value) return
  editing.value = null
  formError.value = ''
}

async function save() {
  if (saving.value) return
  formError.value = ''
  if (!form.question.trim()) {
    formError.value = '问题不能为空'
    return
  }
  if (!form.answer.trim()) {
    formError.value = '答案不能为空'
    return
  }

  saving.value = true
  try {
    const body = { question: form.question, answer: form.answer, category: form.category }
    if (editing.value.id) {
      await request.put(`/faqs/${editing.value.id}`, body)
    } else {
      await request.post('/faqs', body)
    }
    editing.value = null
    await load()
  } catch (e) {
    // 409 问题重复 / 400 校验失败，后端都会把原因放在 message 里
    formError.value = e.response?.data?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove(f) {
  if (!confirm(`确定删除「${f.question}」？删除后技术支持 Agent 将检索不到这条。`)) return
  try {
    await request.delete(`/faqs/${f.id}`)
    await load()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.message || e.message))
  }
}

function onKeydown(e) {
  if (e.key === 'Escape') closeEditor()
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  load()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.col-cat { width: 110px; }
.col-ops { width: 96px; white-space: nowrap; }
.cell-cat { color: var(--text-secondary); font-size: 12px; }
.cell-question { color: var(--text-main); font-weight: 600; line-height: 1.6; word-break: break-word; }
/* 答案通常较长：最多显示 3 行，完整内容看 title 或点编辑 */
.cell-answer {
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, .45);
}
.modal {
  width: min(620px, 100%);
  max-height: 100%;
  overflow: auto;
  padding: 22px 24px;
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}
.modal h2 { margin: 0 0 4px; font-size: 16px; color: var(--text-main); }

.field {
  display: block;
  margin-top: 14px;
  font-size: 13px;
  color: var(--text-secondary);
}
.field input,
.field textarea {
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 9px 11px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main);
  outline: none;
  resize: vertical;
  transition: border-color .15s, box-shadow .15s;
}
.field input:focus,
.field textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, .15);
}

.form-error { margin: 12px 0 0; color: var(--danger); font-size: 12.5px; }

.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
</style>
