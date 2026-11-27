// Lab 7: 공격 질문을 하나씩 대상 API(/ask, 가드레일 경로)로 보내 보기
C.tab("공격 테스트", (p) => {
  const list = C.el("div", { class: "row" });
  const out = C.el("div");
  C.dev("/attacks").then((items) => items.forEach((it) => {
    const b = C.el("button", { text: it.id, title: it.q.slice(0, 80), onclick: () => C.busy(b, out, async () => {
      const x = await C.api("/ask", { q: it.q });
      const raw = typeof x.body === "string" ? x.body : (x.body.answer || x.body.detail || x.body);
      const ans = typeof raw === "string" ? raw : C.json(raw);     // 422 의 detail 은 배열이라 JSON 글자로 보여 줍니다
      out.replaceChildren(
        C.el("div", { class: "muted", text: `${it.id} · 기대 결과: ${it.expect}` }),
        C.el("pre", { text: it.q.length > 300 ? it.q.slice(0, 300) + ` … (총 ${it.q.length}자)` : it.q }),
        C.el("div", { class: x.status === 400 ? "ok" : "", text: `HTTP ${x.status}` }),
        C.el("pre", { text: ans }));
    }) });
    list.append(b);
  })).catch((e) => { out.textContent = "⚠ " + e.message; });
  p.append(C.el("h3", { text: "공격 테스트 (Lab 7)" }),
    C.el("div", { class: "muted", text: "자동 채점은 '평가' 탭에서 합니다. 여기서는 응답을 하나씩 눈으로 봅니다." }), list, out);
});
