import asyncio, json, subprocess, time, sys
import httpx, websockets
CHROME=("/Users/mayursachdeva/.cache/puppeteer/chrome/mac_arm-150.0.7871.24/"
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
PORT=9347
class P:
    def __init__(s,ws): s.ws=ws; s.n=0
    async def send(s,m,**p):
        s.n+=1; await s.ws.send(json.dumps({"id":s.n,"method":m,"params":p}))
        while True:
            msg=json.loads(await s.ws.recv())
            if msg.get("id")==s.n: return msg.get("result",{})
    async def ev(s,e):
        r=await s.send("Runtime.evaluate",expression=e,returnByValue=True)
        return r.get("result",{}).get("value")
async def main():
    c=subprocess.Popen([CHROME,"--headless","--disable-gpu","--no-sandbox",
        f"--remote-debugging-port={PORT}","--window-size=1400,1000","about:blank"],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        t=None
        for _ in range(60):
            try:
                t=next((x for x in httpx.get(f"http://127.0.0.1:{PORT}/json",timeout=2).json() if x["type"]=="page"),None)
                if t: break
            except Exception: pass
            time.sleep(0.5)
        async with websockets.connect(t["webSocketDebuggerUrl"],max_size=60*1024*1024) as ws:
            p=P(ws); await p.send("Page.enable"); await p.send("Runtime.enable")
            await p.send("Page.navigate",url="http://localhost:5173/")
            for _ in range(120):
                if await p.ev("!!document.querySelector('.views button')"): break
                await asyncio.sleep(0.5)
            await asyncio.sleep(2.5)
            await p.ev("""(()=>{[...document.querySelectorAll('.views button')]
              .find(x=>x.textContent.trim()==='The chart itself').click()})()""")
            await asyncio.sleep(1.5)
            for h in (1,10,11):
                await p.ev(f"document.querySelectorAll('.kundli .house-hit')[{h-1}].dispatchEvent(new MouseEvent('click',{{bubbles:true}}))")
                await asyncio.sleep(2.2)
                steps = await p.ev("document.querySelectorAll('.steps button').length")
                print(f"  house {h:2}: {steps} steps")
                for i in range(steps or 0):
                    m = await p.ev("""(()=>{
                      return {page: Math.round(document.body.scrollHeight),
                              screens: +(document.body.scrollHeight/window.innerHeight).toFixed(2),
                              words: document.querySelector('main').innerText.trim().split(/\\s+/).length,
                              step: (document.querySelector('.steps button.here')||{}).textContent}})()""")
                    print(f"      step {i+1} {str(m['step'])[:24]:26} page {m['page']}px "
                          f"({m['screens']} screens) {m['words']} words")
                    await p.ev("""(()=>{const b=document.querySelector('.step-nav .primary');
                      if(b && !/Done/.test(b.textContent)) b.click()})()""")
                    await asyncio.sleep(0.6)
    finally: c.terminate()
asyncio.run(main())
