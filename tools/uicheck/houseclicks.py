"""Real pointer clicks on all twelve houses, in every place a chart is shown."""
import asyncio, json, subprocess, time
import httpx, websockets
CHROME=("/Users/mayursachdeva/.cache/puppeteer/chrome/mac_arm-150.0.7871.24/"
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
PORT=9344
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
    async def click_house(s, n):
        box = await s.ev("""(()=>{const c=document.querySelectorAll('.kundli .house-hit')[%d];
          if(!c) return null; const r=c.getBoundingClientRect();
          return {x:r.x+r.width/2, y:r.y+r.height/2}})()""" % (n-1))
        if not box: return False
        for ev in ("mousePressed","mouseReleased"):
            await s.send("Input.dispatchMouseEvent", type=ev, x=box["x"], y=box["y"],
                         button="left", clickCount=1)
        return True
    async def nav(s, label):
        await s.ev("""(()=>{const b=[...document.querySelectorAll('.views button')]
          .find(x=>x.textContent.trim()===%s); if(b) b.click()})()""" % json.dumps(label))
        await asyncio.sleep(1.2)
async def main():
    c=subprocess.Popen([CHROME,"--headless","--disable-gpu","--no-sandbox",
        f"--remote-debugging-port={PORT}","--window-size=1400,1100","about:blank"],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    bad=[]
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

            # 1. every house from the overview chart
            for h in range(1,13):
                await p.nav("Overview")
                if not await p.click_house(h): bad.append(("Overview", h, "no hit area")); continue
                await asyncio.sleep(2.0)
                title = await p.ev("""(()=>{const e=document.querySelector('.house-reading .panel-head h3');
                  return e?e.textContent:''})()""")
                if f"House {h} " not in title: bad.append(("Overview", h, title))
            print(f"Overview  -> {12-len([b for b in bad if b[0]=='Overview'])}/12 opened")

            # 2. every house in both charts on the technical view
            for tab, label in (("D1","Birth"), ("D9","Navamsa")):
                await p.nav("The chart itself")
                await p.ev("""(()=>{const b=[...document.querySelectorAll('.tabs button')]
                  .find(x=>x.textContent.trim()===%s); if(b) b.click()})()""" % json.dumps(label))
                await asyncio.sleep(0.8)
                ok=0
                for h in range(1,13):
                    if not await p.click_house(h): bad.append((tab,h,"no hit area")); continue
                    await asyncio.sleep(1.6)
                    title = await p.ev("""(()=>{const e=document.querySelector('.house-reading .panel-head h3');
                      return e?e.textContent:''})()""")
                    if f"House {h} " in title or f"house {h} " in title.lower(): ok+=1
                    else: bad.append((tab,h,title))
                print(f"{tab:9} -> {ok}/12 opened")
    finally: c.terminate()
    print("FAILURES:", bad if bad else "none")
asyncio.run(main())
