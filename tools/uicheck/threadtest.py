"""Two turns through the real UI: does the thread hold, and does turn 2 send history?"""
import asyncio, json, subprocess, time
import httpx, websockets
CHROME=("/Users/mayursachdeva/.cache/puppeteer/chrome/mac_arm-150.0.7871.24/"
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
PORT=9350
class P:
    def __init__(s,ws): s.ws=ws; s.n=0
    async def send(s,m,**p):
        s.n+=1; await s.ws.send(json.dumps({"id":s.n,"method":m,"params":p}))
        while True:
            msg=json.loads(await s.ws.recv())
            if msg.get("id")==s.n: return msg.get("result",{})
    async def ev(s,e):
        r=await s.send("Runtime.evaluate",expression=e,returnByValue=True,awaitPromise=True)
        return r.get("result",{}).get("value")
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
            # Record what the page sends, so we can prove turn 2 carried the exchange.
            await p.ev("""(()=>{window.__sent=[]; const f=window.fetch;
              window.fetch=function(u,o){ if(String(u).includes('/ask/stream'))
                window.__sent.push(JSON.parse(o.body)); return f.apply(this,arguments)}; return 1})()""")
            await p.ev("""(()=>{[...document.querySelectorAll('.views button')]
              .find(x=>x.textContent.trim()==='Ask').click()})()""")
            await asyncio.sleep(1.2)

            async def ask(text):
                await p.ev("""(()=>{const i=document.querySelector('.ask-form input');
                  const set=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                  set.call(i,%s); i.dispatchEvent(new Event('input',{bubbles:true}));
                  document.querySelector('.ask-form button').click()})()""" % json.dumps(text))
                for _ in range(420):
                    await asyncio.sleep(1.0)
                    busy = await p.ev("!!document.querySelector('.ask-form button[disabled]')")
                    if not busy: return True
                return False

            ok1 = await ask("What does my chart say about marriage?")
            turns = await p.ev("document.querySelectorAll('.thread .turn').length")
            print(f"  turn 1 finished={ok1}  turns on screen={turns}")
            if turns != 1: problems.append(f"after turn 1 there are {turns} turns")

            ok2 = await ask("yes, do that")
            state = await p.ev("""(()=>({
              turns: document.querySelectorAll('.thread .turn').length,
              asked: [...document.querySelectorAll('.thread .asked')].map(e=>e.textContent),
              answers: document.querySelectorAll('.thread .answer').length,
              sent: window.__sent.map(s=>({q:s.question, hist:(s.history||[]).length})),
              boxEmpty: document.querySelector('.ask-form input').value === ''
            }))()""")
            print(f"  turn 2 finished={ok2}  turns={state['turns']} answers={state['answers']}")
            print(f"  questions kept: {state['asked']}")
            print(f"  requests sent: {state['sent']}")
            print(f"  input cleared after send: {state['boxEmpty']}")
            if state["turns"] != 2: problems.append("thread did not keep both turns")
            if state["answers"] != 2: problems.append("an answer went missing")
            if not state["sent"] or state["sent"][-1]["hist"] != 1:
                problems.append("the follow-up carried no history")
            if not state["boxEmpty"]: problems.append("input not cleared")
    finally: c.terminate()
    print("PROBLEMS:", problems or "none")
asyncio.run(main())
