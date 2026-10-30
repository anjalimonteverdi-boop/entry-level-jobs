(function () {
  var D = window.JOBS_DATA;
  var $ = function (id) { return document.getElementById(id); };
  if (!D) {
    $("count").textContent = "Job data failed to load.";
    return;
  }

  // Category/area labels are plain text for a minimal look.
  var EMOJI = {};
  var AREA_EMOJI = {};

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

  // Single-select chip rows (category, area). "All" is the empty value.
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
  chipRow("area", D.areas, countBy("area"), AREA_EMOJI);

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

  var boxes = ["new", "remote", "salary"];
  function render() {
    var q = $("q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    var f = { new: $("new").checked, remote: $("remote").checked, salary: $("salary").checked };
    var list = D.jobs.filter(function (j) {
      if (state.category && j.category !== state.category) return false;
      if (state.area && j.area !== state.area) return false;
      if (f.remote && !j.remote) return false;
      if (f.salary && !j.salary) return false;
      if (f.new && !j.is_new) return false;
      for (var i = 0; i < q.length; i++) if (j._text.indexOf(q[i]) === -1) return false;
      return true;
    });
    var ol = $("jobs");
    ol.textContent = "";
    var frag = document.createDocumentFragment();
    list.forEach(function (j) { frag.appendChild(card(j)); });
    ol.appendChild(frag);

    var filtered = q.length || state.category || state.area || f.new || f.remote || f.salary;
    $("count").textContent = filtered
      ? list.length + " of " + D.jobs.length + " jobs"
      : "All " + D.jobs.length + " jobs · newest first";
    $("reset").hidden = !filtered;
    $("empty").hidden = list.length > 0;

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
    syncChips("category"); syncChips("area");
    render();
  }

  var params = new URLSearchParams(location.search);
  if (params.get("q")) $("q").value = params.get("q");
  ["category", "area"].forEach(function (id) { state[id] = params.get(id) || ""; syncChips(id); });
  boxes.forEach(function (id) {
    $(id).checked = params.get(id) === "1";
    $(id).addEventListener("change", render);
  });
  $("q").addEventListener("input", render);
  $("reset").addEventListener("click", reset);
  $("reset2").addEventListener("click", reset);
  render();
})();
