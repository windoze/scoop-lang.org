// Site behaviour: Scoop syntax highlighting, copy buttons, tabs, docs TOC.
(function () {
  "use strict";

  const KEYWORDS = new Set([
    "fun", "val", "var", "class", "interface", "object", "struct", "enum", "typealias",
    "companion", "if", "else", "when", "case", "for", "while", "do", "in", "is", "as",
    "return", "break", "continue", "throw", "try", "catch", "finally", "import", "package",
    "this", "super", "true", "false", "suspend", "override", "open", "abstract", "sealed",
    "final", "private", "public", "internal", "protected", "operator", "infix", "inline",
    "constructor", "init", "get", "set", "by", "where", "const", "inner", "context",
    "release", "until", "vararg", "crossinline", "noinline", "lateinit", "it",
  ]);
  const BUILTIN_VALUES = new Set(["Some", "None", "Unit"]);

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function span(cls, text) {
    return '<span class="tok-' + cls + '">' + esc(text) + "</span>";
  }

  // Finds the end of a `${ ... }` interpolation starting at `start` (index of `$`).
  function interpolationEnd(src, start) {
    let depth = 0;
    for (let i = start + 1; i < src.length; i++) {
      const ch = src[i];
      if (ch === "{") depth++;
      else if (ch === "}") {
        depth--;
        if (depth === 0) return i + 1;
      } else if (ch === '"') {
        i++;
        while (i < src.length && src[i] !== '"') {
          if (src[i] === "\\") i++;
          i++;
        }
      }
    }
    return src.length;
  }

  function highlightString(body, interpolate) {
    if (!interpolate) return span("s", body);
    let out = "";
    let buf = "";
    let i = 0;
    while (i < body.length) {
      if (body[i] === "$" && body[i + 1] === "{") {
        out += span("s", buf);
        buf = "";
        const end = interpolationEnd(body, i);
        const inner = body.slice(i + 2, Math.max(i + 2, end - 1));
        out += span("i", "${") + highlightScoop(inner) + span("i", "}");
        i = end;
      } else {
        buf += body[i];
        i++;
      }
    }
    return out + span("s", buf);
  }

  function highlightScoop(src) {
    let out = "";
    let i = 0;
    let prevWord = "";
    while (i < src.length) {
      const rest = src.slice(i);
      let m;
      if (rest.startsWith("//")) {
        const end = src.indexOf("\n", i);
        const stop = end === -1 ? src.length : end;
        out += span("c", src.slice(i, stop));
        i = stop;
        continue;
      }
      if (rest.startsWith("/*")) {
        const end = src.indexOf("*/", i + 2);
        const stop = end === -1 ? src.length : end + 2;
        out += span("c", src.slice(i, stop));
        i = stop;
        continue;
      }
      if (rest.startsWith('f"""') || rest.startsWith('"""')) {
        const prefix = rest[0] === "f" ? 1 : 0;
        const end = src.indexOf('"""', i + prefix + 3);
        const stop = end === -1 ? src.length : end + 3;
        out += highlightString(src.slice(i, stop), prefix === 1);
        i = stop;
        continue;
      }
      if (rest.startsWith('f"') || rest[0] === '"') {
        const prefix = rest[0] === "f" ? 1 : 0;
        let j = i + prefix + 1;
        while (j < src.length && src[j] !== '"' && src[j] !== "\n") {
          if (src[j] === "\\") j++;
          else if (prefix && src[j] === "$" && src[j + 1] === "{") {
            j = interpolationEnd(src, j);
            continue;
          }
          j++;
        }
        const stop = Math.min(j + 1, src.length);
        out += highlightString(src.slice(i, stop), prefix === 1);
        i = stop;
        continue;
      }
      if ((m = /^'(\\.|\\u\{[0-9a-fA-F]+\}|[^'\\])'/.exec(rest))) {
        out += span("s", m[0]);
        i += m[0].length;
        continue;
      }
      if ((m = /^@[A-Za-z_][A-Za-z0-9_]*/.exec(rest))) {
        out += span("a", m[0]);
        i += m[0].length;
        continue;
      }
      if ((m = /^(0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d[\d_]*(\.\d[\d_]*)?([eE][+-]?\d+)?)(uL|UL|ul|u|U|L|f|F)?/.exec(rest))) {
        out += span("n", m[0]);
        i += m[0].length;
        continue;
      }
      if ((m = /^`[^`\n]+`/.exec(rest))) {
        out += span(prevWord === "fun" ? "f" : "o", m[0]);
        i += m[0].length;
        prevWord = "";
        continue;
      }
      if ((m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(rest))) {
        const word = m[0];
        const after = src.slice(i + word.length);
        if (KEYWORDS.has(word)) out += span("k", word);
        else if (BUILTIN_VALUES.has(word)) out += span("p", word);
        else if (/^[A-Z]/.test(word)) out += span("t", word);
        else if (/^(<[\w<>, ?_]*>)?\(/.test(after)) out += span("f", word);
        else out += esc(word);
        prevWord = word;
        i += word.length;
        continue;
      }
      if ((m = /^(->|\?\.|\?:|!!|\.\.|==|!=|<=|>=|&&|\|\||[+\-*/%=<>!?:])/.exec(rest))) {
        out += span("o", m[0]);
        i += m[0].length;
        continue;
      }
      if (!/\s/.test(src[i])) prevWord = "";
      out += esc(src[i]);
      i++;
    }
    return out;
  }

  function highlightShell(src) {
    return src
      .split("\n")
      .map(function (line) {
        if (/^\s*#/.test(line)) return span("c", line);
        const m = /^(\$ )?(\S+)(.*)$/.exec(line);
        if (!m) return esc(line);
        return (m[1] ? span("o", m[1]) : "") + span("f", m[2]) + esc(m[3]).replace(/(\s)(--?[\w-]+)/g, '$1<span class="tok-a">$2</span>');
      })
      .join("\n");
  }

  function highlightToml(src) {
    return src
      .split("\n")
      .map(function (line) {
        if (/^\s*#/.test(line)) return span("c", line);
        if (/^\s*\[.*\]\s*$/.test(line)) return span("k", line);
        const m = /^(\s*)("[^"]*"|[\w.-]+)(\s*=\s*)(.*)$/.exec(line);
        if (!m) return esc(line);
        const value = esc(m[4])
          .replace(/("[^"]*")/g, '<span class="tok-s">$1</span>')
          .replace(/(#.*)$/, '<span class="tok-c">$1</span>');
        return m[1] + span("t", m[2]) + esc(m[3]) + value;
      })
      .join("\n");
  }

  const HIGHLIGHTERS = { scoop: highlightScoop, sh: highlightShell, toml: highlightToml };

  document.querySelectorAll("pre > code").forEach(function (code) {
    const lang = (/language-(\w+)/.exec(code.className) || [])[1];
    const fn = HIGHLIGHTERS[lang];
    const text = code.textContent.replace(/^\n/, "").replace(/\s+$/, "");
    if (fn) code.innerHTML = fn(text);
    else code.textContent = text;

    const pre = code.parentElement;
    const btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "复制";
    btn.addEventListener("click", function () {
      const plain = lang === "sh" ? text.replace(/^\$ /gm, "") : text;
      navigator.clipboard.writeText(plain).then(function () {
        btn.textContent = "已复制";
        setTimeout(function () { btn.textContent = "复制"; }, 1400);
      });
    });
    pre.appendChild(btn);
  });

  // Mobile navigation.
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector(".nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () { nav.classList.toggle("open"); });
  }

  // Showcase tabs on the home page.
  document.querySelectorAll(".showcase").forEach(function (box) {
    const tabs = box.querySelectorAll(".tab");
    const panels = box.querySelectorAll(".panel");
    tabs.forEach(function (tab, index) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) { t.classList.remove("active"); });
        panels.forEach(function (p) { p.classList.remove("active"); });
        tab.classList.add("active");
        panels[index].classList.add("active");
      });
    });
  });

  // Docs: build the sidebar TOC from headings and track the current section.
  document.querySelectorAll(".guide article table").forEach(function (table) {
    const wrapper = document.createElement("div");
    wrapper.className = "table-wrap";
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });

  const article = document.querySelector(".docs article");
  const toc = document.querySelector(".docs aside .toc");
  if (article && toc) {
    const links = [];
    article.querySelectorAll("h2[id], h3[id]").forEach(function (h) {
      const a = document.createElement("a");
      a.className = "anchor";
      a.href = "#" + h.id;
      a.textContent = "#";
      h.appendChild(a);

      const li = document.createElement("li");
      if (h.tagName === "H3") li.className = "sub";
      const link = document.createElement("a");
      link.href = "#" + h.id;
      link.textContent = h.firstChild.textContent.trim();
      li.appendChild(link);
      toc.appendChild(li);
      links.push({ heading: h, link: link });
    });

    function spy() {
      let current = links[0];
      links.forEach(function (entry) {
        if (entry.heading.getBoundingClientRect().top < 120) current = entry;
      });
      links.forEach(function (entry) { entry.link.classList.toggle("active", entry === current); });
    }
    if (links.length) {
      document.addEventListener("scroll", spy, { passive: true });
      spy();
    }
  }
})();
