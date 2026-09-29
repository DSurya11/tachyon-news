/*
  Tiny Markdown renderer for the AI brief that produces React elements directly —
  no innerHTML anywhere, so model output can never inject markup.
  The shallowest heading level becomes the section level (providers disagree on ## vs ###).
*/
import type { ReactNode } from 'react'

export interface Heading { id: string; text: string }

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\[\d{1,10}\](?:\[\d{1,10}\])*|\[[^\]]+\]\(https?:\/\/[^)\s]+\)|(?<![\w*])\*[^*\s][^*]*\*(?![\w*]))/g

export function inline(text: string, cite: (id: number) => ReactNode, keyBase = ''): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let i = 0
  for (const m of text.matchAll(INLINE)) {
    const tok = m[0]
    if (m.index! > last) out.push(text.slice(last, m.index))
    const k = `${keyBase}-${i++}`
    if (tok.startsWith('**') || tok.startsWith('__')) out.push(<strong key={k}>{tok.slice(2, -2)}</strong>)
    else if (tok.startsWith('`')) out.push(<code key={k}>{tok.slice(1, -1)}</code>)
    else if (/^\[\d/.test(tok)) {
      const ids = [...tok.matchAll(/\[(\d+)\]/g)].map((x) => +x[1])
      out.push(<span key={k} className="whitespace-nowrap">{ids.map((id) => <span key={id}>{cite(id)}</span>)}</span>)
    } else if (tok.startsWith('[')) {
      const [, label, href] = tok.match(/^\[([^\]]+)\]\((.+)\)$/)!
      out.push(<a key={k} href={href} target="_blank" rel="noopener noreferrer">{label}</a>)
    } else out.push(<em key={k}>{tok.slice(1, -1)}</em>)
    last = m.index! + tok.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

export function renderMarkdown(src: string, cite: (id: number) => ReactNode): { nodes: ReactNode[]; headings: Heading[] } {
  const clean = (src || '').replace(/\\([#*_[\]()`-])/g, '$1')
  const levels = [...clean.matchAll(/^\s*(#{1,6})\s+\S/gm)].map((m) => m[1].length)
  const top = levels.length ? Math.min(...levels) : 2
  const nodes: ReactNode[] = []
  const headings: Heading[] = []
  let para: string[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let n = 0

  const flushPara = () => {
    if (para.length) { const k = `p${n++}`; nodes.push(<p key={k}>{inline(para.join(' '), cite, k)}</p>); para = [] }
  }
  const flushList = () => {
    if (!list) return
    const k = `l${n++}`
    const items = list.items.map((it, i) => <li key={i}>{inline(it, cite, `${k}-${i}`)}</li>)
    nodes.push(list.ordered ? <ol key={k}>{items}</ol> : <ul key={k}>{items}</ul>)
    list = null
  }

  for (const line of clean.split(/\r?\n/)) {
    let m: RegExpMatchArray | null
    if (!line.trim()) { flushPara(); flushList(); continue }
    if ((m = line.match(/^\s*(#{1,6})\s+(.*)$/))) {
      flushPara(); flushList()
      const text = m[2].replace(/\s*#+\s*$/, '')
      const level = Math.min(4, 2 + m[1].length - top)
      const k = `h${n++}`
      if (level === 2) {
        let id = slug(text) || `section-${headings.length + 1}`
        if (headings.some((h) => h.id === id)) id += `-${headings.length}`
        headings.push({ id, text: text.replace(/[*_`]/g, '') })
        nodes.push(<h2 key={k} id={id}>{inline(text, cite, k)}</h2>)
      } else nodes.push(level === 3 ? <h3 key={k}>{inline(text, cite, k)}</h3> : <h4 key={k}>{inline(text, cite, k)}</h4>)
    } else if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
      flushPara(); flushList(); nodes.push(<hr key={`r${n++}`} />)
    } else if ((m = line.match(/^\s*(?:[-*+]|(\d+)[.)])\s+(.*)$/))) {
      flushPara()
      const ordered = Boolean(m[1])
      if (!list || list.ordered !== ordered) { flushList(); list = { ordered, items: [] } }
      list.items.push(m[2])
    } else if ((m = line.match(/^\s*>\s?(.*)$/))) {
      flushPara(); flushList()
      const k = `q${n++}`
      nodes.push(<blockquote key={k}>{inline(m[1], cite, k)}</blockquote>)
    } else {
      flushList(); para.push(line.trim())
    }
  }
  flushPara(); flushList()
  return { nodes, headings }
}

/** First real paragraph (for teasers). */
export function firstParagraph(src: string) {
  // A heading may sit directly on top of its paragraph ("## Title\nText"), so drop heading lines first.
  const blocks = (src || '').split(/\n\s*\n/)
    .map((b) => b.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n').trim())
    .filter(Boolean)
  return blocks.find((b) => !/^([-*+]\s|\d+[.)]\s|[-*_]{3}|>)/.test(b)) ?? ''
}
