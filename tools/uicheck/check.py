"""Visit every view, report console errors and whether it rendered anything."""
import asyncio, json, subprocess, sys, time
import httpx, websockets
CHROME=("/Users/mayursachdeva/.cache/puppeteer/chrome/mac_arm-150.0.7871.24/"
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
PORT=9341
VIEWS=["Overview","Career","Relationships","Health","Finance","Family","Learning",
       "The years ahead","The chart itself","Ask"]
WIDTHS=[1250, 760]
class P:
    def __init__(s,ws): s.ws=ws; s.n=0; s.errors=[]
    async def send(s,m,**p):
        s.n+=1; await s.ws.send(json.dumps({"id":s.n,"method":m,"params":p}))
        while True:
            msg=json.loads(await s.ws.recv())
            if msg.get("method")=="Runtime.consoleAPICalled" and msg["params"]["type"]=="error":
                s.errors.append(str(msg["params"]["args"])[:200])
            if msg.get("method")=="Runtime.exceptionThrown":
                s.errors.append(str(msg["params"])[:200])
            if msg.get("id")==s.n:
                if "error" in msg: raise RuntimeError(msg["error"])
                return msg.get("result",{})
    async def ev(s,e):
        r=await s.send("Runtime.evaluate",expression=e,returnByValue=True)
        return r.get("result",{}).get("value")
async def main():
    c=subprocess.Popen([CHROME,"--headless","--disable-gpu","--no-sandbox","--hide-scrollbars",
        f"--remote-debugging-port={PORT}","--window-size=1250,1000","about:blank"],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        t=None
        for _ in range(60):
            try:
                t=next((x for x in httpx.get(f"http://127.0.0.1:{PORT}/json",timeout=2).json() if x["type"]=="page"),None)
                if t: break
            except Exception: pass
            time.sleep(0.5)
        async with websockets.connect(t["webSocketDebuggerUrl"],max_size=80*1024*1024) as ws:
            p=P(ws); await p.send("Page.enable"); await p.send("Runtime.enable")
            await p.send("Page.navigate",url="http://localhost:5173/")
            for _ in range(180):
                if await p.ev("!!document.querySelector('.views button')"): break
                await asyncio.sleep(0.5)
            await asyncio.sleep(2.5)
            for width in WIDTHS:
                await p.send("Emulation.setDeviceMetricsOverride", width=width, height=1000,
                             deviceScaleFactor=1, mobile=False)
                print(f"=== width {width}")
                for name in VIEWS:
                    before=len(p.errors)
                    ok = await p.ev("""(()=>{const b=[...document.querySelectorAll('.views button')]
                      .find(x=>x.textContent.trim()===%s); if(!b) return 'no nav'; b.click(); return 'ok'})()""" % json.dumps(name))
                    await asyncio.sleep(1.2)
                    info = await p.ev("""(()=>{const m=document.querySelector('main');
                      const overflow = document.documentElement.scrollWidth > window.innerWidth + 1;
                      return {chars:(m?m.innerText:'').trim().length, panels:document.querySelectorAll('.panel').length,
                              err:!!document.querySelector('.error'), overflow}})()""")
                    new=p.errors[before:]
                    flag = "OK " if info["chars"]>120 and not info["err"] and not new and not info["overflow"] else "!! "
                    print(f"  {flag}{name:18} chars={info['chars']:5} panels={info['panels']:2} "
                          f"overflow={info['overflow']} err={info['err']} console={len(new)}")
                    for e in new[:2]: print("       ", e)
    finally: c.terminate()
asyncio.run(main())
