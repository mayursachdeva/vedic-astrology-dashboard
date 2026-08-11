"""Walk the stepper with real pointer clicks: does it advance, and does the lock hold?"""
import asyncio, json, subprocess, time
import httpx, websockets
CHROME=("/Users/mayursachdeva/.cache/puppeteer/chrome/mac_arm-150.0.7871.24/"
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
PORT=9348
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
    async def click(s, selector, index=0):
        box = await s.ev("""(()=>{const e=document.querySelectorAll(%s)[%d];
          if(!e) return null; e.scrollIntoView({block:'center'});
          const r=e.getBoundingClientRect();
          return {x:r.x+r.width/2, y:r.y+r.height/2}})()""" % (json.dumps(selector), index))
        if not box: return False
        for ev in ("mousePressed","mouseReleased"):
            await s.send("Input.dispatchMouseEvent", type=ev, x=box["x"], y=box["y"],
                         button="left", clickCount=1)
        await asyncio.sleep(0.7)
        return True
async def main():
    c=subprocess.Popen([CHROME,"--headless","--disable-gpu","--no-sandbox",
        f"--remote-debugging-port={PORT}","--window-size=1400,1000","about:blank"],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    problems=[]
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
            await p.click(".kundli .house-hit", 9)
            await asyncio.sleep(2.2)

            locked = await p.ev("document.querySelectorAll('.steps button.locked').length")
            print(f"  on opening: {locked} of 5 steps locked (expect 3)")
            if locked != 3: problems.append(f"locked={locked}")

            # A locked step must not move you.
            await p.click(".steps button", 4)
            here = await p.ev("(document.querySelector('.steps button.here')||{}).textContent")
            print(f"  clicking the last step while locked -> still on {here!r}")
            if "What it is" not in (here or ""): problems.append("lock did not hold")

            # Walk forward with the primary button.
            seen=[]
            for _ in range(5):
                here = await p.ev("(document.querySelector('.steps button.here')||{}).textContent")
                seen.append((here or "")[1:])
                done = await p.ev("""(()=>{const b=document.querySelector('.step-nav .primary');
                  return b ? /Done/.test(b.textContent) : true})()""")
                if done: break
                await p.click(".step-nav .primary")
            print("  walked:", " -> ".join(seen))
            if len(seen) != 5: problems.append(f"walked {len(seen)} steps")

            still = await p.ev("document.querySelectorAll('.steps button.locked').length")
            print(f"  after walking: {still} locked (expect 0)")
            if still: problems.append(f"still locked {still}")

            # Going back must not re-lock what was read.
            await p.click(".steps button", 0)
            back = await p.ev("""(()=>({here:(document.querySelector('.steps button.here')||{}).textContent,
              locked:document.querySelectorAll('.steps button.locked').length}))()""")
            print(f"  jumped back to {back['here']!r}, locked now {back['locked']}")
            if back["locked"]: problems.append("re-locked after going back")

            # And Done closes it.
            await p.click(".steps button", 4)
            await p.click(".step-nav .primary")
            gone = await p.ev("!document.querySelector('.house-reading')")
            print(f"  Done closed the reading: {gone}")
            if not gone: problems.append("Done did not close")
    finally: c.terminate()
    print("PROBLEMS:", problems or "none")
asyncio.run(main())
