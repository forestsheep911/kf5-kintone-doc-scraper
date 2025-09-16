#!/usr/bin/env python3
import sys
from pathlib import Path


MARKER_STYLE = "copy-code-style"
MARKER_SCRIPT = "copy-code-script"


STYLE_BLOCK_TEMPLATE = """
<style id="{style_id}">
.code-block-wrapper {
  position: relative !important;
}
.code-actions {
  position: absolute !important;
  top: 8px !important;
  right: 8px !important;
  display: flex !important;
  gap: 8px !important;
  z-index: 1000 !important;
}
.copy-code-btn, .wrap-code-btn {
  padding: 4px 8px !important;
  font-size: 12px !important;
  line-height: 1 !important;
  color: #2c3e50 !important;
  background: #ecf0f1 !important;
  border: 1px solid #d0d7de !important;
  border-radius: 4px !important;
  cursor: pointer !important;
  opacity: 0.85 !important;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
}
.copy-code-btn:hover, .wrap-code-btn:hover {
  opacity: 1 !important;
  background: #e6ebef !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
}
.wrap-code-btn.active {
  background: #3b82f6 !important;
  color: white !important;
  border-color: #3b82f6 !important;
}
pre.has-copy-btn {
  padding-top: 40px !important;
  position: relative !important;
  white-space: pre !important;
  overflow-x: auto !important;
}
pre.wrapped {
  white-space: pre-wrap !important;
  word-wrap: break-word !important;
  word-break: break-all !important;
}
</style>
"""


SCRIPT_BLOCK_TEMPLATE = '''
<script id="{script_id}">
(function() {
  function isCodePre(pre) {
    if (!pre || pre.tagName !== 'PRE') return false;
    if (pre.querySelector('code')) return true;
    var cls = (pre.getAttribute('class') || '').toLowerCase();
    if (/(brush:|language-|lang-|code)/.test(cls)) return true;

    // Check if pre contains code-like content (JSON, JavaScript, etc.)
    var text = pre.textContent || pre.innerText || '';
    // Check for common code patterns: {, }, [, ], function, var, const, let, etc.
    return /[{}\[\]]/.test(text) || /\\b(function|var|const|let|if|for|while)\\b/.test(text);
  }

  function getCodeText(pre) {
    var code = pre.querySelector('code');
    var el = code || pre;
    return (el.innerText || el.textContent || '').trim();
  }

  function addCopy(pre) {
    if (pre.classList.contains('has-copy-processed')) return;
    pre.classList.add('has-copy-processed');
    var wrapper = pre.parentElement;
    if (!wrapper || !wrapper.classList.contains('code-block-wrapper')) {
      wrapper = document.createElement('div');
      wrapper.className = 'code-block-wrapper';
      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.appendChild(pre);
    }
    pre.classList.add('has-copy-btn');
    
    // 创建按钮容器
    var actionsDiv = document.createElement('div');
    actionsDiv.className = 'code-actions';
    
    // 创建换行按钮
    var wrapBtn = document.createElement('button');
    wrapBtn.className = 'wrap-code-btn';
    wrapBtn.type = 'button';
    wrapBtn.textContent = '换行';
    wrapBtn.addEventListener('click', function() {
      pre.classList.toggle('wrapped');
      if (pre.classList.contains('wrapped')) {
        wrapBtn.textContent = '不换行';
        wrapBtn.classList.add('active');
      } else {
        wrapBtn.textContent = '换行';
        wrapBtn.classList.remove('active');
      }
    });
    
    // 创建复制按钮
    var copyBtn = document.createElement('button');
    copyBtn.className = 'copy-code-btn';
    copyBtn.type = 'button';
    copyBtn.textContent = '复制';
    copyBtn.addEventListener('click', function() {
      var text = getCodeText(pre);
      function done(ok) {
        var old = copyBtn.textContent;
        copyBtn.textContent = ok ? '已复制' : '复制失败';
        copyBtn.disabled = true;
        setTimeout(function() {
          copyBtn.textContent = old;
          copyBtn.disabled = false;
        }, 1200);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() { done(true); }, function() { done(false); });
      } else {
        try {
          var ta = document.createElement('textarea');
          ta.value = text;
          ta.style.position = 'fixed';
          ta.style.top = '-1000px';
          document.body.appendChild(ta);
          ta.focus();
          ta.select();
          var ok = document.execCommand('copy');
          document.body.removeChild(ta);
          done(!!ok);
        } catch (e) { done(false); }
      }
    });
    
    // 添加按钮到容器
    actionsDiv.appendChild(wrapBtn);
    actionsDiv.appendChild(copyBtn);
    wrapper.appendChild(actionsDiv);
  }

  function process() {
    var pres = Array.prototype.slice.call(document.getElementsByTagName('pre'));
    pres.forEach(function(pre, index) {
      var content = pre.textContent || pre.innerText || '';
      if (isCodePre(pre)) {
        addCopy(pre);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', process);
  } else {
    process();
  }
})();
</script>
'''


def inject(html: str) -> str:
    # Force re-injection by removing existing blocks first
    import re
    # Remove existing style block
    html = re.sub(r'<style[^>]*id="[^"]*copy-code-style[^"]*"[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    # Remove existing script block
    html = re.sub(r'<script[^>]*id="[^"]*copy-code-script[^"]*"[^>]*>.*?</script>', '', html, flags=re.DOTALL)

    # Insert style before </head>
    if '</head>' in html:
        style_block = STYLE_BLOCK_TEMPLATE.replace('{style_id}', MARKER_STYLE)
        html = html.replace('</head>', style_block + '\n</head>', 1)
    else:
        # Fallback: prepend style
        html = STYLE_BLOCK_TEMPLATE.replace('{style_id}', MARKER_STYLE) + html

    # Insert script before </body>
    if '</body>' in html:
        script_block = SCRIPT_BLOCK_TEMPLATE.replace('{script_id}', MARKER_SCRIPT)
        html = html.replace('</body>', script_block + '\n</body>', 1)
    else:
        # Fallback: append script
        html = html + SCRIPT_BLOCK_TEMPLATE.replace('{script_id}', MARKER_SCRIPT)

    return html


def main(args):
    # Default targets
    candidates = [
        Path('output_full/html'),
        Path('output/html'),
        Path('output_test/html'),
        Path('output_small/html'),
    ]
    # Allow custom paths via args
    if args:
        candidates = [Path(a) for a in args]

    targets = [p for p in candidates if p.exists()]
    if not targets:
        print('No target HTML directories found.', file=sys.stderr)
        sys.exit(1)

    total = 0
    changed = 0
    for base in targets:
        for fp in base.rglob('*.html'):
            total += 1
            try:
                text = fp.read_text(encoding='utf-8', errors='ignore')
                new_text = inject(text)
                if new_text != text:
                    fp.write_text(new_text, encoding='utf-8')
                    changed += 1
            except Exception as e:
                print(f"Failed to process {fp}: {e}", file=sys.stderr)

    print(f"Scanned {total} HTML files; injected into {changed} files.")


if __name__ == '__main__':
    main(sys.argv[1:])
