// PropSec — Seta do agente. Apenas visual: desenha uma seta que desliza até o ponto
// de cada movimento/clique e mostra as rolagens. Não envia nem guarda nenhum dado.
(() => {
  if (window.__propsecSeta) return;
  window.__propsecSeta = true;

  const host = document.createElement("div");
  host.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:2147483647";
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      .seta{position:fixed;left:0;top:0;width:28px;height:28px;transform:translate(-100px,-100px);
        transition:transform .55s cubic-bezier(.3,.7,.2,1);filter:drop-shadow(0 2px 3px rgba(0,0,0,.45))}
      .tag{position:absolute;left:22px;top:22px;font:600 11px system-ui,sans-serif;color:#fff;
        background:#b3366b;border-radius:6px;padding:2px 6px;white-space:nowrap}
      .onda{position:fixed;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;
        border:3px solid #e0699b;animation:onda .6s ease-out forwards}
      @keyframes onda{from{transform:scale(.4);opacity:1}to{transform:scale(3.2);opacity:0}}
      .rola{position:fixed;right:14px;top:50%;font:700 20px system-ui;color:#fff;background:#b3366bcc;
        border-radius:10px;padding:6px 10px;opacity:0;transition:opacity .25s}
    </style>
    <div class="seta"><svg viewBox="0 0 24 24" width="28" height="28">
      <path d="M3 2l7.5 19 2.6-7.8L21 10.6z" fill="#fff" stroke="#1d1b18" stroke-width="1.6" stroke-linejoin="round"/></svg>
      <span class="tag">agente</span></div>
    <div class="rola">↕</div>`;
  const seta = root.querySelector(".seta");
  const rola = root.querySelector(".rola");
  const pronto = () => (document.body || document.documentElement).appendChild(host);
  pronto();
  // O Instagram troca a página sem recarregar; garante que a seta continue lá.
  new MutationObserver(() => { if (!host.isConnected) pronto(); })
    .observe(document.documentElement, { childList: true });

  const mover = (x, y) => { seta.style.transform = `translate(${x - 4}px, ${y - 2}px)`; };
  addEventListener("mousemove", (e) => mover(e.clientX, e.clientY), true);
  addEventListener("mousedown", (e) => {
    mover(e.clientX, e.clientY);
    const o = document.createElement("div");
    o.className = "onda"; o.style.left = e.clientX + "px"; o.style.top = e.clientY + "px";
    root.appendChild(o); setTimeout(() => o.remove(), 700);
  }, true);
  let t;
  addEventListener("scroll", () => {
    rola.style.opacity = 1; clearTimeout(t); t = setTimeout(() => (rola.style.opacity = 0), 600);
  }, true);
})();
