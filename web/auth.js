// Phone sign-in shared by every page: mobile number, 6-digit code, then name and role the first time.
// Firebase sends the SMS when the server has Firebase configured; otherwise Govi sends its own code
// on WhatsApp (and to the simulator). Demo numbers sign in with a fixed code and no SMS.
//   GOVI.auth.me()                         -> the signed-in user, or null
//   GOVI.auth.open({ role, lang, demo })   -> resolves to the user once signed in (null if closed)
//   GOVI.auth.logout()
// Sinhala and Tamil strings need a native speaker's review before the demo.
(() => {
  const FB = "https://www.gstatic.com/firebasejs/10.14.1/";
  const T = {
    en: { title: "Sign in with your mobile number", sub: "We'll send you a 6-digit code. New to Govi? This creates your account.",
      phone: "Mobile number", send: "Send code", code_h: "Enter the code", code_sub: "We sent a 6-digit code to {p}.", code_sim: "This site cannot send SMS yet. Govi staff can read your code from the console.",
      code_wa: "Check WhatsApp for the code.", code_demo: "Demo account: the code is {c}.", verify: "Verify", change: "Change number", resend: "Send a new code",
      prof_h: "Welcome to Govi", prof_sub: "Tell us who you are. You only do this once.", name: "Your name", role: "I am a", farmer: "Farmer", buyer: "Buyer", agent: "Market agent",
      business: "Business name", pin: "Agent PIN (from Govi)", save: "Save", demo: "Or try a demo account", bad_phone: "Enter a valid mobile number.", bad_code: "Enter the 6-digit code.",
      need_name: "Please enter your name.", err: "Something went wrong. Please try again.", close: "Close",
      fb_invalid: "That number does not look right.", fb_many: "Too many tries. Please wait a little and try again.", fb_code: "That code is not right.", fb_expired: "That code has expired. Ask for a new one.", fb_setup: "Phone sign-in is not switched on for this site yet.", fb_net: "We could not reach the SMS service. Check your connection and try again." },
    si: { title: "ජංගම දුරකථන අංකයෙන් පිවිසෙන්න", sub: "අපි ඔබට ඉලක්කම් 6ක කේතයක් එවන්නෙමු. Govi වලට අලුත් නම්, මෙයින් ඔබේ ගිණුම සෑදේ.",
      phone: "ජංගම දුරකථන අංකය", send: "කේතය එවන්න", code_h: "කේතය ඇතුළත් කරන්න", code_sub: "{p} අංකයට ඉලක්කම් 6ක කේතයක් එව්වා.", code_sim: "මෙම අඩවියට තවම SMS යැවිය නොහැක. Govi කාර්ය මණ්ඩලයට කොන්සෝලයෙන් ඔබේ කේතය කියවිය හැක.",
      code_wa: "කේතය සඳහා WhatsApp බලන්න.", code_demo: "ආදර්ශ ගිණුම: කේතය {c}.", verify: "තහවුරු කරන්න", change: "අංකය වෙනස් කරන්න", resend: "නව කේතයක් එවන්න",
      prof_h: "Govi වෙත සාදරයෙන් පිළිගනිමු", prof_sub: "ඔබ කවුදැයි කියන්න. මෙය එක් වරක් පමණි.", name: "ඔබේ නම", role: "මම", farmer: "ගොවියෙක්", buyer: "ගැනුම්කරුවෙක්", agent: "වෙළඳපොළ නියෝජිතයෙක්",
      business: "ව්‍යාපාරයේ නම", pin: "නියෝජිත PIN (Govi වෙතින්)", save: "සුරකින්න", demo: "නැතහොත් ආදර්ශ ගිණුමක් භාවිතා කරන්න", bad_phone: "නිවැරදි ජංගම අංකයක් දාන්න.", bad_code: "ඉලක්කම් 6ක කේතය දාන්න.",
      need_name: "කරුණාකර ඔබේ නම දාන්න.", err: "වැරැද්දක් සිදු විය. නැවත උත්සාහ කරන්න.", close: "වසන්න",
      fb_invalid: "මෙම අංකය නිවැරදි නැති බව පෙනේ.", fb_many: "උත්සාහයන් වැඩියි. ටික වේලාවකින් නැවත උත්සාහ කරන්න.", fb_code: "කේතය වැරදියි.", fb_expired: "කේතය කල් ඉකුත් වී ඇත. නව කේතයක් ඉල්ලන්න.", fb_setup: "මෙම අඩවියට දුරකථන පිවිසුම තවම සක්‍රිය කර නැත.", fb_net: "SMS සේවාවට සම්බන්ධ විය නොහැකි විය. සම්බන්ධතාවය පරීක්ෂා කර නැවත උත්සාහ කරන්න." },
    ta: { title: "உங்கள் மொபைல் எண்ணுடன் உள்நுழையுங்கள்", sub: "6 இலக்கக் குறியீட்டை அனுப்புவோம். Govi க்குப் புதியவரா? இது உங்கள் கணக்கை உருவாக்கும்.",
      phone: "மொபைல் எண்", send: "குறியீட்டை அனுப்பு", code_h: "குறியீட்டை உள்ளிடுங்கள்", code_sub: "{p} க்கு 6 இலக்கக் குறியீடு அனுப்பினோம்.", code_sim: "இந்தத் தளம் இன்னும் SMS அனுப்ப முடியாது. Govi ஊழியர்கள் கன்சோலில் உங்கள் குறியீட்டைப் பார்க்கலாம்.",
      code_wa: "குறியீட்டுக்கு WhatsApp ஐப் பாருங்கள்.", code_demo: "மாதிரிக் கணக்கு: குறியீடு {c}.", verify: "சரிபார்", change: "எண்ணை மாற்று", resend: "புதிய குறியீடு அனுப்பு",
      prof_h: "Govi க்கு வரவேற்கிறோம்", prof_sub: "நீங்கள் யார் என்று சொல்லுங்கள். ஒருமுறை மட்டுமே.", name: "உங்கள் பெயர்", role: "நான்", farmer: "விவசாயி", buyer: "வாங்குபவர்", agent: "சந்தை முகவர்",
      business: "வணிகத்தின் பெயர்", pin: "முகவர் PIN (Govi இடமிருந்து)", save: "சேமி", demo: "அல்லது மாதிரிக் கணக்கைப் பயன்படுத்துங்கள்", bad_phone: "சரியான மொபைல் எண்ணை உள்ளிடுங்கள்.", bad_code: "6 இலக்கக் குறியீட்டை உள்ளிடுங்கள்.",
      need_name: "உங்கள் பெயரை உள்ளிடுங்கள்.", err: "ஏதோ தவறு. மீண்டும் முயற்சிக்கவும்.", close: "மூடு",
      fb_invalid: "இந்த எண் சரியாகத் தெரியவில்லை.", fb_many: "அதிக முயற்சிகள். சிறிது நேரம் கழித்து முயற்சிக்கவும்.", fb_code: "குறியீடு தவறு.", fb_expired: "குறியீடு காலாவதியானது. புதியதைக் கேளுங்கள்.", fb_setup: "இந்தத் தளத்தில் தொலைபேசி உள்நுழைவு இன்னும் இயக்கப்படவில்லை.", fb_net: "SMS சேவையை அடைய முடியவில்லை. இணைப்பைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்." },
  };
  const FB_ERR = { "auth/invalid-phone-number": "fb_invalid", "auth/too-many-requests": "fb_many", "auth/quota-exceeded": "fb_many",
    "auth/invalid-verification-code": "fb_code", "auth/code-expired": "fb_expired", "auth/operation-not-allowed": "fb_setup",
    "auth/captcha-check-failed": "fb_setup", "auth/unauthorized-domain": "fb_setup",
    "auth/network-request-failed": "fb_net", "auth/internal-error": "fb_net" };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // Same rules as the server: 0771234567 or 771234567 -> 94771234567.
  const norm = (raw) => { let d = String(raw || "").replace(/\D/g, ""); if (d.length === 10 && d[0] === "0") d = "94" + d.slice(1); if (d.length === 9 && d[0] === "7") d = "94" + d; return d.length >= 9 && d.length <= 15 ? d : ""; };
  const pretty = (d) => d.startsWith("94") && d.length === 11 ? `+94 ${d.slice(2, 4)} ${d.slice(4, 7)} ${d.slice(7)}` : "+" + d;

  let cfg = null, mePromise = null, fbAuth = null, verifier = null, confirmation = null;
  const config = () => (cfg ||= fetch("/api/auth/config").then((r) => r.json()).catch(() => ({ provider: "govi", demo: [] })));

  async function post(path, body, method = "POST") {
    const r = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : r.statusText);
    return d;
  }
  function me(refresh) {
    if (refresh || !mePromise) mePromise = fetch("/api/me").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    return mePromise;
  }
  const load = (src) => new Promise((ok, bad) => { const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = bad; document.head.appendChild(s); });
  async function firebaseAuth(c) {
    if (!fbAuth) {
      try { await load(FB + "firebase-app-compat.js"); await load(FB + "firebase-auth-compat.js"); }
      catch { throw Object.assign(new Error("sdk"), { code: "auth/network-request-failed" }); }
      firebase.initializeApp(c.firebase); fbAuth = firebase.auth();
    }
    return fbAuth;
  }

  // ---- the sheet
  let root, opts, done, step, phone = "", sentVia = "", demoCode = "";
  const t = (k, o = {}) => ((T[opts.lang] || T.en)[k] ?? T.en[k]).replace(/\{(\w+)\}/g, (_, x) => o[x] ?? "");
  function mount() {
    if (root) return;
    root = document.createElement("div");
    root.className = "auth-scrim"; root.hidden = true;
    root.innerHTML = `<div class="auth-sheet card" role="dialog" aria-modal="true" aria-labelledby="auth-h"><button type="button" class="auth-x">×</button><div class="auth-body"></div><div id="auth-captcha"></div></div>`;
    document.body.appendChild(root);
    root.onclick = (e) => { if (e.target === root) close(null); };
    root.querySelector(".auth-x").onclick = () => close(null);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !root.hidden) close(null); });
  }
  function close(user) { root.hidden = true; document.body.style.overflow = ""; const d = done; done = null; d && d(user); }
  const body = () => root.querySelector(".auth-body");
  const $ = (id) => root.querySelector("#" + id);
  function err(msg) { const e = $("a-err"); e.hidden = !msg; e.textContent = msg ? "⚠ " + msg : ""; }
  function busy(id, on, label) { const b = $(id); b.disabled = on; b.textContent = on ? "…" : label; }

  async function render() {
    const c = await config();
    root.querySelector(".auth-x").setAttribute("aria-label", t("close"));
    if (step === "phone") {
      const demos = (c.demo || []).filter((d) => !opts.role || !d.role || d.role === opts.role);
      body().innerHTML = `<h2 id="auth-h">${t("title")}</h2><p class="muted">${t("sub")}</p>
        <label class="auth-f"><span>${t("phone")}</span><input type="tel" id="a-phone" inputmode="tel" autocomplete="tel" placeholder="077 123 4567" value="${esc(phone && "0" + phone.slice(2))}"></label>
        <div class="auth-err" id="a-err" hidden></div>
        <button type="button" class="btn primary auth-go" id="a-send">${t("send")}</button>
        ${demos.length && opts.demo !== false ? `<div class="auth-demo"><span>${t("demo")}</span>${demos.map((d) => `<button type="button" class="btn" data-demo="${d.phone}" data-code="${esc(d.code)}">${esc(d.name || pretty(d.phone))}${d.role ? ` · ${t(d.role)}` : ""}</button>`).join("")}</div>` : ""}`;
      $("a-phone").onkeydown = (e) => { if (e.key === "Enter") $("a-send").click(); };
      $("a-send").onclick = () => sendCode(c);
      body().querySelectorAll("[data-demo]").forEach((b) => (b.onclick = () => { phone = b.dataset.demo; finish(c, { phone, code: b.dataset.code }); }));
      setTimeout(() => $("a-phone")?.focus(), 50);
    } else if (step === "code") {
      const note = demoCode ? t("code_demo", { c: demoCode }) : sentVia === "console" ? t("code_sim") : sentVia === "whatsapp" ? t("code_wa") : "";
      body().innerHTML = `<h2 id="auth-h">${t("code_h")}</h2><p class="muted">${t("code_sub", { p: pretty(phone) })}${note ? "<br>" + esc(note) : ""}</p>
        <input type="text" id="a-code" class="auth-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]*" aria-label="${t("code_h")}">
        <div class="auth-err" id="a-err" hidden></div>
        <button type="button" class="btn primary auth-go" id="a-verify">${t("verify")}</button>
        <div class="auth-links"><a href="#" id="a-change">${t("change")}</a><a href="#" id="a-resend">${t("resend")}</a></div>`;
      $("a-code").oninput = () => { $("a-code").value = $("a-code").value.replace(/\D/g, ""); if ($("a-code").value.length === 6) $("a-verify").click(); };
      $("a-verify").onclick = () => {
        const code = $("a-code").value;
        if (code.length !== 6) return err(t("bad_code"));
        finish(c, { code });
      };
      $("a-change").onclick = (e) => { e.preventDefault(); step = "phone"; render(); };
      $("a-resend").onclick = (e) => { e.preventDefault(); sendCode(c); };
      setTimeout(() => $("a-code")?.focus(), 50);
    } else if (step === "profile") {
      const u = opts.user || {};
      const role = u.role || opts.role || "farmer";
      body().innerHTML = `<h2 id="auth-h">${t("prof_h")}</h2><p class="muted">${t("prof_sub")}</p>
        <label class="auth-f"><span>${t("name")}</span><input type="text" id="a-name" autocomplete="name" value="${esc(u.name || "")}"></label>
        <div class="auth-f"><span>${t("role")}</span><div class="auth-roles" id="a-roles">${["farmer", "buyer", "agent"].map((r) => `<button type="button" data-r="${r}" class="${r === role ? "on" : ""}">${t(r)}</button>`).join("")}</div></div>
        <label class="auth-f" id="a-biz-row"><span>${t("business")}</span><input type="text" id="a-biz" value="${esc(u.business || "")}"></label>
        <label class="auth-f" id="a-pin-row"><span>${t("pin")}</span><input type="password" id="a-pin" inputmode="numeric" autocomplete="off"></label>
        <div class="auth-err" id="a-err" hidden></div>
        <button type="button" class="btn primary auth-go" id="a-save">${t("save")}</button>`;
      let pick = role;
      const show = () => {
        root.querySelectorAll("#a-roles button").forEach((b) => b.classList.toggle("on", b.dataset.r === pick));
        $("a-biz-row").hidden = pick !== "buyer"; $("a-pin-row").hidden = pick !== "agent";
      };
      root.querySelectorAll("#a-roles button").forEach((b) => (b.onclick = () => { pick = b.dataset.r; show(); }));
      show();
      $("a-save").onclick = async () => {
        const name = $("a-name").value.trim();
        if (!name) return err(t("need_name"));
        busy("a-save", true, t("save"));
        try {
          const data = { name, role: pick, lang: opts.lang };
          if (pick === "buyer") data.business = $("a-biz").value.trim() || name;
          if (pick === "agent") data.agent_pin = $("a-pin").value;
          const user = await post("/api/me", data, "PUT");
          mePromise = Promise.resolve(user); close(user);
        } catch (e) { err(e.message); busy("a-save", false, t("save")); }
      };
      setTimeout(() => $("a-name")?.focus(), 50);
    }
  }

  async function sendCode(c) {
    const p = norm($("a-phone") ? $("a-phone").value : "0" + phone.slice(2));
    if (!p) return err(t("bad_phone"));
    phone = p; demoCode = ""; sentVia = "";
    if ($("a-send")) busy("a-send", true, t("send"));
    try {
      const demo = (c.demo || []).find((d) => d.phone === p);
      if (demo) demoCode = demo.code;
      else if (c.provider === "firebase") {
        const auth = await firebaseAuth(c);
        auth.languageCode = opts.lang;
        if (!verifier) verifier = new firebase.auth.RecaptchaVerifier(root.querySelector("#auth-captcha"), { size: "invisible" });
        confirmation = await auth.signInWithPhoneNumber("+" + p, verifier);
        sentVia = "sms";
      } else {
        sentVia = (await post("/api/auth/start", { phone: p })).channel;
      }
      step = "code"; render();
    } catch (e) {
      if (verifier) { try { verifier.clear(); } catch {} verifier = null; root.querySelector("#auth-captcha").innerHTML = ""; }
      err(FB_ERR[e.code] ? t(FB_ERR[e.code]) : e.message || t("err"));
      if ($("a-send")) busy("a-send", false, t("send"));
    }
  }

  async function finish(c, { code }) {
    if ($("a-verify")) busy("a-verify", true, t("verify"));
    try {
      let out;
      if (c.provider === "firebase" && !demoCode && !(c.demo || []).some((d) => d.phone === phone)) {
        const cred = await confirmation.confirm(code);
        out = await post("/api/auth/verify", { id_token: await cred.user.getIdToken() });
        fbAuth.signOut().catch(() => {});  // the Govi session cookie is what counts from here
      } else {
        out = await post("/api/auth/verify", { phone, code });
      }
      const need = out.new || (opts.role === "buyer" && out.user.role === "buyer" && !out.user.business);
      if (need) { opts.user = out.user; step = "profile"; return render(); }
      mePromise = Promise.resolve(out.user);
      close(out.user);
    } catch (e) {
      err(FB_ERR[e.code] ? t(FB_ERR[e.code]) : e.message || t("err"));
      if ($("a-verify")) busy("a-verify", false, t("verify"));
    }
  }

  function open(o = {}) {
    mount();
    opts = { lang: o.lang || (document.documentElement.lang in T ? document.documentElement.lang : "en"), role: o.role, demo: o.demo, user: o.user || null };
    step = o.user ? "profile" : "phone"; phone = o.phone ? norm(o.phone) : phone;
    root.hidden = false; document.body.style.overflow = "hidden";
    render();
    return new Promise((ok) => { done = ok; });
  }
  // Ask for the missing profile only (e.g. a WhatsApp farmer opening the business portal).
  const profile = (user, o = {}) => open({ ...o, user });
  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    mePromise = Promise.resolve(null);
  }

  // common.js declares GOVI with const, which is not a window property.
  (typeof GOVI !== "undefined" ? GOVI : (window.GOVI ||= {})).auth = { me, open, profile, logout, config, norm, pretty };
})();
