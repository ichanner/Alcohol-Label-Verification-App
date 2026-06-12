// Label Check front end. No framework, it's one page with two forms.

"use strict";

const $ = (id) => document.getElementById(id);

// tiny element builder so server data never goes through innerHTML
function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  for (const child of children) {
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

function modelLabel(id) {
  if (!id) return "";
  if (id.includes("haiku")) return "Haiku";
  if (id.includes("sonnet")) return "Sonnet";
  return id;
}

const MARKS = { match: "✓", review: "⚠", mismatch: "✕", missing: "⚠" };
const TONE = { match: "ok", review: "warn", mismatch: "bad", missing: "bad" };
const OVERALL = {
  pass:   { tone: "ok",   text: "Looks good",
            sub: "Every field on the label matches the application." },
  review: { tone: "warn", text: "Needs review",
            sub: "Nothing is plainly wrong, but at least one item needs a human look." },
  fail:   { tone: "bad",  text: "Problems found",
            sub: "At least one field doesn't match the application." },
  error:  { tone: "bad",  text: "Couldn't check this label", sub: "" },
};

/* ---------------- tabs ---------------- */

function showTab(which) {
  const single = which === "single";
  $("panel-single").hidden = !single;
  $("panel-batch").hidden = single;
  $("tab-single").classList.toggle("active", single);
  $("tab-batch").classList.toggle("active", !single);
  $("tab-single").setAttribute("aria-selected", single);
  $("tab-batch").setAttribute("aria-selected", !single);
}
$("tab-single").addEventListener("click", () => showTab("single"));
$("tab-batch").addEventListener("click", () => showTab("batch"));

/* ---------------- single label ---------------- */

let labelFile = null; // the image we'll submit, from drop/browse/sample

const dropzone = $("dropzone");
const fileInput = $("file-input");

function setImage(file) {
  labelFile = file;
  const url = URL.createObjectURL(file);
  const preview = $("preview");
  preview.src = url;
  preview.hidden = false;
  $("dropzone-hint").hidden = true;
}

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) setImage(fileInput.files[0]);
});
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files[0]) setImage(e.dataTransfer.files[0]);
});

// loads the bundled Old Tom sample so you can try the tool in one click
$("load-example").addEventListener("click", async () => {
  try {
    const resp = await fetch("/samples/old-tom-correct.png");
    if (!resp.ok) throw new Error(resp.statusText);
    setImage(new File([await resp.blob()], "old-tom-correct.png", { type: "image/png" }));
    $("brand_name").value = "OLD TOM DISTILLERY";
    $("class_type").value = "Kentucky Straight Bourbon Whiskey";
    $("alcohol_content").value = "45%";
    $("net_contents").value = "750 mL";
  } catch {
    setStatus($("single-status"), "Couldn't load the sample image.", true);
  }
});

function setStatus(node, message, isError = false) {
  node.hidden = !message;
  node.textContent = message || "";
  node.classList.toggle("error", isError);
}

$("single-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resultBox = $("single-result");
  resultBox.hidden = true;
  resultBox.replaceChildren();

  if (!labelFile) {
    setStatus($("single-status"), "Add a label image first (or load the sample).", true);
    return;
  }

  const form = new FormData($("single-form"));
  form.append("image", labelFile);

  const btn = $("check-btn");
  btn.disabled = true;
  setStatus($("single-status"), "Checking… this usually takes a few seconds.");

  try {
    const resp = await fetch("/api/verify", { method: "POST", body: form });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || "Something went wrong.");
    setStatus($("single-status"), "");
    renderResult(resultBox, body);
  } catch (err) {
    setStatus($("single-status"), err.message, true);
  } finally {
    btn.disabled = false;
  }
});

function renderResult(box, result) {
  const overall = OVERALL[result.overall] || OVERALL.error;
  const banner = h("div", { class: `banner ${overall.tone}` }, overall.text);
  if (overall.sub) banner.append(h("small", {}, overall.sub));
  box.append(banner);

  for (const note of result.notes || []) {
    box.append(h("p", { class: "note" }, "⚠ " + note));
  }

  const list = h("div", { class: "checks" });
  for (const c of result.checks) {
    const item = h("div", { class: `check ${TONE[c.status]}` },
      h("div", { class: "mark" }, MARKS[c.status] || "•"),
    );
    const body = h("div", {});
    body.append(h("h3", {}, c.label));

    const vals = h("div", { class: "vals" });
    vals.append(h("div", {}, h("b", {}, "Application: "), c.expected || "—"));
    vals.append(h("div", {}, h("b", {}, "On the label: "), c.found || "not found"));
    body.append(vals);

    for (const note of c.notes || []) {
      body.append(h("div", { class: "note" }, note));
    }
    item.append(body);
    list.append(item);
  }
  box.append(list);

  if (result.elapsed_s != null) {
    const usedModel = result.model ? ` · ${modelLabel(result.model)}` : "";
    box.append(h("p", { class: "timing" },
      `Checked in ${result.elapsed_s}s${usedModel}.`));
  }
  box.hidden = false;
}

/* ---------------- batch ---------------- */

$("batch-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resultBox = $("batch-result");
  resultBox.hidden = true;
  resultBox.replaceChildren();

  const csv = $("csv-input").files[0];
  const images = $("images-input").files;
  if (!csv || !images.length) {
    setStatus($("batch-status"), "Pick the CSV and its label images first.", true);
    return;
  }

  const form = new FormData();
  form.append("applications", csv);
  for (const img of images) form.append("images", img);

  const btn = $("batch-btn");
  btn.disabled = true;
  setStatus($("batch-status"),
    `Checking ${images.length} label${images.length === 1 ? "" : "s"}… ` +
    "this runs a handful at a time, so larger batches take a few minutes.");

  try {
    const resp = await fetch("/api/verify-batch", { method: "POST", body: form });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || "Something went wrong.");
    setStatus($("batch-status"), "");
    renderBatch(resultBox, body);
  } catch (err) {
    setStatus($("batch-status"), err.message, true);
  } finally {
    btn.disabled = false;
  }
});

const CHIP_TEXT = { pass: "Pass", review: "Review", fail: "Fail", error: "Error" };
const CHIP_TONE = { pass: "ok", review: "warn", fail: "bad", error: "bad" };

function renderBatch(box, body) {
  const counts = { pass: 0, review: 0, fail: 0, error: 0 };
  for (const r of body.results) counts[r.overall] = (counts[r.overall] || 0) + 1;

  box.append(h("div", { class: `banner ${counts.fail || counts.error ? "bad" : counts.review ? "warn" : "ok"}` },
    `${body.count} labels checked — ${counts.pass} pass, ${counts.review} need review, ` +
    `${counts.fail} fail${counts.error ? `, ${counts.error} errored` : ""}`,
    h("small", {}, `Finished in ${body.elapsed_s}s${body.model ? " · " + modelLabel(body.model) : ""}.`)));

  const table = h("table", {},
    h("thead", {}, h("tr", {},
      h("th", {}, "Image"), h("th", {}, "Brand"), h("th", {}, "Result"),
      h("th", {}, "Details"), h("th", {}, "Time"))));
  const tbody = h("tbody", {});

  for (const r of body.results) {
    const details = h("td", {});
    if (r.error) {
      details.append(r.error);
    } else {
      const problems = (r.checks || []).filter((c) => c.status !== "match");
      if (!problems.length) details.append("All fields match.");
      for (const p of problems) {
        details.append(h("p", { class: "why" },
          `${MARKS[p.status]} ${p.label}: ${(p.notes && p.notes[0]) || p.status}`));
      }
      for (const note of r.notes || []) {
        details.append(h("p", { class: "why" }, "⚠ " + note));
      }
    }
    tbody.append(h("tr", {},
      h("td", {}, r.image || "—"),
      h("td", {}, r.brand_name || "—"),
      h("td", {}, h("span", { class: `chip ${CHIP_TONE[r.overall] || "bad"}` },
        CHIP_TEXT[r.overall] || r.overall)),
      details,
      h("td", {}, r.elapsed_s != null ? `${r.elapsed_s}s` : "—")));
  }
  table.append(tbody);
  box.append(table);
  box.hidden = false;
}
