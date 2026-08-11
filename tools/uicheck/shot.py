"""Screenshot a named view of the dashboard."""
import asyncio, base64, json, subprocess, sys, time
import httpx, websockets
CHROME=("/Users/mayursachdeva/.cache/puppeteer/chrome/mac_arm-150.0.7871.24/"
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
PORT=9340; OUT=sys.argv[1]; NAV=sys.argv[2] if len(sys.argv)>2 else ""
class P:
    def __init__(s,ws): s.ws=ws; s.n=0
    async def send(s,m,**p):
        s.n+=1; await s.ws.send(json.dumps({"id":s.n,"method":m,"params":p}))
        while True:
            msg=json.loads(await s.ws.recv())
            if msg.get("id")==s.n:
                if "error" in msg: raise RuntimeError(msg["error"])
                return msg.get("result",{})
    async def ev(s,e):
        r=await s.send("Runtime.evaluate",expression=e,returnByValue=True)
        return r.get("result",{}).get("value")
async def main():
    c=subprocess.Popen([CHROME,"--headless","--disable-gpu","--no-sandbox","--hide-scrollbars",
        f"--remote-debugging-port={PORT}","--window-size=1250,1500","about:blank"],
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
            if NAV:
                await p.ev("""(()=>{const b=[...document.querySelectorAll('.views button')]
                  .find(x=>x.textContent.trim()===%s); if(b) b.click(); return !!b})()""" % json.dumps(NAV))
                await asyncio.sleep(2.0)
            errs = await p.ev("(()=>{const e=document.querySelector('.error'); return e?e.textContent:''})()")
            if errs: print("PAGE ERROR:", errs)
            h = await p.ev("Math.min(document.body.scrollHeight, 2600)")
            shot=await p.send("Page.captureScreenshot",format="png",
                clip={"x":0,"y":0,"width":1250,"height":h,"scale":1.6}, captureBeyondViewport=True)
            open(OUT,"wb").write(base64.b64decode(shot["data"])); print("saved",OUT,"height",h)
    finally: c.terminate()
asyncio.run(main())
