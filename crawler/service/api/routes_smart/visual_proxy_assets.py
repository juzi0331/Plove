from __future__ import annotations

import re


def build_injected_visual_proxy_html(
    target_url: str, html_content: str, mode: str = "pick"
) -> str:
    """为目标页面注入 <base> 与可视化元素点选拾取器脚本。"""
    # 移除原站 CSP 与 X-Frame-Options 相关的 meta 标签，防止其限制在 iframe 中运行或阻断通信
    cleaned_html = re.sub(
        r'<meta[^>]+http-equiv=["\']?(?:Content-Security-Policy|X-Frame-Options)["\']?[^>]*>',
        "",
        html_content,
        flags=re.IGNORECASE,
    )
    # 移除原站可能的 frame-busting 恶意顶层跳转代码
    cleaned_html = re.sub(
        r'(?:window\.)?top\.location\s*=\s*(?:window\.)?self\.location',
        "/* neutralized frame-busting */",
        cleaned_html,
        flags=re.IGNORECASE,
    )
    # 移除 disable-devtool 等防审查脚本
    cleaned_html = re.sub(
        r'<script[^>]*disable-devtool[^>]*>.*?</script>',
        "",
        cleaned_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # 注入解除防盗链的 no-referrer meta，以及 base 标签
    meta_referrer = '<meta name="referrer" content="no-referrer"/>'
    base_tag = f'<base href="{target_url}"/>\n    {meta_referrer}'
    initial_mode = "browse" if mode == "browse" else "pick"

    injected_assets = f"""
    {base_tag}
    <style id="__plove_visual_picker_styles">
      #__plove_inspect_overlay {{
        position: fixed !important;
        pointer-events: none !important;
        z-index: 2147483647 !important;
        border: 2px solid #2563eb !important;
        background: rgba(37, 99, 235, 0.15) !important;
        box-shadow: 0 0 10px rgba(37, 99, 235, 0.4) !important;
        transition: all 0.05s ease-out !important;
        border-radius: 4px !important;
        box-sizing: border-box !important;
        display: none;
      }}
      #__plove_inspect_badge {{
        position: fixed !important;
        pointer-events: none !important;
        z-index: 2147483647 !important;
        background: #0f172a !important;
        color: #38bdf8 !important;
        border: 1px solid #334155 !important;
        font-size: 11px !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        padding: 2px 7px !important;
        border-radius: 4px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.35) !important;
        white-space: nowrap !important;
        max-width: 360px !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: none;
      }}
    </style>
    <script id="__plove_visual_picker_script">
    (function() {{
      if (window.__plove_picker_installed) return;
      window.__plove_picker_installed = true;

      // 自动解开常见懒加载图片 (data-src / data-original 等)
      function unrollLazyImages() {{
        try {{
          var imgs = document.querySelectorAll('img');
          for (var i = 0; i < imgs.length; i++) {{
            var img = imgs[i];
            var realSrc = img.getAttribute('data-src') || img.getAttribute('data-original') || img.getAttribute('data-lazy-src') || img.getAttribute('data-echo') || img.getAttribute('data-url');
            if (realSrc && img.getAttribute('src') !== realSrc) {{
              img.setAttribute('src', realSrc);
            }}
          }}
          var bgElements = document.querySelectorAll('[data-bg], [data-background], [data-original-bg]');
          for (var j = 0; j < bgElements.length; j++) {{
            var bEl = bgElements[j];
            var bSrc = bEl.getAttribute('data-bg') || bEl.getAttribute('data-background') || bEl.getAttribute('data-original-bg');
            if (bSrc && !bEl.style.backgroundImage) {{
              bEl.style.backgroundImage = 'url(' + bSrc + ')';
            }}
          }}
        }} catch(e) {{}}
      }}
      unrollLazyImages();
      window.addEventListener('DOMContentLoaded', unrollLazyImages);
      window.addEventListener('load', unrollLazyImages);
      setInterval(unrollLazyImages, 1200);

      var currentMode = "{initial_mode}";
      var isPickingMode = (currentMode === "pick");

      var overlay = document.createElement('div');
      overlay.id = '__plove_inspect_overlay';

      var badge = document.createElement('div');
      badge.id = '__plove_inspect_badge';

      function ensureMount() {{
        if (!document.body) return;
        if (!document.getElementById('__plove_inspect_overlay')) {{
          document.body.appendChild(overlay);
        }}
        if (!document.getElementById('__plove_inspect_badge')) {{
          document.body.appendChild(badge);
        }}
      }}

      var tipEl = document.createElement('div');
      tipEl.id = '__plove_tip';
      tipEl.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#0f172a;color:#f8fafc;padding:10px 20px;border-radius:30px;font-size:12px;z-index:2147483647;box-shadow:0 12px 30px rgba(0,0,0,0.6);display:none;pointer-events:none;font-family:system-ui,sans-serif;border:1px solid #38bdf8;transition:all 0.2s ease;';
      var tipTimer = null;

      function showPickerTip(msg) {{
        ensureMount();
        if (!document.getElementById('__plove_tip') && document.body) {{
          document.body.appendChild(tipEl);
        }}
        tipEl.innerText = msg;
        tipEl.style.display = 'block';
        clearTimeout(tipTimer);
        tipTimer = setTimeout(function() {{ tipEl.style.display = 'none'; }}, 3500);
      }}

      function notifyPageReady() {{
        ensureMount();
        unrollLazyImages();
        try {{
          window.parent.postMessage({{
            type: 'PLOVE_PAGE_READY',
            url: '{target_url}',
            mode: currentMode,
            title: document.title || ''
          }}, '*');
        }} catch(e) {{}}
      }}

      if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', notifyPageReady);
      }} else {{
        notifyPageReady();
      }}

      function getCssSelector(el) {{
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return '#' + el.id;
        var parts = [];
        var curr = el;
        while (curr && curr.nodeType === 1 && parts.length < 3) {{
          var tag = curr.tagName.toLowerCase();
          var classPart = '';
          if (curr.className && typeof curr.className === 'string') {{
            var cls = curr.className.trim().split(/\\s+/).filter(function(c) {{
              return c && !c.startsWith('__plove') && !c.includes(':');
            }}).slice(0, 2);
            if (cls.length > 0) {{
              classPart = '.' + cls.join('.');
            }}
          }}
          parts.unshift(tag + classPart);
          curr = curr.parentElement;
        }}
        return parts.join(' > ');
      }}

      function findSimilarElements(el) {{
        var results = [];
        if (!el || !el.parentElement) return results;

        var tag = el.tagName.toLowerCase();
        var parent = el.parentElement;
        var candidateElements = [];

        // 策略 A: 同父级容器下的相同标签兄弟节点 (例如 div.tags > a 或 ul > li)
        var parentChildren = Array.from(parent.children).filter(function(child) {{
          return !child.id || !child.id.startsWith('__plove');
        }});

        if (parentChildren.length > 1) {{
          var sameTagChildren = parentChildren.filter(function(c) {{
            return c.tagName.toLowerCase() === tag;
          }});
          if (sameTagChildren.length > 1) {{
            candidateElements = sameTagChildren;
          }}
        }}

        // 策略 B: 两级嵌套列表结构 (例如 ul > li > a，点击的是 a)
        if (candidateElements.length <= 1 && parent.parentElement) {{
          var grandParent = parent.parentElement;
          var grandChildren = Array.from(grandParent.children).filter(function(child) {{
            return !child.id || !child.id.startsWith('__plove');
          }});
          if (grandChildren.length > 1) {{
            var extracted = [];
            for (var i = 0; i < grandChildren.length; i++) {{
              var gc = grandChildren[i];
              var sub = gc.tagName.toLowerCase() === tag ? gc : gc.querySelector(tag);
              if (sub) {{
                extracted.push(sub);
              }}
            }}
            if (extracted.length > 1) {{
              candidateElements = extracted;
            }}
          }}
        }}

        // 策略 C: 相同 class 的同祖先兄弟项
        if (candidateElements.length <= 1 && el.className && typeof el.className === 'string') {{
          var firstCls = el.className.trim().split(/\\s+/).filter(function(c) {{
            return c && !c.startsWith('__plove') && !c.includes(':');
          }})[0];
          if (firstCls) {{
            var ancestor = el.closest('nav, ul, ol, .nav, .menu, .tags, .filter, .list, .module, .tab') || parent.parentElement || parent;
            if (ancestor) {{
              try {{
                var classMatches = Array.from(ancestor.querySelectorAll('.' + firstCls));
                if (classMatches.length > 1 && classMatches.length <= 60) {{
                  candidateElements = classMatches;
                }}
              }} catch (err) {{}}
            }}
          }}
        }}

        // 遍历提取候选元素的属性与文本
        var seenTexts = {{}};
        for (var j = 0; j < candidateElements.length; j++) {{
          var item = candidateElements[j];
          var targetItem = (tag === 'a' && item.tagName.toLowerCase() !== 'a') ? (item.querySelector('a') || item) : item;
          var txt = (targetItem.innerText || targetItem.textContent || '').trim().replace(/\\s+/g, ' ');
          if (!txt || txt.length > 40) continue;
          if (seenTexts[txt]) continue;
          seenTexts[txt] = true;

          var anchor = targetItem.tagName.toUpperCase() === 'A' ? targetItem : (targetItem.closest('a') || targetItem.querySelector('a'));
          var href = anchor ? (anchor.getAttribute('href') || '') : '';
          var fullHref = '';
          if (href && !href.startsWith('javascript:') && !href.startsWith('#')) {{
            try {{
              fullHref = new URL(href, document.baseURI).href;
            }} catch (err) {{
              fullHref = href;
            }}
          }}

          results.push({{
            text: txt,
            href: fullHref || href,
            selector: getCssSelector(targetItem),
            tagName: targetItem.tagName.toUpperCase()
          }});
        }}

        return results;
      }}

      function extractElementData(el) {{
        var rect = el.getBoundingClientRect();
        var tagName = el.tagName.toUpperCase();
        var text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
        var anchor = el.closest('a');
        var rawHref = (anchor ? anchor.getAttribute('href') : el.getAttribute('href')) || '';
        var fullHref = '';
        if (rawHref && !rawHref.startsWith('javascript:') && !rawHref.startsWith('#')) {{
          try {{
            fullHref = new URL(rawHref, document.baseURI).href;
          }} catch (err) {{
            fullHref = rawHref;
          }}
        }}
        var img = el.tagName.toUpperCase() === 'IMG' ? el : el.querySelector('img');
        if (!img && el.parentElement) {{
          img = el.parentElement.querySelector('img');
        }}
        var src = '';
        if (img) {{
          src = img.getAttribute('data-src') || img.getAttribute('data-original') || img.getAttribute('data-lazy-src') || img.getAttribute('data-echo') || img.getAttribute('data-url') || img.getAttribute('data-bg') || img.getAttribute('src') || '';
          if (src && src.startsWith('data:image') && src.length < 300) {{
            var altSrc = img.getAttribute('data-src') || img.getAttribute('data-original') || img.getAttribute('data-lazy-src') || img.getAttribute('data-echo');
            if (altSrc) src = altSrc;
          }}
          if (src && !src.startsWith('data:')) {{
            try {{
              src = new URL(src, document.baseURI).href;
            }} catch(e) {{}}
          }}
        }}
        if (!src) {{
          var bgEl = el.getAttribute('data-bg') ? el : (el.querySelector('[data-bg]') || (el.parentElement ? el.parentElement.querySelector('[data-bg]') : null) || el);
          var bgData = bgEl.getAttribute('data-bg') || bgEl.getAttribute('data-background') || bgEl.getAttribute('data-original-bg');
          if (bgData) {{
            src = bgData;
          }} else {{
            var bg = el.style.backgroundImage || (window.getComputedStyle ? window.getComputedStyle(el).backgroundImage : '');
            if (bg && bg.indexOf('url(') !== -1) {{
              var m = bg.match(/url\\(['"]?(.*?)['"]?\\)/);
              if (m && m[1]) src = m[1];
            }}
          }}
          if (src && !src.startsWith('data:')) {{
            try {{
              src = new URL(src, document.baseURI).href;
            }} catch(e) {{}}
          }}
        }}

        return {{
          tagName: tagName,
          text: text.slice(0, 160),
          href: fullHref || rawHref,
          src: src,
          selector: getCssSelector(el),
          rect: {{
            top: rect.top,
            left: rect.left,
            width: rect.width,
            height: rect.height
          }},
          siblings: findSimilarElements(el)
        }};
      }}

      document.addEventListener('mouseover', function(e) {{
        if (!isPickingMode) return;
        var target = e.target;
        if (!target || target === overlay || target === badge || (target.id && target.id.startsWith('__plove'))) return;
        ensureMount();

        var rect = target.getBoundingClientRect();
        overlay.style.top = rect.top + 'px';
        overlay.style.left = rect.left + 'px';
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
        overlay.style.display = 'block';

        var selector = getCssSelector(target);
        badge.innerText = selector;
        badge.style.top = Math.max(0, rect.top - 24) + 'px';
        badge.style.left = rect.left + 'px';
        badge.style.display = 'block';

        window.parent.postMessage({{
          type: 'PLOVE_ELEMENT_HOVERED',
          data: extractElementData(target)
        }}, '*');
      }}, true);

      document.addEventListener('mouseout', function(e) {{
        if (!isPickingMode) return;
        overlay.style.display = 'none';
        badge.style.display = 'none';
      }}, true);

      document.addEventListener('click', function(e) {{
        var target = e.target;
        if (!target || target === overlay || target === badge) return;

        var isCtrlClick = !!(e.ctrlKey || e.metaKey);
        var anchor = target.closest('a');

        // 穿透跳转机制: 任何模式下按住 Ctrl/Cmd 键点击链接，直接跳转进入新页面
        if (isCtrlClick && anchor && anchor.getAttribute('href')) {{
          var ctrlHref = anchor.getAttribute('href');
          if (ctrlHref && !ctrlHref.startsWith('#') && !ctrlHref.startsWith('javascript:')) {{
            e.preventDefault();
            e.stopPropagation();
            try {{
              var fullUrl = new URL(ctrlHref, document.baseURI).href;
              window.parent.postMessage({{
                type: 'PLOVE_NAVIGATE_PAGE',
                url: fullUrl,
                mode: currentMode
              }}, '*');
              window.location.href = '/api/v1/smart/visual-proxy?url=' + encodeURIComponent(fullUrl) + '&mode=' + encodeURIComponent(currentMode);
              return;
            }} catch (err) {{
              console.warn('URL 解析失败', err);
            }}
          }}
        }}

        if (isPickingMode) {{
          e.preventDefault();
          e.stopPropagation();
          var data = extractElementData(target);
          window.parent.postMessage({{
            type: 'PLOVE_ELEMENT_CLICKED',
            data: data
          }}, '*');
          if (anchor && anchor.getAttribute('href')) {{
            showPickerTip('🎯 已捕获该链接元素。如需直接跳转进入分类/详情页，请切换顶部【🌐 自由浏览模式】，或按住 Ctrl 键点击链接！');
          }}
        }} else {{
          // 自由浏览模式下拦截站内 a 标签并重写走代理，同时保持当前 browse 模式不变
          if (anchor && anchor.getAttribute('href')) {{
            var rawHref = anchor.getAttribute('href');
            if (rawHref && !rawHref.startsWith('#') && !rawHref.startsWith('javascript:')) {{
              e.preventDefault();
              try {{
                var fullUrl = new URL(rawHref, document.baseURI).href;
                window.parent.postMessage({{
                  type: 'PLOVE_NAVIGATE_PAGE',
                  url: fullUrl,
                  mode: currentMode
                }}, '*');
                window.location.href = '/api/v1/smart/visual-proxy?url=' + encodeURIComponent(fullUrl) + '&mode=' + encodeURIComponent(currentMode);
              }} catch (err) {{
                console.warn('URL 解析失败', err);
              }}
            }}
          }}
        }}
      }}, true);

      window.addEventListener('message', function(evt) {{
        if (!evt.data) return;
        if (evt.data.type === 'PLOVE_SET_MODE') {{
          currentMode = evt.data.mode;
          isPickingMode = (currentMode === 'pick');
          if (!isPickingMode) {{
            overlay.style.display = 'none';
            badge.style.display = 'none';
          }}
        }}
      }});
    }})();
    </script>
    """

    head_match = re.search(r"<head[^>]*>", cleaned_html, re.IGNORECASE)
    if head_match:
        pos = head_match.end()
        result = cleaned_html[:pos] + injected_assets + cleaned_html[pos:]
    else:
        result = injected_assets + cleaned_html

    return result
