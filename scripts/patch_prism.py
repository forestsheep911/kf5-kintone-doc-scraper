#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给已生成的静态输出补丁：注入 Prism 语法高亮、映射 brush 标记、启发式补全语言。

用法：
  poetry run python scripts/patch_prism.py [OUTPUT_DIR]

默认 OUTPUT_DIR = output_full
"""

from pathlib import Path
import sys


PRISM_CSS = (
    '\n    <!-- Prism syntax highlighting -->\n'
    '    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs/themes/prism.min.css">\n'
    '    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs/plugins/line-numbers/prism-line-numbers.min.css">\n'
)

PRISM_JS = (
    '\n    <!-- Prism core + autoloader -->\n'
    '    <script src="https://cdn.jsdelivr.net/npm/prismjs/prism.min.js"></script>\n'
    '    <script src="https://cdn.jsdelivr.net/npm/prismjs/plugins/autoloader/prism-autoloader.min.js"></script>\n'
)

ENHANCE_JS = (
    """
    <!-- PRISM_ENHANCER -->
    <script>
      (function(){
        if (window.Prism && Prism.plugins && Prism.plugins.autoloader) {
          Prism.plugins.autoloader.languages_path = 'https://cdn.jsdelivr.net/npm/prismjs/components/';
        }
        function inferLanguage(text){
          const t = (text || '').trim();
          if (!t) return null;
          if (/^\{[\s\S]*\}$/.test(t) || /^\[/.test(t)) { try { JSON.parse(t); return 'json'; } catch(e){} }
          if (/<\/?[a-zA-Z]/.test(t)) return 'markup';
          if (/^(\$ |curl |#\!\/|sudo |apt |yum |brew )/m.test(t)) return 'bash';
          if (/(import |from |def |class |print\(|lambda )/.test(t)) return 'python';
          if (/(const |let |var |=>|function\s+\w+\()/.test(t)) return 'javascript';
          if (/(SELECT |INSERT |UPDATE |DELETE |CREATE TABLE)/i.test(t)) return 'sql';
          return null;
        }
        function mapBrushToPrism(brush){
          const m = String(brush || '').toLowerCase();
          const map = { js:'javascript', javascript:'javascript', ts:'typescript', typescript:'typescript',
                        html:'markup', xml:'markup', markup:'markup', json:'json', css:'css',
                        bash:'bash', shell:'bash', sh:'bash', sql:'sql', java:'java', py:'python', python:'python',
                        yaml:'yaml', yml:'yaml', ini:'ini', txt:'none' };
          return map[m] || null;
        }
        function enhanceCodeBlocks(root){
          const container = root || document;
          const pres = Array.from(container.querySelectorAll('pre'));
          pres.forEach(pre => {
            let lang = null;
            const cls = pre.getAttribute('class') || '';
            const m = cls.match(/brush:([\w-]+)/i);
            if (m) lang = mapBrushToPrism(m[1]);
            let code = pre.querySelector('code');
            if (code) {
              const codeCls = code.getAttribute('class') || '';
              const mm = codeCls.match(/language-([\w-]+)/i);
              if (mm) lang = mm[1];
            }
            if (!lang) {
              const text = (code ? code.textContent : pre.textContent) || '';
              lang = inferLanguage(text) || 'none';
            }
            const actions = pre.querySelector('.code-actions');
            if (!code) {
              const rawText = pre.textContent || '';
              pre.innerHTML = '';
              code = document.createElement('code');
              code.textContent = rawText;
              pre.appendChild(code);
              if (actions) pre.appendChild(actions);
            }
            const langClass = 'language-' + lang;
            if (!code.classList.contains(langClass)) code.classList.add(langClass);
            const textForLines = code.textContent || '';
            if (textForLines.indexOf('\n') !== -1) pre.classList.add('line-numbers');
          });
          if (window.Prism && Prism.highlightAllUnder) {
            Prism.highlightAllUnder(container);
          }
        }
        window.enhanceCodeBlocks = enhanceCodeBlocks;
        document.addEventListener('DOMContentLoaded', function(){
          try { enhanceCodeBlocks(document); } catch(e) {}
          try {
            const contentArea = document.querySelector('.content-area');
            if (contentArea && window.MutationObserver) {
              const obs = new MutationObserver(function(records){
                records.forEach(function(m){
                  if (m.type === 'attributes' && m.target && m.target.classList && m.target.classList.contains('article-content') && m.target.classList.contains('active')) {
                    enhanceCodeBlocks(m.target);
                  }
                  if (m.type === 'childList') {
                    m.addedNodes && m.addedNodes.forEach(function(n){
                      if (n.nodeType === 1 && n.classList && n.classList.contains('article-content') && n.classList.contains('active')) {
                        enhanceCodeBlocks(n);
                      }
                    });
                  }
                });
              });
              obs.observe(contentArea, { subtree: true, childList: true, attributes: true, attributeFilter: ['class'] });
            }
          } catch(e) {}
        });
      })();
    </script>
    <script>
      // ARTICLE_LINK_ROUTER: 在单篇文章页面内，将站内文章链接跳转到首页+hash
      document.addEventListener('click', function(e){
        var el = e.target && e.target.closest ? e.target.closest('a.article-link') : null;
        if (!el) return;
        var aid = el.getAttribute('data-article-id');
        var original = el.getAttribute('data-original-href');
        if (!aid) return;
        e.preventDefault();
        try {
          var back = document.querySelector('.navbar .back-to-home');
          var indexLink = (back && back.getAttribute('href')) || 'index.html';
          if (indexLink.indexOf('#') !== -1) indexLink = indexLink.split('#')[0];
          var target = indexLink + '#' + String(aid);
          window.location.href = target;
        } catch(err) {
          if (original) {
            window.location.href = original;
          } else {
            window.location.hash = String(aid);
          }
        }
      }, false);
    </script>
    """
)

SPA_ROUTER_JS = (
    """
    <!-- SPA_ROUTER -->
    <script>
      (function(){
        function getIdFromHash(){ return (location.hash || '').replace(/^#/, ''); }
        function isId(v){ return /^\d+$/.test(v || ''); }
        function safe(fn){ try { fn(); } catch(e) {} }

        document.addEventListener('DOMContentLoaded', function(){
          // 初次根据 hash 展示
          var id = getIdFromHash();
          if (isId(id) && typeof showArticle === 'function') {
            safe(function(){ showArticle(id); });
          } else if (typeof showWelcome === 'function') {
            safe(function(){ showWelcome(); });
          }

          // 拦截正文内的站内文章链接
          document.addEventListener('click', function(e){
            var a = e.target && e.target.closest ? e.target.closest('a.article-link') : null;
            if (!a) return;
            var aid = a.getAttribute('data-article-id');
            if (isId(aid)) {
              e.preventDefault();
              // 更新 hash，触发 hashchange
              if (location.hash !== ('#' + aid)) location.hash = '#' + aid;
              else if (typeof showArticle === 'function') safe(function(){ showArticle(aid); });
            }
          }, false);
        });

        // 前进/后退
        window.addEventListener('hashchange', function(){
          var id = getIdFromHash();
          if (isId(id) && typeof showArticle === 'function') {
            safe(function(){ showArticle(id); });
          } else if (typeof showWelcome === 'function') {
            safe(function(){ showWelcome(); });
          }
        });
      })();
    </script>
    """
)


def patch_index_html(index_file: Path) -> None:
    html = index_file.read_text(encoding='utf-8')
    changed = False

    if 'prism.min.css' not in html:
        html = html.replace('</head>', PRISM_CSS + '\n</head>')
        changed = True
    if 'prism.min.js' not in html:
        # 插在第一个 <script> 之前，或 </body> 之前
        if '<script>' in html:
            html = html.replace('<script>', PRISM_JS + '\n    <script>', 1)
        else:
            html = html.replace('</body>', PRISM_JS + '\n</body>')
        changed = True
    if 'PRISM_ENHANCER' not in html:
        html = html.replace('</body>', ENHANCE_JS + '\n</body>')
        changed = True
    if 'SPA_ROUTER' not in html:
        html = html.replace('</body>', SPA_ROUTER_JS + '\n</body>')
        changed = True

    if changed:
        index_file.write_text(html, encoding='utf-8')
        print(f"[patched] {index_file}")
    else:
        print(f"[skip] {index_file} (no changes)")


def patch_article_html(file_path: Path) -> None:
    html = file_path.read_text(encoding='utf-8', errors='ignore')
    changed = False

    if 'prism.min.css' not in html:
        html = html.replace('</head>', PRISM_CSS + '\n</head>')
        changed = True
    if 'prism.min.js' not in html:
        html = html.replace('</body>', PRISM_JS + '\n</body>')
        changed = True
    if 'PRISM_ENHANCER' not in html:
        html = html.replace('</body>', ENHANCE_JS + '\n</body>')
        changed = True

    # 增补 data-original-href 便于兜底：a.article-link[data-article-id]
    try:
        import re
        def add_original_href(m):
            before, mid, aid, after = m.group(1), m.group(2), m.group(3), m.group(4)
            if 'data-original-href' in mid or 'data-original-href' in after:
                return m.group(0)
            return f"<a{before}class=\"article-link\"{mid}data-article-id=\"{aid}\" data-original-href=\"https://cybozudev.kf5.com/hc/kb/article/{aid}/\"{after}>"
        new_html = re.sub(r'<a([^>]*?)class=\"article-link\"([^>]*?)data-article-id=\"(\d+)\"([^>]*)>', add_original_href, html)
        if new_html != html:
            html = new_html
            changed = True
    except Exception:
        pass

    if changed:
        file_path.write_text(html, encoding='utf-8')
        print(f"[patched]")


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('output_full')
    index_file = out_dir / 'index.html'
    if index_file.exists():
        patch_index_html(index_file)
    else:
        print(f"! 未找到 {index_file}")

    html_root = out_dir / 'html'
    if html_root.exists():
        for p in html_root.rglob('*.html'):
            patch_article_html(p)
    else:
        print(f"= 未找到文章目录: {html_root}")


if __name__ == '__main__':
    main()
