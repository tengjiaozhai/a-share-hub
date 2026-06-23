# youtube.py
"""
打开 YouTube, page-agent 搜索"latest AI models 2025"并点开第一个视频。
所有 LLM 凭证走环境变量, 脚本里没有任何敏感字面量。
跑之前先做一次 API probe, key 或 model 名错就立刻退出, 不开浏览器。
"""
import asyncio
import json
import os
import sys
import urllib.request
from playwright.async_api import async_playwright

BASE_URL = "https://newapi.tinno.com/v1"
API_KEY  = os.environ["PAGE_AGENT_KEY"]
MODEL    = "qwen3.7-plus"

CDN = (
    "https://cdn.jsdelivr.net/npm/page-agent@1.10.0/"
    "dist/iife/page-agent.demo.js?autoInit=false"
)

TASK = """
You are on YouTube. Do these steps in order:
1. Click the search input at the top of the page.
2. Type exactly: latest AI models 2025
3. Press Enter.
4. Wait for the results page to load.
5. Click the title of the first video result.
6. Wait for the video page to load.
""".strip()


def probe_api() -> None:
    """先用一次最小请求验证 endpoint + key + model, 失败立即退出."""
    if not API_KEY:
        print("[!] LLM_API_KEY 环境变量为空, 退出.", file=sys.stderr)
        sys.exit(2)
    masked = API_KEY[:6] + "..." + API_KEY[-4:]
    print(f"[probe] base = {BASE_URL}")
    print(f"[probe] key  = {masked}  (len={len(API_KEY)})")
    print(f"[probe] model= {MODEL}")

    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read())
        print(f"[probe] OK, model回声 = {resp.get('model', '?')}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        print(f"[!] API 返回 HTTP {e.code}: {detail}", file=sys.stderr)
        if e.code in (401, 403):
            print("    → key 无效或被吊销, 去后台 rotate.", file=sys.stderr)
        elif e.code == 404:
            print(f"    → model 名 '{MODEL}' 不存在. "
                  f"试试 qwen-plus / qwen3-max / qwen2.5-plus.", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"[!] API probe 失败: {e}", file=sys.stderr)
        print("    → 检查网络, 或 baseURL 是否需要加 /v1 后缀.", file=sys.stderr)
        sys.exit(3)


async def main():
    probe_api()

    async with async_playwright() as p:
        # 看得见的浏览器, 慢放, 使用系统 Chrome
        browser = await p.chromium.launch(
            headless=False, 
            slow_mo=300,
            channel="chrome",
            args=["--disable-web-security", "--disable-features=IsolateOrigins,site-per-process"]
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = await ctx.new_page()
        page.on("console",   lambda m: print(f"  [browser:{m.type}] {m.text}"))
        page.on("pageerror", lambda e: print(f"  [browser:ERR] {e}"))

        # 走 init_script: 每次 navigation 前都注入, 避免 CSP 拦截
        await page.add_init_script(f"""
            window.__CFG__ = {{
                baseURL: {BASE_URL!r},
                apiKey:  {API_KEY!r},
                model:   {MODEL!r},
            }};
        """)

        print("[1/5] goto YouTube ...")
        await page.goto("https://www.youtube.com/", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        await page.screenshot(path="01_home.png")

        print("[2/5] inject page-agent (CDN, ?autoInit=false) ...")
        # 在浏览器中下载并注入脚本
        await page.evaluate(f"""
            // 创建 Trusted Types policy
            if (window.trustedTypes && window.trustedTypes.createPolicy) {{
                window.__ttPolicy = window.trustedTypes.createPolicy('default', {{
                    createHTML: (s) => s,
                    createScript: (s) => s,
                    createScriptURL: (s) => s,
                }});
            }}
            
            // 禁用 PageAgent 自动初始化
            window.__PAGE_AGENT_AUTO_INIT__ = false;
        """)
        
        # 通过浏览器 fetch 下载脚本并注入
        await page.evaluate(f"""
            async () => {{
                const resp = await fetch({CDN!r});
                const script = await resp.text();
                const el = document.createElement('script');
                el.textContent = script;
                document.head.appendChild(el);
            }}
        """)
        
        await page.wait_for_function(
            "typeof window.PageAgent === 'function'", timeout=30_000
        )
        print("[3/5] PageAgent ready")

        print("[4/5] agent.execute(task) ... (看着浏览器自己动)")
        result = await page.evaluate(
            """
            async (task) => {
                const cfg = window.__CFG__;
                // 直接创建实例并传入配置
                const agent = new window.PageAgent({
                    baseURL: cfg.baseURL,
                    apiKey:  cfg.apiKey,
                    model:   cfg.model,
                    language: 'en-US',
                });
                try {
                    return { ok: true, value: await agent.execute(task) };
                } catch (e) {
                    return { ok: false, error: String(e) };
                }
            }
            """,
            TASK,
        )

        print("[5/5] done")
        await page.screenshot(path="02_after.png")
        print(f"      final url = {page.url}")
        print(f"      agent result = {result}")
        print("      (浏览器再开 8s, 你看着结果)")
        await asyncio.sleep(8)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())