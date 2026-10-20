(function () {
  var D = window.JOBS_DATA;
  var $ = function (id) { return document.getElementById(id); };
  if (!D) {
    $("count").textContent = "Job data failed to load.";
    return;
  }

  $("site-title").textContent = D.title;
  document.title = D.title;
  $("tagline").textContent = D.tagline || "";
  $("updated").textContent = D.updated;
  $("updated").setAttribute("datetime", D.updated_iso);

  function fill(select, values, counts) {
    values.forEach(function (v) {
      if (!counts[v]) return;
      var o = document.createElement("option");
      o.value = v;
      o.textContent = v + " (" + counts[v] + ")";
      select.appendChild(o);
    });
  }
  function countBy(key) {
    var c = {};
    D.jobs.forEach(function (j) { c[j[key]] = (c[j[key]] || 0) + 1; });
    return c;
  }
  fill($("category"), D.categories, countBy("category"));
  fill($("area"), D.areas, countBy("area"));

  D.search_links.forEach(function (l) {
    var li = document.createElement("li");
    var a = document.createElement("a");
    a.href = l.url; a.textContent = l.name; a.target = "_blank"; a.rel = "noopener nofollow";
    li.appendChild(a);
    $("links").appendChild(li);
  });

  // Search text is precomputed once per job.
  D.jobs.forEach(function (j) {
    j._text = [j.title, j.company, j.summary, j.location, j.category].join(" ").toLowerCase();
  });

  function fmtDate(iso) {
    if (!iso) return "";
    var d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function card(j) {
    var li = el("li", "job");
    var h = el("h3");
    var a = el("a", null, j.title);
    a.href = j.url; a.target = "_blank"; a.rel = "noopener nofollow";
    h.appendChild(a);
    li.appendChild(h);
    li.appendChild(el("div", "company", j.company));

    var meta = el("div", "meta");
    meta.appendChild(el("span", null, "📍 " + (j.location || j.area)));
    if (j.work_mode && j.work_mode !== "Remote") meta.appendChild(el("span", null, j.work_mode));
    if (j.salary) meta.appendChild(el("span", null, "💵 " + j.salary));
    if (j.posted) meta.appendChild(el("span", null, "Posted " + fmtDate(j.posted)));
    if (j.closes) meta.appendChild(el("span", null, "Closes " + fmtDate(j.closes)));
    li.appendChild(meta);

    li.appendChild(el("p", "summary", j.summary));

    var tags = el("div", "tags");
    if (j.is_new) tags.appendChild(el("span", "tag new", "New today"));
    tags.appendChild(el("span", "tag", j.category));
    (j.flags || []).forEach(function (f) { tags.appendChild(el("span", "tag flag", f)); });
    var apply = el("a", "apply", "Apply");
    apply.href = j.url; apply.target = "_blank"; apply.rel = "noopener nofollow";
    apply.setAttribute("aria-label", "Apply: " + j.title + " at " + j.company);
    tags.appendChild(apply);
    li.appendChild(tags);
    return li;
  }

  var inputs = ["q", "category", "area", "mode", "salary", "new"];
  function render() {
    var q = $("q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    var cat = $("category").value, area = $("area").value, mode = $("mode").value;
    var sal = $("salary").checked, onlyNew = $("new").checked;
    var list = D.jobs.filter(function (j) {
      if (cat && j.category !== cat) return false;
      if (area && j.area !== area) return false;
      if (mode === "Remote" && !j.remote) return false;
      if (mode === "onsite" && j.remote) return false;
      if (sal && !j.salary) return false;
      if (onlyNew && !j.is_new) return false;
      for (var i = 0; i < q.length; i++) if (j._text.indexOf(q[i]) === -1) return false;
      return true;
    });
    var ol = $("jobs");
    ol.textContent = "";
    var frag = document.createDocumentFragment();
    list.forEach(function (j) { frag.appendChild(card(j)); });
    ol.appendChild(frag);
    var newCount = D.jobs.filter(function (j) { return j.is_new; }).length;
    $("count").textContent = list.length + " of " + D.jobs.length + " jobs · " + newCount + " new today";
    $("empty").hidden = list.length > 0;

    // Keep filters in the URL so a filtered view can be bookmarked or shared.
    var p = new URLSearchParams();
    inputs.forEach(function (id) {
      var e = $(id);
      var v = e.type === "checkbox" ? (e.checked ? "1" : "") : e.value;
      if (v) p.set(id, v);
    });
    var qs = p.toString();
    history.replaceState(null, "", qs ? "?" + qs : location.pathname);
  }

  var params = new URLSearchParams(location.search);
  inputs.forEach(function (id) {
    var e = $(id);
    if (params.has(id)) {
      if (e.type === "checkbox") e.checked = params.get(id) === "1"; else e.value = params.get(id);
    }
    e.addEventListener(e.type === "search" ? "input" : "change", render);
  });
  $("reset").addEventListener("click", function () {
    $("filters").reset();
    render();
  });
  render();
})();
