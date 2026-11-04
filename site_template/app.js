(function () {
  var D = window.JOBS_DATA;
  var $ = function (id) { return document.getElementById(id); };
  if (!D) {
    $("count").textContent = "Job data failed to load.";
    return;
  }

  // Category labels are plain text for a minimal look.

  // Last word of the title in orange, e.g. "Launchpad <Listings>".
  var words = D.title.split(" ");
  var last = words.pop();
  $("site-title").textContent = words.length ? words.join(" ") + " " : "";
  var acc = document.createElement("span");
  acc.className = "title-accent";
  acc.textContent = last;
  $("site-title").appendChild(acc);
  document.title = D.title;
  if (D.tagline) $("tagline").textContent = D.tagline;
  $("updated").textContent = D.updated;
  $("updated").setAttribute("datetime", D.updated_iso);
  $("stat-total").textContent = D.jobs.length;
  $("stat-new").textContent = D.jobs.filter(function (j) { return j.is_new; }).length;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function countBy(key) {
    var c = {};
    D.jobs.forEach(function (j) { c[j[key]] = (c[j[key]] || 0) + 1; });
    return c;
  }

  // Single-select chip row (category). "All" is the empty value.
  var state = { category: "", area: "", posted: "" };

  // How long ago a job was posted, in days (first seen if no post date).
  var updatedDay = new Date(D.updated_iso);
  D.jobs.forEach(function (j) {
    var d = j.posted || j.first_seen;
    j._age = d ? Math.max(0, Math.round((updatedDay - new Date(d + "T12:00:00")) / 864e5)) : 0;
    j._posted = j.is_new ? ["today", "week", "month"] : j._age <= 7 ? ["week", "month"] : j._age <= 30 ? ["month"] : ["older"];
  });
  var POSTED = ["today", "week", "month", "older"];
  var POSTED_LABELS = { today: "New today", week: "Past week", month: "Past month", older: "Older" };
  function postedCounts(list) {
    var c = {};
    list.forEach(function (j) { j._posted.forEach(function (k) { c[k] = (c[k] || 0) + 1; }); });
    return c;
  }
  function chipRow(id, values, counts, labels) {
    var box = $(id);
    var all = [""].concat(values.filter(function (v) { return counts[v]; }));
    all.forEach(function (v) {
      var b = el("button", "chip");
      b.type = "button";
      b.setAttribute("role", "radio");
      b.dataset.value = v;
      b.appendChild(document.createTextNode(v ? (labels[v] || v) : "All"));
      if (v) b.appendChild(el("span", "n", String(counts[v])));
      b.addEventListener("click", function () {
        state[id] = v;
        syncChips(id);
        render();
      });
      box.appendChild(b);
    });
  }
  function syncChips(id) {
    Array.prototype.forEach.call($(id).children, function (b) {
      b.setAttribute("aria-checked", String(b.dataset.value === state[id]));
    });
  }
  chipRow("posted", POSTED, postedCounts(D.jobs), POSTED_LABELS);
  chipRow("category", D.categories, countBy("category"), {});
  // Location is a grouped dropdown: a state group (California), its regions
  // (Northern California...), their areas (East Bay...), then other states.
  // Values: "a:<area>", "r:<region key>", "g:<group>".
  var REGIONS = D.regions || [];
  var regionByKey = {};
  REGIONS.forEach(function (r) { regionByKey[r.key] = r; });
  function inArea(j, v) {
    var kind = v.slice(0, 2), name = v.slice(2);
    if (kind === "a:") return j.area === name;
    if (kind === "r:") return j.region === name;
    if (kind === "g:") {
      var r = regionByKey[j.region];
      return r ? r.group === name : j.region === "us_state" && j.area === name;
    }
    return true;
  }
  var areaCounts = countBy("area");
  function addOption(parent, value, label, depth) {
    var o = el("option", null, label);
    o.value = value;
    o.dataset.name = "   ".repeat(depth) + label;
    parent.appendChild(o);
  }
  if (areaCounts["Remote (US)"]) addOption($("area"), "a:Remote (US)", "Remote (US)", 0);
  var groups = [];
  REGIONS.forEach(function (r) { if (groups.indexOf(r.group) === -1) groups.push(r.group); });
  groups.forEach(function (g) {
    var og = document.createElement("optgroup");
    og.label = g;
    addOption(og, "g:" + g, "All of " + g, 0);
    REGIONS.filter(function (r) { return r.group === g; }).forEach(function (r) {
      if (REGIONS.filter(function (x) { return x.group === g; }).length > 1) addOption(og, "r:" + r.key, r.label, 1);
      r.areas.forEach(function (a) { if (areaCounts[a]) addOption(og, "a:" + a, a, 2); });
    });
    if (areaCounts[g]) addOption(og, "a:" + g, "Elsewhere in " + g, 1);
    $("area").appendChild(og);
  });
  var states = D.areas.filter(function (a) {
    return areaCounts[a] && a !== "Remote (US)" && groups.indexOf(a) === -1 &&
      !REGIONS.some(function (r) { return r.areas.indexOf(a) !== -1; });
  });
  if (states.length) {
    var og2 = document.createElement("optgroup");
    og2.label = groups.length ? "Other states" : "States";
    states.forEach(function (a) { addOption(og2, "a:" + a, a, 0); });
    $("area").appendChild(og2);
  }
  $("area").addEventListener("change", function () {
    state.area = $("area").value;
    render();
  });

  D.search_links.forEach(function (l) {
    var a = el("a", null, l.name + " ↗");
    a.href = l.url; a.target = "_blank"; a.rel = "noopener nofollow";
    $("links").appendChild(a);
  });

  D.jobs.forEach(function (j) {
    j._text = [j.title, j.company, j.summary, j.location, j.category].join(" ").toLowerCase();
  });

  var today = new Date(D.updated_iso);
  function ago(iso) {
    if (!iso) return "";
    var days = Math.round((today - new Date(iso + "T12:00:00")) / 864e5);
    if (days <= 0) return "Posted today";
    if (days === 1) return "Posted yesterday";
    if (days < 7) return "Posted " + days + "d ago";
    return "Posted " + Math.floor(days / 7) + "w ago";
  }

  function card(j) {
    var li = el("li", "job");
    var top = el("div", "job-top");
    top.appendChild(el("div", "avatar", (j.company || "?").trim().charAt(0).toUpperCase()));
    var head = el("div", "job-head");
    var h = el("h3");
    var a = el("a", null, j.title);
    a.href = j.url; a.target = "_blank"; a.rel = "noopener nofollow";
    h.appendChild(a);
    head.appendChild(h);
    head.appendChild(el("div", "company", j.company));
    top.appendChild(head);
    if (j.is_new) top.appendChild(el("span", "badge-new", "New"));
    var fav = el("button", "fav", favs.has(j.id) ? "♥" : "♡");
    fav.type = "button";
    fav.setAttribute("aria-pressed", String(favs.has(j.id)));
    fav.setAttribute("aria-label", "Save " + j.title + " at " + j.company);
    fav.addEventListener("click", function () { toggleFav(j.id); });
    top.appendChild(fav);
    li.appendChild(top);

    var facts = el("ul", "facts");
    facts.appendChild(el("li", "fact", (j.location || j.area)));
    if (j.work_mode && j.work_mode !== "Remote") facts.appendChild(el("li", "fact", j.work_mode));
    if (j.salary) facts.appendChild(el("li", "fact pay", j.salary));
    li.appendChild(facts);

    li.appendChild(el("p", "summary", (j.summary || "").replace(/\s+/g, " ")));

    var foot = el("div", "job-foot");
    foot.appendChild(el("span", "tag", j.category));
    (j.flags || []).forEach(function (f) { foot.appendChild(el("span", "tag flag", f)); });
    var when = j.closes ? "Closes " + new Date(j.closes + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }) : ago(j.posted);
    if (when) foot.appendChild(el("span", "when", when));
    var apply = el("a", "apply", "Apply ↗");
    apply.href = j.url; apply.target = "_blank"; apply.rel = "noopener nofollow";
    apply.setAttribute("aria-label", "Apply: " + j.title + " at " + j.company);
    foot.appendChild(apply);
    li.appendChild(foot);
    onDoubleTap(li, function (e) { saveFav(j.id, e, false); });
    return li;
  }


  // ---------- favorites ----------
  // Always kept on this device. When someone signs in (email link, via
  // Firebase), they're also saved to their account so they follow them to
  // any device. Accounts switch on once settings.yaml has Firebase values.
  var FAV_KEY = "launchpad-favs";
  var favs = new Set();
  try { JSON.parse(localStorage.getItem(FAV_KEY) || "[]").forEach(function (id) { favs.add(id); }); } catch (e) {}
  var cloud = null; // { db, uid } when signed in

  function storeFavs() {
    var arr = Array.from(favs);
    try { localStorage.setItem(FAV_KEY, JSON.stringify(arr)); } catch (e) {}
    if (cloud) cloud.db.collection("users").doc(cloud.uid).set({ favs: arr }, { merge: true });
  }
  // Double-tap (or double-click) a job to save it, like a photo on Instagram.
  // It only ever saves; the heart button is how to unsave.
  function onDoubleTap(node, fn) {
    var last = 0;
    node.addEventListener("pointerup", function (e) {
      if (e.target.closest("a, button")) return;
      var now = Date.now();
      if (now - last < 320) { last = 0; e.preventDefault(); fn(e); } else last = now;
    });
    // Stop the double-click from selecting a word.
    node.addEventListener("mousedown", function (e) { if (e.detail > 1) e.preventDefault(); });
  }
  function saveFav(id, e, big) {
    // The heart pops where the finger tapped. It lives on <body> because
    // saving re-draws the list underneath it.
    var burst = el("span", big ? "burst big" : "burst", "♥");
    burst.style.left = e.clientX + "px";
    burst.style.top = e.clientY + "px";
    document.body.appendChild(burst);
    setTimeout(function () { burst.remove(); }, 800);
    if (favs.has(id)) return;
    toggleFav(id);
  }
  function toggleFav(id) {
    if (favs.has(id)) favs.delete(id); else favs.add(id);
    storeFavs();
    if (!$("feed").hidden) syncFeedHearts(); else render();
  }

  function loadScript(src) {
    return new Promise(function (ok, fail) {
      var t = document.createElement("script");
      t.src = src; t.onload = ok; t.onerror = fail;
      document.head.appendChild(t);
    });
  }

  function setupAccounts() {
    if (!D.firebase || !D.firebase.apiKey) return;
    var base = "https://www.gstatic.com/firebasejs/10.12.2/";
    loadScript(base + "firebase-app-compat.js")
      .then(function () { return loadScript(base + "firebase-auth-compat.js"); })
      .then(function () { return loadScript(base + "firebase-firestore-compat.js"); })
      .then(function () {
        firebase.initializeApp(D.firebase);
        var auth = firebase.auth();
        var db = firebase.firestore();
        var btn = $("account");
        btn.hidden = false;
        var EMAIL_KEY = "launchpad-signin-email";

        // Coming back from the link in the email.
        if (auth.isSignInWithEmailLink(location.href)) {
          var email = null;
          try { email = localStorage.getItem(EMAIL_KEY); } catch (e) {}
          if (!email) email = window.prompt("Confirm your email to finish signing in");
          if (email) {
            auth.signInWithEmailLink(email, location.href).catch(function () {
              alert("That sign-in link expired or was already used. Please try again.");
            });
          }
          try { localStorage.removeItem(EMAIL_KEY); } catch (e) {}
          history.replaceState(null, "", location.pathname);
        }

        auth.onAuthStateChanged(function (user) {
          if (!user) {
            cloud = null;
            btn.textContent = "Sign in";
            return;
          }
          btn.textContent = "Sign out";
          btn.title = "Signed in as " + user.email;
          cloud = { db: db, uid: user.uid };
          // Merge what's on this device with what's in the account.
          db.collection("users").doc(user.uid).get().then(function (doc) {
            ((doc.exists && doc.data().favs) || []).forEach(function (id) { favs.add(id); });
            storeFavs();
            render();
          });
        });

        btn.addEventListener("click", function () {
          if (auth.currentUser) { auth.signOut(); return; }
          $("signin-text").textContent = "Enter your email and we'll send you a sign-in link. No password needed. Your saved jobs will show up on any device.";
          $("signin-send").hidden = false;
          $("email").hidden = false;
          $("signin").showModal();
        });
        $("signin-cancel").addEventListener("click", function () { $("signin").close(); });
        $("signin-form").addEventListener("submit", function (ev) {
          ev.preventDefault();
          var email = $("email").value.trim();
          auth.sendSignInLinkToEmail(email, { url: location.origin + location.pathname, handleCodeInApp: true })
            .then(function () {
              try { localStorage.setItem(EMAIL_KEY, email); } catch (e) {}
              $("signin-text").textContent = "Check your inbox for a link from Launchpad Listings. Open it on this device to finish signing in.";
              $("signin-send").hidden = true;
              $("email").hidden = true;
            })
            .catch(function () {
              $("signin-text").textContent = "Couldn't send the link. Check the email address and try again.";
            });
        });
      })
      .catch(function () { /* accounts unavailable; hearts still save on this device */ });
  }


  // ---------- swipe feed ----------
  // Full-screen, one job per screen, swipe up for the next (like a social
  // feed). Uses whatever filters are set on the list.
  var current = [];
  function shareJob(j) {
    var data = { title: j.title + " at " + j.company, url: j.url };
    if (navigator.share) { navigator.share(data).catch(function () {}); return; }
    try { navigator.clipboard.writeText(j.url); alert("Link copied"); } catch (e) { window.open(j.url, "_blank"); }
  }
  function railButton(icon, label, onClick) {
    var wrap = el("div");
    var b = el("button", null, icon);
    b.type = "button";
    b.setAttribute("aria-label", label);
    b.addEventListener("click", onClick);
    wrap.appendChild(b);
    wrap.appendChild(el("small", null, label));
    return wrap;
  }
  function slide(j) {
    var sl = el("section", "slide");
    sl.dataset.id = j.id;
    sl.appendChild(el("div", "slide-big", (j.company || "?").trim().charAt(0).toUpperCase()));
    var chips = el("div", "slide-chips");
    if (j.is_new) chips.appendChild(el("span", "slide-chip hot", "New today"));
    chips.appendChild(el("span", "slide-chip", j.category));
    if (j.work_mode) chips.appendChild(el("span", "slide-chip", j.work_mode));
    var when = ago(j.posted);
    if (when) chips.appendChild(el("span", "slide-chip", when));
    sl.appendChild(chips);
    sl.appendChild(el("div", "slide-company", j.company));
    sl.appendChild(el("h2", null, j.title));
    if (j.salary) sl.appendChild(el("p", "slide-pay", j.salary));
    sl.appendChild(el("p", "slide-loc", j.location || j.area));
    sl.appendChild(el("p", "slide-sum", (j.summary || "").replace(/\s+/g, " ")));
    var a = el("a", "slide-apply", "Apply ↗");
    a.href = j.url; a.target = "_blank"; a.rel = "noopener nofollow";
    sl.appendChild(a);
    var rail = el("div", "rail");
    var save = railButton(favs.has(j.id) ? "♥" : "♡", "Save", function () { toggleFav(j.id); });
    save.firstChild.classList.add("rail-save");
    save.firstChild.setAttribute("aria-pressed", String(favs.has(j.id)));
    rail.appendChild(save);
    rail.appendChild(railButton("↗", "Share", function () { shareJob(j); }));
    sl.appendChild(rail);
    onDoubleTap(sl, function (e) { saveFav(j.id, e, true); });
    return sl;
  }
  function syncFeedHearts() {
    Array.prototype.forEach.call(document.querySelectorAll(".slide"), function (sl) {
      var b = sl.querySelector(".rail-save");
      var on = favs.has(sl.dataset.id);
      b.textContent = on ? "♥" : "♡";
      b.setAttribute("aria-pressed", String(on));
    });
    var n = D.jobs.filter(function (j) { return favs.has(j.id); }).length;
    $("saved-n").textContent = n ? String(n) : "";
  }
  function buildFeed() {
    var track = $("feed-track");
    track.textContent = "";
    var frag = document.createDocumentFragment();
    current.forEach(function (j, i) {
      var sl = slide(j);
      if (i === 0 && current.length > 1) sl.appendChild(el("div", "swipe-hint", "Swipe up for the next job"));
      frag.appendChild(sl);
    });
    var end = el("section", "feed-end");
    var box = el("div");
    box.appendChild(el("p", null, current.length ? "You're all caught up." : "No jobs match these filters."));
    var back = el("button", "feed-btn", "Back to the list");
    back.type = "button";
    back.addEventListener("click", closeFeed);
    box.appendChild(back);
    end.appendChild(box);
    frag.appendChild(end);
    track.appendChild(frag);
    track.scrollTop = 0;
    updatePos();
  }
  function updatePos() {
    var track = $("feed-track");
    var i = Math.round(track.scrollTop / Math.max(1, track.clientHeight));
    $("feed-pos").textContent = current.length ? Math.min(i + 1, current.length) + " / " + current.length : "";
  }
  function openFeed() {
    $("feed").hidden = false;
    document.body.classList.add("feed-open");
    buildFeed();
    $("close-feed").focus();
  }
  function closeFeed() {
    $("feed").hidden = true;
    document.body.classList.remove("feed-open");
    render();
  }
  $("feed-track").addEventListener("scroll", updatePos, { passive: true });
  $("open-feed").addEventListener("click", openFeed);
  $("close-feed").addEventListener("click", closeFeed);
  document.addEventListener("keydown", function (e) {
    if ($("feed").hidden) return;
    var t = $("feed-track");
    if (e.key === "Escape") closeFeed();
    if (e.key === "ArrowDown" || e.key === "j") { t.scrollBy({ top: t.clientHeight, behavior: "smooth" }); e.preventDefault(); }
    if (e.key === "ArrowUp" || e.key === "k") { t.scrollBy({ top: -t.clientHeight, behavior: "smooth" }); e.preventDefault(); }
  });

  var boxes = ["remote", "salary", "saved"];

  // Show how many jobs each filter choice would actually give with the
  // other filters applied, and hide choices that would give none.
  function updateCounts(matches) {
    [["category", function (j) { return [j.category]; }],
     ["posted", function (j) { return j._posted; }]].forEach(function (row) {
      var id = row[0], keys = row[1], c = {};
      D.jobs.forEach(function (j) {
        if (matches(j, id)) keys(j).forEach(function (k) { c[k] = (c[k] || 0) + 1; });
      });
      Array.prototype.forEach.call($(id).children, function (b) {
        var v = b.dataset.value;
        if (!v) return;
        var n = c[v] || 0;
        b.querySelector(".n").textContent = String(n);
        b.hidden = n === 0 && state[id] !== v;
      });
    });
    var pool = D.jobs.filter(function (j) { return matches(j, "area"); });
    Array.prototype.forEach.call($("area").options, function (o) {
      if (!o.value) return;
      var n = pool.filter(function (j) { return inArea(j, o.value); }).length;
      o.textContent = o.dataset.name + " (" + n + ")";
      o.hidden = o.disabled = n === 0 && state.area !== o.value;
    });
  }
  function render() {
    var q = $("q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    var f = { remote: $("remote").checked, salary: $("salary").checked, saved: $("saved").checked };
    // skip: leave one filter out, so its own counts show what each choice would give.
    function matches(j, skip) {
      if (skip !== "category" && state.category && j.category !== state.category) return false;
      if (skip !== "area" && state.area && !inArea(j, state.area)) return false;
      if (skip !== "posted" && state.posted && j._posted.indexOf(state.posted) === -1) return false;
      if (f.remote && !j.remote) return false;
      if (f.salary && !j.salary) return false;
      if (f.saved && !favs.has(j.id)) return false;
      for (var i = 0; i < q.length; i++) if (j._text.indexOf(q[i]) === -1) return false;
      return true;
    }
    var list = D.jobs.filter(function (j) { return matches(j); });
    updateCounts(matches);
    current = list;
    if (!$("feed").hidden) buildFeed();
    var ol = $("jobs");
    ol.textContent = "";
    var frag = document.createDocumentFragment();
    list.forEach(function (j) { frag.appendChild(card(j)); });
    ol.appendChild(frag);

    var filtered = q.length || state.category || state.area || state.posted || f.remote || f.salary || f.saved;
    $("count").textContent = filtered
      ? list.length + " of " + D.jobs.length + " jobs"
      : "All " + D.jobs.length + " jobs · newest first";
    $("reset").hidden = !filtered;
    $("empty").hidden = list.length > 0;
    var n = D.jobs.filter(function (j) { return favs.has(j.id); }).length;
    $("saved-n").textContent = n ? String(n) : "";

    // Keep filters in the URL so a view can be bookmarked or shared.
    var p = new URLSearchParams();
    if ($("q").value.trim()) p.set("q", $("q").value.trim());
    if (state.category) p.set("category", state.category);
    if (state.area) p.set("area", state.area);
    if (state.posted) p.set("posted", state.posted);
    boxes.forEach(function (id) { if (f[id]) p.set(id, "1"); });
    var qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }

  function reset() {
    $("q").value = "";
    state.category = state.area = state.posted = "";
    boxes.forEach(function (id) { $(id).checked = false; });
    syncChips("category"); syncChips("posted"); $("area").value = "";
    render();
  }

  var params = new URLSearchParams(location.search);
  if (params.get("q")) $("q").value = params.get("q");
  state.category = params.get("category") || "";
  syncChips("category");
  state.posted = params.get("posted") || (params.get("new") === "1" ? "today" : "");
  syncChips("posted");
  state.area = params.get("area") || "";
  if (state.area && state.area.charAt(1) !== ":") state.area = "a:" + state.area; // old links
  $("area").value = state.area;
  if ($("area").value !== state.area) state.area = "";
  boxes.forEach(function (id) {
    $(id).checked = params.get(id) === "1";
    $(id).addEventListener("change", render);
  });
  $("q").addEventListener("input", render);
  // Results update as you type; Enter closes the keyboard and jumps to them.
  $("q").addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    render();
    $("q").blur();
    $("count").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("reset").addEventListener("click", reset);
  $("reset2").addEventListener("click", reset);
  render();
  setupAccounts();
  // Opened from the home-screen icon: start in the feed.
  var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (standalone || params.get("view") === "feed") openFeed();
  if ("serviceWorker" in navigator && location.protocol === "https:") {
    navigator.serviceWorker.register("sw.js").catch(function () {});
  }
})();
