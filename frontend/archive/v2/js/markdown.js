/*
  Minimal Markdown → HTML for the AI market brief.
  Everything is HTML-escaped FIRST, so model output can never inject markup;
  only a fixed set of constructs is then re-introduced.
*/
import { esc } from './util.js';

export const slug = (s) => String(s).toLowerCase().replace(/<[^>]+>/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

function inline(t) {
  return t
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*(?=[\s).,;:!?]|$)/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\[(\d{1,10})\]/g, '<a class="cite" href="#" data-action="open-article" data-id="$1">$1</a>');
}

/**
 * Returns { html, headings: [{id, text}] }.
 * The shallowest heading level in the document becomes the section level (<h2 id>,
 * listed in the TOC) — providers disagree on whether sections are `##` or `###`.
 */
export function renderMarkdown(src) {
  const out = [];
  const headings = [];
  let list = null;
  let para = [];
  const levels = [...String(src || '').matchAll(/^\s*(#{1,6})\s+\S/gm)].map((m) => m[1].length);
  const top = levels.length ? Math.min(...levels) : 2;
  const flushPara = () => { if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para = []; } };
  const flushList = () => { if (list) { out.push(`</${list}>`); list = null; } };

  esc(src || '')
    .replace(/\\([#*_[\]()`-])/g, '$1') // markdownify escapes
    .split(/\r?\n/)
    .forEach((line) => {
      let m;
      if (!line.trim()) { flushPara(); flushList(); return; }
      if ((m = line.match(/^\s*(#{1,6})\s+(.*)$/))) {
        flushPara(); flushList();
        const level = Math.min(4, 2 + m[1].length - top);
        const text = inline(m[2].replace(/\s*#+\s*$/, ''));
        if (level === 2) {
          let id = slug(text) || `section-${headings.length + 1}`;
          if (headings.some((h) => h.id === id)) id += `-${headings.length}`;
          headings.push({ id, text: text.replace(/<[^>]+>/g, '') });
          out.push(`<h2 id="${id}">${text}</h2>`);
        } else {
          out.push(`<h${level}>${text}</h${level}>`);
        }
      } else if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
        flushPara(); flushList(); out.push('<hr>');
      } else if ((m = line.match(/^\s*(?:[-*+]|(\d+)[.)])\s+(.*)$/))) {
        flushPara();
        const tag = m[1] ? 'ol' : 'ul';
        if (list !== tag) { flushList(); out.push(`<${tag}>`); list = tag; }
        out.push(`<li>${inline(m[2])}</li>`);
      } else if ((m = line.match(/^\s*&gt;\s?(.*)$/))) {
        flushPara(); flushList(); out.push(`<blockquote>${inline(m[1])}</blockquote>`);
      } else {
        flushList(); para.push(line.trim());
      }
    });
  flushPara(); flushList();
  return { html: out.join(''), headings };
}

/** First paragraph under the first heading — used as the Overview teaser. */
export function firstParagraph(src) {
  const blocks = String(src || '').split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const para = blocks.find((b) => !/^(#|[-*+]\s|\d+[.)]\s|[-*_]{3})/.test(b));
  return para || '';
}
