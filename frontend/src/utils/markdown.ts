import { marked } from 'marked'
import hljs from 'highlight.js'

marked.setOptions({
  breaks: true,
  gfm: true,
})

export function renderMarkdown(text: string): string {
  if (!text) return ''
  if (text.length > 50000) {
    text = text.substring(0, 50000) + '... (truncated)'
  }

  // Pre-process code blocks to add syntax highlighting
  const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g
  let processed = text.replace(codeBlockRegex, (_match, lang, code) => {
    try {
      const highlighted = lang && hljs.getLanguage(lang)
        ? hljs.highlight(code.trim(), { language: lang }).value
        : hljs.highlightAuto(code.trim()).value
      return `<pre><code class="hljs language-${lang || 'auto'}">${highlighted}</code></pre>`
    } catch {
      return `<pre><code>${escapeHtml(code.trim())}</code></pre>`
    }
  })

  // Process inline code
  processed = processed.replace(/`([^`]+)`/g, (_match, code) => {
    return `<code>${escapeHtml(code)}</code>`
  })

  return marked.parse(processed) as string
}

function escapeHtml(text: string): string {
  const el = document.createElement('div')
  el.textContent = text
  return el.innerHTML
}
