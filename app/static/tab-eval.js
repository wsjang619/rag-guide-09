// Lab 6 · 7: 평가 실행과 버전 비교  (= python -m eval.run_eval · python -m eval.compare v1 v2)
C.tab("평가", (p) => {
  const ver = C.el("input", { type: "text", value: "v1", style: "width:100px" });
  const a = C.el("input", { type: "text", value: "v1", style: "width:80px" });
  const b = C.el("input", { type: "text", value: "v2", style: "width:80px" });
  const out = C.el("div");
  const run = C.el("button", { text: "평가 실행", onclick: () => C.busy(run, out, async () => {
    out.replaceChildren(...C.runView(await C.dev("/run", { name: "run_eval", prompt_version: ver.value })));
  }) });
  const res = C.el("button", { text: "결과 표", onclick: () => C.busy(res, out, async () => {
    // eval/results/<버전>.json 은 { questions: [...], attacks: [...] } 구조입니다
    const r = await C.dev("/results/" + encodeURIComponent(ver.value));
    const q = r.questions || [];
    const pass = q.filter((x) => x.pass).length;
    // 행마다 열을 맞줍니다: 규정에 없음(none) 문항에는 cited · src · must 가 없고, forbidden=false 는 좋은 상태라 빨강으로 칠하지 않습니다
    const rows = q.map((x) => ({ id: x.id, 통과: x.pass, 출처표시: x.cited ?? "-", 근거문서: x.src ?? "-", 핵심어: x.must ?? "-",
                                 금지답변: x.forbidden ? "있음" : "없음" }));
    const parts = [C.el("div", { class: pass === q.length ? "ok" : "muted", text: `${ver.value}: 질문 통과 ${pass}/${q.length}` }), C.table(rows)];
    if ((r.attacks || []).length) {
      const ap = r.attacks.filter((x) => x.pass).length;
      const arows = r.attacks.map((x) => ({ id: x.id, 통과: x.pass, 상태코드: x.status }));
      parts.push(C.el("div", { class: ap === r.attacks.length ? "ok" : "bad", text: `공격 방어 ${ap}/${r.attacks.length}` }), C.table(arows));
    }
    out.replaceChildren(...parts);
  }) });
  const cmp = C.el("button", { text: "문항별 비교", onclick: () => C.busy(cmp, out, async () => {
    out.replaceChildren(...C.runView(await C.dev("/run", { name: "compare", args: [a.value, b.value] })));
  }) });
  p.append(C.el("h3", { text: "평가 (Lab 6 · 7 · 12)" }),
    C.el("div", { class: "row" }, "PROMPT_VERSION", ver, run, res),
    C.el("div", { class: "row" }, a, "vs", b, cmp),
    C.el("div", { class: "muted", text: "평가 1회 = Bedrock 호출 수십 번 (수 분 · 비용 발생). 끝날 때까지 기다리세요." }), out);
});
