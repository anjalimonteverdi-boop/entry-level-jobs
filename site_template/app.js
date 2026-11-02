(function () {
  var D = window.JOBS_DATA;
  var $ = function (id) { return document.getElementById(id); };
  if (!D) {
    $("count").textContent = "Job data failed to load.";
    return;
  }

  // Category labels are plain text for a minimal look.
  var EMOJI = {};

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
  var state = { category: "", area: "" };
  function chipRow(id, values, counts, emoji) {
    var box = $(id);
    var all = [""].concat(values.filter(function (v) { return counts[v]; }));
    all.forEach(function (v) {
      var b = el("button", "chip");
      b.type = "button";
      b.setAttribute("role", "radio");
      b.dataset.value = v;
      var label = v ? ((emoji[v] ? emoji[v] + " " : "") + v) : "All";
      b.appendChild(document.createTextNode(label));
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
  chipRow("category", D.categories, countBy("category"), EMOJI);
  // Location is a dropdown: with all US states there are too many for chips.
  var areaCounts = countBy("area");
  D.areas.filter(function (v) { return areaCounts[v]; }).forEach(function (v) {
    var o = el("option", null, v + " (" + areaCounts[v] + ")");
    o.value = v;
    $("area").appendChild(o);
  });
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
  function toggleFav(id) {
    if (favs.has(id)) favs.delete(id); else favs.add(id);
    storeFavs();
    render();
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

  var boxes = ["new", "remote", "salary", "saved"];
  function render() {
    var q = $("q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    var f = { new: $("new").checked, remote: $("remote").checked, salary: $("salary").checked,
              saved: $("saved").checked };
    var list = D.jobs.filter(function (j) {
      if (state.category && j.category !== state.category) return false;
      if (state.area && j.area !== state.area) return false;
      if (f.remote && !j.remote) return false;
      if (f.salary && !j.salary) return false;
      if (f.new && !j.is_new) return false;
      if (f.saved && !favs.has(j.id)) return false;
      for (var i = 0; i < q.length; i++) if (j._text.indexOf(q[i]) === -1) return false;
      return true;
    });
    var ol = $("jobs");
    ol.textContent = "";
    var frag = document.createDocumentFragment();
    list.forEach(function (j) { frag.appendChild(card(j)); });
    ol.appendChild(frag);

    var filtered = q.length || state.category || state.area || f.new || f.remote || f.salary || f.saved;
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
    boxes.forEach(function (id) { if (f[id]) p.set(id, "1"); });
    var qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }

  function reset() {
    $("q").value = "";
    state.category = state.area = "";
    boxes.forEach(function (id) { $(id).checked = false; });
    syncChips("category"); $("area").value = "";
    render();
  }

  var params = new URLSearchParams(location.search);
  if (params.get("q")) $("q").value = params.get("q");
  state.category = params.get("category") || "";
  syncChips("category");
  state.area = params.get("area") || "";
  $("area").value = state.area;
  if ($("area").value !== state.area) state.area = "";
  boxes.forEach(function (id) {
    $(id).checked = params.get(id) === "1";
    $(id).addEventListener("change", render);
  });
  $("q").addEventListener("input", render);
  $("reset").addEventListener("click", reset);
  $("reset2").addEventListener("click", reset);
  render();
  setupAccounts();
})();
