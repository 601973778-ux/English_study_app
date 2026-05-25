# -*- coding: utf-8 -*-
"""Regenerate app/pages/api-config.html with correct UTF-8."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "pages" / "api-config.html"

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>API \u63a5\u5165\u914d\u7f6e \u00b7 \u5355\u8bcd\u5b66\u4e60</title>
<script src="https://modao.cc/agent-py/static/source/js/tailwindcss.3.4.3.js"></script>
<script src="https://modao.cc/agent-py/static/source/js/iconify-icon.min.1.0.7.js"></script>
<style>body { background: #F4F4F4; font-family: system-ui, sans-serif; }</style>
</head>
<body class="min-h-screen p-8">
  <motion class="max-w-lg mx-auto bg-white rounded-xl shadow-sm border border-gray-200 p-8">
    <h1 class="text-xl font-bold text-gray-900 mb-2 flex items-center gap-2">
      <iconify-icon icon="ph:plugs-connected-bold" class="text-blue-600"></iconify-icon>
      \u8baf\u98de\u6587\u5b57\u8f6c\u8bed\u97f3 API
    </h1>
    <p class="text-sm text-gray-500 mb-4">
      \u4fdd\u5b58\u81f3\u672c\u5730 <code class="bg-gray-100 px-1 rounded text-xs">user_data/xfyun_credentials.json</code>\uff08\u4e0d\u5165 Git\uff09\u3002
      \u53d1\u97f3\u63a5\u53e3\uff1a<code class="bg-gray-100 px-1 rounded text-xs">GET /api/tts</code>
    </p>
    <p id="status" class="text-sm mb-6 px-3 py-2 rounded-lg bg-gray-50 text-gray-600">\u52a0\u8f7d\u4e2d\u2026</p>

    <motion class="space-y-4">
      <motion>
        <label class="block text-sm font-medium text-gray-700 mb-1" for="appid">APPID</label>
        <input id="appid" type="text" autocomplete="off" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="\u8baf\u98de\u63a7\u5236\u53f0\u5e94\u7528 APPID" />
      </motion>
      <motion>
        <label class="block text-sm font-medium text-gray-700 mb-1" for="apiKey">API Key</label>
        <input id="apiKey" type="password" autocomplete="new-password" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="\u8baf\u98de API Key" />
      </motion>
      <motion>
        <label class="block text-sm font-medium text-gray-700 mb-1" for="apiSecret">API Secret</label>
        <input id="apiSecret" type="password" autocomplete="new-password" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="\u8baf\u98de API Secret" />
      </motion>
    </motion>

    <p class="text-xs text-gray-400 mt-4">
      \u5728
      <a class="text-blue-600 hover:underline" href="https://console.xfyun.cn/services/tts" target="_blank" rel="noopener">\u8baf\u98de\u5f00\u653e\u5e73\u53f0 \u00b7 \u5728\u7ebf\u8bed\u97f3\u5408\u6210</a>
      \u521b\u5efa\u5e94\u7528\u5e76\u5f00\u901a WebAPI\uff1b\u51ed\u8bc1\u4ec5\u4fdd\u5b58\u5728\u672c\u673a\u3002
    </p>

    <div class="flex flex-wrap gap-3 mt-8">
      <button type="button" id="saveBtn" class="px-5 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-500">\u4fdd\u5b58\u914d\u7f6e</button>
      <button type="button" id="testBtn" class="px-5 py-2.5 rounded-lg border border-blue-300 text-blue-700 text-sm font-semibold hover:bg-blue-50">\u6d4b\u8bd5\u53d1\u97f3</button>
      <button type="button" id="clearBtn" class="px-5 py-2.5 rounded-lg border border-gray-300 text-gray-600 text-sm hover:bg-gray-50">\u6e05\u9664\u672c\u5730\u914d\u7f6e</button>
      <a href="/app/index.html" class="px-5 py-2.5 rounded-lg border border-gray-300 text-sm inline-flex items-center gap-1 hover:bg-gray-50">
        <iconify-icon icon="ph:arrow-left-bold"></iconify-icon> \u8fd4\u56de\u80cc\u8bf5
      </a>
    </div>
    <p id="msg" class="text-sm mt-4 text-gray-600" role="status" aria-live="polite"></p>
  </motion>
  <script>
    async function apiGet(path) {
      const res = await fetch(path);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
      return data;
    }
    async function apiPost(path, body) {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
      return data;
    }

    function renderStatus(cfg) {
      const el = document.getElementById("status");
      if (!cfg.configured) {
        el.className = "text-sm mb-6 px-3 py-2 rounded-lg bg-amber-50 text-amber-800";
        el.textContent = "\u5c1a\u672a\u914d\u7f6e\uff1a\u586b\u5199\u5e76\u4fdd\u5b58\u540e\u53ef\u4f7f\u7528\u53d1\u97f3\u3002";
        return;
      }
      const src = cfg.source === "file" ? "\u672c\u5730\u6587\u4ef6" : (cfg.source === "env" ? "\u73af\u5883\u53d8\u91cf" : "\u672a\u77e5");
      let extra = "";
      if (cfg.env_also_set && cfg.file_has_priority) {
        extra = "\uff08\u5df2\u540c\u65f6\u8bbe\u7f6e\u73af\u5883\u53d8\u91cf\uff0c\u4f18\u5148\u4f7f\u7528\u672c\u5730\u6587\u4ef6\uff09";
      } else if (cfg.source === "env") {
        extra = "\uff08\u5f53\u524d\u7531\u73af\u5883\u53d8\u91cf\u63d0\u4f9b\uff0c\u4fdd\u5b58\u540e\u5199\u5165\u672c\u5730\u6587\u4ef6\uff09";
      }
      el.className = "text-sm mb-6 px-3 py-2 rounded-lg bg-green-50 text-green-800";
      el.textContent = "\u5df2\u914d\u7f6e \u00b7 \u6765\u6e90\uff1a" + src + extra + (cfg.api_key_masked ? " \u00b7 Key\uff1a" + cfg.api_key_masked : "");
    }

    async function loadConfig() {
      const cfg = await apiGet("/api/tts-config");
      document.getElementById("appid").value = cfg.appid || "";
      const keyInput = document.getElementById("apiKey");
      const secretInput = document.getElementById("apiSecret");
      keyInput.placeholder = cfg.has_api_key ? "\u5df2\u4fdd\u5b58\uff08\u7559\u7a7a\u4e0d\u4fee\u6539\uff09" : "\u8baf\u98de API Key";
      secretInput.placeholder = cfg.has_api_secret ? "\u5df2\u4fdd\u5b58\uff08\u7559\u7a7a\u4e0d\u4fee\u6539\uff09" : "\u8baf\u98de API Secret";
      renderStatus(cfg);
      return cfg;
    }

    loadConfig().catch((e) => {
      document.getElementById("status").textContent = "\u52a0\u8f7d\u5931\u8d25\uff1a" + e.message;
    });

    document.getElementById("saveBtn").addEventListener("click", async () => {
      const msg = document.getElementById("msg");
      msg.textContent = "\u6b63\u5728\u4fdd\u5b58\u2026";
      const appid = document.getElementById("appid").value.trim();
      const api_key = document.getElementById("apiKey").value.trim();
      const api_secret = document.getElementById("apiSecret").value.trim();
      if (!appid) {
        msg.textContent = "\u8bf7\u586b\u5199 APPID\u3002";
        return;
      }
      if (!api_key || !api_secret) {
        const cur = await apiGet("/api/tts-config").catch(() => ({}));
        if (!cur.has_api_key || !cur.has_api_secret) {
          msg.textContent = "\u9996\u6b21\u4fdd\u5b58\u9700\u586b\u5199\u5b8c\u6574\u7684 API Key \u4e0e API Secret\u3002";
          return;
        }
      }
      try {
        const cfg = await apiPost("/api/tts-config", { appid, api_key, api_secret });
        document.getElementById("apiKey").value = "";
        document.getElementById("apiSecret").value = "";
        renderStatus(cfg);
        msg.textContent = "\u5df2\u4fdd\u5b58\u3002";
      } catch (e) {
        msg.textContent = "\u4fdd\u5b58\u5931\u8d25\uff1a" + e.message;
      }
    });

    document.getElementById("testBtn").addEventListener("click", async () => {
      const msg = document.getElementById("msg");
      msg.textContent = "\u6b63\u5728\u5408\u6210\u2026";
      try {
        const res = await fetch("/api/tts?text=" + encodeURIComponent("hello"), { method: "GET" });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.error || ("HTTP " + res.status));
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        await new Audio(url).play();
        URL.revokeObjectURL(url);
        msg.textContent = "\u6d4b\u8bd5\u6210\u529f\uff0c\u5df2\u64ad\u653e\u793a\u4f8b\u53d1\u97f3\u3002";
      } catch (e) {
        msg.textContent = "\u6d4b\u8bd5\u5931\u8d25\uff1a" + e.message;
      }
    });

    document.getElementById("clearBtn").addEventListener("click", async () => {
      if (!confirm("\u786e\u5b9a\u6e05\u9664\u672c\u673a\u4fdd\u5b58\u7684\u8baf\u98de\u51ed\u8bc1\uff1f\uff08\u4e0d\u5f71\u54cd\u73af\u5883\u53d8\u91cf\uff09")) return;
      const msg = document.getElementById("msg");
      try {
        const cfg = await apiPost("/api/tts-config", { clear: true });
        document.getElementById("appid").value = "";
        document.getElementById("apiKey").value = "";
        document.getElementById("apiSecret").value = "";
        renderStatus(cfg);
        msg.textContent = "\u5df2\u6e05\u9664\u672c\u5730\u914d\u7f6e\u3002";
      } catch (e) {
        msg.textContent = "\u6e05\u9664\u5931\u8d25\uff1a" + e.message;
      }
    });
  </script>
</body>
</html>
"""


def main() -> None:
    text = HTML.encode("utf-8").decode("unicode_escape")
    text = text.replace("<motion>", "<div>").replace("</motion>", "</div>")
    text = text.replace("motion", "div")
    OUT.write_text(text, encoding="utf-8", newline="\n")
    sample = OUT.read_text(encoding="utf-8")
    assert "讯飞" in sample, "UTF-8 Chinese missing"
    assert "???" not in sample[:500], "garbled text in header"
    print("wrote", OUT)


if __name__ == "__main__":
    main()
